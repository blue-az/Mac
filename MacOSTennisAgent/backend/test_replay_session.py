#!/usr/bin/env python3
"""
Replay Apple Watch session data through WebSocket for dashboard testing.
Reads session from tennis_watch.db and streams at realistic pace.
"""
import asyncio
import csv
import gzip
import io
import json
import sqlite3
import websockets
from pathlib import Path

# Configuration
DB_PATH = Path.home() / "Downloads/SensorDownload/Current/AppleWatch/direct_download/tennis_watch.db"
SERVER_URL = "ws://127.0.0.1:8000/ws"
PLAYBACK_SPEED = 1.0  # 1.0 = real-time, 2.0 = 2x speed

async def get_latest_session(db_path):
    """Get most recent session from database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get latest session
    cursor.execute("""
        SELECT session_id, device, start_time
        FROM sessions
        ORDER BY start_time DESC
        LIMIT 1
    """)
    session = cursor.fetchone()

    if not session:
        print("❌ No sessions found in database")
        return None, []

    session_id, device, start_time = session
    print(f"📊 Session: {session_id}")
    print(f"   Device: {device}")
    print(f"   Start: {start_time}")

    # Get all compressed buffers for this session
    cursor.execute("""
        SELECT compressed_data
        FROM raw_sensor_buffer
        WHERE session_id = ?
        ORDER BY start_timestamp ASC
    """, (session_id,))

    buffers = cursor.fetchall()
    conn.close()

    print(f"   Buffers: {len(buffers)}")

    # Decompress and parse all buffers
    all_samples = []
    for (compressed_data,) in buffers:
        # Try to decompress if gzipped, otherwise use as plain text
        try:
            csv_data = gzip.decompress(compressed_data).decode('utf-8')
        except (gzip.BadGzipFile, OSError):
            # Not compressed, use directly
            csv_data = compressed_data.decode('utf-8')

        # Parse CSV and convert to server API format
        reader = csv.DictReader(io.StringIO(csv_data))
        for row in reader:
            all_samples.append({
                'timestamp': float(row['timestamp']),
                'rotationRateX': float(row['rotX']),
                'rotationRateY': float(row['rotY']),
                'rotationRateZ': float(row['rotZ']),
                'accelerationX': float(row['accX']),
                'accelerationY': float(row['accY']),
                'accelerationZ': float(row['accZ']),
                'gravityX': float(row['gravX']),
                'gravityY': float(row['gravY']),
                'gravityZ': float(row['gravZ']),
                'quaternionW': float(row['quatW']),
                'quaternionX': float(row['quatX']),
                'quaternionY': float(row['quatY']),
                'quaternionZ': float(row['quatZ'])
            })

    print(f"   Total samples: {len(all_samples)}")

    return session_id, all_samples

async def replay_session():
    """Replay session data through WebSocket."""
    session_id, samples = await get_latest_session(DB_PATH)

    if not samples:
        print("❌ No samples to replay")
        return

    print(f"\n🔗 Connecting to {SERVER_URL}...")

    async with websockets.connect(SERVER_URL) as ws:
        print("✅ Connected to Mac server")

        # Send session_start
        start_msg = {
            "type": "session_start",
            "session_id": session_id,
            "device": "AppleWatch_Replay"
        }
        await ws.send(json.dumps(start_msg))
        print(f"📡 Sent session_start")

        # Replay samples in batches of 100 (like real Watch)
        batch_size = 100
        start_time = samples[0]['timestamp']

        for i in range(0, len(samples), batch_size):
            batch = samples[i:i + batch_size]

            # Send batch
            batch_msg = {
                "type": "sensor_batch",
                "session_id": session_id,
                "device": "AppleWatch_Replay",
                "samples": batch  # Already in correct format
            }
            await ws.send(json.dumps(batch_msg))

            # Calculate delay to next batch (based on timestamps)
            if i + batch_size < len(samples):
                current_t = batch[-1]['timestamp']
                next_t = samples[i + batch_size]['timestamp']
                delay = (next_t - current_t) / PLAYBACK_SPEED
                print(f"📡 Sent batch {i//batch_size + 1}/{(len(samples) + batch_size - 1)//batch_size} "
                      f"({len(batch)} samples) - delay {delay:.3f}s")
                await asyncio.sleep(delay)
            else:
                print(f"📡 Sent final batch ({len(batch)} samples)")

        # Send session_end
        end_msg = {
            "type": "session_end",
            "session_id": session_id
        }
        await ws.send(json.dumps(end_msg))
        print(f"✅ Session replay complete")

        await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(replay_session())
    except FileNotFoundError:
        print(f"❌ Database not found: {DB_PATH}")
        print(f"   Update DB_PATH in script if needed")
    except Exception as e:
        print(f"❌ Error: {e}")
