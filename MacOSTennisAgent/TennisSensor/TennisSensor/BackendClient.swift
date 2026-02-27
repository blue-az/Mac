//
//  BackendClient.swift
//  TennisSensor
//
//  v5.0.0 - Dual mode: WebSocket streaming + USB fallback
//  - Live streaming when Mac server reachable (auto-discover)
//  - Falls back to USB-only if server unreachable
//  - Stores all data locally regardless of connection status
//

import Foundation
import UIKit
import WatchConnectivity
import os.log

/// Manages WatchConnectivity, WebSocket streaming, and local database storage
class BackendClient: NSObject, ObservableObject {
    // MARK: - Singleton

    static let shared = BackendClient()

    // Console.app logging
    private let logger = OSLog(subsystem: "com.ef.TennisSensor", category: "BackendClient")
    private let debugDateFormatter = ISO8601DateFormatter()
    private lazy var debugLogURL: URL = {
        let documentsDir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!
        return documentsDir.appendingPathComponent("watch_debug.log")
    }()

    // MARK: - Properties

    @Published var isConnected = false
    @Published var connectionStatus = "Disconnected"
    @Published var serverURL: String?

    // WebSocket
    private var webSocketTask: URLSessionWebSocketTask?
    private var urlSession: URLSession?

    // Server discovery
    private let serverIPs = ["YOUR_MAC_IP", "127.0.0.1"]
    private let serverPort = 8000

    // Track accumulated samples from incremental batches
    private var sessionSamples: [String: [[String: Any]]] = [:]
    private var sessionStarted: Set<String> = []
    private var currentSessionId: String?

    // MARK: - Initialization

