from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from typing import Dict
import json
import time
from app.services.tennis_oracle import TennisOracle, TennisShotDetector

app = FastAPI()

oracle = TennisOracle()
detector = TennisShotDetector(oracle)

current_session: Dict = {"started_at": None, "shots": []}


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
