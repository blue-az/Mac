//
//  LocalDatabase.swift
//  TennisSensor
//
//  Created for v2.7 - Local iPhone storage
//  Stores tennis session data locally on iPhone using SQLite
//

import Foundation
import SQLite3
import Compression

/// Manages local SQLite database on iPhone for offline session storage
class LocalDatabase {
    // MARK: - Singleton
    static let shared = LocalDatabase()

    private var db: OpaquePointer?
    private let dbPath: String

    // MARK: - Initialization

    private init() {
        // Store database in Documents directory (backed up to iCloud)
        let documentsPath = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        dbPath = documentsPath.appendingPathComponent("tennis_watch.db").path

        print("📍 Local database path: \(dbPath)")

        // Open or create database
        if sqlite3_open(dbPath, &db) != SQLITE_OK {
            print("❌ Error opening database")
        } else {
            print("✅ Local database opened successfully")
            createTables()
        }
    }

    deinit {
        sqlite3_close(db)
    }

    // MARK: - Database Schema

    private func createTables() {
        // Create sessions table
        let createSessionsTable = """
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            device TEXT,
            start_time INTEGER,
            end_time INTEGER,
            duration_minutes REAL,
            total_shots INTEGER DEFAULT 0,
            created_at INTEGER DEFAULT (strftime('%s', 'now'))
        );
        """

        // Create raw_sensor_buffer table
        let createBufferTable = """
        CREATE TABLE IF NOT EXISTS raw_sensor_buffer (
            buffer_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            start_timestamp REAL NOT NULL,
            end_timestamp REAL NOT NULL,
            sample_count INTEGER NOT NULL,
            compressed_data BLOB,  -- v2.7.7: Stores uncompressed CSV data
            created_at INTEGER DEFAULT (strftime('%s', 'now')),
            FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
        );
        """

        executeSQL(createSessionsTable)
        executeSQL(createBufferTable)
    }

    private func executeSQL(_ sql: String) {
        var errMsg: UnsafeMutablePointer<Int8>?
        if sqlite3_exec(db, sql, nil, nil, &errMsg) != SQLITE_OK {
            let errorMessage = String(cString: errMsg!)
            print("❌ SQL Error: \(errorMessage)")
            sqlite3_free(errMsg)
        }
    }

    // MARK: - Session Management

    func insertSession(sessionId: String, device: String, startTime: Int) {
        let sql = """
        INSERT OR REPLACE INTO sessions (session_id, device, start_time)
        VALUES (?, ?, ?);
        """

        var stmt: OpaquePointer?
        if sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK {
            sqlite3_bind_text(stmt, 1, (sessionId as NSString).utf8String, -1, nil)
            sqlite3_bind_text(stmt, 2, (device as NSString).utf8String, -1, nil)
            sqlite3_bind_int(stmt, 3, Int32(startTime))

            if sqlite3_step(stmt) == SQLITE_DONE {
                print("✅ Session saved locally: \(sessionId)")
            } else {
                print("❌ Error inserting session")
            }
        }
        sqlite3_finalize(stmt)
    }

    func updateSessionEnd(sessionId: String, endTime: Int, duration: Double) {
        let sql = """
        UPDATE sessions
        SET end_time = ?, duration_minutes = ?
        WHERE session_id = ?;
        """

        var stmt: OpaquePointer?
        if sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK {
            sqlite3_bind_int(stmt, 1, Int32(endTime))
            sqlite3_bind_double(stmt, 2, duration)
            sqlite3_bind_text(stmt, 3, (sessionId as NSString).utf8String, -1, nil)

            if sqlite3_step(stmt) == SQLITE_DONE {
                print("✅ Session ended: \(sessionId)")
            }
        }
        sqlite3_finalize(stmt)
    }

    // MARK: - Sensor Data Storage

