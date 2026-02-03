//
//  ContentView.swift
//  TennisSensor
//
//  v3.4 - Simplified for USB-only workflow
//  Data stored locally, pulled via pymobiledevice3
//

import SwiftUI
import WatchConnectivity

struct ContentView: View {
    @EnvironmentObject var backendClient: BackendClient
    @State private var wcSessionActivated = false
    @State private var watchReachable = false
    @State private var dbStats = (sessions: 0, samples: 0, sizeBytes: 0)
    @State private var showingClearDatabaseAlert = false
    @State private var httpServerRunning = false
    @State private var httpServerURL: String? = nil

    var body: some View {
        NavigationView {
            VStack(spacing: 20) {
                // Header
                VStack(spacing: 10) {
                    Image(systemName: "tennisball.fill")
                        .font(.system(size: 60))
                        .foregroundStyle(.green)

                    Text("TT v4.0.0")
                        .font(.title)
                        .fontWeight(.bold)

                    Text("USB Transfer Mode")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .padding(.top, 20)

                Spacer()

                // WatchConnectivity Status
                VStack(spacing: 15) {
                    HStack(spacing: 15) {
                        HStack(spacing: 4) {
                            Circle()
                                .fill(wcSessionActivated ? Color.green : Color.red)
                                .frame(width: 10, height: 10)
                            Text(wcSessionActivated ? "WC Active" : "WC Inactive")
                                .font(.subheadline)
                        }

                        HStack(spacing: 4) {
                            Circle()
                                .fill(watchReachable ? Color.green : Color.orange)
                                .frame(width: 10, height: 10)
                            Text(watchReachable ? "Watch Connected" : "Watch Not Reachable")
                                .font(.subheadline)
                        }
                    }
                }
                .padding()
                .background(
                    RoundedRectangle(cornerRadius: 15)
                        .fill(Color(.systemGray6))
                )
                .padding(.horizontal)

                // Instructions
                VStack(alignment: .leading, spacing: 10) {
                    Label("Workflow:", systemImage: "info.circle")
                        .font(.headline)

                    VStack(alignment: .leading, spacing: 8) {
                        HStack(alignment: .top) {
                            Text("1.")
                            Text("Record session on Watch")
                        }
                        HStack(alignment: .top) {
                            Text("2.")
                            Text("Data syncs to this iPhone automatically")
                        }
                        HStack(alignment: .top) {
                            Text("3.")
                            Text("Connect iPhone to Mac via USB")
                        }
                        HStack(alignment: .top) {
                            Text("4.")
                            Text("Pull data with pymobiledevice3")
                        }
                        HStack(alignment: .top) {
                            Text("Note:")
                            Text("Keep this iPhone screen on during sessions so it stays awake and receives data.")
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

                // HTTP Server
                VStack(spacing: 10) {
                    HStack {
                        Image(systemName: "network")
                            .foregroundStyle(.purple)
                        Text("HTTP Server")
                            .font(.headline)
                        Spacer()
                    }

                    if let url = httpServerURL, httpServerRunning {
                        Text(url)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .multilineTextAlignment(.leading)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    } else {
                        Text("Start a local HTTP server for direct downloads on the same Wi‑Fi.")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }

                    Button(action: {
                        toggleHTTPServer()
                    }) {
                        HStack {
                            Image(systemName: httpServerRunning ? "stop.circle.fill" : "play.circle.fill")
                            Text(httpServerRunning ? "Stop HTTP Server" : "Start HTTP Server")
                        }
                        .font(.headline)
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(httpServerRunning ? Color.red : Color.purple)
                        .cornerRadius(10)
                    }
                }
                .padding()
                .background(
                    RoundedRectangle(cornerRadius: 15)
                        .fill(Color(.systemGray6))
                )
                .padding(.horizontal)

                Spacer()

                // Local Database Stats
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
                .onReceive(NotificationCenter.default.publisher(for: UIApplication.willEnterForegroundNotification)) { _ in
                    updateDatabaseStats()
                }

                // Clear Database Button
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
                .padding(.horizontal)
                .padding(.bottom, 30)
            }
            .navigationBarTitleDisplayMode(.inline)
            .onAppear {
                checkWCSession()
                // Periodically update Watch reachability
                Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { _ in
                    checkWCSession()
                    updateDatabaseStats()
                }
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

    private func updateDatabaseStats() {
        dbStats = LocalDatabase.shared.getDatabaseStats()
    }

    private func formatBytes(_ bytes: Int) -> String {
        let formatter = ByteCountFormatter()
        formatter.allowedUnits = [.useKB, .useMB]
        formatter.countStyle = .file
        return formatter.string(fromByteCount: Int64(bytes))
    }

    private func clearDatabase() {
        LocalDatabase.shared.clearAllData()
        updateDatabaseStats()

        let generator = UINotificationFeedbackGenerator()
        generator.notificationOccurred(.success)

        print("✅ Database cleared successfully")
    }

    private func toggleHTTPServer() {
        if httpServerRunning {
            HTTPFileServer.shared.stop()
            httpServerRunning = false
            httpServerURL = nil
            return
        }

        let url = LocalDatabase.shared.getDatabaseURL()
        httpServerURL = HTTPFileServer.shared.start(fileURL: url)
        httpServerRunning = httpServerURL != nil
    }
}

#Preview {
    ContentView()
        .environmentObject(BackendClient.shared)
}
