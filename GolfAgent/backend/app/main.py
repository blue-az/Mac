from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List, Dict
import json
from app.services.golf_oracle import GolfOracle, GolfSwingDetector

app = FastAPI()

# Golf Oracle Infrastructure
oracle = GolfOracle()
detector = GolfSwingDetector(oracle)

@app.websocket("/ws/golf")
async def websocket_endpoint(websocket: WebSocket):
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
            
            if message.get("type") == "golf_sensor_batch":
                samples = message.get("samples", [])
                print(f"📊 Received batch: {len(samples)} samples")
                swings = detector.process_samples(samples)
                
                for swing in swings:
                    # Send detection back to watch/iPhone
                    await websocket.send_text(json.dumps({
                        "type": "golf_swing_detected",
                        "swing": swing
                    }))
                    print(f"⛳️ Swing Detected: {swing['metrics']['impact_speed_mph']:.1f} mph, Readiness: {swing['metrics']['readiness_pct']}%")

    except WebSocketDisconnect:
        print("⛳️ Golf Watch disconnected")

@app.post("/phoenix-gps-status")
async def update_gps_status(metrics: Dict):
    """Spec 5.1 Endpoint"""
    print(f"📡 Received GPS Status: {metrics}")
    return {"status": "received"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
