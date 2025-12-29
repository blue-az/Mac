import Foundation
import WatchConnectivity
import os.log

/// Manages WebSocket connection to MacOSTennisAgent backend service
/// Receives sensor data from Watch and forwards to Mac Python service
class BackendClient: NSObject, ObservableObject {
    // MARK: - Singleton

    static let shared = BackendClient()

    // Console.app logging
    private let logger = OSLog(subsystem: "com.ef.TennisSensor", category: "BackendClient")

    // MARK: - Properties

    @Published var isConnected = false
    @Published var connectionStatus = "Disconnected"
    @Published var detectedSwingCount = 0

    private var webSocketTask: URLSessionWebSocketTask?
    private let urlSession: URLSession

    // Track accumulated samples from incremental batches
    private var sessionSamples: [String: [[String: Any]]] = [:]
    private var sessionStarted: Set<String> = []

    /// Mac backend URL - UPDATE THIS WITH YOUR MAC'S IP ADDRESS
    /// To find your Mac's IP: System Preferences → Network → IP Address
    private let backendURL = "ws://192.168.8.159:8000/ws"  // Updated with current Mac IP

    // MARK: - Initialization

    private override init() {
        print("🏗️ BackendClient.init() STARTING")
        os_log("🏗️ BackendClient.init() STARTING", log: OSLog(subsystem: "com.ef.TennisSensor", category: "Initialization"), type: .info)

        self.urlSession = URLSession(configuration: .default)
        super.init()

        print("🚀 BackendClient.shared initialized")
        os_log("🚀 BackendClient.shared initialized", log: logger, type: .info)

        // CRITICAL: Set delegate BEFORE calling activate()
        setupWatchConnectivity()

        print("✅ BackendClient.init() COMPLETE")
        os_log("✅ BackendClient.init() COMPLETE", log: logger, type: .info)

        // Force log to console with NSLog (always visible)
        NSLog("⚡️ BACKENDCLIENT v2.5.1 INITIALIZED - DELEGATE SET ⚡️")
    }

    // MARK: - WatchConnectivity Setup

    private func setupWatchConnectivity() {
        print("📱 Checking WCSession support...")
        os_log("📱 Checking WCSession support...", log: logger, type: .info)

        guard WCSession.isSupported() else {
            print("❌ WCSession NOT supported on this device!")
            os_log("❌ WCSession NOT supported!", log: logger, type: .error)
            return
        }

        let session = WCSession.default
        print("📱 Setting WCSession.default.delegate to BackendClient.shared...")
        os_log("📱 Setting delegate...", log: logger, type: .info)

        session.delegate = self

        print("🔄 Calling WCSession.default.activate()...")
        os_log("🔄 Activating WCSession...", log: logger, type: .info)

        session.activate()

        print("🔗 WatchConnectivity setup complete")
        print("   - Delegate is set: \(session.delegate != nil)")
        print("   - Delegate is BackendClient: \(session.delegate is BackendClient)")
        os_log("🔗 WatchConnectivity setup complete, delegate=%{public}@", log: logger, type: .info, String(describing: session.delegate != nil))
    }

    // MARK: - Connection Management

    func connect() {
        guard let url = URL(string: backendURL) else {
            print("❌ Invalid backend URL: \(backendURL)")
            connectionStatus = "Invalid URL"
            return
        }

        print("🔌 Connecting to backend: \(backendURL)")
        connectionStatus = "Connecting..."

        webSocketTask = urlSession.webSocketTask(with: url)
        webSocketTask?.resume()

        isConnected = true
        connectionStatus = "Connected"
        print("✅ Connected to backend")

        // Start listening for messages
        receiveMessage()
    }

    func disconnect() {
        guard isConnected else { return }

        print("🔌 Disconnecting from backend...")

        webSocketTask?.cancel(with: .goingAway, reason: nil)
        webSocketTask = nil
        isConnected = false
        connectionStatus = "Disconnected"

        print("✅ Disconnected from backend")
    }

