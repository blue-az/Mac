# Mac Restart Recovery Steps - November 10, 2025

## Current Situation
- Watch app (v2.5.5) won't install - gets stuck at "3/4 loaded" or shows "Unable to install"
- Code is correct (exact v2.5.5 that was working on November 8)
- All troubleshooting exhausted except Mac restart

---

## Steps After Mac Restart

### 1. Reconnect Devices
```bash
# Connect iPhone via USB cable
# Unlock iPhone
# Trust computer if prompted
```

### 2. Verify Connections
```bash
xcrun devicectl list devices
# Should show:
#   Erik's iPhone: connected
#   Erik's Apple Watch: available (paired)
```

### 3. Open Xcode
```bash
open /Users/wikiwoo/Projects/MacOSTennisAgent/TennisSensor/TennisSensor.xcodeproj
```

### 4. Configure Xcode
- **Scheme:** Select "TennisSensor" (top dropdown)
- **Device:** Select "Erik's iPhone" (NOT simulator, NOT Watch)
- **Keep iPhone and Watch close together** (Bluetooth range)
- **Keep Watch unlocked** (enter passcode)

### 5. Build and Run
```
Product → Run (Cmd+R)
```

**Expected behavior:**
- iPhone app builds and installs
- iPhone app launches
- Watch app syncs in background (1-2 minutes)

### 6. Check Watch App Installation

**Wait 2-3 minutes**, then check Watch:

**Success signs:**
- ✅ TennisSensor icon appears on Watch
- ✅ Icon fully loads (no 3/4 circle)
- ✅ Tapping icon opens the app
- ✅ Shows "TT v2.5.5" header

**If icon shows "Untrusted Developer":**
- Settings → General → Device Management → Trust developer profile

**If stuck at 3/4 again:**
- Restart Watch
- Check if icon completes after restart

---

## Verification Steps

### Check iPhone App
**Open iPhone TennisSensor app**, look for:
```
✅ WC Active (green)
✅ Watch Reachable (green)
isWatchAppInstalled: true
```

### Test Recording
1. **On Watch:** Tap "Start" button
2. Watch for sample counter to increase
3. **Tap "Stop"** after 10 seconds
4. **On iPhone:** Should see data batches received

### Check Backend Connection
```bash
# Start backend (if not already running)
cd ~/Projects/MacOSTennisAgent/backend
source ../venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Check database after recording
sqlite3 ~/Projects/MacOSTennisAgent/database/tennis_watch.db "
SELECT session_id,
  (SELECT SUM(sample_count) FROM raw_sensor_buffer
   WHERE raw_sensor_buffer.session_id = sessions.session_id) as samples
FROM sessions
ORDER BY start_time DESC
LIMIT 1;"
```

---

## If Mac Restart Doesn't Fix It

### Diagnostic Commands

**Check Watch development status:**
```bash
xcrun devicectl device info details --device 3222270D-BD50-5F67-BA78-EE76BD2443B2 2>&1 | grep -E "(ddiServicesAvailable|developerModeStatus|tunnelState)"
```

**Expected if working:**
```
• ddiServicesAvailable: true  ✅
• developerModeStatus: enabled ✅
• tunnelState: connected ✅
```

**If still blocked:**
```
• ddiServicesAvailable: false  ❌ (STILL BLOCKED)
```

### Next Actions If Still Blocked

**Option 1: Contact Apple Developer Support** (Recommended)
- URL: https://developer.apple.com/support/technical/
- Share: `DDI_SERVICES_BLOCKED.md` (has all technical details)
- They have internal tools to force DDI services or diagnose system blocks

**Option 2: Try Different Mac**
- If you have access to another Mac with Xcode
- Would confirm if issue is Mac-specific or Watch-specific

**Option 3: Wait for System Update**
- Check for watchOS updates periodically
- Sometimes minor updates fix edge cases like this

**Option 4: Use Watch Simulator**
- Not ideal, but functional for development
- Can develop/test while waiting for resolution

---

## Current Code State (Ready to Deploy)

**Version:** v2.5.5 (last known working from November 8)

**Bundle IDs:**
- iPhone: `com.ef.TennisSensor`
- Watch: `com.ef.TennisSensor.watchkitapp`

**Files:**
- All Watch app files restored from git commit `cf4c29e`
- No WorkoutManager, no HealthKit dependencies
- Clean, simple configuration

**Backups:**
- v2.6.2 features backed up with `.v2.6.2.backup` extension
- Can restore after Watch app successfully installs

---

## Key Points

1. **The code is correct** - exact v2.5.5 that was working
2. **The issue is system-level** - DDI services won't load on Watch
3. **Not your fault** - extremely rare edge case (<1%)
4. **Mac restart = last software option** before Apple support

---

## Success Criteria

✅ Watch app icon appears and fully loads (no 3/4 circle)
✅ Can tap and open app on Watch
✅ iPhone shows "isWatchAppInstalled: true"
✅ Can record session and see sample counter increase
✅ Data reaches backend database

---

**Good luck with the Mac restart! 🍀**
