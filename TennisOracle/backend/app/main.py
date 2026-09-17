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


def persist_session_start(session_id: str, start_epoch: int):
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        INSERT OR IGNORE INTO sessions (session_id, device, start_time)
        VALUES (?, ?, ?)
    """, (session_id, "AppleWatch", start_epoch))
    con.commit()
    con.close()


def persist_session_end(session_id: str, end_epoch: int, total_shots: int):
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        UPDATE sessions
        SET end_time = ?,
            duration_minutes = (? - start_time) / 60.0,
            total_shots = ?
        WHERE session_id = ?
    """, (end_epoch, end_epoch, total_shots, session_id))
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


def persist_batch(session_id: str, batch_index: int, samples: List[Dict]):
    if not samples:
        return
    timestamps = [
        float(sample["timestamp"])
        for sample in samples
        if "timestamp" in sample
    ]
    start_ts = min(timestamps) if timestamps else time.time()
    end_ts = max(timestamps) if timestamps else start_ts
    buffer_id = f"{session_id}_b{batch_index:06d}_{uuid.uuid4().hex[:8]}"
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        INSERT INTO raw_sensor_buffer
            (buffer_id, session_id, start_timestamp, end_timestamp, sample_count, compressed_data)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        buffer_id,
        session_id,
        start_ts,
        end_ts,
        len(samples),
        samples_to_csv(samples),
    ))
    con.commit()
    con.close()


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
                if batch_seq is not None and batch_seq in seen_batch_seqs:
                    print(f"⚠️ Duplicate batch_seq={batch_seq} — skipped")
                    continue
                if batch_seq is not None:
                    seen_batch_seqs.add(batch_seq)

                samples = message.get("samples", [])
                mode = message.get("mode", "strokes")
                current_session["batches"] += 1
                current_session["sample_count"] += len(samples)
                persist_batch(session_id, current_session["batches"], samples)
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
        persist_session_end(session_id, end_epoch, len(current_session["shots"]))
        print(f"🎾 Gateway session finalized: session={session_id} shots={len(current_session['shots'])}", flush=True)


@app.get("/sessions/latest")
async def get_latest_session():
    return JSONResponse(content=current_session)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
