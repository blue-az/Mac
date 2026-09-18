import Foundation
import WatchConnectivity

class TennisBackendClient: NSObject, ObservableObject {
    @Published var isConnected = false
    @Published var wcBatchesReceived: Int = 0
    @Published var host: String
    @Published var lastError: String = ""

    private var webSocketTask: URLSessionWebSocketTask?
    private let urlSession = URLSession(configuration: .default)
    private static let hostDefaultsKey = "tennisOracle.backendHost"
    private static let defaultHost = "Mac-mini.local"
    private static let port = 8002

    var backendURL: String {
        "ws://\(Self.normalizedHost(host)):\(Self.port)/ws/tennis"
    }

    override init() {
        let saved = UserDefaults.standard.string(forKey: Self.hostDefaultsKey)?.trimmingCharacters(in: .whitespacesAndNewlines)
        host = (saved?.isEmpty == false) ? saved! : Self.defaultHost
        super.init()
        if WCSession.isSupported() {
            WCSession.default.delegate = self
            WCSession.default.activate()
        }
    }

    func persistHost() {
        let value = Self.normalizedHost(host)
        host = value
        UserDefaults.standard.set(value, forKey: Self.hostDefaultsKey)
    }

    func connect() {
        persistHost()
        print("🔌 Gateway WS connect start: \(backendURL)")
        lastError = ""
        print("🔌 Connecting to Tennis Oracle at \(backendURL)")
        guard let url = URL(string: backendURL) else {
            lastError = "Invalid host"
            return
        }
        webSocketTask?.cancel(with: .goingAway, reason: nil)
        webSocketTask = urlSession.webSocketTask(with: url)
        webSocketTask?.resume()
        ping()
        receiveMessage()
    }

    private static func normalizedHost(_ raw: String) -> String {
        var value = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        if value.hasPrefix("ws://") { value.removeFirst(5) }
        if value.hasPrefix("wss://") { value.removeFirst(6) }
        if let slash = value.firstIndex(of: "/") {
            value = String(value[..<slash])
        }
        if let colon = value.lastIndex(of: ":"), value[value.index(after: colon)...].allSatisfy(\Character.isNumber) {
            value = String(value[..<colon])
        }
        return value.isEmpty ? defaultHost : value
    }

    private func ping() {
        webSocketTask?.sendPing { [weak self] error in
            DispatchQueue.main.async {
                self?.isConnected = (error == nil)
                if let error {
                    print("❌ Gateway WS ping error: \(error.localizedDescription)")
                    self?.lastError = error.localizedDescription
                }
            }
            if error == nil {
                DispatchQueue.global().asyncAfter(deadline: .now() + 5) { [weak self] in
                    self?.ping()
                }
            }
        }
    }

    private func receiveMessage() {
        webSocketTask?.receive { [weak self] result in
            switch result {
            case .success(let message):
                DispatchQueue.main.async { self?.isConnected = true }
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
                print("❌ Gateway WS receive/close: \(error.localizedDescription)")
                DispatchQueue.main.async {
                    self?.isConnected = false
                    self?.lastError = error.localizedDescription
                }
            }
        }
    }

    private func handlePayload(_ data: Data) {
        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let type = json["type"] as? String else { return }
        guard type == "tennis_shot_detected" || type == "batch_ack" else { return }
        if WCSession.default.isReachable {
            WCSession.default.sendMessage(json, replyHandler: nil)
        } else {
            WCSession.default.transferUserInfo(json)
        }
    }
}

extension TennisBackendClient: WCSessionDelegate {
    func session(_ session: WCSession, activationDidCompleteWith activationState: WCSessionActivationState, error: Error?) {
        print("🎾 Gateway WC activated: state=\(activationState.rawValue) reachable=\(session.isReachable) error=\(error?.localizedDescription ?? "none")")
    }
    func sessionDidBecomeInactive(_ session: WCSession) {
        print("⚠️ Gateway WC became inactive")
    }
    func sessionDidDeactivate(_ session: WCSession) {
        print("⚠️ Gateway WC deactivated")
        session.activate()
    }
    func sessionReachabilityDidChange(_ session: WCSession) {
        print("🎾 Gateway WC reachability: \(session.isReachable)")
    }

    func session(_ session: WCSession, didReceiveMessage message: [String : Any]) {
        if message["type"] as? String == "tennis_sensor_batch" {
            print("📥 Gateway WC batch: session=\(message["session_uuid"] ?? "") seq=\(message["batch_seq"] ?? "")")
            DispatchQueue.main.async { self.wcBatchesReceived += 1 }
            sendToMac(message)
        }
    }

    func session(_ session: WCSession, didReceiveUserInfo userInfo: [String : Any] = [:]) {
        if userInfo["type"] as? String == "tennis_sensor_batch" {
            print("📥 Gateway queued batch: session=\(userInfo["session_uuid"] ?? "") seq=\(userInfo["batch_seq"] ?? "")")
            DispatchQueue.main.async { self.wcBatchesReceived += 1 }
            sendToMac(userInfo)
        }
    }
    
    private func sendToMac(_ dict: [String: Any]) {
        guard let data = try? JSONSerialization.data(withJSONObject: dict),
              let task = webSocketTask else { return }
        task.send(.data(data)) { error in
            if let error = error {
                print("❌ Gateway WS send failed: \(error.localizedDescription)")
                DispatchQueue.main.async { self.isConnected = false }
            }
        }
    }
}