    func insertSensorBatch(sessionId: String, samples: [[String: Any]]) {
        guard !samples.isEmpty else { return }

        // Extract timestamps
        let timestamps = samples.compactMap { $0["timestamp"] as? Double }
        guard let startTimestamp = timestamps.min(),
              let endTimestamp = timestamps.max() else {
            print("❌ Invalid timestamps in sensor batch")
            return
        }

        // Compress data (gzip)
        let compressedData = compressSamples(samples)

        // Generate buffer ID
        let bufferId = "buffer_\(UUID().uuidString)"

        let sql = """
        INSERT INTO raw_sensor_buffer (buffer_id, session_id, start_timestamp, end_timestamp, sample_count, compressed_data)
        VALUES (?, ?, ?, ?, ?, ?);
        """

        var stmt: OpaquePointer?
        if sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK {
            sqlite3_bind_text(stmt, 1, (bufferId as NSString).utf8String, -1, nil)
            sqlite3_bind_text(stmt, 2, (sessionId as NSString).utf8String, -1, nil)
            sqlite3_bind_double(stmt, 3, startTimestamp)
            sqlite3_bind_double(stmt, 4, endTimestamp)
            sqlite3_bind_int(stmt, 5, Int32(samples.count))

            // Bind compressed data as BLOB
            _ = compressedData.withUnsafeBytes { bytes in
                sqlite3_bind_blob(stmt, 6, bytes.baseAddress, Int32(compressedData.count), nil)
            }

            if sqlite3_step(stmt) == SQLITE_DONE {
                print("💾 Saved \(samples.count) samples locally (compressed: \(compressedData.count) bytes)")
            } else {
                print("❌ Error inserting sensor batch")
            }
        }
        sqlite3_finalize(stmt)
    }

    // MARK: - Data Compression

    private func compressSamples(_ samples: [[String: Any]]) -> Data {
        // Convert samples to CSV format
        var csvLines: [String] = []
        csvLines.append("timestamp,rotX,rotY,rotZ,accX,accY,accZ,gravX,gravY,gravZ,quatW,quatX,quatY,quatZ")

        for sample in samples {
            // Watch sends: rotationRateX/Y/Z, accelerationX/Y/Z, gravityX/Y/Z, quaternionW/X/Y/Z
            guard let timestamp = sample["timestamp"] as? Double,
                  let rotX = sample["rotationRateX"] as? Double,
                  let rotY = sample["rotationRateY"] as? Double,
                  let rotZ = sample["rotationRateZ"] as? Double,
                  let accX = sample["accelerationX"] as? Double,
                  let accY = sample["accelerationY"] as? Double,
                  let accZ = sample["accelerationZ"] as? Double,
                  let gravX = sample["gravityX"] as? Double,
                  let gravY = sample["gravityY"] as? Double,
                  let gravZ = sample["gravityZ"] as? Double,
                  let quatW = sample["quaternionW"] as? Double,
                  let quatX = sample["quaternionX"] as? Double,
                  let quatY = sample["quaternionY"] as? Double,
                  let quatZ = sample["quaternionZ"] as? Double else {
                continue
            }

            let line = String(format: "%.3f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f",
                            timestamp, rotX, rotY, rotZ, accX, accY, accZ,
                            gravX, gravY, gravZ, quatW, quatX, quatY, quatZ)
            csvLines.append(line)
        }

        let csv = csvLines.joined(separator: "\n")
        let csvData = csv.data(using: .utf8) ?? Data()

        // v2.7.10: Temporarily disable compression (CRC32 too slow, blocking main thread)
        // TODO: Fix CRC32 performance with lookup table, then re-enable
        print("💾 Storing \(csvData.count) bytes uncompressed (compression disabled for performance)")
        return csvData

        // DISABLED: gzip compression (was causing WebSocket disconnections)
        // if let compressed = csvData.gzip() {
        //     let ratio = Double(compressed.count) / Double(csvData.count) * 100.0
        //     print("🗜️ Compressed \(csvData.count) bytes → \(compressed.count) bytes (\(String(format: "%.1f", ratio))%)")
        //     return compressed
        // } else {
        //     print("⚠️ Compression failed, storing uncompressed (\(csvData.count) bytes)")
        //     return csvData
        // }
    }

    // MARK: - Database Stats

