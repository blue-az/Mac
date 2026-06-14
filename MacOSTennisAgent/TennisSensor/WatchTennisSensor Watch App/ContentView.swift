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
    @Environment(\.scenePhase) private var scenePhase
    @StateObject private var motionManager = MotionManager()
    @StateObject private var workoutManager = WorkoutManager()
    @StateObject private var audioManager = AudioManager()
    @StateObject private var settings = SettingsManager.shared
    @State private var pulseAnimation = false
    @State private var wcSessionActivated = false
    @State private var showingSessionComplete = false
    @State private var currentSessionId: String?  // v3.1: Store session ID for audio
    @State private var lastStopTime: Date?
    @State private var audioSegmentIndex = 1

    private let resumeWindow: TimeInterval = 5 * 60

    var body: some View {
        VStack(spacing: 12) {
            // Header
            VStack(spacing: 2) {
                Image(systemName: "tennisball.fill")
                    .font(.system(size: 20))
                    .foregroundStyle(motionManager.isRecording ? .green : .gray)

                Text("TT v4.1.0")
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
                    DebugEventSender.send(
                        "recording_state_changed",
                        sessionId: currentSessionId,
                        details: ["isRecording": isRecording]
                    )
                    if !isRecording && motionManager.sampleCount > 0 {
                        showingSessionComplete = true
                    }
                }

                // Reset Button (appears after session completes) - v3.2: same size as Start/Stop
                if showingSessionComplete && !motionManager.isRecording {
                    Button(action: {
                        resetSession()
                    }) {
                        HStack(spacing: 4) {
                            Image(systemName: "arrow.counterclockwise")
                                .font(.system(size: 22))

                            Text("Reset")
                                .font(.system(size: 13))
                                .fontWeight(.bold)
                        }
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 10)
                        .background(Color.blue)
                        .cornerRadius(10)
                    }
                    .buttonStyle(.plain)
                }

                // Resend Button - appears when sessions are stored locally but not yet delivered
                if motionManager.storedSessionCount > 0 && !motionManager.isRecording {
                    Button(action: {
                        motionManager.resendStoredSessions()
                        WKInterfaceDevice.current().play(.click)
                    }) {
                        HStack(spacing: 4) {
                            Image(systemName: "arrow.up.circle.fill")
                                .font(.system(size: 22))

                            Text("Resend (\(motionManager.storedSessionCount))")
                                .font(.system(size: 13))
                                .fontWeight(.bold)
                        }
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 10)
                        .background(Color.orange)
                        .cornerRadius(10)
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
            motionManager.refreshStoredCount()
        }
        .onChange(of: scenePhase) { _, newPhase in
            DebugEventSender.send(
                "scene_phase_change",
                sessionId: currentSessionId,
                details: ["phase": String(describing: newPhase)]
            )
        }
    }

    private func startSession() {
        print("🎾 Starting tennis session...")
        DebugEventSender.send("start_session_tapped", details: ["has_active_session": currentSessionId != nil])

        let now = Date()
        var isResuming = false

        if let lastStopTime = lastStopTime,
           let _ = currentSessionId,
           now.timeIntervalSince(lastStopTime) <= resumeWindow {
            isResuming = true
        } else {
            currentSessionId = nil
        }

        // v3.1: Generate session ID once and store it for consistent use
        if currentSessionId == nil {
            currentSessionId = "watch_\(DateFormatter.sessionIdFormatter.string(from: now))"
            audioSegmentIndex = 1
        } else if isResuming {
            audioSegmentIndex += 1
        }

        // v2.6: Start workout session FIRST to prevent screen sleep
        workoutManager.startWorkout()

        // Wait briefly for workout to initialize, then start motion recording
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            motionManager.workoutSessionActive = workoutManager.isWorkoutActive
            if let sessionId = currentSessionId {
                DebugEventSender.send("motion_start_requested", sessionId: sessionId)
                motionManager.startSession(sessionId: sessionId)
            }

            // v3.1: Start audio recording if enabled, using stored session ID
            if settings.isAudioEnabled, let sessionId = currentSessionId {
                audioManager.startRecording(sessionId: sessionId, segmentIndex: audioSegmentIndex)
            }
        }

        // Haptic feedback
        WKInterfaceDevice.current().play(.start)
    }

    private func stopSession() {
        print("🏁 Stopping tennis session...")
        DebugEventSender.send("stop_session_tapped", sessionId: currentSessionId)

        // v2.6: Stop motion recording first
        motionManager.stopSession()
        lastStopTime = Date()

        // v3.1: Stop audio recording and transfer file using stored session ID
        if audioManager.isRecording, let sessionId = currentSessionId {
            if let _ = audioManager.stopRecording() {
                audioManager.transferAudioFile(sessionId: sessionId, segmentIndex: audioSegmentIndex)
            }
        }

        // Then end workout session
        workoutManager.stopWorkout()

        // Haptic feedback
        WKInterfaceDevice.current().play(.stop)
    }

    private func resetSession() {
        print("🔄 Resetting to home screen...")
        DebugEventSender.send("reset_session_tapped", sessionId: currentSessionId)

        // Clear the session complete flag to return to home screen
        showingSessionComplete = false
        currentSessionId = nil
        lastStopTime = nil
        audioSegmentIndex = 1

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
