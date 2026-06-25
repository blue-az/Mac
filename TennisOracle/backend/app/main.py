from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from typing import Dict
import json
import time
import sqlite3
import os
from app.services.tennis_oracle import TennisOracle, TennisShotDetector

DB_PATH = os.path.join(os.path.dirname(__file__), "../../../tennis_sessions.db")

app = FastAPI()

oracle = TennisOracle()
detector = TennisShotDetector(oracle)

current_session: Dict = {"started_at": None, "shots": []}


def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    for col, typedef in [
        ("quat_w", "REAL"), ("quat_x", "REAL"), ("quat_y", "REAL"), ("quat_z", "REAL"),
        ("rot_x",  "REAL"), ("rot_y",  "REAL"), ("rot_z",  "REAL"),
    ]:
        try:
            cur.execute(f"ALTER TABLE oracle_shots ADD COLUMN {col} {typedef}")
        except sqlite3.OperationalError:
            pass  # column already exists
    con.commit()
    con.close()


def persist_shot(shot: Dict, session_tag: str):
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
        session_tag,
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
    print("🎾 Tennis Watch connected")
    current_session = {
        "started_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        "shots": []
    }
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
                samples = message.get("samples", [])
                mode = message.get("mode", "strokes")
                print(f"📊 Received batch: {len(samples)} samples (mode={mode})")
                shots = detector.process_samples(samples, mode)

                for shot in shots:
                    current_session["shots"].append(shot)
                    persist_shot(shot, current_session["started_at"][:10])
                    await websocket.send_text(json.dumps({
                        "type": "tennis_shot_detected",
                        "shot": shot
                    }))
                    print(f"🎾 Shot sent: {shot['metrics']['speed_mph']:.1f} mph, "
                          f"clean={shot['flags']['clean_contact']}")

    except WebSocketDisconnect:
        print("🎾 Tennis Watch disconnected")


@app.get("/sessions/latest")
async def get_latest_session():
    return JSONResponse(content=current_session)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
