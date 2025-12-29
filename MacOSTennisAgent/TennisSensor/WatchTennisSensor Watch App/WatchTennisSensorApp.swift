//
//  WatchTennisSensorApp.swift
//  WatchTennisSensor Watch App
//
//  Created by wikiwoo on 4/30/25.
//  Updated for MacOSTennisAgent integration
//

import SwiftUI
import WatchConnectivity
import WatchKit
import os.log

@main
struct WatchTennisSensor_Watch_AppApp: App {
    init() {
        // Set up WatchConnectivity session
        if WCSession.isSupported() {
            let session = WCSession.default
            session.delegate = WatchConnectivityDelegate.shared
            session.activate()
            print("✅ Watch WatchConnectivity session activated")
            os_log("✅ Watch WatchConnectivity session activate() called", log: OSLog(subsystem: "com.ef.TennisSensor.watchkitapp", category: "WCSession"), type: .info)
        }
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}

// Simple WCSessionDelegate for Watch
class WatchConnectivityDelegate: NSObject, WCSessionDelegate {
    static let shared = WatchConnectivityDelegate()

    private let logger = OSLog(subsystem: "com.ef.TennisSensor.watchkitapp", category: "WCSessionDelegate")

    func session(_ session: WCSession, activationDidCompleteWith activationState: WCSessionActivationState, error: Error?) {
        if let error = error {
            print("❌ WCSession activation error: \(error.localizedDescription)")
            os_log("❌ WCSession activation error: %{public}@", log: logger, type: .error, error.localizedDescription)
        } else {
            print("✅ WCSession activated: \(activationState.rawValue)")
            os_log("✅ WCSession activated on Watch: state=%d", log: logger, type: .info, activationState.rawValue)
        }
    }

    func session(_ session: WCSession, didReceiveMessage message: [String : Any]) {
        // Handle messages from iPhone (e.g., swing detection notifications)
        if let messageType = message["type"] as? String, messageType == "swing_detected" {
            print("🎾 Swing detected notification received from iPhone")
            // Trigger haptic feedback
            DispatchQueue.main.async {
                WKInterfaceDevice.current().play(.success)
            }
        }
    }
}
