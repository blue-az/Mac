//
//  TennisSensorApp.swift
//  TennisSensor
//
//  Created by wikiwoo on 4/30/25.
//  Updated for MacOSTennisAgent integration
//

import SwiftUI
import WatchConnectivity

@main
struct TennisSensorApp: App {
    init() {
        // CRITICAL: Force BackendClient initialization IMMEDIATELY at app launch
        // to prevent lazy initialization race condition where WatchConnectivity data
        // arrives before the delegate is set
        NSLog("⚡️ TENNISSENSORAPP v2.5.1 INIT STARTING ⚡️")
        print("🚀 App launching, forcing BackendClient initialization...")
        _ = BackendClient.shared
        print("✅ BackendClient.shared initialized at app launch")
        NSLog("⚡️ TENNISSENSORAPP v2.5.1 INIT COMPLETE ⚡️")
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(BackendClient.shared)
        }
    }
}
