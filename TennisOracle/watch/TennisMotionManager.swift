import CoreMotion
import WatchConnectivity
import HealthKit

class TennisMotionManager: NSObject, ObservableObject, WCSessionDelegate {
    private let motionManager = CMMotionManager()
    private let healthStore = HKHealthStore()
    private let workoutManager = TennisWorkoutManager()
    private let queue = OperationQueue()

    @Published var isRecording = false
    @Published var heartRate: Double = 0
    @Published var mode: TennisMode = .strokes

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
            NotificationCenter.default.post(name: NSNotification.Name("TennisShotDetected"), object: nil, userInfo: message)
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

    private func sendBatch() {
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
