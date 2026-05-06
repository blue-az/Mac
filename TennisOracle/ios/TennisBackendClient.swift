import Foundation
import WatchConnectivity

class TennisBackendClient: NSObject, ObservableObject {
    @Published var isConnected = false
    
    private var webSocketTask: URLSessionWebSocketTask?
    private let urlSession = URLSession(configuration: .default)
    
    // Using Port 8002 for Tennis Oracle
    private let backendURL = "ws://192.168.8.158:8002/ws/tennis"

    override init() {
        super.init()
        if WCSession.isSupported() {
            WCSession.default.delegate = self
            WCSession.default.activate()
        }
    }

    func connect() {
        print("🔌 Connecting to Tennis Oracle...")
        guard let url = URL(string: backendURL) else { return }
        webSocketTask = urlSession.webSocketTask(with: url)
        webSocketTask?.resume()
        
        DispatchQueue.main.async {
            self.isConnected = true
        }
        receiveMessage()
    }

    private func receiveMessage() {
        webSocketTask?.receive { [weak self] result in
            switch result {
            case .success(let message):
                switch message {
                case .string(let text):
                    if let data = text.data(using: .utf8) { self?.handlePayload(data) }
                case .data(let data):
                    self?.handlePayload(data)
                @unknown default:
                    break
                }
                self?.receiveMessage()
            case .failure(let error):
                print("❌ connection lost: \(error.localizedDescription)")
                DispatchQueue.main.async {
                    self?.isConnected = false
                }
            }
        }
    }

    private func handlePayload(_ data: Data) {
        if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let type = json["type"] as? String, type == "tennis_shot_detected" {
            // Forward back to Watch for Haptics/UI
            if WCSession.default.isReachable {
                WCSession.default.sendMessage(json, replyHandler: nil)
            }
        }
    }
}

extension TennisBackendClient: WCSessionDelegate {
    func session(_ session: WCSession, activationDidCompleteWith activationState: WCSessionActivationState, error: Error?) {}
    func sessionDidBecomeInactive(_ session: WCSession) {}
    func sessionDidDeactivate(_ session: WCSession) {}

    func session(_ session: WCSession, didReceiveMessage message: [String : Any]) {
        if message["type"] as? String == "tennis_sensor_batch" {
            sendToMac(message)
        }
    }
    
    private func sendToMac(_ dict: [String: Any]) {
        guard isConnected, let data = try? JSONSerialization.data(withJSONObject: dict) else { return }
        webSocketTask?.send(.data(data)) { _ in }
    }
}
