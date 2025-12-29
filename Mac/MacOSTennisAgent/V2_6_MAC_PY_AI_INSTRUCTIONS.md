# TennisSensor v2.6.0 - Mac Py AI Instructions

**Date:** November 8, 2025
**Prepared by:** Py AI (Linux)
**For:** Mac Py AI

## Overview

v2.6.0 fixes two critical data quality bugs discovered during dual-device calibration testing:

1. **Screen Sleep Data Gaps**: Watch becomes unavailable when screen goes dark, causing 2.6 second gaps during critical serve motions
2. **Database Duplication**: 87% duplicate samples in database (15,623 total → 1,960 unique)

All code changes have been committed to the main branch (commit `fc2da97`).

---

## Git Repository Status

**Branch:** `main`
**Latest Commit:** `fc2da97` - "v2.6.0 - Fix screen sleep data gaps and database duplication"

**Files Changed:**
- ✅ NEW: `TennisSensor/WatchTennisSensor Watch App/WorkoutManager.swift`
- ✅ MODIFIED: `TennisSensor/WatchTennisSensor Watch App/ContentView.swift`
- ✅ MODIFIED: `TennisSensor/WatchTennisSensor Watch App/MotionManager.swift`
- ✅ MODIFIED: `TennisSensor/WatchTennisSensor Watch App/WatchTennisSensor Watch App.entitlements`
- ✅ MODIFIED: `backend/app/main.py`
- ✅ MODIFIED: `TennisSensor/CLAUDE.md`

---

## CRITICAL: Xcode Configuration Required

**⚠️ IMPORTANT:** The code is complete, but Xcode project configuration is required before building.

### Step 1: Pull Latest Code

```bash
cd ~/Projects/MacOSTennisAgent
git pull origin main
```

Verify you see commit `fc2da97` and the new `WorkoutManager.swift` file.

### Step 2: Open Xcode Project

```bash
open TennisSensor/TennisSensor.xcodeproj
```

### Step 3: Configure Watch App Target

1. **Select Target:** In Xcode, select "WatchTennisSensor Watch App" target
2. **Go to:** Signing & Capabilities tab

#### 3a. Add HealthKit Capability

- Click "+ Capability" button
- Search for "HealthKit"
- Click to add HealthKit capability
- ✅ Should see "HealthKit" section appear in Signing & Capabilities

#### 3b. Add Background Modes Capability

- Click "+ Capability" button
- Search for "Background Modes"
- Click to add Background Modes capability
- ✅ Check the box for "Workout Processing"

#### 3c. Add Privacy Strings

**Option 1: Via Xcode Info Tab**
1. Select "WatchTennisSensor Watch App" target
2. Go to "Info" tab
3. Hover over any row and click the "+" button
4. Add these two keys:

```
Key: Privacy - Health Share Usage Description
Type: String
Value: Tennis Sensor needs to record workout sessions to collect continuous motion data during tennis practice.

Key: Privacy - Health Update Usage Description
Type: String
Value: Tennis Sensor saves your tennis session data to HealthKit.
```

**Option 2: Manually Edit Info.plist (if it exists)**

If `TennisSensor/WatchTennisSensor Watch App/Info.plist` exists, add:

```xml
<key>NSHealthShareUsageDescription</key>
<string>Tennis Sensor needs to record workout sessions to collect continuous motion data during tennis practice.</string>

<key>NSHealthUpdateUsageDescription</key>
<string>Tennis Sensor saves your tennis session data to HealthKit.</string>

<key>UIBackgroundModes</key>
<array>
    <string>workout-processing</string>
</array>
```

### Step 4: Build & Install

#### Clean Build (Recommended)

```
Product → Clean Build Folder (Cmd+Shift+K)
Product → Build (Cmd+B)
```

#### Check for Errors

Expected: **Build should succeed with 0 errors**

If you see errors related to:
- "HealthKit framework not found" → Verify HealthKit capability was added
- "Missing privacy string" → Verify privacy descriptions were added
- "Background modes not configured" → Verify Background Modes capability added

#### Install to Devices

1. Select iPhone device from device dropdown
2. `Product → Run` (Cmd+R)
3. App should install on both iPhone and Watch

---

## Testing Checklist

After installation, verify the following:

### First Launch Test

- [ ] **HealthKit Authorization Prompt:** First time you tap "Start" on Watch, you should see:
  - "Tennis Sensor Would Like to Access Health"
  - Options: "Don't Allow" / "Allow"
  - Tap "Allow"

### UI Verification

- [ ] **Watch App Version:** Shows "TT v2.6.0" at top
- [ ] **Version Text:** Bottom shows "v2.6.0 - Workout Session"
- [ ] **Workout Status Indicator:** When recording, shows small orange/green dot with "Workout Active" or "No Workout" text

### Screen Sleep Test (CRITICAL)

1. Start recording on Watch
2. Let screen go dark naturally (about 15 seconds of no interaction)
3. Move wrist to wake screen
4. **Expected:** Sample count continues increasing smoothly (no gaps)
5. **Expected:** No jump in sample count (if jump = data gap occurred)

### Data Quality Test

1. Record a 20-30 second session
2. Stop recording
3. Wait 10-20 seconds for data transfer
4. Check database:

```bash
cd ~/Projects/MacOSTennisAgent

# Get latest session
sqlite3 database/tennis_watch.db "
SELECT
    session_id,
    (SELECT COUNT(*) FROM raw_sensor_buffer
     WHERE raw_sensor_buffer.session_id = sessions.session_id) as buffer_count,
    (SELECT SUM(sample_count) FROM raw_sensor_buffer
     WHERE raw_sensor_buffer.session_id = sessions.session_id) as total_samples
FROM sessions
ORDER BY start_time DESC
LIMIT 1;"
```

