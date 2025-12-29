import Foundation
import WatchConnectivity

/// Manages WebSocket connection to MacOSTennisAgent backend service
/// Receives sensor data from Watch and forwards to Mac Python service
class BackendClient: NSObject, ObservableObject {
    // MARK: - Properties

    @Published var isConnected = false
    @Published var connectionStatus = "Disconnected"
    @Published var detectedSwingCount = 0

    private var webSocketTask: URLSessionWebSocketTask?
    private let urlSession: URLSession

    /// Mac backend URL - UPDATE THIS WITH YOUR MAC'S IP ADDRESS
    /// To find your Mac's IP: System Preferences → Network → IP Address
    private let backendURL = "ws://192.168.8.155:8000/ws"  // Updated with current Mac IP

    // MARK: - Initialization

    override init() {
        self.urlSession = URLSession(configuration: .default)
        super.init()
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
        guard isConnected else {
            print("⚠️  Cannot send batch: not connected")
            return
        }

        do {
            let jsonData = try JSONSerialization.data(withJSONObject: batch)
            let message = URLSessionWebSocketTask.Message.data(jsonData)

            webSocketTask?.send(message) { error in
                if let error = error {
                    print("❌ Error sending batch: \(error.localizedDescription)")
                } else {
                    if let sampleCount = (batch["samples"] as? [[String: Any]])?.count {
                        print("📤 Sent batch: \(sampleCount) samples")
                    }
                }
            }
        } catch {
            print("❌ Error serializing batch: \(error.localizedDescription)")
        }
    }

    func startSession(sessionId: String, device: String = "AppleWatch") {
        let message: [String: Any] = [
            "type": "session_start",
            "session_id": sessionId,
            "device": device
        ]

        sendMessage(message)
    }

    func endSession(sessionId: String) {
        let message: [String: Any] = [
            "type": "session_end",
            "session_id": sessionId
        ]

        sendMessage(message)
    }

    private func sendMessage(_ message: [String: Any]) {
        guard isConnected else { return }

        do {
            let jsonData = try JSONSerialization.data(withJSONObject: message)
            let wsMessage = URLSessionWebSocketTask.Message.data(jsonData)

            webSocketTask?.send(wsMessage) { error in
                if let error = error {
                    print("❌ Error sending message: \(error.localizedDescription)")
                }
            }
        } catch {
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
        if let error = error {
            print("❌ WCSession activation error: \(error.localizedDescription)")
        } else {
            print("✅ WCSession activated: \(activationState.rawValue)")
        }
    }

    func sessionDidBecomeInactive(_ session: WCSession) {
        print("⚠️  WCSession became inactive")
    }

    func sessionDidDeactivate(_ session: WCSession) {
        print("⚠️  WCSession deactivated")
        // Reactivate session
        WCSession.default.activate()
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
        // Received queued sensor batch from Watch
        if let messageType = userInfo["type"] as? String, messageType == "sensor_batch" {
            sendSensorBatch(userInfo)
        }
    }
}
