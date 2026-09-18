from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from typing import Dict, List
import json
import time
import sqlite3
import os
import uuid
from app.services.tennis_oracle import TennisOracle, TennisShotDetector

DB_PATH = os.path.join(os.path.dirname(__file__), "../../../tennis_sessions.db")

app = FastAPI()

oracle = TennisOracle()
detector = TennisShotDetector(oracle)

current_session: Dict = {
    "session_id": None,
    "watch_session_uuid": None,
    "quarantined_batches": 0,
    "started_at": None,
    "ended_at": None,
    "batches": 0,
    "sample_count": 0,
    "shots": [],
}


def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            device TEXT,
            start_time INTEGER,
            end_time INTEGER,
            duration_minutes REAL,
            total_shots INTEGER DEFAULT 0,
            created_at INTEGER DEFAULT (strftime('%s', 'now'))
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS raw_sensor_buffer (
            buffer_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            start_timestamp REAL NOT NULL,
            end_timestamp REAL NOT NULL,
            sample_count INTEGER NOT NULL,
            compressed_data BLOB,
            created_at INTEGER DEFAULT (strftime('%s', 'now')),
            FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
        )
    """)
    for col, typedef in [("watch_session_uuid", "TEXT"), ("batch_seq", "INTEGER")]:
        try:
            cur.execute(f"ALTER TABLE raw_sensor_buffer ADD COLUMN {col} {typedef}")
        except sqlite3.OperationalError as exc:
            if "duplicate column name" not in str(exc).lower():
                raise
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_raw_sensor_watch_batch
        ON raw_sensor_buffer(watch_session_uuid, batch_seq)
        WHERE watch_session_uuid IS NOT NULL AND batch_seq IS NOT NULL
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transport_gaps (
            watch_session_uuid TEXT NOT NULL,
            missing_seq INTEGER NOT NULL,
            first_seen INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
            filled_at INTEGER,
            PRIMARY KEY (watch_session_uuid, missing_seq)
        )
    """)
    for col, typedef in [("transport_status", "TEXT"), ("missing_sequences", "TEXT")]:
        try:
            cur.execute(f"ALTER TABLE sessions ADD COLUMN {col} {typedef}")
        except sqlite3.OperationalError as exc:
            if "duplicate column name" not in str(exc).lower():
                raise
    cur.execute("""
        CREATE TABLE IF NOT EXISTS oracle_shots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            mode TEXT NOT NULL,
            oracle_mph REAL,
            peak_rad REAL,
            session_tag TEXT
        )
    """)
    for col, typedef in [
        ("quat_w", "REAL"), ("quat_x", "REAL"), ("quat_y", "REAL"), ("quat_z", "REAL"),
        ("rot_x",  "REAL"), ("rot_y",  "REAL"), ("rot_z",  "REAL"),
    ]:
        try:
            cur.execute(f"ALTER TABLE oracle_shots ADD COLUMN {col} {typedef}")
        except sqlite3.OperationalError as exc:
            if "duplicate column name" not in str(exc).lower():
                raise
    con.commit()
    con.close()


def missing_sequences(previous: int | None, current: int | None) -> list[int]:
    if previous is None or current is None or current <= previous + 1:
        return []
    return list(range(previous + 1, current))


def persist_session_start(session_id: str, start_epoch: int):
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        INSERT OR IGNORE INTO sessions (session_id, device, start_time)
        VALUES (?, ?, ?)
    """, (session_id, "AppleWatch", start_epoch))
    con.commit()
    con.close()


def persist_session_end(session_id: str, end_epoch: int, total_shots: int,
                        transport_status: str = "clean", missing_sequences: str = "[]"):
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        UPDATE sessions
        SET end_time = ?,
            duration_minutes = (? - start_time) / 60.0,
            total_shots = ?,
            transport_status = ?,
            missing_sequences = ?
        WHERE session_id = ?
    """, (end_epoch, end_epoch, total_shots, transport_status, missing_sequences, session_id))
    con.commit()
    con.close()


def samples_to_csv(samples: List[Dict]) -> bytes:
    columns = [
        "timestamp", "rotationRateX", "rotationRateY", "rotationRateZ",
        "gravityX", "gravityY", "gravityZ",
        "accelerationX", "accelerationY", "accelerationZ",
        "quaternionW", "quaternionX", "quaternionY", "quaternionZ",
        "heartRate", "mode",
    ]
    rows = [",".join(columns)]
    for sample in samples:
        rows.append(",".join(str(sample.get(col, "")) for col in columns))
    return ("\n".join(rows) + "\n").encode("utf-8")