    // MARK: - Message Sending

    func sendSensorBatch(_ batch: [String: Any]) {
        NSLog("⚡️ sendSensorBatch called - isConnected: \(isConnected), webSocketTask: \(webSocketTask != nil)")

        // v2.7: ALWAYS save to local database first
        if let sessionId = batch["session_id"] as? String,
           let samples = batch["samples"] as? [[String: Any]] {
            LocalDatabase.shared.insertSensorBatch(sessionId: sessionId, samples: samples)
            print("💾 Saved \(samples.count) samples to local database")
        }

        // Optional: Sync to backend if connected
        guard isConnected else {
            NSLog("⚡️ NOT CONNECTED - data saved locally only")
            print("✅ Data saved locally (backend offline)")
            return
        }

        do {
            let jsonData = try JSONSerialization.data(withJSONObject: batch)
            guard let jsonString = String(data: jsonData, encoding: .utf8) else {
                NSLog("⚡️ ERROR: Could not convert JSON data to string")
                return
            }
            let message = URLSessionWebSocketTask.Message.string(jsonString)
            NSLog("⚡️ Serialized \(jsonData.count) bytes, sending via WebSocket as TEXT...")

            webSocketTask?.send(message) { error in
                if let error = error {
                    NSLog("⚡️ WEBSOCKET SEND ERROR: \(error.localizedDescription)")
                    print("❌ Error syncing to backend: \(error.localizedDescription)")
                } else {
                    if let sampleCount = (batch["samples"] as? [[String: Any]])?.count {
                        NSLog("⚡️ Successfully sent batch: \(sampleCount) samples")
                        print("📤 Synced batch to backend: \(sampleCount) samples")
                    }
                }
            }
        } catch {
            NSLog("⚡️ JSON SERIALIZATION ERROR: \(error.localizedDescription)")
            print("❌ Error syncing batch: \(error.localizedDescription)")
        }
    }

    func startSession(sessionId: String, device: String = "AppleWatch") {
        // v2.7: Save to local database first
        let startTime = Int(Date().timeIntervalSince1970)
        LocalDatabase.shared.insertSession(sessionId: sessionId, device: device, startTime: startTime)
        print("💾 Session started locally: \(sessionId)")

        // Optional: Notify backend if connected
        let message: [String: Any] = [
            "type": "session_start",
            "session_id": sessionId,
            "device": device
        ]

        sendMessage(message)
    }

    func endSession(sessionId: String) {
        // v2.7: Update local database
        let endTime = Int(Date().timeIntervalSince1970)
        // Duration calculation will happen in the update
        LocalDatabase.shared.updateSessionEnd(sessionId: sessionId, endTime: endTime, duration: 0)
        print("💾 Session ended locally: \(sessionId)")

        // Optional: Notify backend if connected
        let message: [String: Any] = [
            "type": "session_end",
            "session_id": sessionId
        ]

        sendMessage(message)
    }

    private func sendMessage(_ message: [String: Any]) {
        NSLog("⚡️ sendMessage called - isConnected: \(isConnected), webSocketTask: \(webSocketTask != nil)")
        print("📤 sendMessage called - isConnected: \(isConnected), hasWebSocket: \(webSocketTask != nil)")

        guard isConnected else {
            NSLog("⚡️ sendMessage BLOCKED - not connected")
            print("❌ sendMessage blocked - backend not connected")
            return
        }

        do {
            let jsonData = try JSONSerialization.data(withJSONObject: message)
            guard let jsonString = String(data: jsonData, encoding: .utf8) else {
                print("❌ Could not convert JSON data to string")
                return
            }
            let wsMessage = URLSessionWebSocketTask.Message.string(jsonString)

            NSLog("⚡️ Sending WebSocket message: %@", jsonString)
            print("📤 Sending to backend: \(message["type"] ?? "unknown")")

            webSocketTask?.send(wsMessage) { error in
                if let error = error {
                    NSLog("⚡️ WebSocket send ERROR: \(error.localizedDescription)")
                    print("❌ Error sending message: \(error.localizedDescription)")
                } else {
                    NSLog("⚡️ WebSocket send SUCCESS")
                    print("✅ Message sent successfully")
                }
            }
        } catch {
            NSLog("⚡️ JSON serialization ERROR: \(error.localizedDescription)")
            print("❌ Error serializing message: \(error.localizedDescription)")
        }
    }

