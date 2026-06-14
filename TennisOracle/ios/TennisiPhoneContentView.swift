import SwiftUI

struct TennisiPhoneContentView: View {
    @StateObject private var backendClient = TennisBackendClient()
    
    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "figure.tennis.circle.fill")
                .font(.system(size: 80))
                .foregroundColor(.green)
                .shadow(radius: 5)
            
            Text("Tennis Oracle Gateway")
                .font(.title)
                .bold()

            Text("v1.1.0")
                .font(.caption)
                .foregroundColor(.secondary)
            
            StatusRow(
                label: "Mac Backend",
                status: backendClient.isConnected ? "Connected" : "Disconnected",
                color: backendClient.isConnected ? .green : .red
            )
            
            Button(action: {
                backendClient.connect()
            }) {
                Text(backendClient.isConnected ? "Reconnect Gateway" : "Connect to Mac")
                    .bold()
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Color.green)
                    .foregroundColor(.white)
                    .cornerRadius(10)
            }
            
            Text("Keep this app open while playing to relay 100Hz sensor data from your Watch to the Mac Oracle.")
                .font(.caption)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .padding()
        }
        .padding()
    }
}

struct StatusRow: View {
    let label: String
    let status: String
    let color: Color
    
    var body: some View {
        HStack {
            Text(label)
                .bold()
            Spacer()
            Circle()
                .fill(color)
                .frame(width: 10, height: 10)
            Text(status)
                .foregroundColor(color)
        }
        .padding()
        .background(Color.secondary.opacity(0.1))
        .cornerRadius(8)
    }
}
