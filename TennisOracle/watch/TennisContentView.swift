import SwiftUI

struct TennisContentView: View {
    @StateObject private var motionManager = TennisMotionManager()
    @State private var lastShotMph: Double = 0
    @State private var readiness: Double = 100
    @State private var isFatigued = false
    @State private var cleanContact = true

    var body: some View {
        VStack(spacing: 5) {
            // Header: Status & HR
            HStack {
                Circle()
                    .fill(motionManager.isRecording ? Color.green : Color.red)
                    .frame(width: 8, height: 8)
                Text(motionManager.isRecording ? "LIVE" : "READY")
                    .font(.system(size: 10, weight: .bold))
                Text("v1.1")
                    .font(.system(size: 8))
                    .foregroundColor(.secondary)
                Spacer()
                Image(systemName: "heart.fill")
                    .foregroundColor(.red)
                Text("\(Int(motionManager.heartRate))")
                    .font(.system(size: 12, design: .monospaced))
            }
            .padding(.horizontal)

            // Mode Selector (HStack for better compatibility)
            HStack(spacing: 0) {
                Button(action: { motionManager.mode = .strokes }) {
                    Text("STROKES")
                        .font(.system(size: 10, weight: .bold))
                        .frame(maxWidth: .infinity)
                }
                .tint(motionManager.mode == .strokes ? .green : .gray)
                .buttonStyle(.borderedProminent)
                
                Button(action: { motionManager.mode = .serve }) {
                    Text("SERVE")
                        .font(.system(size: 10, weight: .bold))
                        .frame(maxWidth: .infinity)
                }
                .tint(motionManager.mode == .serve ? .green : .gray)
                .buttonStyle(.borderedProminent)
            }
            .disabled(motionManager.isRecording)
            .frame(height: 35)

            // Main Metric: Shot Speed
            VStack(spacing: 0) {
                Text(motionManager.mode == .serve ? "SERVE SPEED" : "SHOT SPEED")
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundColor(.secondary)
                Text(String(format: "%.1f", lastShotMph))
                    .font(.system(size: 30, weight: .black, design: .rounded))
                Text("MPH")
                    .font(.system(size: 10, weight: .bold))
            }

            // Readiness / Fatigue Indicator
            VStack(spacing: 2) {
                HStack {
                    Text(cleanContact ? "CLEAN CONTACT" : "OFF-CENTER")
                        .foregroundColor(cleanContact ? .primary : .orange)
                    Spacer()
                    Text("\(Int(readiness))%")
                }
                .font(.system(size: 9, weight: .bold))

                ProgressView(value: readiness, total: 100)
                    .accentColor(isFatigued ? .yellow : .green)
            }
            .padding(.horizontal, 5)
            .background(isFatigued ? Color.yellow.opacity(0.2) : Color.clear)
            .cornerRadius(8)

            // Control Button
            Button(action: {
                if motionManager.isRecording {
                    motionManager.stopSession()
                } else {
                    motionManager.startSession()
                }
            }) {
                Text(motionManager.isRecording ? "STOP" : "START ORACLE")
                    .font(.system(size: 12, weight: .bold))
                    .frame(maxWidth: .infinity)
            }
            .tint(motionManager.isRecording ? .red : .blue)
            .buttonStyle(.borderedProminent)
            .frame(height: 35)
        }
        .onReceive(NotificationCenter.default.publisher(for: NSNotification.Name("TennisShotDetected"))) { notification in
            if let shot = notification.userInfo?["shot"] as? [String: Any],
               let metrics = shot["metrics"] as? [String: Any],
               let flags = shot["flags"] as? [String: Any] {
                
                self.lastShotMph = metrics["speed_mph"] as? Double ?? 0
                self.readiness = metrics["readiness_pct"] as? Double ?? 100
                self.isFatigued = flags["micro_fatigue"] as? Bool ?? false
                self.cleanContact = flags["clean_contact"] as? Bool ?? true
                
                // Haptic Feedback
                if !cleanContact {
                    WKInterfaceDevice.current().play(.failure)
                } else if isFatigued {
                    WKInterfaceDevice.current().play(.directionUp)
                } else {
                    WKInterfaceDevice.current().play(.success)
                }
            }
        }
    }
}
