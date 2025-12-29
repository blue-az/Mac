import CoreMotion
import WatchConnectivity

/// Manages motion sensor data collection from Apple Watch
/// Collects accelerometer, gyroscope, and orientation data at 100Hz
class MotionManager: NSObject, ObservableObject {
    // MARK: - Properties

    private let motionManager = CMMotionManager()
    private let queue = OperationQueue()

    @Published var isRecording = false
    @Published var sampleCount = 0
    @Published var sessionDuration: TimeInterval = 0

    private var sessionStartTime: Date?
    private var sampleBuffer: [SensorSample] = []
    private let batchSize = 100  // Send 100 samples per batch (1 second at 100Hz)

    // MARK: - Configuration

    /// Sample rate in Hz (default 100Hz = 10ms per sample)
    let sampleRate: Double = 100.0

    var updateInterval: TimeInterval {
        return 1.0 / sampleRate
    }

    // MARK: - Session Control

    func startSession() {
        guard !isRecording else { return }

        print("🎾 Starting motion capture session...")

        // Reset state
        sampleCount = 0
        sampleBuffer.removeAll()
        sessionStartTime = Date()
        isRecording = true

        // Configure motion manager
        motionManager.deviceMotionUpdateInterval = updateInterval

        // Start collecting device motion data
        motionManager.startDeviceMotionUpdates(
            using: .xArbitraryZVertical,
            to: queue
        ) { [weak self] (motion, error) in
            guard let self = self,
                  let motion = motion,
                  self.isRecording else { return }

            // Process motion data
            self.processMotionData(motion)
        }

        print("✅ Motion capture started at \(sampleRate) Hz")
    }

    func stopSession() {
        guard isRecording else { return }

        print("🏁 Stopping motion capture session...")

        isRecording = false
        motionManager.stopDeviceMotionUpdates()

        // Send remaining buffered samples
        if !sampleBuffer.isEmpty {
            sendBatchToPhone()
        }

        print("✅ Motion capture stopped")
        print("   Total samples: \(sampleCount)")
        print("   Duration: \(String(format: "%.1f", sessionDuration)) seconds")
    }

    // MARK: - Motion Data Processing

    private func processMotionData(_ motion: CMDeviceMotion) {
        let timestamp = Date().timeIntervalSince1970

        // Create sensor sample
        let sample = SensorSample(
            timestamp: timestamp,
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
            quaternionZ: motion.attitude.quaternion.z
        )

        // Add to buffer
        sampleBuffer.append(sample)
        sampleCount += 1

        // Update duration
        if let startTime = sessionStartTime {
            sessionDuration = Date().timeIntervalSince(startTime)
        }

        // Send batch when buffer reaches batch size
        if sampleBuffer.count >= batchSize {
            sendBatchToPhone()
        }
    }

    // MARK: - Communication with iPhone

    private func sendBatchToPhone() {
        guard !sampleBuffer.isEmpty else { return }

        // Convert samples to dictionaries
        let samplesData = sampleBuffer.map { $0.toDictionary() }

        // Create batch message
        let sessionId = "watch_\(DateFormatter.sessionIdFormatter.string(from: sessionStartTime ?? Date()))"
        let batchMessage: [String: Any] = [
            "type": "sensor_batch",
            "session_id": sessionId,
            "device": "AppleWatch",
            "samples": samplesData
        ]

        // Send via WatchConnectivity
        if WCSession.default.isReachable {
            WCSession.default.sendMessage(batchMessage, replyHandler: nil) { error in
                print("❌ Error sending batch to iPhone: \(error.localizedDescription)")
            }

            print("📤 Sent batch: \(sampleBuffer.count) samples")
        } else {
            print("⚠️  iPhone not reachable, queuing batch...")
            // Queue for later transmission
            queueBatchForLater(batchMessage)
        }

        // Clear buffer
        sampleBuffer.removeAll()
    }

    private func queueBatchForLater(_ batch: [String: Any]) {
        // Use WatchConnectivity's transferUserInfo for background transfer
        WCSession.default.transferUserInfo(batch)
        print("📦 Queued batch for background transfer")
    }
}

// MARK: - SensorSample Model

struct SensorSample {
    let timestamp: Double
    let rotationRateX: Double
    let rotationRateY: Double
    let rotationRateZ: Double
    let gravityX: Double
    let gravityY: Double
    let gravityZ: Double
    let accelerationX: Double
    let accelerationY: Double
    let accelerationZ: Double
    let quaternionW: Double
    let quaternionX: Double
    let quaternionY: Double
    let quaternionZ: Double

    func toDictionary() -> [String: Any] {
        return [
            "timestamp": timestamp,
            "rotationRateX": rotationRateX,
            "rotationRateY": rotationRateY,
            "rotationRateZ": rotationRateZ,
            "gravityX": gravityX,
            "gravityY": gravityY,
            "gravityZ": gravityZ,
            "accelerationX": accelerationX,
            "accelerationY": accelerationY,
            "accelerationZ": accelerationZ,
            "quaternionW": quaternionW,
            "quaternionX": quaternionX,
            "quaternionY": quaternionY,
            "quaternionZ": quaternionZ
        ]
    }
}

// MARK: - DateFormatter Extension

extension DateFormatter {
    static let sessionIdFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyyMMdd_HHmmss"
        return formatter
    }()
}
