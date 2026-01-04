//
//  ContentView.swift
//  WatchTennisSensor Watch App
//
//  Created by wikiwoo on 4/30/25.
//  Updated for MacOSTennisAgent integration
//

import SwiftUI
import WatchConnectivity

struct ContentView: View {
    @StateObject private var motionManager = MotionManager()
    @StateObject private var workoutManager = WorkoutManager()
    @StateObject private var audioManager = AudioManager()
    @StateObject private var settings = SettingsManager.shared
    @State private var pulseAnimation = false
    @State private var wcSessionActivated = false
    @State private var showingSessionComplete = false

    var body: some View {
        VStack(spacing: 12) {
            // Header
            VStack(spacing: 2) {
                Image(systemName: "tennisball.fill")
                    .font(.system(size: 20))
                    .foregroundStyle(motionManager.isRecording ? .green : .gray)

                Text("TT v3")
                    .font(.system(size: 14))
                    .fontWeight(.bold)
            }

            // Stats - Compact horizontal layout
            if motionManager.isRecording || showingSessionComplete {
                HStack(spacing: 12) {
                    // Sample count
                    VStack(spacing: 0) {
                        Text("\(motionManager.sampleCount)")
                            .font(.system(size: 14))
                            .fontWeight(.bold)
                            .foregroundStyle(motionManager.isRecording ? .green : .blue)
                        Text("Samples")
                            .font(.system(size: 7))
                            .foregroundStyle(.secondary)
                    }

                    // Duration
                    VStack(spacing: 0) {
                        Text(formatDuration(motionManager.sessionDuration))
                            .font(.system(size: 14))
                            .fontWeight(.bold)
                        Text("Duration")
                            .font(.system(size: 7))
                            .foregroundStyle(.secondary)
                    }

                    // Sample rate
                    VStack(spacing: 0) {
                        Text("\(Int(motionManager.sampleRate))")
                            .font(.system(size: 14))
                            .fontWeight(.bold)
                        Text("Hz")
                            .font(.system(size: 7))
                            .foregroundStyle(.secondary)
                    }
                }
                .padding(.vertical, 2)
            }

            Spacer()

            // Audio Toggle - moved above buttons for visibility on small screens
            HStack(spacing: 6) {
                Image(systemName: settings.isAudioEnabled ? "mic.fill" : "mic.slash")
                    .font(.system(size: 12))
                    .foregroundStyle(settings.isAudioEnabled ? .orange : .gray)

                Toggle("", isOn: $settings.isAudioEnabled)
                    .labelsHidden()
                    .tint(.orange)

                Text(settings.isAudioEnabled ? "Audio On" : "Audio Off")
                    .font(.system(size: 10))
                    .foregroundStyle(.secondary)
            }

            // Buttons
            VStack(spacing: 8) {
                // Start/Stop Button
                Button(action: {
                    if motionManager.isRecording {
                        stopSession()
                    } else {
                        startSession()
                    }
                }) {
                    HStack(spacing: 4) {
                        Image(systemName: motionManager.isRecording ? "stop.circle.fill" : "play.circle.fill")
                            .font(.system(size: 22))

                        Text(motionManager.isRecording ? "Stop" : "Start")
                            .font(.system(size: 13))
                            .fontWeight(.bold)
                    }
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 10)
                    .background(motionManager.isRecording ? Color.red : Color.green)
                    .cornerRadius(10)
                    .scaleEffect(motionManager.isRecording && pulseAnimation ? 1.05 : 1.0)
                    .animation(.easeInOut(duration: 0.8).repeatForever(autoreverses: true), value: pulseAnimation)
                }
                .buttonStyle(.plain)
                .onChange(of: motionManager.isRecording) { _, isRecording in
                    pulseAnimation = isRecording
                    if !isRecording && motionManager.sampleCount > 0 {
                        showingSessionComplete = true
                    }
                }

                // Reset Button (appears after session completes)
                if showingSessionComplete && !motionManager.isRecording {
                    Button(action: {
                        resetSession()
                    }) {
                        HStack(spacing: 4) {
                            Image(systemName: "arrow.counterclockwise")
                                .font(.system(size: 16))

                            Text("Reset")
                                .font(.system(size: 12))
                                .fontWeight(.medium)
                        }
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 8)
                        .background(Color.blue)
                        .cornerRadius(8)
                    }
                    .buttonStyle(.plain)
                }
            }

            // WC Status
            HStack(spacing: 2) {
                Circle()
                    .fill(wcSessionActivated ? Color.green : Color.red)
                    .frame(width: 3, height: 3)
                Text(wcSessionActivated ? "WC Active" : "WC Inactive")
                    .font(.system(size: 8))
                    .foregroundStyle(.secondary)

                // Audio recording indicator
                if audioManager.isRecording {
                    Circle()
                        .fill(Color.orange)
                        .frame(width: 3, height: 3)
                    Text("Rec")
                        .font(.system(size: 8))
                        .foregroundStyle(.orange)
                }
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .onAppear {
            checkWCSession()
        }
    }

    private func startSession() {
        print("🎾 Starting tennis session...")

        // v2.6: Start workout session FIRST to prevent screen sleep
        workoutManager.startWorkout()

        // Wait briefly for workout to initialize, then start motion recording
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            motionManager.workoutSessionActive = workoutManager.isWorkoutActive
            motionManager.startSession()

            // v2.7.12: Start audio recording if enabled
            if settings.isAudioEnabled {
                let sessionId = "watch_\(DateFormatter.sessionIdFormatter.string(from: Date()))"
                audioManager.startRecording(sessionId: sessionId)
            }
        }

        // Haptic feedback
        WKInterfaceDevice.current().play(.start)
    }

    private func stopSession() {
        print("🏁 Stopping tennis session...")

        // v2.6: Stop motion recording first
        motionManager.stopSession()

        // v2.7.12: Stop audio recording and transfer file
        if audioManager.isRecording {
            if let audioURL = audioManager.stopRecording() {
                // Get session ID from MotionManager or generate one
                let sessionId = "watch_\(DateFormatter.sessionIdFormatter.string(from: Date()))"
                audioManager.transferAudioFile(sessionId: sessionId)
            }
        }

        // Then end workout session
        workoutManager.stopWorkout()

        // Haptic feedback
        WKInterfaceDevice.current().play(.stop)
    }

    private func resetSession() {
        print("🔄 Resetting to home screen...")

        // Clear the session complete flag to return to home screen
        showingSessionComplete = false

        // Cleanup any audio files
        audioManager.cleanupRecording()

        // Haptic feedback
        WKInterfaceDevice.current().play(.click)
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
