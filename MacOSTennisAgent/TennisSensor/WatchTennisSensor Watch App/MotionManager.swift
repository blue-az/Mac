import CoreMotion
import WatchConnectivity
import os.log

/// Manages motion sensor data collection from Apple Watch
/// Collects accelerometer, gyroscope, and orientation data at 100Hz
class MotionManager: NSObject, ObservableObject {
    // MARK: - Properties

    private let motionManager = CMMotionManager()
    private let queue = OperationQueue()
    private let heartbeatQueue = DispatchQueue(label: "com.ef.TennisSensor.heartbeat")

    // Console.app logging
    private let logger = OSLog(subsystem: "com.ef.TennisSensor.watchkitapp", category: "MotionManager")

    @Published var isRecording = false
    @Published var sampleCount = 0
    @Published var sessionDuration: TimeInterval = 0
    @Published var workoutSessionActive = false

    private var activeSessionId: String?
    private var sessionStartTime: Date?
    private var sampleBuffer: [SensorSample] = []
    private var lastSentCount = 0
    // Send incremental batches every N samples for reliability
    private let batchSize = 100
    private let heartbeatInterval: TimeInterval = 30
    private var heartbeatTimer: DispatchSourceTimer?

    // MARK: - Configuration

    /// Sample rate in Hz (default 100Hz = 10ms per sample)
    let sampleRate: Double = 100.0

    var updateInterval: TimeInterval {
        return 1.0 / sampleRate
    }

    // v2.7: Timestamp throttling to enforce exact sample rate
    private var lastSampleTime: TimeInterval = 0

    // MARK: - Session Control

    func startSession(sessionId: String) {
        guard !isRecording else { return }

        print("🎾 Starting motion capture session...")
        os_log("🎾 Starting motion capture session...", log: logger, type: .info)
        DebugEventSender.send("motion_start", sessionId: sessionId)

        // v2.6: Warn if workout session is not active
        if !workoutSessionActive {
            print("⚠️  Warning: Starting motion recording without active workout session")
            print("   Screen may turn off and suspend data collection")
            os_log("⚠️ Warning: No active workout session - screen sleep may interrupt recording", log: logger, type: .default)
            DebugEventSender.send(
                "motion_start_no_workout",
                sessionId: sessionId,
                details: ["workoutSessionActive": false]
            )
        }

        // Reset state
        sampleCount = 0
        lastSentCount = 0
        sampleBuffer.removeAll()
        sessionStartTime = Date()
        activeSessionId = sessionId
        lastSampleTime = 0  // v2.7: Reset throttling
        isRecording = true
        startHeartbeatTimer(sessionId: sessionId)

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
        os_log("✅ Motion capture started at %f Hz", log: logger, type: .info, sampleRate)
    }

    func stopSession() {
        guard isRecording else { return }

        print("🏁 Stopping motion capture session...")
        DebugEventSender.send("motion_stop", sessionId: activeSessionId)

        isRecording = false
        stopHeartbeatTimer()
        motionManager.stopDeviceMotionUpdates()

        // Send entire session data to iPhone
        if !sampleBuffer.isEmpty {
            sendCompleteSessionToPhone()
        }

        print("✅ Motion capture stopped")
        print("   Total samples: \(sampleCount)")
        print("   Duration: \(String(format: "%.1f", sessionDuration)) seconds")
    }

    // MARK: - Motion Data Processing

    private func processMotionData(_ motion: CMDeviceMotion) {
        let timestamp = Date().timeIntervalSince1970

        // v2.7: Enforce 100Hz sampling with timestamp throttling
        if lastSampleTime > 0 {
            let timeSinceLastSample = timestamp - lastSampleTime
            if timeSinceLastSample < updateInterval {
                // Skip this sample - too soon since last one
                return
            }
        }
        lastSampleTime = timestamp

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

        // Send incremental batches every batchSize samples for reliability
        if sampleCount - lastSentCount >= batchSize {
            sendIncrementalBatchToPhone()
        }
    }

    // MARK: - Communication with iPhone