    // MARK: - Message Receiving

    private func receiveMessage() {
        webSocketTask?.receive { [weak self] result in
            guard let self = self else { return }

            switch result {
            case .failure(let error):
                print("❌ WebSocket receive error: \(error.localizedDescription)")
                self.isConnected = false
                self.connectionStatus = "Connection Lost"

            case .success(let message):
                switch message {
                case .data(let data):
                    self.handleReceivedData(data)
                case .string(let text):
                    if let data = text.data(using: .utf8) {
                        self.handleReceivedData(data)
                    }
                @unknown default:
                    print("⚠️  Unknown message type")
                }

                // Continue listening
                self.receiveMessage()
            }
        }
    }

    private func handleReceivedData(_ data: Data) {
        do {
            guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let messageType = json["type"] as? String else {
                print("⚠️  Invalid message format")
                return
            }

            switch messageType {
            case "swing_detected":
                handleSwingDetected(json)

            case "session_started":
                print("✅ Session started on backend")

            case "session_ended":
                handleSessionEnded(json)

            case "error":
                if let errorMessage = json["message"] as? String {
                    print("❌ Backend error: \(errorMessage)")
                }

            default:
                print("⚠️  Unknown message type: \(messageType)")
            }

        } catch {
            print("❌ Error parsing received message: \(error.localizedDescription)")
        }
    }

    private func handleSwingDetected(_ json: [String: Any]) {
        guard let swing = json["swing"] as? [String: Any],
              let swingId = swing["shot_id"] as? String,
              let rotationMagnitude = swing["rotation_magnitude"] as? Double,
              let speedMph = swing["estimated_speed_mph"] as? Double else {
            return
        }

        DispatchQueue.main.async {
            self.detectedSwingCount += 1
        }

        print("🎾 Swing detected!")
        print("   ID: \(swingId)")
        print("   Rotation: \(String(format: "%.2f", rotationMagnitude)) rad/s")
        print("   Speed: \(String(format: "%.1f", speedMph)) mph")

        // Send notification to Watch
        sendSwingNotificationToWatch(swing)

        // Trigger haptic feedback (implement in ContentView)
        NotificationCenter.default.post(
            name: NSNotification.Name("SwingDetected"),
            object: nil,
            userInfo: swing
        )
    }

    private func handleSessionEnded(_ json: [String: Any]) {
        guard let stats = json["statistics"] as? [String: Any],
              let totalPeaks = stats["total_peaks_detected"] as? Int else {
            return
        }

        print("🏁 Session ended")
        print("   Total swings: \(totalPeaks)")
    }

    private func sendSwingNotificationToWatch(_ swing: [String: Any]) {
        // Send swing detection back to Watch for haptic feedback
        if WCSession.default.isReachable {
            WCSession.default.sendMessage(
                ["type": "swing_detected", "swing": swing],
                replyHandler: nil
            )
        }
    }
}

// MARK: - WatchConnectivity Delegate

extension BackendClient: WCSessionDelegate {
    func session(_ session: WCSession, activationDidCompleteWith activationState: WCSessionActivationState, error: Error?) {
        print("🎯 ===== WCSession ACTIVATION CALLBACK =====")
        os_log("🎯 ===== WCSession ACTIVATION CALLBACK =====", log: logger, type: .info)

        if let error = error {
            print("❌ WCSession activation error: \(error.localizedDescription)")
            os_log("❌ WCSession activation error: %{public}@", log: logger, type: .error, error.localizedDescription)
        } else {
            print("✅ WCSession activated: \(activationState.rawValue)")
            print("   isPaired: \(session.isPaired)")
            print("   isWatchAppInstalled: \(session.isWatchAppInstalled)")
            print("   isReachable: \(session.isReachable)")
            print("   Delegate is set: \(session.delegate != nil)")
            print("   Delegate is BackendClient: \(session.delegate is BackendClient)")
            os_log("✅ WCSession activated: %d, isPaired: %d, isWatchAppInstalled: %d, isReachable: %d",
                   log: logger, type: .info,
                   activationState.rawValue, session.isPaired, session.isWatchAppInstalled, session.isReachable)
        }

        print("==========================================")
        os_log("==========================================", log: logger, type: .info)
    }

