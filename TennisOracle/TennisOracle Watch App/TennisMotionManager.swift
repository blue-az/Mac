import CoreMotion
import WatchConnectivity
import HealthKit
import WatchKit

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
    private var sampleBuffer: [TennisSensorSample] = []
    private let batchSize = 50 

    let sampleRate: Double = 100.0 

    override init() {
        super.init()
        if WCSession.isSupported() {
            WCSession.default.delegate = self
            WCSession.default.activate()
        }
    }

    // MARK: - WCSessionDelegate
    func session(_ session: WCSession, activationDidCompleteWith activationState: WCSessionActivationState, error: Error?) {
        print("🎾 Watch Connectivity Activated: \(activationState.rawValue)")
    }
    
    func session(_ session: WCSession, didReceiveMessage message: [String : Any]) {
        if message["type"] as? String == "tennis_shot_detected" {
            applyShot(message)
        }
    }

    func session(_ session: WCSession, didReceiveUserInfo userInfo: [String : Any] = [:]) {
        if userInfo["type"] as? String == "tennis_shot_detected" {
            applyShot(userInfo)
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
        sampleBuffer.removeAll()

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
        let message: [String: Any] = [
            "type": "tennis_sensor_batch",
            "samples": samplesData,
            "timestamp": Date().timeIntervalSince1970,
            "mode": self.mode.rawValue
        ]

        if WCSession.default.isReachable {
            WCSession.default.sendMessage(message, replyHandler: nil)
        } else {
            WCSession.default.transferUserInfo(message)
        }
        sampleBuffer.removeAll()
    }

    func stopSession() {
        isRecording = false
        motionManager.stopDeviceMotionUpdates()
        workoutManager.stopWorkout()
    }
}
