import Foundation
import WatchConnectivity
import os.log

enum DebugEventSender {
    private static let logger = OSLog(subsystem: "com.ef.TennisSensor.watchkitapp", category: "DebugEvent")

    static func send(_ event: String, sessionId: String? = nil, details: [String: Any] = [:]) {
        var payload: [String: Any] = [
            "type": "debug_event",
            "event": event,
            "timestamp": Date().timeIntervalSince1970,
            "platform": "watch"
        ]

        if let sessionId = sessionId {
            payload["session_id"] = sessionId
        }

        if !details.isEmpty {
            payload["details"] = details
        }

        os_log("DEBUG event=%{public}@ details=%{public}@",
               log: logger,
               type: .info,
               event,
               String(describing: details))

        guard WCSession.isSupported() else { return }
        let session = WCSession.default

        guard session.activationState == .activated else {
            os_log("DEBUG WCSession not activated for debug event: state=%d",
                   log: logger,
                   type: .default,
                   session.activationState.rawValue)
            return
        }

        session.transferUserInfo(payload)
    }
}
