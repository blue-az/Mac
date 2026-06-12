import SwiftUI

struct GolfiPhoneContentView: View {
    @StateObject private var backendClient = GolfBackendClient()
    
    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "figure.golf")
                .font(.system(size: 60))
                .foregroundColor(.blue)
            
            Text("Golf Oracle Gateway (Rev 4)")
                .font(.title)
                .bold()
            
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
                    .background(Color.blue)
                    .foregroundColor(.white)
                    .cornerRadius(10)
            }
            
            Button(action: {
                backendClient.downloadSession { data in
                    if let data = data,
                       let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                       let swings = json["swings"] as? [[String: Any]] {
                        print("📥 Downloaded session: \(swings.count) swings")
                    }
                }
            }) {
                Text("Download Session")
                    .bold()
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Color.green)
                    .foregroundColor(.white)
                    .cornerRadius(10)
            }

            Text("Keep this app open on your iPhone while golfing to relay sensor data from your Watch to the Mac.")
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
