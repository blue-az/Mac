import Foundation
import WatchConnectivity
import UIKit

class GolfBackendClient: NSObject, ObservableObject {
    @Published var isConnected = false

    private var webSocketTask: URLSessionWebSocketTask?
    private let urlSession = URLSession(configuration: .default)
    private var keepaliveTimer: Timer?
    private var backgroundTask: UIBackgroundTaskIdentifier = .invalid

    private let backendURL = "ws://192.168.8.172:8001/ws/golf"

    override init() {
        super.init()
        if WCSession.isSupported() {
            WCSession.default.delegate = self
            WCSession.default.activate()
        }
        NotificationCenter.default.addObserver(self, selector: #selector(appDidEnterBackground),
                                               name: UIApplication.didEnterBackgroundNotification, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(appWillEnterForeground),
                                               name: UIApplication.willEnterForegroundNotification, object: nil)
    }

    @objc private func appDidEnterBackground() {
        backgroundTask = UIApplication.shared.beginBackgroundTask(withName: "GolfGateway") { [weak self] in
            self?.endBackgroundTask()
        }
    }

    @objc private func appWillEnterForeground() {
        endBackgroundTask()
        if !isConnected { connect() }
    }

    private func endBackgroundTask() {
        guard backgroundTask != .invalid else { return }
        UIApplication.shared.endBackgroundTask(backgroundTask)
        backgroundTask = .invalid
    }

    func connect() {
        print("🔌 Connecting to Mac...")
        guard let url = URL(string: backendURL) else { return }
        webSocketTask?.cancel()
        webSocketTask = urlSession.webSocketTask(with: url)
        webSocketTask?.resume()
        receiveMessage()

        webSocketTask?.sendPing { [weak self] error in
            DispatchQueue.main.async {
                self?.isConnected = (error == nil)
                if error == nil {
                    self?.startKeepalive()
                } else {
                    print("❌ Ping failed: \(error!.localizedDescription)")
                }
            }
        }
    }

    private func startKeepalive() {
        keepaliveTimer?.invalidate()
        keepaliveTimer = Timer.scheduledTimer(withTimeInterval: 20, repeats: true) { [weak self] _ in
            self?.webSocketTask?.sendPing { [weak self] error in
                DispatchQueue.main.async {
                    if let error = error {
                        print("❌ Keepalive ping failed: \(error.localizedDescription)")
                        self?.isConnected = false
                        self?.keepaliveTimer?.invalidate()
                    }
                }
            }
        }
    }

    func downloadSession(completion: @escaping (Data?) -> Void) {
        guard let url = URL(string: backendURL.replacingOccurrences(of: "ws://", with: "http://")
                                              .replacingOccurrences(of: "/ws/golf", with: "/sessions/latest")) else {
            completion(nil); return
        }
        URLSession.shared.dataTask(with: url) { data, _, _ in completion(data) }.resume()
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
                let nsError = error as NSError
                guard nsError.code != NSURLErrorCancelled else { return }
                print("❌ connection lost: \(error.localizedDescription)")
                DispatchQueue.main.async {
                    self?.isConnected = false
                    self?.keepaliveTimer?.invalidate()
                    DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
                        self?.connect()
                    }
                }
            }
        }
    }

    private func handlePayload(_ data: Data) {
        if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let type = json["type"] as? String, type == "golf_swing_detected" {
            // Forward back to Watch for Haptics/UI
            if WCSession.default.isReachable {
                WCSession.default.sendMessage(json, replyHandler: nil)
            }
        }
    }
}

extension GolfBackendClient: WCSessionDelegate {
    func session(_ session: WCSession, activationDidCompleteWith activationState: WCSessionActivationState, error: Error?) {}
    func sessionDidBecomeInactive(_ session: WCSession) {}
    func sessionDidDeactivate(_ session: WCSession) {}

    func session(_ session: WCSession, didReceiveMessage message: [String : Any]) {
        if message["type"] as? String == "golf_sensor_batch" {
            sendToMac(message)
        }
    }
    
    private func sendToMac(_ dict: [String: Any]) {
        guard isConnected, let data = try? JSONSerialization.data(withJSONObject: dict) else { return }
        webSocketTask?.send(.data(data)) { _ in }
    }
}
