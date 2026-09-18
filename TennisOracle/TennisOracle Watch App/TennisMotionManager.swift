import CoreMotion
import WatchConnectivity
import HealthKit
import WatchKit

/// Crash-safe observability journal. This records transport/lifecycle state only;
/// detector inputs and thresholds are unchanged.
private final class TennisDiagnostics {
    private let defaults = UserDefaults.standard
    private let queue = DispatchQueue(label: "tennis.oracle.diagnostics")
    private let fileURL: URL
    private let encoder = JSONEncoder()

    init() {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        try? FileManager.default.createDirectory(at: base, withIntermediateDirectories: true)
        fileURL = base.appendingPathComponent("tennis-oracle-events.jsonl")
        if defaults.bool(forKey: "tennis.oracle.recording") {
            append("unclean_exit_detected", fields: ["previous_session_uuid": defaults.string(forKey: "tennis.oracle.session_uuid") ?? ""])
            defaults.set(false, forKey: "tennis.oracle.recording")
        }
        append("launch", fields: [:])
    }

    func beginSession(_ id: String, mode: String) {
        defaults.set(true, forKey: "tennis.oracle.recording")
        defaults.set(id, forKey: "tennis.oracle.session_uuid")
        append("recording_started", fields: ["session_uuid": id, "mode": mode])
    }

    func endSession(_ id: String, reason: String) {
        defaults.set(false, forKey: "tennis.oracle.recording")
        append("recording_ended", fields: ["session_uuid": id, "reason": reason])
    }

    func record(_ event: String, fields: [String: Any]) {
        append(event, fields: fields)
    }

    private func append(_ event: String, fields: [String: Any]) {
        queue.async { [fileURL, encoder] in
            var object: [String: Any] = [
                "event": event,
                "wall_time": Date().timeIntervalSince1970,
                "monotonic_ns": DispatchTime.now().uptimeNanoseconds
            ]
            fields.forEach { object[$0.key] = $0.value }
            guard JSONSerialization.isValidJSONObject(object),
                  let data = try? JSONSerialization.data(withJSONObject: object),
                  let line = String(data: data, encoding: .utf8) else { return }
            if let handle = try? FileHandle(forWritingTo: fileURL) {
                handle.seekToEndOfFile()
                handle.write((line + "\n").data(using: .utf8)!)
                try? handle.close()
            } else {
                try? (line + "\n").data(using: .utf8)?.write(to: fileURL, options: .atomic)
            }
        }
    }
}

class TennisMotionManager: NSObject, ObservableObject, WCSessionDelegate {
    private let motionManager = CMMotionManager()
    private let healthStore = HKHealthStore()
    private let workoutManager = TennisWorkoutManager()
    private let queue = OperationQueue()

    @Published var isRecording = false
    @Published var heartRate: Double = 0
    @Published var mode: TennisMode = .strokes

    // Shot detection result — updated on main thread, observed via onChange
    @Published var lastShotMph: Double = 0
    @Published var lastShotReadiness: Double = 100
    @Published var lastShotFatigued: Bool = false
    @Published var lastShotCleanContact: Bool = true
    @Published var shotCount: Int = 0   // increments on every shot → triggers onChange

    private var sessionStartTime: Date?
    private var sessionUUID: String?
    private let diagnostics = TennisDiagnostics()
    private let outboxDirectory: URL
    private var sampleBuffer: [TennisSensorSample] = []
    private let batchSize = 50
    // Identifies each batch so the Mac can drop duplicates — WatchConnectivity has been
    // observed delivering the same sendMessage batch twice (see raw_sensor_buffer rows
    // with identical timestamps, 2026-09-02). Unique per session, not persisted.
    private var nextBatchSeq: Int = 0

    let sampleRate: Double = 100.0 

    override init() {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        outboxDirectory = base.appendingPathComponent("tennis-oracle-outbox", isDirectory: true)
        try? FileManager.default.createDirectory(at: outboxDirectory, withIntermediateDirectories: true)
        super.init()
        if WCSession.isSupported() {
            WCSession.default.delegate = self
            WCSession.default.activate()
        }
    }

    // MARK: - WCSessionDelegate
    func session(_ session: WCSession, activationDidCompleteWith activationState: WCSessionActivationState, error: Error?) {
        print("🎾 Watch Connectivity Activated: \(activationState.rawValue)")
        diagnostics.record("wc_activation", fields: [
            "state": activationState.rawValue,
            "reachable": session.isReachable,
            "error": error?.localizedDescription ?? ""
        ])
    }

