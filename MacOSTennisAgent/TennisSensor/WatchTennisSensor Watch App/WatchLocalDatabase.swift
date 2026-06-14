import Foundation
import SQLite3
import Compression

/// Persists sensor sessions on the Watch so they can be retransferred if the iPhone app was closed.
class WatchLocalDatabase {
    static let shared = WatchLocalDatabase()

    private var db: OpaquePointer?
    private let dbQueue = DispatchQueue(label: "com.ef.TennisSensor.watchkitapp.db")

    private init() {
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let path = docs.appendingPathComponent("watch_local.db").path
        dbQueue.sync {
            let rc = sqlite3_open_v2(path, &self.db,
                                     SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE | SQLITE_OPEN_FULLMUTEX,
                                     nil)
            guard rc == SQLITE_OK else { return }
            sqlite3_busy_timeout(self.db, 2000)
            self.createTables()
        }
    }

    deinit { dbQueue.sync { sqlite3_close(db) } }

    // MARK: - Schema

    private func createTables() {
        sqlite3_exec(db, "PRAGMA foreign_keys = ON;", nil, nil, nil)
        sqlite3_exec(db, """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id   TEXT PRIMARY KEY,
                start_time   REAL NOT NULL,
                end_time     REAL,
                sample_count INTEGER DEFAULT 0,
                is_transferred INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS batches (
                batch_id     TEXT PRIMARY KEY,
                session_id   TEXT NOT NULL,
                batch_index  INTEGER NOT NULL,
                sample_count INTEGER NOT NULL,
                samples_data BLOB NOT NULL,
                is_final     INTEGER DEFAULT 0,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
            );
        """, nil, nil, nil)
    }

    // MARK: - Write

    func createSession(sessionId: String, startTime: Date) {
        dbQueue.async { [weak self] in
            guard let self else { return }
            var stmt: OpaquePointer?
            let sql = "INSERT OR IGNORE INTO sessions (session_id, start_time) VALUES (?, ?);"
            if sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK {
                sqlite3_bind_text(stmt, 1, (sessionId as NSString).utf8String, -1, nil)
                sqlite3_bind_double(stmt, 2, startTime.timeIntervalSince1970)
                sqlite3_step(stmt)
            }
            sqlite3_finalize(stmt)
        }
    }

    func saveBatch(sessionId: String, batchIndex: Int, samples: [[String: Any]], isFinal: Bool,
                   completion: (() -> Void)? = nil) {
        guard let jsonData = try? JSONSerialization.data(withJSONObject: samples),
              let compressed = compress(jsonData) else {
            DispatchQueue.main.async { completion?() }
            return
        }

        dbQueue.async { [weak self] in
            guard let self else { return }

            var stmt: OpaquePointer?
            let insertSQL = """
                INSERT OR REPLACE INTO batches
                    (batch_id, session_id, batch_index, sample_count, samples_data, is_final)
                VALUES (?, ?, ?, ?, ?, ?);
            """
            if sqlite3_prepare_v2(db, insertSQL, -1, &stmt, nil) == SQLITE_OK {
                let batchId = "\(sessionId)_b\(batchIndex)"
                sqlite3_bind_text(stmt, 1, (batchId as NSString).utf8String, -1, nil)
                sqlite3_bind_text(stmt, 2, (sessionId as NSString).utf8String, -1, nil)
                sqlite3_bind_int(stmt, 3, Int32(batchIndex))
                sqlite3_bind_int(stmt, 4, Int32(samples.count))
                compressed.withUnsafeBytes { ptr in
                    _ = sqlite3_bind_blob(stmt, 5, ptr.baseAddress, Int32(compressed.count), nil)
                }
                sqlite3_bind_int(stmt, 6, isFinal ? 1 : 0)
                sqlite3_step(stmt)
            }
            sqlite3_finalize(stmt)

            var updateStmt: OpaquePointer?
            let updateSQL = "UPDATE sessions SET sample_count = sample_count + ?, end_time = ? WHERE session_id = ?;"
            if sqlite3_prepare_v2(db, updateSQL, -1, &updateStmt, nil) == SQLITE_OK {
                sqlite3_bind_int(updateStmt, 1, Int32(samples.count))
                sqlite3_bind_double(updateStmt, 2, Date().timeIntervalSince1970)
                sqlite3_bind_text(updateStmt, 3, (sessionId as NSString).utf8String, -1, nil)
                sqlite3_step(updateStmt)
            }
            sqlite3_finalize(updateStmt)

            DispatchQueue.main.async { completion?() }
        }
    }