    func sessionDidBecomeInactive(_ session: WCSession) {
        print("⚠️  WCSession became inactive")
    }

    func sessionDidDeactivate(_ session: WCSession) {
        print("⚠️  WCSession deactivated")
        // Reactivate session
        WCSession.default.activate()
    }

    func sessionReachabilityDidChange(_ session: WCSession) {
        print("🔄 WCSession reachability changed: \(session.isReachable)")
    }

    func session(_ session: WCSession, didReceiveMessage message: [String : Any]) {
        // Received sensor batch from Watch
        if let messageType = message["type"] as? String {
            switch messageType {
            case "sensor_batch":
                // Forward to backend
                sendSensorBatch(message)

            default:
                print("⚠️  Unknown message from Watch: \(messageType)")
            }
        }
    }

    func session(_ session: WCSession, didReceiveUserInfo userInfo: [String : Any] = [:]) {
        print("🎯 didReceiveUserInfo CALLED on iPhone!")
        print("   userInfo keys: \(userInfo.keys)")
        os_log("🎯 didReceiveUserInfo CALLED on iPhone! keys: %{public}@", log: logger, type: .info, String(describing: userInfo.keys))

        // Received queued data from Watch (complete session after stopping)
        if let messageType = userInfo["type"] as? String {
            print("   Message type: \(messageType)")
            os_log("   Message type: %{public}@", log: logger, type: .info, messageType)
            switch messageType {
            case "sensor_batch":
                print("   Handling sensor_batch")
                sendSensorBatch(userInfo)
            case "complete_session":
                print("   Handling complete_session")
                handleCompleteSession(userInfo)
            default:
                print("⚠️  Unknown queued message type: \(messageType)")
                os_log("⚠️ Unknown queued message type: %{public}@", log: logger, type: .default, messageType)
            }
        } else {
            print("❌ No 'type' field in userInfo!")
            os_log("❌ No 'type' field in userInfo!", log: logger, type: .error)
        }
    }

    func session(_ session: WCSession, didReceiveApplicationContext applicationContext: [String : Any]) {
        NSLog("⚡️ didReceiveApplicationContext CALLED - \(applicationContext.count) entries")
        print("🎯 ===== didReceiveApplicationContext CALLED =====")
        print("   Context keys: \(applicationContext.keys)")
        print("   Data size: \(applicationContext.count) entries")
        os_log("🎯 ===== didReceiveApplicationContext CALLED ===== keys: %{public}@", log: logger, type: .info, String(describing: applicationContext.keys))

        if let messageType = applicationContext["type"] as? String {
            NSLog("⚡️ Message type: \(messageType)")
            print("   Message type: \(messageType)")
            os_log("   Message type: %{public}@", log: logger, type: .info, messageType)
            switch messageType {
            case "incremental_batch":
                NSLog("⚡️ Forwarding to handleIncrementalBatch...")
                print("   → Forwarding to handleIncrementalBatch...")
                os_log("   → Forwarding to handleIncrementalBatch...", log: logger, type: .info)
                handleIncrementalBatch(applicationContext)
            default:
                NSLog("⚡️ Unknown type: \(messageType)")
                print("⚠️  Unknown application context type: \(messageType)")
                os_log("⚠️ Unknown application context type: %{public}@", log: logger, type: .default, messageType)
            }
        } else {
            NSLog("⚡️ NO 'type' field in applicationContext! Keys: \(applicationContext.keys)")
            print("❌ No 'type' field in applicationContext!")
            os_log("❌ No 'type' field in applicationContext!", log: logger, type: .error)
        }

        print("==================================================")
        os_log("==================================================", log: logger, type: .info)
    }

