# MacOSTennisAgent Architecture

System design, data flow, and technical specifications.

## Table of Contents

1. [System Overview](#system-overview)
2. [Data Flow](#data-flow)
3. [Component Details](#component-details)
4. [Algorithm Design](#algorithm-design)
5. [Database Schema](#database-schema)
6. [Network Protocol](#network-protocol)
7. [Performance Characteristics](#performance-characteristics)

---

## System Overview

MacOSTennisAgent is a distributed real-time sensor data processing system with three primary components:

```
┌───────────────────────────────────────────────────────────────────┐
│                   MACOSTENNISAGENT SYSTEM                         │
└───────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  APPLE WATCH (WatchOS)                                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  CMMotionManager                                         │   │
│  │  - Accelerometer (3-axis, g)                            │   │
│  │  - Gyroscope (3-axis, rad/s)                            │   │
│  │  - Quaternion orientation (w, x, y, z)                  │   │
│  │  - Sample Rate: 100 Hz (10ms intervals)                 │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           │                                      │
│                           │ WatchConnectivity (WCSession)        │
│                           │ Batch: 100 samples/second            │
│                           ↓                                      │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  IPHONE (iOS)                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  WatchConnectivity Receiver                             │   │
│  │  - Receive batches from Watch                           │   │
│  │  - Buffer management                                     │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           │                                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  WebSocket Client                                        │   │
│  │  - Connect to Mac backend                               │   │
│  │  - Forward sensor batches                               │   │
│  │  - Receive swing notifications                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           │                                      │
│                           │ WebSocket over WiFi                  │
│                           │ JSON messages                        │
│                           ↓                                      │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  MAC BACKEND (Python)                                           │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  FastAPI WebSocket Server                               │   │
│  │  - Async WebSocket handler                              │   │
│  │  - Session management                                    │   │
│  │  - Message routing                                       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           │                                      │
│                           ↓                                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  SwingDetector Service                                   │   │
│  │  - Sliding window buffer (300 samples)                  │   │
│  │  - scipy.signal.find_peaks()                            │   │
│  │  - Threshold: 2.0 rad/s                                 │   │
│  │  - Min distance: 50 samples (0.5s)                      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           │                                      │
│                           ↓                                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  SQLite Database                                         │   │
│  │  - sessions: Session metadata                           │   │
│  │  - shots: Detected swings                               │   │
│  │  - calculated_metrics: Aggregated stats                 │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Session Lifecycle

```
1. SESSION START
   ┌──────┐  "Start"   ┌──────┐  session_start   ┌──────┐
   │Watch │───────────→│iPhone│────────────────→│ Mac  │
   └──────┘           └──────┘   (WebSocket)    └──────┘
                                                    │
                                                    ↓
                                        Create SwingDetector
                                        Store session in DB

2. SENSOR STREAMING
   ┌──────┐  100 samples/s  ┌──────┐  sensor_batch   ┌──────┐
   │Watch │───────────────→│iPhone│───────────────→│ Mac  │
   └──────┘                 └──────┘                 └──────┘
      │                                                 │
      │ CMMotionManager                                │
      │ - DeviceMotion                                 │
      │ - 100 Hz sampling                              │
      │                                                 ↓
      └→ Batch 100 samples                    SwingDetector.process_batch()
         Send via WCSession                    ↓
                                              find_peaks() → Detect swings
                                                 │
                                                 ├→ Store in DB
                                                 └→ Send notification

3. SWING DETECTION
   ┌──────┐                  ┌──────┐  swing_detected  ┌──────┐
   │ Mac  │────────────────→│iPhone│───────────────→│Watch │
   └──────┘   (WebSocket)    └──────┘                 └──────┘
      │                         │                        │
      │ Detected swing          │ Forward notification   │
      └→ shot_id: shot_...      └→ Show feedback        └→ Haptic

4. SESSION END
   ┌──────┐  "Stop"    ┌──────┐  session_end    ┌──────┐
   │Watch │───────────→│iPhone│────────────────→│ Mac  │
   └──────┘            └──────┘                  └──────┘
                                                    │
                                                    ↓
                                        Calculate session stats
                                        Update DB
                                        Send summary
```

---

## Component Details

### 1. Apple Watch (Data Acquisition)

**Technology**: WatchOS + CoreMotion

**Key Classes**:
- `MotionManager`: Wraps CMMotionManager
- `SensorSample`: Data model

**Responsibilities**:
1. Configure CMMotionManager for 100Hz sampling
2. Capture IMU data: acceleration, rotation, quaternion
3. Buffer samples (100 samples = 1 second)
4. Transmit batches to iPhone via WCSession

**Sample Data Structure**:
```swift
struct SensorSample {
    timestamp: Double           // Unix timestamp
    rotationRate: (x, y, z)    // rad/s
    gravity: (x, y, z)         // normalized
    acceleration: (x, y, z)    // g (excluding gravity)
    quaternion: (w, x, y, z)   // orientation
}
```

### 2. iPhone (Bridge & Coordinator)

**Technology**: iOS + WatchConnectivity + Network

**Key Classes**:
- `BackendClient`: WebSocket client
- `WCSessionDelegate`: Watch communication

**Responsibilities**:
1. Receive sensor batches from Watch
2. Maintain WebSocket connection to Mac backend
3. Forward sensor data in real-time
4. Receive swing notifications from backend
5. Send haptic feedback to Watch

**Message Format**:
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
      ...
    }
  ]
}
```

### 3. Mac Backend (Processing & Storage)

**Technology**: Python + FastAPI + SQLite

**Key Components**:
- `FastAPI`: Web framework with WebSocket support
- `SwingDetector`: Real-time peak detection
- `SQLite`: Persistent storage

**Responsibilities**:
1. Accept WebSocket connections from iPhone
2. Process sensor batches through SwingDetector
3. Detect swings using peak detection algorithm
4. Store sessions and swings in database
5. Send real-time notifications

---

## Algorithm Design

### Swing Detection Algorithm

**Based on**: `domains/TennisAgent/cli/swing_analyzer.py` (Zepp sensor analysis)

**Adaptation**: Batch processing → Real-time streaming

#### Core Algorithm: `SwingDetector.process_batch()`

```python
class SwingDetector:
    def __init__(self):
        self.buffer = deque(maxlen=300)  # 3-second sliding window
        self.threshold = 2.0              # rad/s
        self.min_distance = 50            # 0.5s between peaks

    def process_batch(self, samples):
        # 1. Add samples to buffer
        self.buffer.extend(samples)

        # 2. Extract rotation magnitudes
        magnitudes = [sqrt(x² + y² + z²) for (x,y,z) in buffer]

        # 3. Detect peaks using scipy
        peaks = find_peaks(
            magnitudes,
            height=threshold,      # Minimum 2.0 rad/s
            distance=min_distance  # At least 0.5s apart
        )

        # 4. Create SwingPeak objects
        for peak_idx in peaks:
            swing = SwingPeak(
                timestamp=buffer[peak_idx].timestamp,
                rotation_magnitude=magnitudes[peak_idx],
                acceleration_magnitude=calc_accel_mag(buffer[peak_idx])
            )
            yield swing
```

#### scipy.find_peaks() Parameters

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `height` | 2.0 rad/s | Minimum rotation magnitude |
| `distance` | 50 samples | Minimum 0.5s between peaks |
| `prominence` | (not used) | Could filter false positives |
| `width` | (not used) | Could validate swing duration |

#### Threshold Tuning

```python
# Conservative (fewer false positives)
threshold = 3.0  # Only strong swings

# Balanced (default)
threshold = 2.0  # Most swings

# Sensitive (more detections, may have false positives)
threshold = 1.5  # Light swings
```

### Speed Estimation

Simplified model (can be replaced with ML):

```python
def estimate_swing_speed(peak):
    # Linear velocity = angular velocity × radius
    arm_length = 0.6   # meters
    racket_length = 0.7  # meters
    total_radius = 1.3   # meters

    linear_velocity_ms = peak.rotation_magnitude * total_radius

    # Convert m/s to mph
    speed_mph = linear_velocity_ms * 2.237

    return speed_mph
```

---

## Database Schema

### Tables

#### `sessions`
```sql
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,     -- watch_YYYYMMDD_HHMMSS
    device TEXT NOT NULL,
    date TEXT NOT NULL,              -- YYYY-MM-DD
    start_time INTEGER NOT NULL,     -- Unix timestamp
    end_time INTEGER,
    duration_minutes INTEGER,
    shot_count INTEGER DEFAULT 0,
    data_json TEXT NOT NULL,         -- Session metadata
    created_at INTEGER,
    updated_at INTEGER
);
```

#### `shots`
```sql
CREATE TABLE shots (
    shot_id TEXT PRIMARY KEY,        -- shot_YYYYMMDD_HHMMSS_NNN
    session_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    sequence_number INTEGER NOT NULL,
    rotation_magnitude REAL NOT NULL,
    acceleration_magnitude REAL NOT NULL,
    shot_type TEXT,                  -- forehand, backhand, serve
    spin_type TEXT,                  -- topspin, slice, flat
    speed_mph REAL,
    power REAL,
    consistency REAL,
    data_json TEXT NOT NULL,
    created_at INTEGER,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);
```

#### `calculated_metrics`
```sql
CREATE TABLE calculated_metrics (
    calc_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    metric_type TEXT NOT NULL,       -- avg_speed, max_rotation, etc.
    values_json TEXT NOT NULL,
    created_at INTEGER,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);
```

### Indexes

```sql
CREATE INDEX idx_sessions_date ON sessions(date DESC);
CREATE INDEX idx_shots_session ON shots(session_id, sequence_number);
CREATE INDEX idx_shots_timestamp ON shots(timestamp DESC);
```

---

## Network Protocol

### WebSocket Messages

#### Client → Server

**Session Start**:
```json
{
  "type": "session_start",
  "session_id": "watch_20241107_143025",
  "device": "AppleWatch"
}
```

**Sensor Batch**:
```json
{
  "type": "sensor_batch",
  "session_id": "watch_20241107_143025",
  "device": "AppleWatch",
  "samples": [...]  // 100 samples
}
```

**Session End**:
```json
{
  "type": "session_end",
  "session_id": "watch_20241107_143025"
}
```

#### Server → Client

**Swing Detected**:
```json
{
  "type": "swing_detected",
  "session_id": "watch_20241107_143025",
  "swing": {
    "shot_id": "shot_20241107_143201_001",
    "timestamp": 1699370721.453,
    "rotation_magnitude": 4.23,
    "acceleration_magnitude": 2.15,
    "estimated_speed_mph": 58.3
  }
}
```

**Session Started Ack**:
```json
{
  "type": "session_started",
  "session_id": "watch_20241107_143025",
  "message": "Session started"
}
```

**Error**:
```json
{
  "type": "error",
  "message": "Invalid JSON"
}
```

---

## Performance Characteristics

### Latency

| Stage | Typical Latency |
|-------|-----------------|
| Watch → iPhone | 10-50ms (WCSession) |
| iPhone → Mac | 20-100ms (WebSocket over WiFi) |
| Peak Detection | 1-5ms (Python processing) |
| **Total End-to-End** | **30-155ms** |

### Throughput

| Metric | Value |
|--------|-------|
| Sample Rate | 100 Hz (100 samples/second) |
| Batch Size | 100 samples (1 second) |
| Batch Rate | 1 batch/second |
| Data per Sample | ~112 bytes (JSON) |
| Bandwidth | ~11 KB/second |

### Resource Usage

**Apple Watch**:
- CPU: ~5-10% (CMMotionManager)
- Battery: ~2-3% per hour

**iPhone**:
- CPU: ~3-5% (forwarding)
- Battery: ~1-2% per hour

**Mac Backend**:
- CPU: ~5-10% (one session)
- Memory: ~50-100 MB
- Disk: ~100 KB per session

---

## Comparison with Zepp Sensor

| Feature | Zepp (Original) | Apple Watch (This System) |
|---------|-----------------|---------------------------|
| Data Source | origins table (SQLite) | CMMotionManager stream |
| Processing | Batch (371 frames) | Real-time (sliding window) |
| Detection | Retrospective phases | Online peak detection |
| Storage | All frames stored | Peaks only |
| Latency | Post-session | Real-time (~100ms) |
| Platform | Zepp U hardware | Apple Watch |

---

## Future Enhancements

1. **ML Classification**: Train model for forehand/backhand/serve detection
2. **3D Visualization**: Real-time swing path visualization (like TennisAgent `swing_visualizer.py`)
3. **Cloud Sync**: Store sessions in cloud database
4. **Multi-User**: Support multiple concurrent sessions
5. **Advanced Metrics**: Spin rate, ball speed estimation, technique analysis
6. **Video Integration**: Sync swing data with video recording

---

**Version**: 1.0.0
**Last Updated**: November 7, 2024