**Expected Results:**
- `buffer_count` should be ~20-30 (for 20-30 second session)
- `total_samples` should be ~2000-3000 (100Hz × 20-30s)
- **NO DUPLICATES** (run query below to verify)

### Duplication Check

```bash
sqlite3 database/tennis_watch.db "
SELECT
    session_id,
    start_timestamp,
    end_timestamp,
    COUNT(*) as duplicate_count
FROM raw_sensor_buffer
GROUP BY session_id, start_timestamp, end_timestamp
HAVING COUNT(*) > 1;"
```

**Expected:** No rows returned (no duplicates)

### HealthKit Verification

1. Open Apple Watch app on iPhone
2. Go to Health app
3. Navigate to: Browse → Activity → Workouts
4. **Expected:** See "Tennis" workout entry with date/time of your session

---

## Bug Fixes Explained

### Bug #1: Screen Sleep Data Gaps

**Before v2.6:**
- Watch screen goes dark → watchOS suspends app → CMMotionManager stops → 2.6s data gap
- Example: Session `watch_20251108_173309` had gaps right during serve motion

**After v2.6:**
- WorkoutManager starts HKWorkoutSession BEFORE motion recording
- HKWorkoutSession tells watchOS "this is a workout, keep running"
- Screen still goes dark (saves battery) BUT app continues running
- CMMotionManager keeps collecting 100Hz data continuously

### Bug #2: Database Duplication

**Before v2.6:**
- `insert_raw_sensor_buffer()` generated random buffer_id and inserted without checking
- WatchConnectivity sometimes sends same batch multiple times
- Result: Same timestamp range inserted 8-10 times

**After v2.6:**
- Before INSERT, check if buffer with same `(session_id, start_timestamp, end_timestamp)` exists
- If exists → skip with warning message
- If new → insert normally

---

## Troubleshooting

### Build Error: "HealthKit framework not found"

**Solution:**
1. Select "WatchTennisSensor Watch App" target
2. Go to "General" tab
3. Scroll to "Frameworks, Libraries, and Embedded Content"
4. Click "+" button
5. Search for "HealthKit.framework"
6. Add it (should be set to "Do Not Embed")

### Runtime Error: "Missing Info.plist key NSHealthShareUsageDescription"

**Solution:**
Privacy strings not configured. Follow Step 3c above.

### Workout Status Shows "No Workout" During Recording

**Possible Causes:**
1. HealthKit authorization denied → Check Settings → Privacy → Health → Tennis Sensor
2. Workout session failed to start → Check Xcode console for errors
3. Delay in workout initialization → Wait 1-2 seconds, should change to "Workout Active"

### Data Gaps Still Occurring

**Check:**
1. Workout status shows "Workout Active" (not "No Workout")
2. Console logs show "✅ Workout session started successfully"
3. No HealthKit errors in logs

**If still having gaps:**
- Workout session may have failed silently
- Check HealthKit authorization in Settings
- Rebuild and reinstall app

---

## Expected Backend Logs (v2.6)

When receiving data from v2.6 Watch:

```
📦 Stored batch: 100 samples (session: watch_20251108_184530)
💾 Saved 100 raw samples to database (compressed: 12413 bytes)
⚠️  Buffer already exists for time range 1762648394.0-1762648395.0, skipping duplicate
📦 Stored batch: 100 samples (session: watch_20251108_184530)
💾 Saved 100 raw samples to database (compressed: 12413 bytes)
...
```

**Key indicators:**
- ✅ "Saved X raw samples to database" (successful insert)
- ⚠️ "Buffer already exists... skipping duplicate" (duplicate prevention working)

---

## Next Steps After v2.6 Testing

Once v2.6 is verified working:

1. **Dual-Device Calibration:**
   ```bash
   # Record session with both Apple Watch (v2.6) and Zepp U
   # Then import to TennisAgent for calibration
   cd ~/Python/warrior-tau-bench
   python domains/TennisAgent/scripts/import_apple_watch.py --date 2025-11-08
   python domains/TennisAgent/scripts/query_dual_device_sessions.py --date 2025-11-08
   ```

2. **Extended Session Testing:**
   - Record 30+ minute practice session
   - Verify no data gaps throughout
   - Check battery impact
   - Verify workout appears in Health app

3. **Real Tennis Court Testing:**
   - Record full practice session
   - Analyze swing detection accuracy
   - Compare with Zepp U data for validation

---

## Files Reference

**All code changes documented in:**
- `TennisSensor/CLAUDE.md` - Complete v2.6 documentation (lines 521-778)

**Implementation details:**
- `WorkoutManager.swift` - HKWorkoutSession wrapper (220 lines)
- `ContentView.swift` - UI and workout integration (lines 14, 26-27, 63-70, 108, 131-138, 147-151)
- `MotionManager.swift` - Workout awareness (lines 19, 45-49)
- `main.py` - Duplicate prevention (lines 166-179)

---

## Contact

If you encounter any issues during Xcode configuration or testing:

1. Check `TennisSensor/CLAUDE.md` for detailed explanations
2. Review Xcode console logs for specific errors
3. Verify all 4 configuration steps completed (HealthKit capability, Background Modes, Privacy Strings, Build)

**Status:** All code changes complete and committed. Ready for Mac Py AI to configure Xcode and test.

🎾 Good luck with v2.6 deployment!