def persist_batch(
    session_id: str,
    batch_index: int,
    samples: List[Dict],
    watch_session_uuid: str = "",
    batch_seq: int | None = None,
) -> bool:
    if not samples:
        return False
    timestamps = [
        float(sample["timestamp"])
        for sample in samples
        if "timestamp" in sample
    ]
    start_ts = min(timestamps) if timestamps else time.time()
    end_ts = max(timestamps) if timestamps else start_ts
    buffer_id = f"{session_id}_b{batch_index:06d}_{uuid.uuid4().hex[:8]}"
    con = sqlite3.connect(DB_PATH)
    if watch_session_uuid and batch_seq is not None:
        cur = con.execute("""
            INSERT OR IGNORE INTO raw_sensor_buffer
                (buffer_id, session_id, start_timestamp, end_timestamp, sample_count,
                 compressed_data, watch_session_uuid, batch_seq)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (buffer_id, session_id, start_ts, end_ts, len(samples),
              samples_to_csv(samples), watch_session_uuid, batch_seq))
    else:
        cur = con.execute("""
            INSERT INTO raw_sensor_buffer
                (buffer_id, session_id, start_timestamp, end_timestamp, sample_count, compressed_data)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (buffer_id, session_id, start_ts, end_ts, len(samples), samples_to_csv(samples)))
    inserted = cur.rowcount == 1
    con.commit()
    con.close()
    return inserted


def persist_shot(shot: Dict, session_id: str):
    ps = shot.get("peak_sample", {})
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        INSERT INTO oracle_shots
            (ts, mode, oracle_mph, peak_rad, session_tag,
             quat_w, quat_x, quat_y, quat_z, rot_x, rot_y, rot_z)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        shot["timestamp"],
        shot["mode"],
        shot["metrics"]["speed_mph"],
        shot.get("peak_rad"),
        session_id,
        ps.get("quat_w"), ps.get("quat_x"), ps.get("quat_y"), ps.get("quat_z"),
        ps.get("rot_x"),  ps.get("rot_y"),  ps.get("rot_z"),
    ))
    con.commit()
    con.close()


init_db()


