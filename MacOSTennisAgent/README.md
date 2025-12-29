# MacOSTennisAgent

Real-time tennis swing detection system using Apple Watch sensor data and Python backend.

## Overview

MacOSTennisAgent is a complete solution for capturing, analyzing, and storing tennis swing data in real-time. The system uses Apple Watch IMU sensors (accelerometer, gyroscope, quaternion) to detect swings during practice sessions and provides immediate feedback.

### Architecture

```
┌─────────────┐
│ Apple Watch │  CMMotionManager (100 Hz IMU sampling)
└──────┬──────┘
       │ WatchConnectivity (WCSession)
       ↓
┌─────────────┐
│   iPhone    │  Buffer & forward sensor data
└──────┬──────┘
       │ WebSocket over WiFi
       ↓
┌─────────────┐
│ Mac Backend │  FastAPI + Real-time peak detection
└──────┬──────┘
       │ Store sessions & swings
       ↓
┌─────────────┐
│ SQLite DB   │  tennis_watch.db
└─────────────┘
```

### Key Features

✅ **Real-Time Detection** - Identifies swings as they happen using scipy peak detection
✅ **High-Frequency Sampling** - 100Hz IMU data from Apple Watch
✅ **WebSocket Streaming** - Low-latency data transmission
✅ **Persistent Storage** - SQLite database for session history
✅ **Swing Analytics** - Rotation magnitude, acceleration, estimated speed
✅ **Cross-Platform** - Python backend works on any Mac with WiFi

## Quick Start

### Prerequisites

- **Mac**: macOS 13.0+ with Python 3.10+
- **iPhone**: iOS 16.0+ (paired with Watch)
- **Apple Watch**: Series 4+ with watchOS 9.0+
- **Network**: Mac and iPhone on same WiFi network

### Installation

#### 1. Clone Repository

```bash
git clone https://github.com/blue-az/MacOSTennisAgent.git
cd MacOSTennisAgent
```

#### 2. Setup Python Backend

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Initialize database
python backend/scripts/init_database.py
```

#### 3. Start Backend Server

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Server runs at:
- **WebSocket**: `ws://YOUR_MAC_IP:8000/ws`
- **API Docs**: `http://localhost:8000/docs`
- **Health Check**: `http://localhost:8000/api/health`

#### 4. Configure iPhone App

1. Open `ios/TennisTrackerPhone.xcodeproj` in Xcode
2. Edit `BackendClient.swift`:
   ```swift
   private let backendURL = "ws://YOUR_MAC_IP:8000/ws"  // Update this!
   ```
3. Build and run on your iPhone

#### 5. Configure Watch App

1. Open `watch/TennisTrackerWatch.xcodeproj` in Xcode
2. Build and run on your Apple Watch

### Usage

1. **Start Backend**: Launch the Python server on your Mac
2. **Connect iPhone**: Open the iPhone app, it will auto-connect to backend
3. **Start Watch Session**: Open Watch app, tap "Start Session"
4. **Play Tennis**: Swings are detected automatically in real-time
5. **View Results**: Check backend logs for swing detections

## Project Structure

```
MacOSTennisAgent/
├── backend/                    # Python FastAPI service
│   ├── app/
│   │   ├── main.py            # FastAPI application
│   │   ├── services/
│   │   │   └── swing_detector.py  # Real-time peak detection
│   │   ├── models/            # Pydantic models
│   │   └── database/          # SQLite schema
│   └── scripts/
│       ├── init_database.py   # Database initialization
│       └── import_wristmotion.py  # Import CSV data
│
├── watch/                      # WatchOS app (Swift)
│   └── MotionManager.swift    # CMMotionManager wrapper
│
├── ios/                        # iOS companion app (Swift)
│   └── BackendClient.swift    # WebSocket client
│
├── shared/                     # Shared Swift models
│   └── Models/
│       └── SensorSample.swift
│
├── database/                   # SQLite database location
│   └── tennis_watch.db
│
└── docs/                       # Documentation
    ├── SETUP.md               # Detailed setup guide
    ├── ARCHITECTURE.md        # System design
    └── API.md                 # Backend API reference
```

