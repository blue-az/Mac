//
//  BackendClient.swift
//  TennisSensor
//
//  v3.4 - Simplified for USB-only workflow
//  Receives data from Watch via WatchConnectivity, stores in local SQLite
//  Data pulled via pymobiledevice3 when connected to Mac
//

import Foundation
import UIKit
import WatchConnectivity
import os.log

/// Manages WatchConnectivity and local database storage
/// Deprecated: WebSocket backend connection (use USB pull instead)
class BackendClient: NSObject, ObservableObject {
    // MARK: - Singleton

    static let shared = BackendClient()

    // Console.app logging
    private let logger = OSLog(subsystem: "com.ef.TennisSensor", category: "BackendClient")

    // MARK: - Properties

    @Published var isConnected = false  // Deprecated - always false in v3.4
    @Published var connectionStatus = "USB Mode"

    // Track accumulated samples from incremental batches
    private var sessionSamples: [String: [[String: Any]]] = [:]
    private var sessionStarted: Set<String> = []

    // MARK: - Initialization

    private override init() {
        print("🏗️ BackendClient.init() v3.4 - USB Mode")
        super.init()

        // Setup WatchConnectivity
        setupWatchConnectivity()

        NSLog("⚡️ BACKENDCLIENT v3.4 INITIALIZED - USB MODE ⚡️")
    }

    // MARK: - WatchConnectivity Setup

    private func setupWatchConnectivity() {
        guard WCSession.isSupported() else {
            print("❌ WCSession NOT supported on this device!")
            return
        }

        let session = WCSession.default
        session.delegate = self
        session.activate()

        print("🔗 WatchConnectivity setup complete")
    }

    // MARK: - Deprecated Methods (kept for compatibility)

    func connect() {
        // Deprecated - no backend connection in v3.4
        print("⚠️ connect() deprecated in v3.4 - using USB mode")
    }

    func disconnect() {
        // Deprecated - no backend connection in v3.4
        print("⚠️ disconnect() deprecated in v3.4 - using USB mode")
    }

    // MARK: - Local Database Operations

    func saveSensorBatch(_ batch: [String: Any]) {
        guard let sessionId = batch["session_id"] as? String,
              let samples = batch["samples"] as? [[String: Any]] else {
            print("❌ Invalid batch data")
            return
        }

        LocalDatabase.shared.insertSensorBatch(sessionId: sessionId, samples: samples)
        print("💾 Saved \(samples.count) samples to local database")
    }

    func startSession(sessionId: String, device: String = "AppleWatch") {
        let startTime = Int(Date().timeIntervalSince1970)
        LocalDatabase.shared.insertSession(sessionId: sessionId, device: device, startTime: startTime)
        setIdleTimerDisabled(true)
        print("💾 Session started: \(sessionId)")
    }

    func endSession(sessionId: String) {
        let endTime = Int(Date().timeIntervalSince1970)
        LocalDatabase.shared.updateSessionEnd(sessionId: sessionId, endTime: endTime, duration: 0)
        print("💾 Session ended: \(sessionId)")
    }

    private func setIdleTimerDisabled(_ disabled: Bool) {
        DispatchQueue.main.async {
            UIApplication.shared.isIdleTimerDisabled = disabled
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
            print("   isPaired: \(session.isPaired)")
            print("   isWatchAppInstalled: \(session.isWatchAppInstalled)")
        }
    }

    func sessionDidBecomeInactive(_ session: WCSession) {
        print("⚠️ WCSession became inactive")
    }

    func sessionDidDeactivate(_ session: WCSession) {
        print("⚠️ WCSession deactivated - reactivating")
        WCSession.default.activate()
    }

    func sessionReachabilityDidChange(_ session: WCSession) {
        print("🔄 WCSession reachability: \(session.isReachable)")
    }

    // v3.4: Primary data transfer method - queued, reliable delivery
    func session(_ session: WCSession, didReceiveUserInfo userInfo: [String : Any] = [:]) {
        NSLog("⚡️ didReceiveUserInfo - keys: \(userInfo.keys)")

        guard let messageType = userInfo["type"] as? String else {
            print("❌ No 'type' field in userInfo!")
            return
        }

        switch messageType {
        case "incremental_batch":
            handleIncrementalBatch(userInfo)
        default:
            print("⚠️ Unknown message type: \(messageType)")
        }
    }

    // Deprecated: applicationContext overwrites previous - use userInfo instead
    func session(_ session: WCSession, didReceiveApplicationContext applicationContext: [String : Any]) {
        NSLog("⚠️ didReceiveApplicationContext (deprecated) - forwarding to userInfo handler")

        if let messageType = applicationContext["type"] as? String,
           messageType == "incremental_batch" {
            handleIncrementalBatch(applicationContext)
        }
    }

    // Audio file transfer
    func session(_ session: WCSession, didReceive file: WCSessionFile) {
        print("🎤 Received audio file from Watch")

        guard let metadata = file.metadata,
              let type = metadata["type"] as? String,
              type == "audio_file",
              let sessionId = metadata["session_id"] as? String else {
            print("⚠️ Invalid audio file metadata")
            return
        }

        let duration = metadata["duration"] as? Double ?? 0
        let segmentIndex = metadata["segment_index"] as? Int ?? 1
        let documentsDir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!
        let audioDir = documentsDir.appendingPathComponent("audio")

        do {
            try FileManager.default.createDirectory(at: audioDir, withIntermediateDirectories: true)

            let fileName = segmentIndex > 1
                ? "audio_\(sessionId)_part\(segmentIndex).m4a"
                : "audio_\(sessionId).m4a"
            let destinationURL = audioDir.appendingPathComponent(fileName)

            try? FileManager.default.removeItem(at: destinationURL)
            try FileManager.default.copyItem(at: file.fileURL, to: destinationURL)

            let fileSize = (try? FileManager.default.attributesOfItem(atPath: destinationURL.path)[.size] as? Int) ?? 0
            print("🎤 Audio saved: \(fileName) (\(fileSize/1024) KB, \(String(format: "%.1f", duration))s)")

        } catch {
            print("❌ Failed to save audio: \(error.localizedDescription)")
        }
    }

    // MARK: - Batch Processing

    private func handleIncrementalBatch(_ batchData: [String: Any]) {
        guard let sessionId = batchData["session_id"] as? String,
              let samples = batchData["samples"] as? [[String: Any]],
              let isFinal = batchData["is_final"] as? Bool else {
            print("❌ Invalid batch data")
            return
        }

        let totalSoFar = batchData["total_samples_so_far"] as? Int ?? 0

        NSLog("⚡️ Batch: session=\(sessionId), samples=\(samples.count), total=\(totalSoFar), final=\(isFinal)")

        // Start session if first batch
        if !sessionStarted.contains(sessionId) {
            startSession(sessionId: sessionId, device: "AppleWatch")
            sessionStarted.insert(sessionId)
        }

        // Save batch to local database
        let batchMessage: [String: Any] = [
            "session_id": sessionId,
            "samples": samples
        ]
        saveSensorBatch(batchMessage)

        // End session if final batch
        if isFinal {
            endSession(sessionId: sessionId)
            sessionStarted.remove(sessionId)
            if sessionStarted.isEmpty {
                setIdleTimerDisabled(false)
            }
            print("✅ Session complete: \(sessionId) (\(totalSoFar) samples)")
        }
    }
}
