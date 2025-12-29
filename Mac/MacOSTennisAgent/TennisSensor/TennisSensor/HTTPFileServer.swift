//
//  HTTPFileServer.swift
//  TennisSensor
//
//  Created for v2.7 - HTTP server for database export
//  Allows direct download from Linux using wget/curl
//

import Foundation
import Network
import Darwin

/// Simple HTTP server to serve database file for download
class HTTPFileServer {
    static let shared = HTTPFileServer()

    private var listener: NWListener?
    private var fileURL: URL?
    private var connections: [NWConnection] = []

    private init() {}

    // MARK: - Server Control

    func start(fileURL: URL) -> String? {
        guard listener == nil else {
            print("⚠️  HTTP server already running")
            return getServerURL()
        }

        self.fileURL = fileURL

        do {
            // Start listener on port 8080
            listener = try NWListener(using: .tcp, on: 8080)

            listener?.stateUpdateHandler = { state in
                switch state {
                case .ready:
                    print("✅ HTTP server started on port 8080")
                case .failed(let error):
                    print("❌ HTTP server failed: \(error)")
                case .cancelled:
                    print("🛑 HTTP server stopped")
                default:
                    break
                }
            }

            listener?.newConnectionHandler = { [weak self] connection in
                self?.handleConnection(connection)
            }

            listener?.start(queue: .global(qos: .userInitiated))

            return getServerURL()

        } catch {
            print("❌ Failed to start HTTP server: \(error)")
            return nil
        }
    }

    func stop() {
        listener?.cancel()
        listener = nil

        // Close all active connections
        connections.forEach { $0.cancel() }
        connections.removeAll()

        fileURL = nil
        print("🛑 HTTP server stopped")
    }

    private func getServerURL() -> String {
        // Get device IP address
        if let ipAddress = getLocalIPAddress() {
            return "http://\(ipAddress):8080/tennis_watch.db"
        }
        return "http://[your-ip]:8080/tennis_watch.db"
    }

    // MARK: - Connection Handling

    private func handleConnection(_ connection: NWConnection) {
        connections.append(connection)

        connection.start(queue: .global(qos: .userInitiated))

        connection.receive(minimumIncompleteLength: 1, maximumLength: 65536) { [weak self] data, _, isComplete, error in
            guard let self = self else { return }

            if let data = data, !data.isEmpty {
                // Parse HTTP request (simple GET detection)
                if let request = String(data: data, encoding: .utf8), request.hasPrefix("GET") {
                    self.sendFileResponse(connection: connection)
                }
            }

            if isComplete {
                connection.cancel()
                self.connections.removeAll { $0 === connection }
            }
        }
    }

    private func sendFileResponse(connection: NWConnection) {
        guard let fileURL = fileURL else {
            sendErrorResponse(connection: connection)
            return
        }

        do {
            // Read file data
            let fileData = try Data(contentsOf: fileURL)
            let fileSize = fileData.count

            // Build HTTP response
            var response = "HTTP/1.1 200 OK\r\n"
            response += "Content-Type: application/x-sqlite3\r\n"
            response += "Content-Disposition: attachment; filename=\"tennis_watch.db\"\r\n"
            response += "Content-Length: \(fileSize)\r\n"
            response += "Connection: close\r\n"
            response += "\r\n"

            // Send headers
            if let headerData = response.data(using: .utf8) {
                connection.send(content: headerData, completion: .contentProcessed { error in
                    if error == nil {
                        // Send file data
                        connection.send(content: fileData, completion: .contentProcessed { error in
                            if let error = error {
                                print("❌ Error sending file: \(error)")
                            } else {
                                print("✅ File sent successfully (\(fileSize) bytes)")
                            }
                            connection.cancel()
                        })
                    }
                })
            }

        } catch {
            print("❌ Error reading file: \(error)")
            sendErrorResponse(connection: connection)
        }
    }

    private func sendErrorResponse(connection: NWConnection) {
        let response = """
        HTTP/1.1 500 Internal Server Error\r
        Content-Type: text/plain\r
        Connection: close\r
        \r
        Error: Could not read database file
        """

        if let data = response.data(using: .utf8) {
            connection.send(content: data, completion: .contentProcessed { _ in
                connection.cancel()
            })
        }
    }

    // MARK: - Network Utilities

    private func getLocalIPAddress() -> String? {
        var address: String?

        // Get list of all interfaces
        var ifaddr: UnsafeMutablePointer<ifaddrs>?
        guard getifaddrs(&ifaddr) == 0 else { return nil }
        guard let firstAddr = ifaddr else { return nil }

        // Iterate through linked list of interfaces
        for ifptr in sequence(first: firstAddr, next: { $0.pointee.ifa_next }) {
            let interface = ifptr.pointee

            // Check for IPv4 interface
            let addrFamily = interface.ifa_addr.pointee.sa_family
            if addrFamily == UInt8(AF_INET) {
                // Check interface name (en0 is WiFi on most devices)
                let name = String(cString: interface.ifa_name)
                if name == "en0" {
                    // Convert interface address to string
                    var hostname = [CChar](repeating: 0, count: Int(NI_MAXHOST))
                    getnameinfo(interface.ifa_addr,
                              socklen_t(interface.ifa_addr.pointee.sa_len),
                              &hostname,
                              socklen_t(hostname.count),
                              nil,
                              socklen_t(0),
                              NI_NUMERICHOST)
                    address = String(cString: hostname)
                }
            }
        }

        freeifaddrs(ifaddr)
        return address
    }
}
