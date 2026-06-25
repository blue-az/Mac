import CoreMotion
import WatchConnectivity
import HealthKit
import WatchKit

class GolfMotionManager: NSObject, ObservableObject, WCSessionDelegate {
    private let motionManager = CMMotionManager()
    private let healthStore = HKHealthStore()
    private let workoutManager = GolfWorkoutManager()
    private let queue = OperationQueue()

    @Published var isRecording = false
    @Published var heartRate: Double = 0

    @Published var lastSwingMph: Double = 0
    @Published var lastSwingReadiness: Double = 100
    @Published var lastSwingFatigued: Bool = false
    @Published var swingCount: Int = 0

    private var sessionStartTime: Date?
    private var sessionID: String?
    private var sampleBuffer: [GolfSensorSample] = []
    private let batchSize = 50 // Smaller batches for lower latency
    private var lastAppliedSwingId: String?

    let sampleRate: Double = 100.0 // 100Hz as per spec

    override init() {
        super.init()
        if WCSession.isSupported() {
            WCSession.default.delegate = self
            WCSession.default.activate()
        }
    }

    // MARK: - WCSessionDelegate
    func session(_ session: WCSession, activationDidCompleteWith activationState: WCSessionActivationState, error: Error?) {
        print("⌚️ Watch Connectivity Activated: \(activationState.rawValue)")
    }
    
    func session(_ session: WCSession, didReceiveMessage message: [String : Any]) {
        if message["type"] as? String == "golf_swing_detected" {
            applySwing(message)
        }
    }

    func session(_ session: WCSession, didReceiveUserInfo userInfo: [String : Any] = [:]) {
        if userInfo["type"] as? String == "golf_swing_detected" {
            applySwing(userInfo)
        }
    }

    private func applySwing(_ message: [String: Any]) {
        guard let swing = message["swing"] as? [String: Any],
              let metrics = swing["metrics"] as? [String: Any],
              let flags = swing["flags"] as? [String: Any] else { return }
        let swingId = swing["swing_id"] as? String
        DispatchQueue.main.async {
            if let sid = swingId {
                guard sid != self.lastAppliedSwingId else { return }
                self.lastAppliedSwingId = sid
            }
            self.lastSwingMph = metrics["impact_speed_mph"] as? Double ?? 0
            self.lastSwingReadiness = metrics["readiness_pct"] as? Double ?? 100
            self.lastSwingFatigued = flags["micro_fatigue"] as? Bool ?? false
            self.swingCount += 1
        }
    }

    func startSession() {
        guard !isRecording else { return }

        isRecording = true
        sessionStartTime = Date()
        sessionID = UUID().uuidString
        sampleBuffer.removeAll()
        swingCount = 0
        lastSwingMph = 0
        lastSwingReadiness = 100
        lastSwingFatigued = false
        sendControlMessage(type: "golf_session_start")

        // 0. Start Workout Session to keep app alive
        workoutManager.startWorkout()

        // 1. Start Motion Updates (100Hz)
        motionManager.deviceMotionUpdateInterval = 1.0 / sampleRate
        motionManager.startDeviceMotionUpdates(using: .xArbitraryZVertical, to: queue) { [weak self] (motion, error) in
            guard let self = self, let motion = motion, self.isRecording else { return }
            self.processMotionData(motion)
        }

        // 2. Start Heart Rate Updates (1Hz)
        startHeartRateQuery()
    }

    private func processMotionData(_ motion: CMDeviceMotion) {
        let sample = GolfSensorSample(
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
            heartRate: self.heartRate > 0 ? self.heartRate : nil
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

    private func sendBatch() {
        guard let sessionID else { return }
        let samplesData = sampleBuffer.map { $0.toDictionary() }
        let message: [String: Any] = [
            "type": "golf_sensor_batch",
            "session_id": sessionID,
            "samples": samplesData,
            "timestamp": Date().timeIntervalSince1970
        ]

        if WCSession.default.isReachable {
            WCSession.default.sendMessage(message, replyHandler: nil)
        } else {
            WCSession.default.transferUserInfo(message)
        }
        sampleBuffer.removeAll()
    }

    private func sendControlMessage(type: String) {
        guard let sessionID else { return }
        let message: [String: Any] = [
            "type": type,
            "session_id": sessionID,
            "timestamp": Date().timeIntervalSince1970
        ]

        if WCSession.default.isReachable {
            WCSession.default.sendMessage(message, replyHandler: nil)
        }
        WCSession.default.transferUserInfo(message)
    }

    func stopSession() {
        isRecording = false
        motionManager.stopDeviceMotionUpdates()
        if !sampleBuffer.isEmpty {
            sendBatch()
        }
        sendControlMessage(type: "golf_session_stop")
        workoutManager.stopWorkout()
        sessionID = nil
    }
}
