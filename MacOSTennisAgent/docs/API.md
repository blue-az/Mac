# MacOSTennisAgent API Reference

Complete reference for the FastAPI backend REST and WebSocket APIs.

## Base URL

```
http://localhost:8000
```

Replace `localhost` with your Mac's IP address when accessing from iPhone.

---

## Table of Contents

1. [WebSocket API](#websocket-api)
2. [REST API](#rest-api)
3. [Data Models](#data-models)
4. [Error Handling](#error-handling)

---

## WebSocket API

### Endpoint

```
ws://YOUR_MAC_IP:8000/ws
```

### Connection

Connect using standard WebSocket protocol:

```javascript
// JavaScript example
const ws = new WebSocket('ws://192.168.1.100:8000/ws');
```

```swift
// Swift example
let url = URL(string: "ws://192.168.1.100:8000/ws")!
let task = URLSession.shared.webSocketTask(with: url)
task.resume()
```

### Message Protocol

All messages are JSON objects with a `type` field.

---

### Client → Server Messages

#### 1. Session Start

Start a new recording session.

**Message**:
```json
{
  "type": "session_start",
  "session_id": "watch_20241107_143025",
  "device": "AppleWatch",
  "metadata": {
    "user_id": "optional_user_id",
    "location": "optional_location"
  }
}
```

**Fields**:
- `type` (string, required): Must be `"session_start"`
- `session_id` (string, required): Unique session identifier (format: `watch_YYYYMMDD_HHMMSS`)
- `device` (string, optional): Device name (default: `"AppleWatch"`)
- `metadata` (object, optional): Additional session metadata

**Response**:
```json
{
  "type": "session_started",
  "session_id": "watch_20241107_143025",
  "message": "Session watch_20241107_143025 started"
}
```

---

#### 2. Sensor Batch

Send a batch of sensor samples for processing.

**Message**:
```json
{
  "type": "sensor_batch",
  "session_id": "watch_20241107_143025",
  "device": "AppleWatch",
  "samples": [
    {
      "timestamp": 1699370625.123,
      "rotationRateX": 0.208,
      "rotationRateY": 0.033,
      "rotationRateZ": -0.130,
      "gravityX": 0.424,
      "gravityY": 0.722,
      "gravityZ": -0.546,
      "accelerationX": -0.025,
      "accelerationY": -0.023,
      "accelerationZ": -0.050,
      "quaternionW": 0.879,
      "quaternionX": -0.411,
      "quaternionY": 0.241,
      "quaternionZ": 0.000
    }
    // ... more samples (typically 100 per batch)
  ]
}
```

**Fields**:
- `type` (string, required): Must be `"sensor_batch"`
- `session_id` (string, required): Session identifier
- `device` (string, optional): Device name
- `samples` (array, required): Array of sensor samples (see [SensorSample](#sensorsample))

**Response**: None (unless swing detected)

**Note**: If a swing is detected, server will send `swing_detected` message.

---

#### 3. Session End

End the recording session.

**Message**:
```json
{
  "type": "session_end",
  "session_id": "watch_20241107_143025"
}
```

**Fields**:
- `type` (string, required): Must be `"session_end"`
- `session_id` (string, required): Session identifier

**Response**:
```json
{
  "type": "session_ended",
  "session_id": "watch_20241107_143025",
  "statistics": {
    "total_samples_processed": 45600,
    "total_peaks_detected": 23,
    "buffer_size": 300,
    "buffer_capacity": 300,
    "elapsed_time_seconds": 456.2,
    "sample_rate_hz": 99.9,
    "threshold": 2.0,
    "min_distance": 50
  }
}
```

---

### Server → Client Messages

#### 1. Swing Detected

Sent when a swing is detected in real-time.

**Message**:
```json
{
  "type": "swing_detected",
  "session_id": "watch_20241107_143025",
  "swing": {
    "shot_id": "shot_20241107_143201_001",
    "timestamp": 1699370721.453,
    "rotation_magnitude": 4.23,
    "acceleration_magnitude": 2.15,
    "estimated_speed_mph": 58.3,
    "sensor_data": {
      "timestamp": 1699370721.453,
      "rotation_rate": {
        "x": 0.512,
        "y": 4.182,
        "z": 0.324,
        "magnitude": 4.23
      },
      "gravity": {
        "x": 0.424,
        "y": 0.722,
        "z": -0.546
      },
      "acceleration": {
        "x": -0.825,
        "y": 1.923,
        "z": -0.450,
        "magnitude": 2.15
      },
      "quaternion": {
        "w": 0.879,
        "x": -0.411,
        "y": 0.241,
        "z": 0.000
      }
    }
  }
}
```

**Fields**:
- `type` (string): Always `"swing_detected"`
- `session_id` (string): Session identifier
- `swing` (object): Detected swing data
  - `shot_id` (string): Unique shot identifier
  - `timestamp` (number): Unix timestamp of peak
  - `rotation_magnitude` (number): Peak rotation magnitude (rad/s)
  - `acceleration_magnitude` (number): Peak acceleration magnitude (g)
  - `estimated_speed_mph` (number): Estimated racket speed (mph)
  - `sensor_data` (object): Full sensor data at peak

---

#### 2. Error

Sent when an error occurs.

**Message**:
```json
{
  "type": "error",
  "message": "Invalid JSON: Expecting value: line 1 column 1 (char 0)"
}
```

**Fields**:
- `type` (string): Always `"error"`
- `message` (string): Error description

---

## REST API

### Health Check

Check if the backend is running.

**Endpoint**: `GET /api/health`

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2024-11-07T14:30:25.123456",
  "active_sessions": 2
}
```

**cURL Example**:
```bash
curl http://localhost:8000/api/health
```

---

### Root Info

Get service information and endpoints.

**Endpoint**: `GET /`

**Response**:
```json
{
  "service": "MacOSTennisAgent Backend",
  "version": "1.0.0",
  "status": "running",
  "active_sessions": 1,
  "endpoints": {
    "websocket": "ws://localhost:8000/ws",
    "docs": "http://localhost:8000/docs",
    "sessions": "GET /api/sessions",
    "swings": "GET /api/swings",
    "detector_stats": "GET /api/detector/stats"
  }
}
```

---

### Detector Statistics

Get real-time statistics from active detectors.

**Endpoint**: `GET /api/detector/stats`

**Response**:
```json
{
  "active_sessions": 2,
  "sessions": {
    "watch_20241107_143025": {
      "total_samples_processed": 12000,
      "total_peaks_detected": 8,
      "buffer_size": 300,
      "buffer_capacity": 300,
      "elapsed_time_seconds": 120.5,
      "sample_rate_hz": 99.6,
      "threshold": 2.0,
      "min_distance": 50
    },
    "watch_20241107_150000": {
      "total_samples_processed": 5400,
      "total_peaks_detected": 3,
      "buffer_size": 300,
      "buffer_capacity": 300,
      "elapsed_time_seconds": 54.2,
      "sample_rate_hz": 99.7,
      "threshold": 2.0,
      "min_distance": 50
    }
  }
}
```

---

### List Sessions

List all sessions (placeholder - requires database implementation).

**Endpoint**: `GET /api/sessions`

**Response**:
```json
{
  "message": "Database queries not yet implemented",
  "active_sessions": ["watch_20241107_143025", "watch_20241107_150000"]
}
```

---

### Get Session

Get details for a specific session.

**Endpoint**: `GET /api/sessions/{session_id}`

**Path Parameters**:
- `session_id` (string): Session identifier

**Response (active session)**:
```json
{
  "session_id": "watch_20241107_143025",
  "status": "active",
  "statistics": {
    "total_samples_processed": 12000,
    "total_peaks_detected": 8,
    "buffer_size": 300,
    "buffer_capacity": 300,
    "elapsed_time_seconds": 120.5,
    "sample_rate_hz": 99.6,
    "threshold": 2.0,
    "min_distance": 50
  }
}
```

**Response (completed session)**:
```json
{
  "message": "Database queries not yet implemented",
  "session_id": "watch_20241107_143025"
}
```

---

### List Swings

List swings for a session (placeholder - requires database implementation).

**Endpoint**: `GET /api/swings`

**Query Parameters**:
- `session_id` (string, optional): Filter by session

**Response**:
```json
{
  "message": "Database queries not yet implemented",
  "session_id": "watch_20241107_143025"
}
```

---

## Data Models

### SensorSample

Single sensor reading from Apple Watch.

**Schema**:
```typescript
interface SensorSample {
  timestamp: number;         // Unix timestamp (seconds)
  rotationRateX: number;     // Gyroscope X (rad/s)
  rotationRateY: number;     // Gyroscope Y (rad/s)
  rotationRateZ: number;     // Gyroscope Z (rad/s)
  gravityX: number;          // Gravity vector X (normalized)
  gravityY: number;          // Gravity vector Y (normalized)
  gravityZ: number;          // Gravity vector Z (normalized)
  accelerationX: number;     // User acceleration X (g)
  accelerationY: number;     // User acceleration Y (g)
  accelerationZ: number;     // User acceleration Z (g)
  quaternionW: number;       // Quaternion W component
  quaternionX: number;       // Quaternion X component
  quaternionY: number;       // Quaternion Y component
  quaternionZ: number;       // Quaternion Z component
}
```

**Example**:
```json
{
  "timestamp": 1699370625.123,
  "rotationRateX": 0.208,
  "rotationRateY": 0.033,
  "rotationRateZ": -0.130,
  "gravityX": 0.424,
  "gravityY": 0.722,
  "gravityZ": -0.546,
  "accelerationX": -0.025,
  "accelerationY": -0.023,
  "accelerationZ": -0.050,
  "quaternionW": 0.879,
  "quaternionX": -0.411,
  "quaternionY": 0.241,
  "quaternionZ": 0.000
}
```

---

### DetectorStatistics

Statistics from the swing detector.

**Schema**:
```typescript
interface DetectorStatistics {
  total_samples_processed: number;  // Total samples received
  total_peaks_detected: number;     // Total swings detected
  buffer_size: number;              // Current buffer size
  buffer_capacity: number;          // Maximum buffer size
  elapsed_time_seconds: number;     // Session duration
  sample_rate_hz: number;           // Actual sample rate
  threshold: number;                // Detection threshold (rad/s)
  min_distance: number;             // Minimum samples between peaks
}
```

---

## Error Handling

### Error Responses

All errors are sent as WebSocket messages:

```json
{
  "type": "error",
  "message": "Error description"
}
```

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `"session_id is required"` | Missing session_id in message | Include session_id field |
| `"Invalid JSON: ..."` | Malformed JSON | Verify JSON syntax |
| `"Processing error: ..."` | Internal processing error | Check backend logs |
| `"Unknown message type: ..."` | Invalid message type | Use valid type (session_start, sensor_batch, session_end) |

---

## Interactive Documentation

FastAPI provides automatic interactive API documentation.

### Swagger UI

```
http://localhost:8000/docs
```

Features:
- Try out endpoints directly
- View request/response schemas
- See all available endpoints

### ReDoc

```
http://localhost:8000/redoc
```

Alternative documentation interface with cleaner layout.

---

## Example Usage

### Python Client

```python
import asyncio
import websockets
import json

async def test_session():
    async with websockets.connect('ws://192.168.1.100:8000/ws') as ws:
        # Start session
        await ws.send(json.dumps({
            "type": "session_start",
            "session_id": "test_session_001",
            "device": "TestClient"
        }))

        # Receive confirmation
        response = await ws.recv()
        print(json.loads(response))

        # Send sensor batch
        await ws.send(json.dumps({
            "type": "sensor_batch",
            "session_id": "test_session_001",
            "samples": [...]  # Sample data
        }))

        # End session
        await ws.send(json.dumps({
            "type": "session_end",
            "session_id": "test_session_001"
        }))

asyncio.run(test_session())
```

### cURL Examples

```bash
# Health check
curl http://localhost:8000/api/health

# Detector statistics
curl http://localhost:8000/api/detector/stats

# Get session (replace session_id)
curl http://localhost:8000/api/sessions/watch_20241107_143025
```

---

**Version**: 1.0.0
**Last Updated**: November 7, 2024
