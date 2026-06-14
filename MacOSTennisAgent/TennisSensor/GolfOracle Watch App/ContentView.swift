import SwiftUI
import WatchKit

struct ContentView: View {
    @StateObject private var motionManager = GolfMotionManager()
    @State private var lastSwingMph: Double = 0
    @State private var readiness: Double = 100
    @State private var isFatigued = false

    var body: some View {
        VStack(spacing: 8) {
            HStack {
                Circle()
                    .fill(motionManager.isRecording ? Color.green : Color.red)
                    .frame(width: 8, height: 8)
                Text(motionManager.isRecording ? "LIVE" : "READY (Rev 4)")
                    .font(.system(size: 12, weight: .bold))
                Spacer()
                Image(systemName: "heart.fill").foregroundColor(.red)
                Text("\(Int(motionManager.heartRate))")
                    .font(.system(.body, design: .monospaced))
            }
            .padding(.horizontal)

            Divider()

            VStack {
                Text("IMPACT SPEED")
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundColor(.secondary)
                Text(String(format: "%.1f", lastSwingMph))
                    .font(.system(size: 34, weight: .black, design: .rounded))
                Text("MPH")
                    .font(.system(size: 10, weight: .bold))
            }

            VStack(spacing: 2) {
                HStack {
                    Text("READINESS")
                    Spacer()
                    Text("\(Int(readiness))%")
                }
                .font(.system(size: 10, weight: .bold))

                ProgressView(value: readiness, total: 100)
                    .accentColor(isFatigued ? .yellow : .green)
            }
            .padding(.horizontal)
            .background(isFatigued ? Color.yellow.opacity(0.2) : Color.clear)
            .cornerRadius(8)

            Button(action: {
                if motionManager.isRecording {
                    motionManager.stopSession()
                } else {
                    motionManager.startSession()
                }
            }) {
                Text(motionManager.isRecording ? "STOP SESSION" : "START ORACLE")
                    .font(.system(size: 14, weight: .bold))
                    .frame(maxWidth: .infinity)
            }
            .tint(motionManager.isRecording ? .red : .blue)
            .buttonStyle(.borderedProminent)
        }
        .onReceive(NotificationCenter.default.publisher(for: NSNotification.Name("GolfSwingDetected"))) { notification in
            if let swing = notification.userInfo?["swing"] as? [String: Any],
               let metrics = swing["metrics"] as? [String: Any],
               let flags = swing["flags"] as? [String: Any] {
                self.lastSwingMph = metrics["impact_speed_mph"] as? Double ?? 0
                self.readiness = metrics["readiness_pct"] as? Double ?? 100
                self.isFatigued = flags["micro_fatigue"] as? Bool ?? false

                WKInterfaceDevice.current().play(isFatigued ? .directionUp : .success)
            }
        }
    }
}