@app.websocket("/ws/tennis")
async def websocket_endpoint(websocket: WebSocket):
    global current_session
    await websocket.accept()
    start_epoch = int(time.time())
    session_id = time.strftime("oracle_%Y%m%d_%H%M%S", time.localtime(start_epoch))
    persist_session_start(session_id, start_epoch)
    client = websocket.client
    print(f"🎾 Gateway connected: session={session_id} client={client}", flush=True)
    current_session = {
        "session_id": session_id,
        "watch_session_uuid": None,
        "quarantined_batches": 0,
        "started_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        "ended_at": None,
        "batches": 0,
        "sample_count": 0,
        "shots": []
    }
    # WatchConnectivity has been observed delivering the same sendMessage batch twice
    # (identical raw_sensor_buffer timestamps, 2026-09-02). The Watch now tags each
    # batch with a per-session batch_seq; skip anything already seen this connection.
    seen_batch_seqs = set()
    last_seq_by_watch = {}
    try:
        while True:
            message_data = await websocket.receive()

            if message_data["type"] == "websocket.disconnect":
                print("🎾 Tennis Watch disconnected")
                break

            if "text" in message_data:
                message = json.loads(message_data["text"])
            elif "bytes" in message_data:
                message = json.loads(message_data["bytes"])
            else:
                continue

            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if message.get("type") == "tennis_sensor_batch":
                watch_session_uuid = message.get("session_uuid", "")
                batch_seq = message.get("batch_seq")
                print(
                    f"📥 Batch received: backend_session={session_id} "
                    f"watch_session={watch_session_uuid} batch_seq={batch_seq}",
                    flush=True,
                )
                if watch_session_uuid and current_session["watch_session_uuid"] is None:
                    current_session["watch_session_uuid"] = watch_session_uuid
                if watch_session_uuid and current_session["watch_session_uuid"] != watch_session_uuid:
                    current_session["quarantined_batches"] += 1
                    print(f"🚧 Quarantined cross-session batch: watch_session={watch_session_uuid} expected={current_session['watch_session_uuid']} seq={batch_seq}", flush=True)
                    continue
                if watch_session_uuid and batch_seq is not None:
                    previous = last_seq_by_watch.get(watch_session_uuid)
                    for missing in missing_sequences(previous, batch_seq):
                        con_gap = sqlite3.connect(DB_PATH)
                        con_gap.execute("INSERT OR IGNORE INTO transport_gaps (watch_session_uuid, missing_seq) VALUES (?, ?)", (watch_session_uuid, missing))
                        con_gap.commit(); con_gap.close()
                    last_seq_by_watch[watch_session_uuid] = max(batch_seq, previous or batch_seq)
                    con_gap = sqlite3.connect(DB_PATH)
                    con_gap.execute("UPDATE transport_gaps SET filled_at=strftime('%s','now') WHERE watch_session_uuid=? AND missing_seq=? AND filled_at IS NULL", (watch_session_uuid, batch_seq))
                    con_gap.commit(); con_gap.close()
                if batch_seq is not None and batch_seq in seen_batch_seqs:
                    print(f"⚠️ Duplicate batch_seq={batch_seq} — skipped")
                    continue
                if batch_seq is not None:
                    seen_batch_seqs.add(batch_seq)

                samples = message.get("samples", [])
                mode = message.get("mode", "strokes")
                current_session["batches"] += 1
                inserted = persist_batch(
                    session_id, current_session["batches"], samples,
                    watch_session_uuid, batch_seq,
                )
                if inserted:
                    current_session["sample_count"] += len(samples)
                await websocket.send_json({
                    "type": "batch_ack",
                    "session_uuid": watch_session_uuid,
                    "batch_seq": batch_seq,
                    "status": "persisted" if inserted else "duplicate",
                })
                if not inserted:
                    print(f"↩️ Duplicate persisted batch: watch_session={watch_session_uuid} batch_seq={batch_seq}", flush=True)
                    continue
                print(
                    f"📊 Received batch: {len(samples)} samples "
                    f"(mode={mode}, total={current_session['sample_count']})",
                    flush=True,
                )
                shots = detector.process_samples(samples, mode)

                for shot in shots:
                    current_session["shots"].append(shot)
                    persist_shot(shot, session_id)
                    await websocket.send_text(json.dumps({
                        "type": "tennis_shot_detected",
                        "shot": shot
                    }))
                    print(f"🎾 Shot sent: {shot['metrics']['speed_mph']:.1f} mph, "
                          f"clean={shot['flags']['clean_contact']}", flush=True)

    except WebSocketDisconnect as exc:
        print(f"🎾 Gateway disconnected: session={session_id} code={exc.code} reason={exc.reason or ''}", flush=True)
    except Exception as exc:
        print(f"❌ Gateway error: session={session_id} type={type(exc).__name__} error={exc}", flush=True)
        raise
    finally:
        end_epoch = int(time.time())
        current_session["ended_at"] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(end_epoch))
        con_gap = sqlite3.connect(DB_PATH)
        missing = [r[0] for r in con_gap.execute("SELECT DISTINCT missing_seq FROM transport_gaps WHERE filled_at IS NULL AND watch_session_uuid IN (SELECT DISTINCT watch_session_uuid FROM raw_sensor_buffer WHERE session_id=?) ORDER BY missing_seq", (session_id,))]
        con_gap.close()
        status = "clean" if not missing else "loss_report_required"
        persist_session_end(session_id, end_epoch, len(current_session["shots"]), status, json.dumps(missing))
        print(f"🎾 Gateway session finalized: session={session_id} shots={len(current_session['shots'])} transport={status} missing={missing}", flush=True)


@app.get("/sessions/latest")
async def get_latest_session():
    return JSONResponse(content=current_session)


@app.get("/diagnostics/transport")
async def get_transport_diagnostics():
    con = sqlite3.connect(DB_PATH)
    rows = con.execute("SELECT watch_session_uuid, COUNT(DISTINCT missing_seq), SUM(filled_at IS NULL), MAX(missing_seq) FROM transport_gaps GROUP BY watch_session_uuid").fetchall()
    con.close()
    return JSONResponse(content={"sessions": [{"session_uuid": r[0], "gap_count": r[1], "pending_gaps": r[2], "last_missing_seq": r[3]} for r in rows]})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
