//
//  ContentView.swift - FALLBACK v2.5.6
//  WatchTennisSensor Watch App
//
//  Simplified version without WorkoutManager
//  Use this if v2.6.2 installation fails
//
//  TO USE:
//  1. Replace WatchTennisSensor Watch App/ContentView.swift with this file
//  2. Remove HealthKit from entitlements (or use FALLBACK_v2_5_6_Entitlements.plist)
//  3. Build and install
//

import SwiftUI
import WatchConnectivity

struct ContentView: View {
    @StateObject private var motionManager = MotionManager()
    @State private var pulseAnimation = false
    @State private var wcSessionActivated = false

    var body: some View {
        VStack(spacing: 20) {
            // Header
            VStack(spacing: 3) {
                Image(systemName: "tennisball.fill")
                    .font(.system(size: 24))
                    .foregroundStyle(motionManager.isRecording ? .green : .gray)

                Text("TT v2.5.6")
                    .font(.system(size: 16))
                    .fontWeight(.bold)
            }

            // Stats
            if motionManager.isRecording {
                VStack(spacing: 6) {
                    // Sample count
                    VStack(spacing: 1) {
                        Text("Samples")
                            .font(.system(size: 10))
                            .foregroundStyle(.secondary)

                        Text("\(motionManager.sampleCount)")
                            .font(.system(size: 18))
                            .fontWeight(.bold)
                            .foregroundStyle(.green)
                    }

                    // Duration
                    VStack(spacing: 1) {
                        Text("Duration")
                            .font(.system(size: 10))
                            .foregroundStyle(.secondary)

                        Text(formatDuration(motionManager.sessionDuration))
                            .font(.system(size: 16))
                            .fontWeight(.semibold)
                    }

                    // Sample rate
                    Text("\(Int(motionManager.sampleRate)) Hz")
                        .font(.system(size: 10))
                        .foregroundStyle(.secondary)
                }
                .padding(.vertical, 6)
            }

            Spacer()

            // Start/Stop Button
            Button(action: {
                if motionManager.isRecording {
                    stopSession()
                } else {
                    startSession()
                }
            }) {
                VStack(spacing: 4) {
                    Image(systemName: motionManager.isRecording ? "stop.circle.fill" : "play.circle.fill")
                        .font(.system(size: 28))

                    Text(motionManager.isRecording ? "⏹ Stop" : "🎾 Start")
                        .font(.system(size: 14))
                        .fontWeight(.bold)
                }
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 12)
                .background(motionManager.isRecording ? Color.red : Color.green)
                .cornerRadius(12)
                .scaleEffect(motionManager.isRecording && pulseAnimation ? 1.05 : 1.0)
                .animation(.easeInOut(duration: 0.8).repeatForever(autoreverses: true), value: pulseAnimation)
            }
            .buttonStyle(.plain)
            .onChange(of: motionManager.isRecording) { _, isRecording in
                pulseAnimation = isRecording
            }

            // WC Status
            HStack(spacing: 2) {
                Circle()
                    .fill(wcSessionActivated ? Color.green : Color.red)
                    .frame(width: 4, height: 4)
                Text(wcSessionActivated ? "WC Active" : "WC Inactive")
                    .font(.system(size: 9))
                    .foregroundStyle(.secondary)
            }
        }
        .padding()
        .onAppear {
            checkWCSession()
        }
    }

    private func startSession() {
        print("🎾 Starting tennis session...")

        // Simple session start (no WorkoutManager)
        motionManager.startSession()

        // Haptic feedback
        WKInterfaceDevice.current().play(.start)
    }

    private func stopSession() {
        print("🏁 Stopping tennis session...")

        // Simple session stop
        motionManager.stopSession()

        // Haptic feedback
        WKInterfaceDevice.current().play(.stop)
    }

    private func formatDuration(_ duration: TimeInterval) -> String {
        let minutes = Int(duration) / 60
        let seconds = Int(duration) % 60
        return String(format: "%d:%02d", minutes, seconds)
    }

    private func checkWCSession() {
        if WCSession.isSupported() {
            wcSessionActivated = WCSession.default.activationState == .activated
        }
    }
}

#Preview {
    ContentView()
}