    private func handleCompleteSession(_ sessionData: [String: Any]) {
        print("🔍 handleCompleteSession called")

        guard let sessionId = sessionData["session_id"] as? String,
              let samples = sessionData["samples"] as? [[String: Any]],
              let totalSamples = sessionData["total_samples"] as? Int else {
            print("❌ Invalid complete session data")
            print("   Available keys: \(sessionData.keys)")
            return
        }

        print("📥 Received complete session from Watch:")
        print("   Session ID: \(sessionId)")
        print("   Total samples: \(totalSamples)")
        print("   Backend connected: \(isConnected)")

        guard isConnected else {
            print("❌ Cannot forward session - backend not connected!")
            return
        }

        // Send session start
        print("   → Sending session_start")
        startSession(sessionId: sessionId, device: "AppleWatch")

        // Send all samples as one batch
        print("   → Sending sensor_batch")
        let batchMessage: [String: Any] = [
            "type": "sensor_batch",
            "session_id": sessionId,
            "device": "AppleWatch",
            "samples": samples
        ]
        sendSensorBatch(batchMessage)

        // Send session end
        print("   → Sending session_end")
        endSession(sessionId: sessionId)

        print("✅ Complete session forwarded to backend for processing")
    }

    private func handleIncrementalBatch(_ batchData: [String: Any]) {
        NSLog("⚡️ handleIncrementalBatch called - isConnected: \(isConnected)")
        print("🔍 handleIncrementalBatch called")

        guard let sessionId = batchData["session_id"] as? String,
              let samples = batchData["samples"] as? [[String: Any]],
              let isFinal = batchData["is_final"] as? Bool else {
            NSLog("⚡️ Invalid incremental batch data - keys: \(batchData.keys)")
            print("❌ Invalid incremental batch data")
            print("   Available keys: \(batchData.keys)")
            return
        }

        let totalSoFar = batchData["total_samples_so_far"] as? Int ?? 0

        NSLog("⚡️ Received batch: session=\(sessionId), samples=\(samples.count), total=\(totalSoFar), final=\(isFinal), connected=\(isConnected)")
        print("📥 Received incremental batch:")
        print("   Session ID: \(sessionId)")
        print("   Batch samples: \(samples.count)")
        print("   Total so far: \(totalSoFar)")
        print("   Is final: \(isFinal)")
        print("   Backend connected: \(isConnected)")

        // v2.7: ALWAYS process batches (save locally), regardless of backend connection

        // Start session if not already started
        if !sessionStarted.contains(sessionId) {
            print("   → Starting session (local DB + optional backend)")
            startSession(sessionId: sessionId, device: "AppleWatch")
            sessionStarted.insert(sessionId)
            sessionSamples[sessionId] = []
        }

        // Accumulate samples
        if sessionSamples[sessionId] == nil {
            sessionSamples[sessionId] = []
        }
        sessionSamples[sessionId]?.append(contentsOf: samples)

        // Save batch to local DB (and optionally sync to backend)
        print("   → Saving sensor_batch (\(samples.count) samples)")
        let batchMessage: [String: Any] = [
            "type": "sensor_batch",
            "session_id": sessionId,
            "device": "AppleWatch",
            "samples": samples
        ]
        sendSensorBatch(batchMessage)

        // If final batch, end the session
        if isFinal {
            print("   → Ending session (local DB + optional backend)")
            endSession(sessionId: sessionId)

            // Cleanup
            sessionStarted.remove(sessionId)
            sessionSamples.removeValue(forKey: sessionId)

            let connectionStatus = isConnected ? "backend" : "local only"
            print("✅ Complete session saved (\(connectionStatus), total samples: \(totalSoFar))")
        }
    }
}
