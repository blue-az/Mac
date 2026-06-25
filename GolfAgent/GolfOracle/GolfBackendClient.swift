import Foundation
import WatchConnectivity
import UIKit

class GolfBackendClient: NSObject, ObservableObject {
    static let shared = GolfBackendClient()

    @Published var isConnected = false

    private var webSocketTask: URLSessionWebSocketTask?
    private let urlSession = URLSession(configuration: .default)
    private var keepaliveTimer: Timer?
    private var backgroundTask: UIBackgroundTaskIdentifier = .invalid
    private let relayQueue = DispatchQueue(label: "GolfBackendClient.relay")
    private var pendingPayloads: [Data] = []
    private var isConnecting = false

    // iPhone-owned session lifecycle — avoids WC message ordering dependency
    private var activeSessionId: String?
    private var sessionInactivityTimer: Timer?
    private let sessionInactivityTimeout: TimeInterval = 10.0

    private let backendURL = "ws://192.168.8.124:8001/ws/golf"

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
        connect()
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
        if isConnected || isConnecting {
            return
        }
        isConnecting = true
        print("🔌 Connecting to Mac...")
        guard let url = URL(string: backendURL) else { return }
        webSocketTask?.cancel()
        webSocketTask = urlSession.webSocketTask(with: url)
        webSocketTask?.resume()
        receiveMessage()

        webSocketTask?.sendPing { [weak self] error in
            DispatchQueue.main.async {
                self?.isConnecting = false
                self?.isConnected = (error == nil)
                if error == nil {
                    self?.startKeepalive()
                    self?.flushPendingPayloads()
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
                    self?.isConnecting = false
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
        if shouldRelayToMac(message) {
            enqueueForMac(message)
        }
    }

    func session(_ session: WCSession, didReceiveUserInfo userInfo: [String : Any] = [:]) {
        if shouldRelayToMac(userInfo) {
            enqueueForMac(userInfo)
        }
    }

    private func shouldRelayToMac(_ dict: [String: Any]) -> Bool {
        guard let type = dict["type"] as? String else { return false }
        return type == "golf_sensor_batch" || type == "golf_session_start" || type == "golf_session_stop"
    }
    
    private func enqueueForMac(_ dict: [String: Any]) {
        guard let type = dict["type"] as? String else { return }

        // golf_session_start from Watch is ignored — iPhone owns session open
        if type == "golf_session_start" { return }

        relayQueue.async { [weak self] in
            guard let self else { return }

            if type == "golf_session_stop" {
                self.closeSessionOnQueue()
                return
            }

            if type == "golf_sensor_batch" {
                self.openSessionIfNeededOnQueue()
                DispatchQueue.main.async { self.resetInactivityTimer() }
            }

            var outgoing = dict
            if type == "golf_sensor_batch", let sid = self.activeSessionId {
                outgoing["session_id"] = sid
            }

            guard let data = try? JSONSerialization.data(withJSONObject: outgoing) else { return }
            self.pendingPayloads.append(data)
            DispatchQueue.main.async {
                if !self.isConnected { self.connect() }
                else { self.flushPendingPayloads() }
            }
        }
    }

    // Must be called on relayQueue
    private func openSessionIfNeededOnQueue() {
        guard activeSessionId == nil else { return }
        let sid = UUID().uuidString
        activeSessionId = sid
        let startMsg: [String: Any] = ["type": "golf_session_start", "session_id": sid]
        if let data = try? JSONSerialization.data(withJSONObject: startMsg) {
            pendingPayloads.insert(data, at: 0)  // prepend so it reaches backend before first batch
        }
        print("🆕 iPhone opened session: \(sid)")
    }

    // Must be called on relayQueue
    private func closeSessionOnQueue() {
        guard let sid = activeSessionId else { return }
        activeSessionId = nil
        DispatchQueue.main.async {
            self.sessionInactivityTimer?.invalidate()
            self.sessionInactivityTimer = nil
        }
        let stopMsg: [String: Any] = ["type": "golf_session_stop", "session_id": sid]
        if let data = try? JSONSerialization.data(withJSONObject: stopMsg) {
            pendingPayloads.append(data)
        }
        DispatchQueue.main.async {
            if self.isConnected { self.flushPendingPayloads() }
        }
        print("🛑 iPhone closed session: \(sid)")
    }

    // Must be called on main thread
    private func resetInactivityTimer() {
        sessionInactivityTimer?.invalidate()
        sessionInactivityTimer = Timer.scheduledTimer(withTimeInterval: sessionInactivityTimeout, repeats: false) { [weak self] _ in
            guard let self else { return }
            print("⏱ Session inactivity timeout — closing")
            self.relayQueue.async { self.closeSessionOnQueue() }
        }
    }

    private func flushPendingPayloads() {
        relayQueue.async { [weak self] in
            guard let self, self.isConnected else { return }
            while !self.pendingPayloads.isEmpty {
                let payload = self.pendingPayloads.removeFirst()
                self.webSocketTask?.send(.data(payload)) { [weak self] error in
                    guard let self, let error else { return }
                    print("❌ Failed to forward batch to Mac: \(error.localizedDescription)")
                    self.relayQueue.async {
                        self.pendingPayloads.insert(payload, at: 0)
                    }
                    DispatchQueue.main.async {
                        self.isConnected = false
                        self.keepaliveTimer?.invalidate()
                        self.connect()
                    }
                }
            }
        }
    }
}
