"""
FastAPI application for MacOSTennisAgent backend service.
Provides WebSocket endpoint for real-time sensor data ingestion and REST API for queries.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import json
import asyncio
import sqlite3
import gzip
import uuid
from typing import Dict, List
from datetime import datetime
from pathlib import Path

from app.services.swing_detector import SwingDetector, SensorSample, estimate_swing_speed
from app.models.sensor_data import (
    SensorBatchMessage,
    SwingDetectedMessage,
    DetectorStatistics,
    SessionSummaryResponse,
    SwingResponse
)


# Global state
active_sessions: Dict[str, SwingDetector] = {}
database_path = Path(__file__).parent.parent.parent / "database" / "tennis_watch.db"


# ============================================================================
# Configuration
# ============================================================================

# Real-time swing detection (optional - disabled by default)
# When False: Backend only stores raw sensor data (SensorLogger mode)
# When True: Backend detects swings in real-time and saves to shots table
ENABLE_REALTIME_SWING_DETECTION = False

# Note: With real-time detection disabled, you can still analyze sessions
# offline using Python scripts that read from raw_sensor_buffer table


# ============================================================================
# Database Helper Functions
# ============================================================================

def get_db_connection():
    """
    Get a database connection with proper configuration.

    Returns:
        sqlite3.Connection: Configured database connection
    """
    conn = sqlite3.connect(str(database_path))
    conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
    conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign key constraints
    return conn


def insert_session(session_id: str, device: str, start_time: float):
    """
    Insert a new session into the database.

    Args:
        session_id: Session identifier (e.g., watch_20251108_024942)
        device: Device name (e.g., AppleWatch)
        start_time: Unix timestamp when session started
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Extract date from session_id or start_time
        date = datetime.fromtimestamp(start_time).strftime('%Y-%m-%d')

        # Prepare metadata
        data_json = json.dumps({
            "device": device,
            "start_time": start_time
        })

        cursor.execute("""
            INSERT INTO sessions (
                session_id, device, date, start_time, data_json
            ) VALUES (?, ?, ?, ?, ?)
        """, (session_id, device, date, int(start_time), data_json))

        conn.commit()
        conn.close()
        print(f"💾 Saved session to database: {session_id}")

    except Exception as e:
        print(f"❌ Error saving session to database: {e}")


def insert_shot(shot_id: str, session_id: str, timestamp: float,
                sequence_number: int, rotation_magnitude: float,
                acceleration_magnitude: float, speed_mph: float,
                sensor_data: dict):
    """
    Insert a detected shot/swing into the database.

    Args:
        shot_id: Shot identifier
        session_id: Parent session ID
        timestamp: Unix timestamp of shot
        sequence_number: Shot number within session
        rotation_magnitude: Peak rotation (rad/s)
        acceleration_magnitude: Peak acceleration (g)
        speed_mph: Estimated speed (mph)
        sensor_data: Full sensor readings at peak
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Prepare sensor data JSON
        data_json = json.dumps(sensor_data)

        cursor.execute("""
            INSERT INTO shots (
                shot_id, session_id, timestamp, sequence_number,
                rotation_magnitude, acceleration_magnitude,
                speed_mph, data_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            shot_id, session_id, timestamp, sequence_number,
            rotation_magnitude, acceleration_magnitude,
            speed_mph, data_json
        ))

        conn.commit()
        conn.close()
        print(f"💾 Saved shot to database: {shot_id}")

    except Exception as e:
        print(f"❌ Error saving shot to database: {e}")