## Algorithm

The swing detector uses **real-time peak detection** on gyroscope rotation magnitude:

1. **Sliding Window Buffer**: 300 samples (3 seconds at 100Hz)
2. **Peak Detection**: `scipy.signal.find_peaks()`
   - Threshold: 2.0 rad/s
   - Min distance: 50 samples (0.5 seconds)
3. **Swing Classification**: Estimate speed, type (future: ML model)

### Adaptation from swing_analyzer.py

This system adapts the batch processing logic from `domains/TennisAgent/cli/swing_analyzer.py` (used for Zepp sensor data) to **real-time streaming**:

| Feature | Zepp (Batch) | Apple Watch (Real-Time) |
|---------|--------------|-------------------------|
| Data Source | origins table (SQLite) | CMMotionManager stream |
| Processing | Complete swing (371 frames) | Sliding window (300 samples) |
| Detection | Retrospective phases | Real-time peaks |
| Storage | All frames | Detected peaks only |

## Example: Import Historical Data

Process existing WristMotion.csv data:

```bash
python backend/scripts/import_wristmotion.py \
    --input ~/Downloads/WristMotion.csv \
    --threshold 2.0
```

Output:
```
📂 Loading CSV: WristMotion.csv
✅ Loaded 44,837 samples
   Duration: 463.0 seconds

🎾 Swing Detection Results:
   Total swings detected: 23

📊 Detected Swings:
     #    Timestamp  Rotation     Accel  Speed (mph)
   ---  -----------  ----------  ------  -----------
     1   1718329320        4.23    2.15         58.3
     2   1718329325        3.87    1.98         53.2
   ...
```

## Documentation

- **[SETUP.md](docs/SETUP.md)** - Detailed installation and configuration
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System design and data flow
- **[API.md](docs/API.md)** - Backend REST/WebSocket API reference
- **[ALGORITHMS.md](docs/ALGORITHMS.md)** - Peak detection algorithms (Coming soon)

## Development

### Backend Testing

```bash
# Run backend tests
cd backend
pytest tests/

# Test swing detector standalone
python -m app.services.swing_detector
```

### Swift Development

```bash
# Open projects in Xcode
open watch/TennisTrackerWatch.xcodeproj
open ios/TennisTrackerPhone.xcodeproj
```

## Troubleshooting

### iPhone Can't Connect to Backend

1. **Check Mac IP**: System Preferences → Network → IP Address
2. **Update BackendClient.swift**: Use correct IP in `backendURL`
3. **Check Firewall**: System Preferences → Security → Firewall → Allow port 8000
4. **Verify WiFi**: Mac and iPhone must be on same network

### No Swings Detected

1. **Lower Threshold**: Edit `swing_detector.py` → `threshold=1.5`
2. **Check Buffer**: Ensure Watch is sending data (check iPhone/backend logs)
3. **Test with CSV**: Use `import_wristmotion.py` to verify algorithm works

### Database Errors

```bash
# Reinitialize database
rm database/tennis_watch.db
python backend/scripts/init_database.py
```

## Contributing

This is a standalone reference implementation. Feel free to fork and adapt for your needs.

## License

MIT License - See LICENSE file

## Acknowledgments

- Adapted from TennisAgent swing_analyzer.py (warrior-tau-bench)
- Inspired by Zepp Tennis sensor analysis
- Uses Apple Watch CMMotionManager API
- Peak detection via scipy.signal.find_peaks()

## Contact

For questions or issues, please refer to the documentation in `docs/` or open an issue on GitHub.

---

**Status**: ✅ Production Ready
**Version**: 1.0.0
**Last Updated**: November 7, 2024
