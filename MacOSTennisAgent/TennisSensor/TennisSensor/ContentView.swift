//
//  ContentView.swift
//  TennisSensor
//
//  Created by wikiwoo on 4/30/25.
//  Updated for MacOSTennisAgent integration
//

import SwiftUI
import WatchConnectivity

struct ContentView: View {
    @EnvironmentObject var backendClient: BackendClient
    @State private var showConnectionAlert = false
    @State private var wcSessionActivated = false
    @State private var watchReachable = false
    @State private var showingExportSheet = false
    @State private var httpServerRunning = false
    @State private var httpServerURL = ""
    @State private var dbStats = (sessions: 0, samples: 0, sizeBytes: 0)
    @State private var showingClearDatabaseAlert = false

    var body: some View {
        NavigationView {
            VStack(spacing: 30) {
                // Header
                VStack(spacing: 10) {
                    Image(systemName: "tennisball.fill")
                        .font(.system(size: 60))
                        .foregroundStyle(.green)

                    Text("TT v3.1")
                        .font(.title)
                        .fontWeight(.bold)
                }
                .padding(.top, 10)

                Spacer()

                // Connection Status
                VStack(spacing: 15) {
                    HStack {
                        Circle()
                            .fill(backendClient.isConnected ? Color.green : Color.red)
                            .frame(width: 12, height: 12)

                        Text(backendClient.connectionStatus)
                            .font(.headline)
                    }

                    Text("Backend: ws://192.168.8.185:8000/ws")
                        .font(.caption)
                        .foregroundStyle(.secondary)

                    // WatchConnectivity Status
                    HStack(spacing: 15) {
                        HStack(spacing: 4) {
                            Circle()
                                .fill(wcSessionActivated ? Color.green : Color.red)
                                .frame(width: 8, height: 8)
                            Text(wcSessionActivated ? "WC Active" : "WC Inactive")
                                .font(.caption2)
                        }

                        HStack(spacing: 4) {
                            Circle()
                                .fill(watchReachable ? Color.green : Color.orange)
                                .frame(width: 8, height: 8)
                            Text(watchReachable ? "Watch Reachable" : "Watch Not Reachable")
                                .font(.caption2)
                        }
                    }
                    .foregroundStyle(.secondary)
                }
                .padding()
                .background(
                    RoundedRectangle(cornerRadius: 15)
                        .fill(Color(.systemGray6))
                )
                .padding(.horizontal)

                Spacer()

                // Instructions
                VStack(alignment: .leading, spacing: 10) {
                    Label("Instructions:", systemImage: "info.circle")
                        .font(.headline)

                    VStack(alignment: .leading, spacing: 8) {
                        HStack(alignment: .top) {
                            Text("1.")
                            Text("Open the Watch app on your Apple Watch")
                        }

                        HStack(alignment: .top) {
                            Text("2.")
                            Text("Tap 'Start Session' to begin recording")
                        }

                        HStack(alignment: .top) {
                            Text("3.")
                            Text("Sensor data will be collected")
                        }
                    }
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                }
                .padding()
                .background(
                    RoundedRectangle(cornerRadius: 15)
                        .fill(Color(.systemGray6))
                )
                .padding(.horizontal)

                Spacer()

                // v2.7: Local Database Stats
                VStack(spacing: 8) {
                    HStack {
                        Image(systemName: "cylinder.fill")
                            .foregroundStyle(.blue)
                        Text("Local Database")
                            .font(.headline)
                        Spacer()
                    }

                    HStack {
                        Text("\(dbStats.sessions) sessions")
                        Text("•")
                        Text("\(dbStats.samples) samples")
                        Text("•")
                        Text(formatBytes(dbStats.sizeBytes))
                    }
                    .font(.caption)
                    .foregroundStyle(.secondary)
                }
                .padding()
                .background(
                    RoundedRectangle(cornerRadius: 15)
                        .fill(Color(.systemGray6))
                )
                .padding(.horizontal)
                .onAppear {
                    updateDatabaseStats()
                }

                // v2.7: Export Buttons
                VStack(spacing: 12) {
                    // Export to Files App
                    Button(action: {
                        exportDatabase()
                    }) {
                        HStack {
                            Image(systemName: "square.and.arrow.up")
                            Text("Export Database")
                        }
                        .font(.headline)
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.green)
                        .cornerRadius(10)
                    }

                    // Clear Database Button (v2.7.4)
                    Button(action: {
                        showingClearDatabaseAlert = true
                    }) {
                        HStack {
                            Image(systemName: "trash.fill")
                            Text("Clear Database")
                        }
                        .font(.headline)
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.red)
                        .cornerRadius(10)
                    }

                    // HTTP Server for Linux Download
                    Button(action: {
                        toggleHTTPServer()
                    }) {
                        HStack {
                            Image(systemName: httpServerRunning ? "stop.circle" : "arrow.down.circle")
                            Text(httpServerRunning ? "Stop Server" : "Start HTTP Server")
                        }
                        .font(.headline)
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(httpServerRunning ? Color.orange : Color.purple)
                        .cornerRadius(10)
                    }

                    if httpServerRunning {
                        Text("Download at: \(httpServerURL)")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .padding(.horizontal)
                    }
                }
                .padding(.horizontal)

                // Connect/Disconnect Button
                Button(action: {
                    if backendClient.isConnected {
                        backendClient.disconnect()
                    } else {
                        backendClient.connect()
                    }
                }) {
                    Text(backendClient.isConnected ? "Disconnect" : "🔌 Connect Backend")
                        .font(.headline)
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(backendClient.isConnected ? Color.red : Color.blue)
                        .cornerRadius(10)
                }
                .padding(.horizontal)
                .padding(.bottom, 30)
            }
            .navigationBarTitleDisplayMode(.inline)
            .onAppear {
                // Auto-connect on appear
                backendClient.connect()
                // Check WatchConnectivity status
                checkWCSession()
                // Periodically update Watch reachability
                Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { _ in
                    checkWCSession()
                }
            }
            .onReceive(NotificationCenter.default.publisher(for: NSNotification.Name("SwingDetected"))) { notification in
                // Haptic feedback when swing detected
                let generator = UINotificationFeedbackGenerator()
                generator.notificationOccurred(.success)

                // Show alert (optional)
                showConnectionAlert = true
            }
            .alert("Clear Database?", isPresented: $showingClearDatabaseAlert) {
                Button("Cancel", role: .cancel) { }
                Button("Clear All Data", role: .destructive) {
                    clearDatabase()
                }
            } message: {
                Text("This will permanently delete all sessions and sensor data. This action cannot be undone.")
            }
        }
    }

    private func checkWCSession() {
        if WCSession.isSupported() {
            wcSessionActivated = WCSession.default.activationState == .activated
            watchReachable = WCSession.default.isReachable
        }
    }

    // v2.7: Database Management

    private func updateDatabaseStats() {
        dbStats = LocalDatabase.shared.getDatabaseStats()
    }

    private func formatBytes(_ bytes: Int) -> String {
        let formatter = ByteCountFormatter()
        formatter.allowedUnits = [.useKB, .useMB]
        formatter.countStyle = .file
        return formatter.string(fromByteCount: Int64(bytes))
    }

    private func exportDatabase() {
        let dbURL = LocalDatabase.shared.getDatabaseURL()
        let activityVC = UIActivityViewController(
            activityItems: [dbURL],
            applicationActivities: nil
        )

        if let windowScene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
           let rootVC = windowScene.windows.first?.rootViewController {
            rootVC.present(activityVC, animated: true)
        }

        // Update stats after export
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            updateDatabaseStats()
        }
    }

    private func toggleHTTPServer() {
        if httpServerRunning {
            // Stop server
            HTTPFileServer.shared.stop()
            httpServerRunning = false
            httpServerURL = ""
        } else {
            // Start server
            let dbURL = LocalDatabase.shared.getDatabaseURL()
            if let url = HTTPFileServer.shared.start(fileURL: dbURL) {
                httpServerRunning = true
                httpServerURL = url
            }
        }
    }

    private func clearDatabase() {
        // Clear all data from local database
        LocalDatabase.shared.clearAllData()

        // Update stats to show empty database
        updateDatabaseStats()

        // Haptic feedback
        let generator = UINotificationFeedbackGenerator()
        generator.notificationOccurred(.success)

        print("✅ Database cleared successfully")
    }
}

#Preview {
    ContentView()
        .environmentObject(BackendClient.shared)
}