def insert_raw_sensor_buffer(session_id: str, samples: List[dict]):
    """
    Insert raw sensor data into buffer table for debugging/reprocessing.
    Data is compressed with gzip to save space.

    v2.6: Added duplicate prevention to avoid storing same timestamp range multiple times.

    Args:
        session_id: Parent session ID
        samples: List of sensor sample dictionaries
    """
    if not samples:
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Extract timestamp range
        start_timestamp = min(s['timestamp'] for s in samples)
        end_timestamp = max(s['timestamp'] for s in samples)
        sample_count = len(samples)

        # v2.6: Check if buffer already exists for this time range
        # This prevents duplicate inserts when WatchConnectivity sends the same batch multiple times
        cursor.execute("""
            SELECT buffer_id FROM raw_sensor_buffer
            WHERE session_id = ?
            AND start_timestamp = ?
            AND end_timestamp = ?
        """, (session_id, start_timestamp, end_timestamp))

        existing_buffer = cursor.fetchone()
        if existing_buffer:
            print(f"⚠️  Buffer already exists for time range {start_timestamp}-{end_timestamp}, skipping duplicate")
            conn.close()
            return

        # Convert to CSV format and compress
        # Format: timestamp,rotX,rotY,rotZ,accX,accY,accZ,gravX,gravY,gravZ,quatW,quatX,quatY,quatZ
        csv_lines = []
        for s in samples:
            line = f"{s['timestamp']},{s['rotationRateX']},{s['rotationRateY']},{s['rotationRateZ']}," \
                   f"{s['accelerationX']},{s['accelerationY']},{s['accelerationZ']}," \
                   f"{s['gravityX']},{s['gravityY']},{s['gravityZ']}," \
                   f"{s['quaternionW']},{s['quaternionX']},{s['quaternionY']},{s['quaternionZ']}"
            csv_lines.append(line)

        csv_data = "\n".join(csv_lines).encode('utf-8')
        compressed_data = gzip.compress(csv_data)

        # Generate unique buffer ID
        buffer_id = f"buffer_{uuid.uuid4().hex[:12]}"

        cursor.execute("""
            INSERT INTO raw_sensor_buffer (
                buffer_id, session_id, start_timestamp, end_timestamp,
                sample_count, compressed_data
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            buffer_id, session_id, start_timestamp, end_timestamp,
            sample_count, compressed_data
        ))

        conn.commit()
        conn.close()
        print(f"💾 Saved {sample_count} raw samples to database (compressed: {len(compressed_data)} bytes)")

    except Exception as e:
        print(f"❌ Error saving raw sensor buffer to database: {e}")


def update_session_end(session_id: str, end_time: float, shot_count: int):
    """
    Update session with end time and statistics.

    Args:
        session_id: Session identifier
        end_time: Unix timestamp when session ended
        shot_count: Total shots detected in session
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get start time to calculate duration
        cursor.execute("SELECT start_time FROM sessions WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()

        if row:
            start_time = row['start_time']
            duration_minutes = int((end_time - start_time) / 60)

            cursor.execute("""
                UPDATE sessions
                SET end_time = ?,
                    duration_minutes = ?,
                    shot_count = ?,
                    updated_at = strftime('%s', 'now')
                WHERE session_id = ?
            """, (int(end_time), duration_minutes, shot_count, session_id))

            conn.commit()
            print(f"💾 Updated session end: {session_id} ({duration_minutes} min, {shot_count} shots)")
        else:
            print(f"⚠️  Session not found in database: {session_id}")

        conn.close()

    except Exception as e:
        print(f"❌ Error updating session end in database: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    print("="*70)
    print("MacOSTennisAgent Backend Service")
    print("="*70)
    print(f"Database: {database_path}")
    print(f"WebSocket endpoint: ws://localhost:8000/ws")
    print(f"API docs: http://localhost:8000/docs")
    print(f"Real-time swing detection: {'ENABLED' if ENABLE_REALTIME_SWING_DETECTION else 'DISABLED (SensorLogger mode)'}")
    print("="*70)

    # Ensure database directory exists
    database_path.parent.mkdir(parents=True, exist_ok=True)

    yield

    # Shutdown
    print("\nShutting down MacOSTennisAgent backend...")
    active_sessions.clear()


app = FastAPI(
    title="MacOSTennisAgent API",
    description="Real-time tennis swing detection service for Apple Watch",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# WebSocket Endpoint - Real-time Sensor Data Ingestion
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for receiving sensor data from iPhone.

    Protocol:
    - Client sends: SensorBatchMessage (JSON)
    - Server responds: SwingDetectedMessage when swing detected
    - Server responds: Error messages if processing fails
    """
    await websocket.accept()
    print(f"📱 Client connected: {websocket.client}")

    current_session_id = None
    detector = None

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                message_type = message.get("type", "")

                # Handle session start
                if message_type == "session_start":
                    session_id = message.get("session_id")
                    device = message.get("device", "AppleWatch")

                    if not session_id:
                        await websocket.send_json({
                            "type": "error",
                            "message": "session_id is required"
                        })
                        continue

                    # Create new detector for this session
                    detector = SwingDetector(
                        buffer_size=300,      # 3 seconds at 100Hz
                        threshold=2.0,        # rad/s
                        min_distance=50       # 0.5s between peaks
                    )
                    active_sessions[session_id] = detector
                    current_session_id = session_id

                    print(f"🎾 Session started: {session_id} ({device})")

                    # Save session to database
                    insert_session(session_id, device, datetime.now().timestamp())

                    await websocket.send_json({
                        "type": "session_started",
                        "session_id": session_id,
                        "message": f"Session {session_id} started"
                    })

                # Handle sensor batch
                elif message_type == "sensor_batch":
                    # Parse batch message
                    batch = SensorBatchMessage(**message)
                    session_id = batch.session_id

                    # Get or create detector for this session
                    if session_id not in active_sessions:
                        detector = SwingDetector()
                        active_sessions[session_id] = detector
                        current_session_id = session_id
                        print(f"🎾 Auto-started session: {session_id}")

                    detector = active_sessions[session_id]

                    # Convert Pydantic models to SensorSample objects
                    samples = []
                    for sample_data in batch.samples:
                        sample = SensorSample(
                            timestamp=sample_data.timestamp,
                            rotation_rate=(
                                sample_data.rotationRateX,
                                sample_data.rotationRateY,
                                sample_data.rotationRateZ
                            ),
                            gravity=(
                                sample_data.gravityX,
                                sample_data.gravityY,
                                sample_data.gravityZ
                            ),
                            acceleration=(
                                sample_data.accelerationX,
                                sample_data.accelerationY,
                                sample_data.accelerationZ
                            ),
                            quaternion=(
                                sample_data.quaternionW,
                                sample_data.quaternionX,
                                sample_data.quaternionY,
                                sample_data.quaternionZ
                            )
                        )
                        samples.append(sample)

                    # Save raw sensor data to database
                    # Convert samples list to dict format for storage
                    sample_dicts = [
                        {
                            "timestamp": s.timestamp,
                            "rotationRateX": s.rotation_x,
                            "rotationRateY": s.rotation_y,
                            "rotationRateZ": s.rotation_z,
                            "accelerationX": s.accel_x,
                            "accelerationY": s.accel_y,
                            "accelerationZ": s.accel_z,
                            "gravityX": s.gravity_x,
                            "gravityY": s.gravity_y,
                            "gravityZ": s.gravity_z,
                            "quaternionW": s.quat_w,
                            "quaternionX": s.quat_x,
                            "quaternionY": s.quat_y,
                            "quaternionZ": s.quat_z
                        }
                        for s in samples
                    ]
                    insert_raw_sensor_buffer(session_id, sample_dicts)

                    # Real-time swing detection (optional)
                    if ENABLE_REALTIME_SWING_DETECTION:
                        # Process batch and detect swings
                        detected_peaks = detector.process_batch(samples)

                        # Send swing detection messages
                        for peak in detected_peaks:
                            shot_id = f"shot_{datetime.fromtimestamp(peak.timestamp).strftime('%Y%m%d_%H%M%S')}_{detector.total_peaks_detected:03d}"

                            swing_data = {
                                "shot_id": shot_id,
                                "timestamp": peak.timestamp,
                                "rotation_magnitude": peak.rotation_magnitude,
                                "acceleration_magnitude": peak.acceleration_magnitude,
                                "estimated_speed_mph": estimate_swing_speed(peak),
                                "sensor_data": peak.sensor_data.to_dict()
                            }

                            # Save shot to database
                            insert_shot(
                                shot_id=shot_id,
                                session_id=session_id,
                                timestamp=peak.timestamp,
                                sequence_number=detector.total_peaks_detected,
                                rotation_magnitude=peak.rotation_magnitude,
                                acceleration_magnitude=peak.acceleration_magnitude,
                                speed_mph=swing_data["estimated_speed_mph"],
                                sensor_data=swing_data["sensor_data"]
                            )

                            response = SwingDetectedMessage(
                                session_id=session_id,
                                swing=swing_data
                            )

                            await websocket.send_json(response.dict())
                            print(f"🎾 Swing detected: {shot_id} (rotation: {peak.rotation_magnitude:.2f} rad/s)")
                    else:
                        # SensorLogger mode: Just store raw data, skip detection
                        print(f"📦 Stored batch: {len(samples)} samples (session: {session_id})")

                # Handle session end
                elif message_type == "session_end":
                    session_id = message.get("session_id")

                    if session_id in active_sessions:
                        detector = active_sessions[session_id]
                        stats = detector.get_statistics()

                        print(f"🏁 Session ended: {session_id}")

                        if ENABLE_REALTIME_SWING_DETECTION:
                            print(f"   Total swings: {stats['total_peaks_detected']}")
                            print(f"   Total samples: {stats['total_samples_processed']}")
                            shot_count = stats['total_peaks_detected']
                        else:
                            print(f"   Total samples: {stats['total_samples_processed']}")
                            print(f"   (Swing detection disabled - analyze offline)")
                            shot_count = 0  # No real-time detection, shots will be added offline

                        # Update session in database
                        update_session_end(
                            session_id=session_id,
                            end_time=datetime.now().timestamp(),
                            shot_count=shot_count
                        )

                        # Clean up
                        del active_sessions[session_id]

                        await websocket.send_json({
                            "type": "session_ended",
                            "session_id": session_id,
                            "statistics": stats
                        })

                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown message type: {message_type}"
                    })

            except json.JSONDecodeError as e:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Invalid JSON: {str(e)}"
                })
            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Processing error: {str(e)}"
                })
                print(f"❌ Error processing message: {e}")

    except WebSocketDisconnect:
        print(f"📱 Client disconnected: {websocket.client}")

        # Clean up session
        if current_session_id and current_session_id in active_sessions:
            detector = active_sessions[current_session_id]
            stats = detector.get_statistics()
            print(f"   Session {current_session_id}: {stats['total_peaks_detected']} swings detected")
            del active_sessions[current_session_id]

    except Exception as e:
        print(f"❌ WebSocket error: {e}")


# ============================================================================
# REST API Endpoints - Query Historical Data
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "MacOSTennisAgent Backend",
        "version": "1.0.0",
        "status": "running",
        "active_sessions": len(active_sessions),
        "endpoints": {
            "websocket": "ws://localhost:8000/ws",
            "docs": "http://localhost:8000/docs",
            "sessions": "GET /api/sessions",
            "swings": "GET /api/swings",
            "detector_stats": "GET /api/detector/stats"
        }
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "active_sessions": len(active_sessions)
    }


@app.get("/api/detector/stats")
async def get_detector_stats():
    """Get statistics from active detectors."""
    stats = {}
    for session_id, detector in active_sessions.items():
        stats[session_id] = detector.get_statistics()

    return {
        "active_sessions": len(active_sessions),
        "sessions": stats
    }


@app.get("/api/sessions")
async def list_sessions(limit: int = 50):
    """
    List all sessions from database.

    Args:
        limit: Maximum number of sessions to return (default 50)

    Returns:
        List of sessions with statistics
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                session_id,
                device,
                date,
                datetime(start_time, 'unixepoch') as start_datetime,
                datetime(end_time, 'unixepoch') as end_datetime,
                duration_minutes,
                shot_count
            FROM sessions
            ORDER BY start_time DESC
            LIMIT ?
        """, (limit,))

        sessions = []
        for row in cursor.fetchall():
            sessions.append({
                "session_id": row['session_id'],
                "device": row['device'],
                "date": row['date'],
                "start_time": row['start_datetime'],
                "end_time": row['end_datetime'],
                "duration_minutes": row['duration_minutes'],
                "shot_count": row['shot_count']
            })

        conn.close()

        return {
            "total": len(sessions),
            "sessions": sessions,
            "active_sessions": list(active_sessions.keys())
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """
    Get detailed session information including all shots.

    Args:
        session_id: Session identifier

    Returns:
        Session details with list of shots
    """
    # Check if session is currently active
    if session_id in active_sessions:
        detector = active_sessions[session_id]
        return {
            "session_id": session_id,
            "status": "active",
            "statistics": detector.get_statistics()
        }

    # Query database for completed session
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get session info
        cursor.execute("""
            SELECT
                session_id,
                device,
                date,
                datetime(start_time, 'unixepoch') as start_datetime,
                datetime(end_time, 'unixepoch') as end_datetime,
                duration_minutes,
                shot_count
            FROM sessions
            WHERE session_id = ?
        """, (session_id,))

        session_row = cursor.fetchone()

        if not session_row:
            conn.close()
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

        # Get all shots for this session
        cursor.execute("""
            SELECT
                shot_id,
                timestamp,
                sequence_number,
                rotation_magnitude,
                acceleration_magnitude,
                speed_mph
            FROM shots
            WHERE session_id = ?
            ORDER BY sequence_number
        """, (session_id,))

        shots = []
        for row in cursor.fetchall():
            shots.append({
                "shot_id": row['shot_id'],
                "timestamp": row['timestamp'],
                "sequence_number": row['sequence_number'],
                "rotation_magnitude": row['rotation_magnitude'],
                "acceleration_magnitude": row['acceleration_magnitude'],
                "speed_mph": row['speed_mph']
            })

        conn.close()

        return {
            "session_id": session_row['session_id'],
            "device": session_row['device'],
            "date": session_row['date'],
            "start_time": session_row['start_datetime'],
            "end_time": session_row['end_datetime'],
            "duration_minutes": session_row['duration_minutes'],
            "shot_count": session_row['shot_count'],
            "shots": shots,
            "status": "completed"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/api/swings")
async def list_swings(session_id: str = None, limit: int = 100):
    """
    List swings/shots from database.

    Args:
        session_id: Optional session filter
        limit: Maximum number of swings to return (default 100)

    Returns:
        List of shots with metrics
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if session_id:
            # Get shots for specific session
            cursor.execute("""
                SELECT
                    shot_id,
                    session_id,
                    timestamp,
                    sequence_number,
                    rotation_magnitude,
                    acceleration_magnitude,
                    speed_mph,
                    datetime(timestamp, 'unixepoch') as shot_datetime
                FROM shots
                WHERE session_id = ?
                ORDER BY sequence_number
                LIMIT ?
            """, (session_id, limit))
        else:
            # Get recent shots across all sessions
            cursor.execute("""
                SELECT
                    shot_id,
                    session_id,
                    timestamp,
                    sequence_number,
                    rotation_magnitude,
                    acceleration_magnitude,
                    speed_mph,
                    datetime(timestamp, 'unixepoch') as shot_datetime
                FROM shots
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))

        shots = []
        for row in cursor.fetchall():
            shots.append({
                "shot_id": row['shot_id'],
                "session_id": row['session_id'],
                "timestamp": row['timestamp'],
                "shot_datetime": row['shot_datetime'],
                "sequence_number": row['sequence_number'],
                "rotation_magnitude": row['rotation_magnitude'],
                "acceleration_magnitude": row['acceleration_magnitude'],
                "speed_mph": row['speed_mph']
            })

        conn.close()

        return {
            "total": len(shots),
            "session_id": session_id,
            "shots": shots
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ============================================================================
# Run Application
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    print("Starting MacOSTennisAgent Backend...")
    print("Press Ctrl+C to stop")

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
