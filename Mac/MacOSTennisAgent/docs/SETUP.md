# MacOSTennisAgent Setup Guide

Complete step-by-step installation and configuration instructions.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Mac Backend Setup](#mac-backend-setup)
3. [iOS App Setup](#ios-app-setup)
4. [Watch App Setup](#watch-app-setup)
5. [Network Configuration](#network-configuration)
6. [Testing & Verification](#testing--verification)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Hardware Requirements

| Device | Requirement |
|--------|-------------|
| **Mac** | macOS 13.0+ (Ventura or later) |
| **iPhone** | iOS 16.0+, paired with Apple Watch |
| **Apple Watch** | Series 4+ with watchOS 9.0+ |
| **Network** | Mac and iPhone on same WiFi network |

### Software Requirements

**Mac:**
- Python 3.10 or later
- Xcode 15.0+ (for Swift development)
- Git

**Development Tools:**
```bash
# Verify Python version
python3 --version  # Should be 3.10+

# Verify pip
pip3 --version

# Verify Xcode
xcodebuild -version  # Should be 15.0+
```

---

## Mac Backend Setup

### Step 1: Clone Repository

```bash
# Clone from GitHub
git clone https://github.com/blue-az/MacOSTennisAgent.git
cd MacOSTennisAgent
```

### Step 2: Create Python Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Verify activation (should show venv in prompt)
which python  # Should show path inside venv/
```

### Step 3: Install Python Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install requirements
pip install -r backend/requirements.txt

# Verify installation
python -c "import fastapi, scipy, numpy; print('✅ All dependencies installed')"
```

**Key Dependencies:**
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `numpy`, `scipy` - Numerical processing & peak detection
- `aiosqlite` - Async database
- `pydantic` - Data validation

### Step 4: Initialize Database

```bash
# Run initialization script
python backend/scripts/init_database.py
```

**Expected Output:**
```
==================================================================
MacOSTennisAgent - Database Initialization
==================================================================

📦 Initializing database: /path/to/database/tennis_watch.db
✅ Database initialized successfully!

📊 Tables created:
   - sessions
   - shots
   - calculated_metrics
   - devices
   - raw_sensor_buffer

📈 Current data:
   sessions: 0 rows
   shots: 0 rows
   calculated_metrics: 0 rows
   devices: 0 rows

✨ Database ready at: /path/to/database/tennis_watch.db
```

### Step 5: Start Backend Server

```bash
# Navigate to backend directory
cd backend

# Start server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Server Endpoints:**
- WebSocket: `ws://YOUR_MAC_IP:8000/ws`
- API Docs: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/api/health`

**Verify Server:**
```bash
# In another terminal
curl http://localhost:8000/api/health

# Expected response:
# {"status":"healthy","timestamp":"2024-11-07T...","active_sessions":0}
```

### Step 6: Find Your Mac's IP Address

You'll need your Mac's local IP address for the iPhone app.

**Method 1: System Preferences**
1. Open System Preferences
2. Click Network
3. Select active connection (WiFi or Ethernet)
4. Note the IP Address (e.g., `192.168.1.100`)

**Method 2: Terminal**
```bash
# Get local IP
ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}'

# Alternative
ipconfig getifaddr en0  # WiFi
ipconfig getifaddr en1  # Ethernet
```

**Save this IP - you'll need it for iOS configuration!**

---

## iOS App Setup

### Step 1: Open Xcode Project

```bash
cd ios/TennisTrackerPhone
open TennisTrackerPhone.xcodeproj
```

### Step 2: Configure Backend URL

1. In Xcode, open `BackendClient.swift`
2. Find this line:
   ```swift
   private let backendURL = "ws://192.168.1.100:8000/ws"  // CHANGE THIS!
   ```
3. Replace `192.168.1.100` with your Mac's IP address from Step 6 above

**Example:**
```swift
private let backendURL = "ws://192.168.1.150:8000/ws"  // Your Mac's IP
```

### Step 3: Configure Signing & Capabilities

1. In Xcode, select the project in Navigator
2. Select target: **TennisTrackerPhone**
3. Go to **Signing & Capabilities** tab
4. Select your **Team**
5. Xcode will automatically provision the app

**Required Capabilities:**
- ✅ Background Modes → Background fetch
- ✅ WatchConnectivity framework (auto-added)

### Step 4: Build and Run

1. Connect your iPhone via USB or WiFi
2. Select your iPhone in the device dropdown
3. Press **Cmd + R** to build and run

**Verification:**
- App launches on iPhone
- Status shows "Connecting..." then "Connected"
- Backend logs show: `📱 Client connected`

---

## Watch App Setup

### Step 1: Open Xcode Project

```bash
cd watch/TennisTrackerWatch
open TennisTrackerWatch.xcodeproj
```

### Step 2: Configure Signing

1. In Xcode, select the project in Navigator
2. Select target: **TennisTrackerWatch**
3. Go to **Signing & Capabilities** tab
4. Select your **Team**

**Required Capabilities:**
- ✅ WatchConnectivity framework
- ✅ HealthKit (for motion access)
- ✅ Background Modes → Workout processing

### Step 3: Build and Run

**Important**: The Watch app must be deployed alongside the iPhone app.

1. In Xcode, select **TennisTrackerWatch** scheme
2. Select your **Apple Watch** as deployment target
3. Press **Cmd + R** to build and run

**Verification:**
- App appears on Apple Watch
- "Start Session" button visible
- Tapping button shows "Recording..."

---

## Network Configuration

### Firewall Settings

If the iPhone can't connect, check your Mac's firewall:

1. **System Preferences** → **Security & Privacy** → **Firewall**
2. Click **Firewall Options...**
3. Ensure Python/uvicorn is allowed, or:
   - Click **+** → Add `/usr/local/bin/python3`
   - Set to **Allow incoming connections**

### Port Forwarding (Optional)

For testing outside local network:

```bash
# Check if port 8000 is accessible
nc -zv YOUR_MAC_IP 8000

# If blocked, configure router port forwarding:
# External Port 8000 → Internal IP YOUR_MAC_IP:8000
```

### Same WiFi Network

**Critical**: Mac and iPhone MUST be on the same WiFi network.

**Verify:**
```bash
# On Mac
ipconfig getifaddr en0  # e.g., 192.168.1.100

# On iPhone (Settings → WiFi → tap network name)
# IP should be in same subnet, e.g., 192.168.1.xxx
```

---

## Testing & Verification

### End-to-End Test

1. **Start Backend** (Mac):
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

2. **Launch iPhone App**:
   - Should show "Connected"
   - Backend logs: `📱 Client connected`

3. **Start Watch Session**:
   - Open Watch app
   - Tap "Start Session"
   - Backend logs: `🎾 Session started: watch_20241107_143025`

4. **Swing Detection**:
   - Make swing motions with the Watch
   - Backend logs: `🎾 Swing detected: shot_20241107_143201_001 (rotation: 3.45 rad/s)`
   - iPhone should vibrate or show notification

5. **Stop Session**:
   - Tap "Stop" on Watch
   - Backend logs: `🏁 Session ended: watch_20241107_143025`

### Test with Historical Data

Process existing CSV data:

```bash
python backend/scripts/import_wristmotion.py \
    --input ~/Downloads/WristMotion.csv \
    --threshold 2.0
```

**Expected**: Detects swings from CSV and prints summary.

### Backend API Test

```bash
# Health check
curl http://localhost:8000/api/health

# Detector statistics
curl http://localhost:8000/api/detector/stats

# API documentation
open http://localhost:8000/docs
```

---

## Troubleshooting

### Backend Won't Start

**Error**: `ModuleNotFoundError: No module named 'fastapi'`

**Solution**:
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r backend/requirements.txt
```

**Error**: `Address already in use`

**Solution**:
```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9

# Or use different port
uvicorn app.main:app --port 8001
```

### iPhone Can't Connect

**Symptom**: Connection status stuck on "Connecting..."

**Solutions**:

1. **Verify Mac IP**:
   ```bash
   ipconfig getifaddr en0
   ```
   Update `BackendClient.swift` with correct IP.

2. **Check Backend Running**:
   ```bash
   curl http://YOUR_MAC_IP:8000/api/health
   ```

3. **Firewall**: Disable Mac firewall temporarily to test.

4. **Same Network**: Verify iPhone and Mac on same WiFi.

5. **Restart Backend**: Stop and restart uvicorn server.

### Watch App Not Sending Data

**Symptom**: No backend logs after starting Watch session.

**Solutions**:

1. **Check Watch-iPhone Pair**: Settings → General → Watch
2. **Restart WatchConnectivity**:
   - Close both apps
   - Restart iPhone
   - Restart Watch
3. **Verify MotionManager**: Check Watch app logs in Xcode

### No Swings Detected

**Symptom**: Backend receives data but no swings detected.

**Solutions**:

1. **Lower Threshold**:
   Edit `backend/app/services/swing_detector.py`:
   ```python
   detector = SwingDetector(
       threshold=1.5,  # Lower from 2.0
       min_distance=50
   )
   ```

2. **Check Sensor Data**:
   Add print statement in `main.py`:
   ```python
   print(f"Sample: rotation={sample.rotation_magnitude:.2f}")
   ```

3. **Test with CSV**: Verify algorithm works:
   ```bash
   python backend/scripts/import_wristmotion.py --input test.csv --threshold 1.5
   ```

### Database Errors

**Error**: `sqlite3.OperationalError: no such table: sessions`

**Solution**:
```bash
# Reinitialize database
rm database/tennis_watch.db
python backend/scripts/init_database.py
```

---

## Next Steps

Once everything is working:

1. **Tune Detection**: Adjust `threshold` and `min_distance` in `swing_detector.py`
2. **Add ML Classification**: Train model for forehand/backhand/serve detection
3. **Visualization**: Add Dash app to visualize swings (see TennisAgent `swing_visualizer.py`)
4. **Data Export**: Export sessions to CSV for analysis
5. **Cloud Sync**: Add cloud storage for multi-device access

---

## Support

- **Documentation**: `docs/ARCHITECTURE.md`, `docs/API.md`
- **Issues**: GitHub Issues
- **Examples**: `backend/scripts/` folder

**Happy Swing Tracking! 🎾**