    func getDatabaseStats() -> (sessions: Int, samples: Int, sizeBytes: Int) {
        var sessionCount = 0
        var sampleCount = 0

        // Count sessions
        var stmt: OpaquePointer?
        if sqlite3_prepare_v2(db, "SELECT COUNT(*) FROM sessions", -1, &stmt, nil) == SQLITE_OK {
            if sqlite3_step(stmt) == SQLITE_ROW {
                sessionCount = Int(sqlite3_column_int(stmt, 0))
            }
        }
        sqlite3_finalize(stmt)

        // Count total samples
        if sqlite3_prepare_v2(db, "SELECT SUM(sample_count) FROM raw_sensor_buffer", -1, &stmt, nil) == SQLITE_OK {
            if sqlite3_step(stmt) == SQLITE_ROW {
                sampleCount = Int(sqlite3_column_int(stmt, 0))
            }
        }
        sqlite3_finalize(stmt)

        // Get file size
        let fileSize = (try? FileManager.default.attributesOfItem(atPath: dbPath)[.size] as? Int) ?? 0

        return (sessionCount, sampleCount, fileSize)
    }

    // MARK: - Export

    func getDatabaseURL() -> URL {
        return URL(fileURLWithPath: dbPath)
    }

    // MARK: - Database Management

    func clearAllData() {
        // Delete all sensor data
        executeSQL("DELETE FROM raw_sensor_buffer;")

        // Delete all sessions
        executeSQL("DELETE FROM sessions;")

        // Vacuum database to reclaim space
        executeSQL("VACUUM;")

        print("🗑️ All database data cleared")
    }
}

// MARK: - Data Compression Extension

extension Data {
    func gzip() -> Data? {
        // Compress using zlib/deflate, then wrap with gzip headers
        guard !self.isEmpty else { return nil }

        return self.withUnsafeBytes { (sourcePtr: UnsafeRawBufferPointer) -> Data? in
            guard let baseAddress = sourcePtr.baseAddress else { return nil }

            // Allocate buffer for compressed data (source size + 1KB overhead)
            let destinationBufferSize = self.count + 1024
            var destinationBuffer = Data(count: destinationBufferSize)

            // Compress with zlib
            let compressedSize = destinationBuffer.withUnsafeMutableBytes { (destPtr: UnsafeMutableRawBufferPointer) -> Int in
                guard let destAddress = destPtr.baseAddress else { return 0 }

                return compression_encode_buffer(
                    destAddress,
                    destinationBufferSize,
                    baseAddress,
                    self.count,
                    nil,
                    COMPRESSION_ZLIB
                )
            }

            guard compressedSize > 0 else {
                print("❌ compression_encode_buffer returned 0")
                return nil
            }

            // Get just the compressed data (no excess buffer)
            let compressedData = destinationBuffer.prefix(compressedSize)

            // Now wrap with gzip headers
            var gzipData = Data()

            // gzip header (10 bytes)
            gzipData.append(contentsOf: [
                0x1f, 0x8b,        // Magic number
                0x08,              // Compression method (deflate)
                0x00,              // Flags
                0x00, 0x00, 0x00, 0x00,  // Timestamp (0 = no timestamp)
                0x00,              // Extra flags
                0xff               // OS (unknown)
            ])

            // Compressed data
            gzipData.append(compressedData)

            // gzip footer (8 bytes)
            let crc = self.crc32()
            let size = UInt32(self.count)

            Swift.withUnsafeBytes(of: crc.littleEndian) { gzipData.append(contentsOf: $0) }
            Swift.withUnsafeBytes(of: size.littleEndian) { gzipData.append(contentsOf: $0) }

            return gzipData
        }
    }

    // CRC32 calculation for gzip footer
    private func crc32() -> UInt32 {
        var crc: UInt32 = 0xffffffff

        for byte in self {
            crc ^= UInt32(byte)
            for _ in 0..<8 {
                crc = (crc >> 1) ^ ((crc & 1) * 0xedb88320)
            }
        }

        return ~crc
    }
}
