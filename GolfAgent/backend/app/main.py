from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from typing import List, Dict
import json
import time
import sqlite3
import os
from app.services.golf_oracle import GolfOracle, GolfSwingDetector

app = FastAPI()

# Golf Oracle Infrastructure
oracle = GolfOracle()
detector = GolfSwingDetector(oracle)

# In-memory session store (latest session only)
current_session: Dict = {"session_id": None, "started_at": None, "stopped_at": None, "swings": []}

DB_PATH = os.path.join(os.path.dirname(__file__), "../../../golf_sessions.db")

def init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS sessions (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id  TEXT UNIQUE,
        date        TEXT,
        started_at  TEXT,
        stopped_at  TEXT,
        swing_count INTEGER DEFAULT 0,
        notes       TEXT
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS swings (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id       TEXT,
        ts               TEXT,
        swing_event_id   TEXT,
        impact_speed_mph REAL,
        hand_speed_mph   REAL,
        peak_rad         REAL,
        readiness_pct    REAL,
        hr_bpm           INTEGER,
        micro_fatigue    INTEGER DEFAULT 0,
        FOREIGN KEY(session_id) REFERENCES sessions(session_id)
    )""")
    con.commit(); con.close()

def persist_swing(swing: Dict, session_id: str):
    m = swing.get("metrics", {})
    con = sqlite3.connect(DB_PATH)
    con.execute("""INSERT INTO swings
        (session_id, ts, swing_event_id, impact_speed_mph, hand_speed_mph, peak_rad, readiness_pct, hr_bpm, micro_fatigue)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (session_id, swing["timestamp"], swing["swing_id"],
         m.get("impact_speed_mph"), m.get("hand_speed_mph"),
         swing.get("peak_rad"), m.get("readiness_pct"), m.get("hr_bpm"),
         1 if swing.get("flags", {}).get("micro_fatigue") else 0))
    con.execute("UPDATE sessions SET swing_count = swing_count + 1 WHERE session_id = ?", (session_id,))
    con.commit(); con.close()

def persist_session_start(session_id: str, started_at: str):
    local_date = time.strftime('%Y-%m-%d')
    con = sqlite3.connect(DB_PATH)
    con.execute("""INSERT OR IGNORE INTO sessions (session_id, date, started_at) VALUES (?,?,?)""",
                (session_id, local_date, started_at))
    con.commit(); con.close()

def persist_session_stop(session_id: str, stopped_at: str):
    con = sqlite3.connect(DB_PATH)
    con.execute("UPDATE sessions SET stopped_at = ? WHERE session_id = ?", (stopped_at, session_id))
    con.commit(); con.close()

init_db()


def _begin_session(session_id: str | None):
    global current_session
    detector.reset_session_state()
    started_at = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    current_session = {
        "session_id": session_id,
        "started_at": started_at,
        "stopped_at": None,
        "swings": []
    }
    if session_id:
        persist_session_start(session_id, started_at)

@app.websocket("/ws/golf")
async def websocket_endpoint(websocket: WebSocket):
    global current_session
    await websocket.accept()
    print("⛳️ Golf Watch connected")
    try:
        while True:
            # Handle both text and binary frames
            message_data = await websocket.receive()

            # Check for disconnect
            if message_data["type"] == "websocket.disconnect":
                print("⛳️ Golf Watch disconnected")
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

            if message.get("type") == "golf_session_start":
                session_id = message.get("session_id")
                _begin_session(session_id)  # persist_session_start called inside
                print(f"🏁 Golf session started ({session_id})")
                continue

            if message.get("type") == "golf_session_stop":
                session_id = message.get("session_id")
                if current_session["started_at"] is not None and (
                    session_id is None or current_session["session_id"] == session_id
                ):
                    current_session["stopped_at"] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                    persist_session_stop(session_id, current_session["stopped_at"])
                print(f"🛑 Golf session stopped ({session_id})")
                continue

            if message.get("type") == "golf_sensor_batch":
                session_id = message.get("session_id")
                if current_session["started_at"] is None or (
                    session_id is not None and current_session["session_id"] != session_id
                ):
                    _begin_session(session_id)
                samples = message.get("samples", [])
                print(f"📊 Received batch: {len(samples)} samples")
                swings = detector.process_samples(samples)

                for swing in swings:
                    current_session["swings"].append(swing)
                    if current_session["session_id"]:
                        persist_swing(swing, current_session["session_id"])
                    await websocket.send_text(json.dumps({
                        "type": "golf_swing_detected",
                        "swing": swing
                    }))
                    print(f"⛳️ Swing Detected: {swing['metrics']['impact_speed_mph']:.1f} mph, Readiness: {swing['metrics']['readiness_pct']}%")

    except WebSocketDisconnect:
        print("⛳️ Golf Watch disconnected")


@app.get("/sessions/latest")
async def get_latest_session():
    return JSONResponse(content=current_session)

@app.post("/phoenix-gps-status")
async def update_gps_status(metrics: Dict):
    """Spec 5.1 Endpoint"""
    print(f"📡 Received GPS Status: {metrics}")
    return {"status": "received"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