    func markSessionTransferred(_ sessionId: String) {
        dbQueue.async { [weak self] in
            guard let self else { return }
            var stmt: OpaquePointer?
            let sql = "UPDATE sessions SET is_transferred = 1 WHERE session_id = ?;"
            if sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK {
                sqlite3_bind_text(stmt, 1, (sessionId as NSString).utf8String, -1, nil)
                sqlite3_step(stmt)
            }
            sqlite3_finalize(stmt)
        }
    }

    // MARK: - Read

    func getUnsentSessionCount() -> Int {
        var count = 0
        dbQueue.sync { [weak self] in
            guard let self else { return }
            var stmt: OpaquePointer?
            if sqlite3_prepare_v2(db, "SELECT COUNT(*) FROM sessions WHERE is_transferred = 0;",
                                  -1, &stmt, nil) == SQLITE_OK,
               sqlite3_step(stmt) == SQLITE_ROW {
                count = Int(sqlite3_column_int(stmt, 0))
            }
            sqlite3_finalize(stmt)
        }
        return count
    }

    func getUnsentSessions() -> [(sessionId: String, startTime: Double, sampleCount: Int)] {
        var result: [(String, Double, Int)] = []
        dbQueue.sync { [weak self] in
            guard let self else { return }
            var stmt: OpaquePointer?
            let sql = "SELECT session_id, start_time, sample_count FROM sessions WHERE is_transferred = 0 ORDER BY start_time ASC;"
            if sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK {
                while sqlite3_step(stmt) == SQLITE_ROW {
                    let sid = String(cString: sqlite3_column_text(stmt, 0))
                    let ts = sqlite3_column_double(stmt, 1)
                    let sc = Int(sqlite3_column_int(stmt, 2))
                    result.append((sid, ts, sc))
                }
            }
            sqlite3_finalize(stmt)
        }
        return result
    }

    func getBatchesForSession(_ sessionId: String) -> [(batchIndex: Int, samples: [[String: Any]], isFinal: Bool)] {
        var result: [(Int, [[String: Any]], Bool)] = []
        dbQueue.sync { [weak self] in
            guard let self else { return }
            var stmt: OpaquePointer?
            let sql = "SELECT batch_index, samples_data, is_final FROM batches WHERE session_id = ? ORDER BY batch_index ASC;"
            if sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK {
                sqlite3_bind_text(stmt, 1, (sessionId as NSString).utf8String, -1, nil)
                while sqlite3_step(stmt) == SQLITE_ROW {
                    let idx = Int(sqlite3_column_int(stmt, 0))
                    let final = sqlite3_column_int(stmt, 2) == 1
                    let sz = Int(sqlite3_column_bytes(stmt, 1))
                    if let ptr = sqlite3_column_blob(stmt, 1), sz > 0 {
                        let compressed = Data(bytes: ptr, count: sz)
                        if let raw = decompress(compressed),
                           let samples = try? JSONSerialization.jsonObject(with: raw) as? [[String: Any]] {
                            result.append((idx, samples, final))
                        }
                    }
                }
            }
            sqlite3_finalize(stmt)
        }
        return result
    }

    // MARK: - Compression (raw ZLIB, no gzip wrapper needed for internal storage)

    private func compress(_ data: Data) -> Data? {
        let bufferSize = data.count + 1024
        var output = Data(count: bufferSize)
        let n = data.withUnsafeBytes { inPtr in
            output.withUnsafeMutableBytes { outPtr in
                compression_encode_buffer(
                    outPtr.bindMemory(to: UInt8.self).baseAddress!,
                    bufferSize,
                    inPtr.bindMemory(to: UInt8.self).baseAddress!,
                    data.count,
                    nil,
                    COMPRESSION_ZLIB
                )
            }
        }
        guard n > 0 else { return nil }
        return output.prefix(n)
    }

    private func decompress(_ data: Data) -> Data? {
        // Estimate: compressed sensor JSON typically expands ~10-15x
        let bufferSize = max(data.count * 20, 65536)
        var output = Data(count: bufferSize)
        let n = data.withUnsafeBytes { inPtr in
            output.withUnsafeMutableBytes { outPtr in
                compression_decode_buffer(
                    outPtr.bindMemory(to: UInt8.self).baseAddress!,
                    bufferSize,
                    inPtr.bindMemory(to: UInt8.self).baseAddress!,
                    data.count,
                    nil,
                    COMPRESSION_ZLIB
                )
            }
        }
        guard n > 0 else { return nil }
        return output.prefix(n)
    }
}