    private func sendIncrementalBatchToPhone() {
        let session = WCSession.default

        guard session.activationState == .activated else {
            print("⚠️  WCSession not activated, skipping batch send")
            DebugEventSender.send(
                "wc_not_activated_incremental",
                sessionId: activeSessionId,
                details: ["activationState": session.activationState.rawValue]
            )
            return
        }

        print("📬 Pending userInfo transfers: \(session.outstandingUserInfoTransfers.count)")

        // Get new samples since last send
        let newSamples = Array(sampleBuffer[lastSentCount..<sampleBuffer.count])
        guard !newSamples.isEmpty else { return }

        let sessionId = activeSessionId ?? "watch_\(DateFormatter.sessionIdFormatter.string(from: sessionStartTime ?? Date()))"
        let samplesData = newSamples.map { $0.toDictionary() }

        let batchMessage: [String: Any] = [
            "type": "incremental_batch",
            "session_id": sessionId,
            "device": "AppleWatch",
            "samples": samplesData,
            "batch_start_index": lastSentCount,
            "total_samples_so_far": sampleCount,
            "is_final": false
        ]

        // v3.3: Use transferUserInfo instead of updateApplicationContext
        // updateApplicationContext OVERWRITES previous context - only last batch survives!
        // transferUserInfo QUEUES messages - all batches delivered in order
        session.transferUserInfo(batchMessage)
        lastSentCount = sampleCount
        print("📤 Sent incremental batch: \(samplesData.count) samples (total: \(sampleCount))")
    }

    private func sendCompleteSessionToPhone() {
        guard !sampleBuffer.isEmpty else {
            print("⚠️  No samples to send")
            os_log("⚠️ No samples to send", log: logger, type: .default)
            return
        }

        // Check WCSession state
        let session = WCSession.default
        let sessionId = activeSessionId ?? "watch_\(DateFormatter.sessionIdFormatter.string(from: sessionStartTime ?? Date()))"
        print("🔍 WCSession Debug Info:")
        print("   isSupported: \(WCSession.isSupported())")
        print("   activationState: \(session.activationState.rawValue)")
        print("   isReachable: \(session.isReachable)")
        print("   pendingUserInfo: \(session.outstandingUserInfoTransfers.count)")
        os_log("🔍 WCSession Debug: isSupported=%d, activationState=%d, isReachable=%d",
               log: logger, type: .info,
               WCSession.isSupported(), session.activationState.rawValue, session.isReachable)

        guard session.activationState == .activated else {
            print("❌ WCSession not activated! Cannot send data.")
            os_log("❌ WCSession not activated! Cannot send data. State: %d", log: logger, type: .error, session.activationState.rawValue)
            DebugEventSender.send(
                "wc_not_activated_final",
                sessionId: sessionId,
                details: ["activationState": session.activationState.rawValue]
            )
            return
        }

        // Get any remaining unsent samples
        let newSamples = Array(sampleBuffer[lastSentCount..<sampleBuffer.count])
        if !newSamples.isEmpty {
            let samplesData = newSamples.map { $0.toDictionary() }

            let finalBatchMessage: [String: Any] = [
                "type": "incremental_batch",
                "session_id": sessionId,
                "device": "AppleWatch",
                "samples": samplesData,
                "batch_start_index": lastSentCount,
                "total_samples_so_far": sampleCount,
                "is_final": true
            ]

            print("📦 Sending final batch to iPhone:")
            print("   Session ID: \(sessionId)")
            print("   Final batch samples: \(samplesData.count)")
            print("   Total samples: \(sampleCount)")
            print("   Duration: \(String(format: "%.1f", sessionDuration))s")
            os_log("📦 Sending final batch: sessionId=%{public}@, samples=%d, total=%d, duration=%.1fs",
                   log: logger, type: .info,
                   sessionId, samplesData.count, sampleCount, sessionDuration)

            // v3.3: Use transferUserInfo for reliable delivery
            session.transferUserInfo(finalBatchMessage)
            print("✅ transferUserInfo called successfully (final batch)")
            os_log("✅ transferUserInfo called successfully (final batch)", log: logger, type: .info)
        } else {
            print("✅ All samples already sent incrementally")
        }

        // Clear buffer after session ends
        sampleBuffer.removeAll()
        lastSentCount = 0
    }

    // MARK: - Heartbeat

    private func startHeartbeatTimer(sessionId: String) {
        stopHeartbeatTimer()

        let timer = DispatchSource.makeTimerSource(queue: heartbeatQueue)
        timer.schedule(deadline: .now() + heartbeatInterval, repeating: heartbeatInterval)
        timer.setEventHandler { [weak self] in
            guard let self = self, self.isRecording else { return }
            DebugEventSender.send(
                "heartbeat",
                sessionId: sessionId,
                details: [
                    "samples": self.sampleCount,
                    "duration": Int(self.sessionDuration),
                    "workoutActive": self.workoutSessionActive
                ]
            )
        }
        heartbeatTimer = timer
        timer.resume()
    }

    private func stopHeartbeatTimer() {
        heartbeatTimer?.cancel()
        heartbeatTimer = nil
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