    func sessionReachabilityDidChange(_ session: WCSession) {
        diagnostics.record("wc_reachability", fields: ["reachable": session.isReachable])
    }
    
    func session(_ session: WCSession, didReceiveMessage message: [String : Any]) {
        handleIncoming(message)
    }

    func session(_ session: WCSession, didReceiveUserInfo userInfo: [String : Any] = [:]) {
        handleIncoming(userInfo)
    }

    private func handleIncoming(_ message: [String: Any]) {
        if message["type"] as? String == "tennis_shot_detected" { applyShot(message) }
        if message["type"] as? String == "batch_ack",
           let seq = message["batch_seq"] as? Int,
           let sid = message["session_uuid"] as? String {
            removeOutbox(sessionID: sid, batchSeq: seq)
            diagnostics.record("batch_ack_received", fields: ["session_uuid": sid, "batch_seq": seq, "status": message["status"] ?? ""])
        }
    }

    private func applyShot(_ message: [String: Any]) {
        guard let shot = message["shot"] as? [String: Any],
              let metrics = shot["metrics"] as? [String: Any],
              let flags = shot["flags"] as? [String: Any] else { return }
        DispatchQueue.main.async {
            self.lastShotMph = metrics["speed_mph"] as? Double ?? 0
            self.lastShotReadiness = metrics["readiness_pct"] as? Double ?? 100
            self.lastShotFatigued = flags["micro_fatigue"] as? Bool ?? false
            self.lastShotCleanContact = flags["clean_contact"] as? Bool ?? true
            self.shotCount += 1
        }
    }

    func startSession() {
        guard !isRecording else { return }

        isRecording = true
        sessionStartTime = Date()
        sessionUUID = UUID().uuidString
        sampleBuffer.removeAll()
        nextBatchSeq = 0
        diagnostics.beginSession(sessionUUID!, mode: mode.rawValue)

        workoutManager.startWorkout()

        motionManager.deviceMotionUpdateInterval = 1.0 / sampleRate
        motionManager.startDeviceMotionUpdates(using: .xArbitraryZVertical, to: queue) { [weak self] (motion, error) in
            guard let self = self, let motion = motion, self.isRecording else { return }
            self.processMotionData(motion)
        }

        startHeartRateQuery()
    }

    private func processMotionData(_ motion: CMDeviceMotion) {
        let sample = TennisSensorSample(
            timestamp: Date().timeIntervalSince1970,
            rotationRateX: motion.rotationRate.x,
            rotationRateY: motion.rotationRate.y,
            rotationRateZ: motion.rotationRate.z,
            gravityX: motion.gravity.x,
            gravityY: motion.gravity.y,
            gravityZ: motion.gravity.z,
            accelerationX: motion.userAcceleration.x,
            accelerationY: motion.userAcceleration.y,
            accelerationZ: motion.userAcceleration.z,
            quaternionW: motion.attitude.quaternion.w,
            quaternionX: motion.attitude.quaternion.x,
            quaternionY: motion.attitude.quaternion.y,
            quaternionZ: motion.attitude.quaternion.z,
            heartRate: self.heartRate > 0 ? self.heartRate : nil,
            mode: self.mode
        )

        sampleBuffer.append(sample)

        if sampleBuffer.count >= batchSize {
            sendBatch()
        }
    }

    private func startHeartRateQuery() {
        guard HKHealthStore.isHealthDataAvailable() else { return }

        let heartRateType = HKQuantityType.quantityType(forIdentifier: .heartRate)!
        let query = HKAnchoredObjectQuery(type: heartRateType, predicate: nil, anchor: nil, limit: HKObjectQueryNoLimit) { [weak self] (query, samples, deletedObjects, newAnchor, error) in
            self?.updateHeartRate(samples)
        }

        query.updateHandler = { [weak self] (query, samples, deletedObjects, newAnchor, error) in
            self?.updateHeartRate(samples)
        }

        healthStore.execute(query)
    }

    private func updateHeartRate(_ samples: [HKSample]?) {
        guard let heartRateSamples = samples as? [HKQuantitySample], let lastSample = heartRateSamples.last else { return }
        let unit = HKUnit.count().unitDivided(by: HKUnit.minute())
        DispatchQueue.main.async {
            self.heartRate = lastSample.quantity.doubleValue(for: unit)
        }
    }

