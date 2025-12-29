# MacOSTennisAgent - Complete Setup Instructions

## ✅ Phase 1 & 2: Backend Setup - COMPLETED

### What's Been Done:

1. **✅ Python Virtual Environment Created**
   - Location: `~/Projects/MacOSTennisAgent/venv`
   - Python 3.9 with all dependencies installed

2. **✅ Backend Dependencies Installed**
   - FastAPI, uvicorn, websockets
   - numpy, scipy, pandas
   - aiosqlite, pydantic
   - All testing and visualization tools

3. **✅ Database Initialized**
   - SQLite database at: `~/Projects/MacOSTennisAgent/database/tennis_watch.db`
   - Tables created: sessions, shots, calculated_metrics, devices, raw_sensor_buffer

4. **✅ Backend Server Tested**
   - Server can start successfully
   - WebSocket endpoint ready at port 8000

5. **✅ Mac IP Address Found**
   - **Your Mac IP: 192.168.8.155**
   - Backend URL: `ws://192.168.8.155:8000/ws`

6. **✅ Historical Data Processed**
   - WristMotion.csv copied to project
   - Swing detection algorithm tested successfully
   - **Results: 189 swings detected in 7.7 minutes**
   - Peak speeds: 113.6 mph (39.05 rad/s rotation)

7. **✅ iOS BackendClient.swift Updated**
   - Backend URL configured with correct Mac IP: `ws://192.168.8.155:8000/ws`

---

## 🚀 How to Start the Backend Server

```bash
cd ~/Projects/MacOSTennisAgent/backend
source ../venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Server will be available at:**
- WebSocket: `ws://192.168.8.155:8000/ws`
- API Docs: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/api/health`

---

## 📱 Phase 3: iOS/Watch App Setup - NEXT STEPS

### Current Status:

The MacOSTennisAgent repository contains **component Swift files** but **not complete Xcode projects**:

**Available Components:**
- ✅ `ios/BackendClient.swift` - WebSocket client (IP already configured)
- ✅ `watch/MotionManager.swift` - Apple Watch sensor data collector
- ✅ `shared/Models/SensorSample.swift` - Shared data model

**Missing:**
- ❌ Complete iOS Xcode project
- ❌ Complete Watch Xcode project
- ❌ UI/ContentView implementations

### Integration Options:

#### Option 1: Use Existing TennisSensor Project (Recommended)

You already have a TennisSensor Xcode project at:
`/Users/wikiwoo/Documents/WatchProject/TennisSensor/TennisSensor.xcodeproj`

**Steps to integrate:**

1. **Open the existing project:**
   ```bash
   open /Users/wikiwoo/Documents/WatchProject/TennisSensor/TennisSensor.xcodeproj
   ```

2. **Add BackendClient to iOS app:**
   - Drag `~/Projects/MacOSTennisAgent/ios/BackendClient.swift` into Xcode
   - Add to TennisSensor target
   - Import WatchConnectivity framework

3. **Add MotionManager to Watch app:**
   - Drag `~/Projects/MacOSTennisAgent/watch/MotionManager.swift` into Xcode
   - Add to WatchTennisSensor Watch App target
   - Import CoreMotion and WatchConnectivity

4. **Update ContentView files:**
   - iOS: Add BackendClient integration, connection status UI
   - Watch: Add MotionManager integration, Start/Stop recording buttons

5. **Configure capabilities:**
   - iOS: Background Modes → Background fetch
   - Watch: HealthKit, Background Modes → Workout processing

#### Option 2: Create New Xcode Projects

If you prefer to start fresh:

1. **Create iOS App:**
   - New iOS App project: "TennisTrackerPhone"
   - Add BackendClient.swift
   - Add WatchConnectivity framework
   - Create UI with connection status

2. **Create Watch App:**
   - New watchOS App: "TennisTrackerWatch"
   - Add MotionManager.swift
   - Add CoreMotion framework
   - Create UI with Start/Stop buttons

---

## 🎾 Testing the Complete System

Once iOS/Watch apps are built:

### 1. Start Backend
```bash
cd ~/Projects/MacOSTennisAgent/backend
source ../venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Launch iPhone App
- Should auto-connect to backend at `ws://192.168.8.155:8000/ws`
- Check backend logs for: `📱 Client connected`

### 3. Start Watch Session
- Open Watch app
- Tap "Start Session"
- Backend logs: `🎾 Session started`

### 4. Play Tennis
- Make swing motions
- Backend detects swings in real-time
- Logs: `🎾 Swing detected: [details]`

### 5. Stop Session
- Tap "Stop" on Watch
- Backend logs session statistics

---

## 📊 Test with Historical Data

Without physical devices, you can test the algorithm:

```bash
cd ~/Projects/MacOSTennisAgent
source venv/bin/activate
python backend/scripts/import_wristmotion.py --input WristMotion.csv --threshold 2.0
```

**Expected Output:**
- 189 swings detected
- Speed estimates from 5.8 to 114.1 mph
- Processing rate: ~224,000 samples/second

---

## 🔧 Troubleshooting

### Backend won't start
```bash
# Ensure virtual environment is activated
source ~/Projects/MacOSTennisAgent/venv/bin/activate

# Check if port 8000 is in use
lsof -i:8000

# Kill existing process if needed
lsof -ti:8000 | xargs kill -9
```

### iPhone can't connect
1. Verify Mac and iPhone on same WiFi network
2. Check Mac firewall settings (allow port 8000)
3. Verify IP address hasn't changed:
   ```bash
   ifconfig | grep "inet " | grep -v 127.0.0.1
   ```
4. Update BackendClient.swift if IP changed

### No swings detected
- Lower threshold in `backend/app/services/swing_detector.py`:
  ```python
  threshold=1.5  # Lower from 2.0
  ```

---

## 📁 Project Structure

```
~/Projects/MacOSTennisAgent/
├── backend/                     # ✅ Python backend (configured & tested)
│   ├── app/
│   │   ├── main.py             # FastAPI application
│   │   ├── services/
│   │   │   └── swing_detector.py
│   │   ├── models/
│   │   └── database/
│   │       └── schema.sql
│   ├── scripts/
│   │   ├── init_database.py    # ✅ Database initialized
│   │   └── import_wristmotion.py  # ✅ Tested with data
│   └── requirements.txt        # ✅ All deps installed
│
├── ios/                        # Swift component files
│   └── BackendClient.swift    # ✅ IP configured (192.168.8.155)
│
├── watch/                      # Swift component files
│   └── MotionManager.swift
│
├── shared/                     # Shared models
│   └── Models/
│       └── SensorSample.swift
│
├── database/
│   └── tennis_watch.db        # ✅ Database initialized
│
├── venv/                       # ✅ Python virtual environment
│
└── WristMotion.csv            # ✅ Test data (44,836 samples)
```

---

## 🎯 Summary

**Phase 1 & 2: ✅ COMPLETE**
- Backend fully configured and tested
- Database initialized
- Swing detection algorithm working (189 swings detected)
- Mac IP configured in iOS client

**Phase 3: 🔄 PENDING**
- Need to integrate Swift files into Xcode projects
- Option A: Use existing TennisSensor project at `/Users/wikiwoo/Documents/WatchProject/TennisSensor/`
- Option B: Create new Xcode projects from scratch

**Ready for Real-Time Testing:**
- Backend can detect swings at 224K samples/second
- WebSocket endpoint ready on Mac
- Component code ready for integration

---

## 📞 Next Steps

Choose your path:

1. **Integrate with existing TennisSensor project** (faster)
2. **Create new Xcode projects** (cleaner)

Let me know which option you prefer, and I can help guide you through the Xcode integration!
