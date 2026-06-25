import SwiftUI
import WatchKit

struct GolfContentView: View {
    @StateObject private var motionManager = GolfMotionManager()

    var body: some View {
        VStack(spacing: 8) {
            HStack {
                Circle()
                    .fill(motionManager.isRecording ? Color.green : Color.red)
                    .frame(width: 8, height: 8)
                Text(motionManager.isRecording ? "LIVE" : "READY (Rev 6)")
                    .font(.system(size: 12, weight: .bold))
                Spacer()
                Image(systemName: "heart.fill")
                    .foregroundColor(.red)
                Text("\(Int(motionManager.heartRate))")
                    .font(.system(.body, design: .monospaced))
            }
            .padding(.horizontal)

            Divider()

            VStack {
                Text("IMPACT SPEED")
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundColor(.secondary)
                Text(String(format: "%.1f", motionManager.lastSwingMph))
                    .font(.system(size: 34, weight: .black, design: .rounded))
                Text("MPH")
                    .font(.system(size: 10, weight: .bold))
            }

            VStack(spacing: 2) {
                HStack {
                    Text("READINESS")
                    Spacer()
                    Text("\(Int(motionManager.lastSwingReadiness))%")
                }
                .font(.system(size: 10, weight: .bold))

                ProgressView(value: motionManager.lastSwingReadiness, total: 100)
                    .accentColor(motionManager.lastSwingFatigued ? .yellow : .green)
            }
            .padding(.horizontal)
            .background(motionManager.lastSwingFatigued ? Color.yellow.opacity(0.2) : Color.clear)
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
        .onChange(of: motionManager.swingCount) {
            WKInterfaceDevice.current().play(motionManager.lastSwingFatigued ? .directionUp : .success)
        }
    }
}