    // Cooldown to avoid rapid-fire haptics from a single swing
    private var localHapticCooldownUntil: Date = .distantPast

    private func sendBatch() {
        // Local peak detection — immediate haptic without Mac round-trip
        let mags = sampleBuffer.map {
            sqrt($0.rotationRateX * $0.rotationRateX +
                 $0.rotationRateY * $0.rotationRateY +
                 $0.rotationRateZ * $0.rotationRateZ)
        }
        if let peak = mags.max(), peak > 12.0, Date() > localHapticCooldownUntil {
            localHapticCooldownUntil = Date().addingTimeInterval(1.5)
            let clean = (mags.max() ?? 0) > 15.0  // stronger swing = more likely clean
            DispatchQueue.main.async {
                self.lastShotMph = peak * 2.5 * 1.4
                self.lastShotCleanContact = clean
                self.shotCount += 1
                WKInterfaceDevice.current().play(clean ? .success : .failure)
            }
        }

        let samplesData = sampleBuffer.map { $0.toDictionary() }
        let batchSeq = nextBatchSeq
        nextBatchSeq += 1
        let sessionID = sessionUUID ?? "unknown"
        diagnostics.record("batch_send_started", fields: [
            "session_uuid": sessionID, "batch_seq": batchSeq,
            "sample_count": samplesData.count,
            "first_sample": sampleBuffer.first?.timestamp as Any,
            "last_sample": sampleBuffer.last?.timestamp as Any,
            "reachable": WCSession.default.isReachable
        ])
        let message: [String: Any] = [
            "type": "tennis_sensor_batch",
            "session_uuid": sessionID,
            "samples": samplesData,
            "timestamp": Date().timeIntervalSince1970,
            "mode": self.mode.rawValue,
            "batch_seq": batchSeq
        ]

        persistOutbox(message, sessionID: sessionID, batchSeq: batchSeq)
        if WCSession.default.isReachable {
            WCSession.default.sendMessage(message, replyHandler: { [weak self] _ in
                self?.diagnostics.record("batch_send_completed", fields: ["session_uuid": sessionID, "batch_seq": batchSeq, "path": "sendMessage"])
            }, errorHandler: { [weak self] error in
                self?.diagnostics.record("batch_send_error", fields: ["session_uuid": sessionID, "batch_seq": batchSeq, "path": "sendMessage", "error": error.localizedDescription])
            })
        } else {
            WCSession.default.transferUserInfo(message)
            diagnostics.record("batch_send_completed", fields: ["session_uuid": sessionID, "batch_seq": batchSeq, "path": "transferUserInfo"])
        }
        sampleBuffer.removeAll()
    }

    private func persistOutbox(_ message: [String: Any], sessionID: String, batchSeq: Int) {
        guard let data = try? JSONSerialization.data(withJSONObject: message) else { return }
        let url = outboxDirectory.appendingPathComponent("\(sessionID)_\(batchSeq).json")
        do {
            try data.write(to: url, options: .atomic)
            diagnostics.record("outbox_persisted", fields: ["session_uuid": sessionID, "batch_seq": batchSeq])
        } catch {
            diagnostics.record("outbox_persist_error", fields: ["session_uuid": sessionID, "batch_seq": batchSeq, "error": error.localizedDescription])
        }
    }

    private func removeOutbox(sessionID: String, batchSeq: Int) {
        let url = outboxDirectory.appendingPathComponent("\(sessionID)_\(batchSeq).json")
        try? FileManager.default.removeItem(at: url)
    }

    func stopSession() {
        let id = sessionUUID ?? "unknown"
        diagnostics.record("recording_stopped", fields: ["session_uuid": id, "buffered_samples": sampleBuffer.count])
        isRecording = false
        motionManager.stopDeviceMotionUpdates()
        workoutManager.stopWorkout()
        diagnostics.endSession(id, reason: "user_stop")
        sessionUUID = nil
    }

    func recordScene(_ phase: String) {
        diagnostics.record("scene_\(phase)", fields: [
            "session_uuid": sessionUUID ?? "",
            "recording": isRecording,
            "buffered_samples": sampleBuffer.count
        ])
    }
}