    private override init() {
        print("🏗️ BackendClient.init() v5.0.0 - Dual Mode (WebSocket + USB)")
        super.init()

        // Setup URLSession
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 10
        config.timeoutIntervalForResource = 300
        urlSession = URLSession(configuration: config)

        // Setup WatchConnectivity
        setupWatchConnectivity()

        // Auto-connect to Mac server
        autoDiscoverAndConnect()

        NSLog("⚡️ BACKENDCLIENT v5.0.0 INITIALIZED - DUAL MODE ⚡️")
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

    // MARK: - WebSocket Connection

    private func autoDiscoverAndConnect() {
        Task {
            for ip in serverIPs {
                let urlString = "http://\(ip):\(serverPort)/api/health"
                guard let url = URL(string: urlString) else { continue }

                do {
                    let (_, response) = try await URLSession.shared.data(from: url)
                    if let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 {
                        print("✅ Found Mac server at \(ip):\(serverPort)")
                        await connectToServer(ip: ip)
                        return
                    }
                } catch {
                    // Server not reachable at this IP, try next
                    continue
                }
            }

            // No server found - fallback to USB mode
            await MainActor.run {
                self.connectionStatus = "USB Mode (Server not found)"
                self.isConnected = false
                print("⚠️ No Mac server found - using USB-only mode")
            }
        }
    }

    @MainActor
    private func connectToServer(ip: String) {
        let wsURL = URL(string: "ws://\(ip):\(serverPort)/ws")!
        serverURL = wsURL.absoluteString

        webSocketTask = urlSession?.webSocketTask(with: wsURL)
        webSocketTask?.resume()

        connectionStatus = "Connected to \(ip)"
        isConnected = true

        print("🔗 WebSocket connected: \(wsURL)")

        // Start receiving messages
        receiveMessage()
    }

    func disconnect() {
        webSocketTask?.cancel(with: .goingAway, reason: nil)
        webSocketTask = nil

        DispatchQueue.main.async {
            self.isConnected = false
            self.connectionStatus = "Disconnected"
        }

        print("🔌 WebSocket disconnected")
    }

    private func receiveMessage() {
        webSocketTask?.receive { [weak self] result in
            guard let self = self else { return }

            switch result {
            case .success(let message):
                switch message {
                case .string(let text):
                    print("📥 Received: \(text)")
                case .data(let data):
                    print("📥 Received data: \(data.count) bytes")
                @unknown default:
                    break
                }
                // Continue receiving
                self.receiveMessage()

            case .failure(let error):
                print("❌ WebSocket receive error: \(error.localizedDescription)")
                DispatchQueue.main.async {
                    self.isConnected = false
                    self.connectionStatus = "Disconnected"
                }
            }
        }
    }

    private func sendMessage(_ message: [String: Any]) {
        guard isConnected, let webSocketTask = webSocketTask else {
            print("⚠️ WebSocket not connected - data saved locally only")
            return
        }

        do {
            let jsonData = try JSONSerialization.data(withJSONObject: message)
            let jsonString = String(data: jsonData, encoding: .utf8)!
            let wsMessage = URLSessionWebSocketTask.Message.string(jsonString)

            webSocketTask.send(wsMessage) { error in
                if let error = error {
                    print("❌ WebSocket send error: \(error.localizedDescription)")
                }
            }
        } catch {
            print("❌ Failed to serialize message: \(error.localizedDescription)")
        }
    }

    // MARK: - Local Database Operations

    func saveSensorBatch(_ batch: [String: Any]) {
        guard let sessionId = batch["session_id"] as? String,
              let samples = batch["samples"] as? [[String: Any]] else {
            print("❌ Invalid batch data")
            return
        }

        // Always save locally (USB fallback)
        LocalDatabase.shared.insertSensorBatch(sessionId: sessionId, samples: samples)
        print("💾 Saved \(samples.count) samples to local database")

        // Stream to Mac server if connected
        if isConnected {
            let message: [String: Any] = [
                "type": "sensor_batch",
                "session_id": sessionId,
                "samples": samples
            ]
            sendMessage(message)
            print("📡 Streamed \(samples.count) samples to Mac server")
        }
    }

    func startSession(sessionId: String, device: String = "AppleWatch") {
        currentSessionId = sessionId
        let startTime = Int(Date().timeIntervalSince1970)

        // Always save locally
        LocalDatabase.shared.insertSession(sessionId: sessionId, device: device, startTime: startTime)
        setIdleTimerDisabled(true)
        print("💾 Session started: \(sessionId)")

        // Send to Mac server if connected
        if isConnected {
            let message: [String: Any] = [
                "type": "session_start",
                "session_id": sessionId,
                "device": device
            ]
            sendMessage(message)
            print("📡 Session start sent to Mac server")
        }
    }

    func endSession(sessionId: String) {
        let endTime = Int(Date().timeIntervalSince1970)

        // Always save locally
        LocalDatabase.shared.updateSessionEnd(sessionId: sessionId, endTime: endTime, duration: 0)
        print("💾 Session ended: \(sessionId)")

        // Send to Mac server if connected
        if isConnected {
            let message: [String: Any] = [
                "type": "session_end",
                "session_id": sessionId
            ]
            sendMessage(message)
            print("📡 Session end sent to Mac server")
        }

        currentSessionId = nil
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
        case "debug_event":
            handleDebugEvent(userInfo)
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

    private func handleDebugEvent(_ userInfo: [String: Any]) {
        let timestamp = userInfo["timestamp"] as? Double
        let date = timestamp.map { Date(timeIntervalSince1970: $0) } ?? Date()
        let event = userInfo["event"] as? String ?? "unknown"
        let sessionId = userInfo["session_id"] as? String ?? "-"
        let details = userInfo["details"] as? [String: Any] ?? [:]

        let line = "\(debugDateFormatter.string(from: date)) | \(event) | session=\(sessionId) | \(details)\n"
        appendDebugLog(line)
        print("🐞 Watch debug: \(line.trimmingCharacters(in: .whitespacesAndNewlines))")
    }

    private func appendDebugLog(_ line: String) {
        let data = Data(line.utf8)
        if FileManager.default.fileExists(atPath: debugLogURL.path) {
            if let handle = try? FileHandle(forWritingTo: debugLogURL) {
                handle.seekToEndOfFile()
                handle.write(data)
                try? handle.close()
            }
        } else {
            try? data.write(to: debugLogURL, options: .atomic)
        }
    }
}
