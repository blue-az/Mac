# Critical Issue: DDI Services Won't Load on Apple Watch SE

**Date:** November 10, 2025
**watchOS:** 10.6.1
**Xcode:** 16.3 (23785)
**macOS:** 15.7.2

---

## Issue Summary

Apple Watch SE cannot load Developer Disk Image (DDI) services, blocking all development app installations despite Developer Mode being enabled.

**Status:**
```
• developerModeStatus: enabled ✅
• ddiServicesAvailable: false ❌ (BLOCKING ISSUE)
• tunnelState: disconnected ❌
```

---

## Timeline

### November 9, 2025 - System Was Working
- v2.5.5 Watch app successfully installed and running
- Recording tennis motion data successfully
- Complete end-to-end pipeline verified

### November 9, 2025 - Problem Began
1. Updated Watch app code to v2.6.2 (added WorkoutManager/HealthKit)
2. iPhone app updated successfully via Xcode
3. Watch app would not update (stuck at v2.5.5)
4. **User deleted Watch app from Watch to force reinstall**
5. **Watch app completely disappeared - would not reinstall**

### Troubleshooting Attempted

**Phase 1: Standard Fixes (Failed)**
- ❌ Restarted iPhone and Watch multiple times
- ❌ Changed Watch app bundle ID (tried 3 different IDs)
- ❌ Installed simplified v2.5.6 (removed WorkoutManager/HealthKit)
- ❌ Clean builds and reinstalls

**Phase 2: Nuclear Option #1 (Failed)**
- ❌ Unpaired and re-paired Watch
- ❌ Set up as new Watch (no backup restore)
- Result: Same issue - DDI services won't load

**Phase 3: Nuclear Option #2 (Failed)**
- ❌ Erased ALL content from Watch (Settings → General → Reset → Erase All Content)
- ❌ Manually deleted Watch backups from iPhone
- ❌ Re-paired as completely new Watch
- ❌ Enabled Developer Mode (succeeded - shows as `enabled`)
- ❌ Watch app appears in iPhone Watch app "Available Apps"
- ❌ Watch app starts installing (icon appears at "3/4 loading")
- ❌ Installation hangs - never completes
- ❌ Direct Xcode build hangs waiting to connect to Watch

**Phase 4: Cache Clearing (Failed)**
- ❌ Cleared all Xcode device support caches
- ❌ Cleared CoreDevice caches
- ❌ Restarted `coredeviced` daemon multiple times
- ❌ Result: `ddiServicesAvailable: false` persists

---

## Technical Details

### Device IDs
```
iPhone: 00008130-000214E90891401C (iPhone 15 Pro)
Watch:  00008006-0008CD291E00C02E (Apple Watch SE, Watch5,11)
Watch CoreDevice ID: 3222270D-BD50-5F67-BA78-EE76BD2443B2
```

### Current Watch Status (from devicectl)
```
▿ deviceProperties:
    • ddiServicesAvailable: false ❌ BLOCKING ISSUE
    • developerModeStatus: enabled ✅
    • hasInternalOSBuild: false
    • name: Erik's Apple Watch
    • osBuildUpdate: 21U580
    • osVersionNumber: 10.6.1
    • rootFileSystemIsWritable: false

▿ connectionProperties:
    • authenticationType: manualPairing
    • pairingState: paired ✅
    • transportType: localNetwork
    • tunnelState: disconnected ❌
```

### Build Status
- ✅ iPhone app builds successfully
- ✅ Watch app builds successfully
- ✅ Watch app is properly embedded in iPhone bundle at `TennisSensor.app/Watch/WatchTennisSensor Watch App.app`
- ✅ Watch app appears in iPhone Watch app "Available Apps" list
- ❌ Watch app installation hangs at 3/4 progress
- ❌ Xcode hangs with: `Timed out waiting for all destinations` when building to Watch
- ❌ Error: `Erik's Apple Watch may need to be unlocked to recover from previously reported preparation errors`

### Symptoms
1. **Via iPhone Watch App Sync:**
   - Watch app appears in "Available Apps"
   - Tapping "Install" starts installation
   - Icon appears on Watch at "3/4 loading" (gray circle with partial ring)
   - Hangs indefinitely - never completes
   - Toggle switch in iPhone Watch app auto-disables (installation failed silently)

2. **Via Xcode Direct Build:**
   - Select "WatchTennisSensor Watch App" scheme
   - Select physical Apple Watch as target
   - Product → Run
   - Xcode hangs: "Preparing Erik's Apple Watch"
   - Times out after ~60 seconds
   - Error: `com.apple.dt.deviceprep error -25` (Operation timed out)

3. **WatchConnectivity Status:**
   ```
   ✅ WCSession activated: 2
      isPaired: true ✅
      isWatchAppInstalled: false ❌
      isReachable: false ❌
   ```

---

## Why This is Unusual

1. **Developer Mode IS Enabled**
   - `devicectl` confirms: `developerModeStatus: enabled`
   - But DDI services won't load

2. **System Was Working 24 Hours Ago**
   - No Xcode update
   - No macOS update
   - No watchOS update
   - Only change: deleted and tried to reinstall Watch app

3. **Survives Complete Erase**
   - Even after erasing ALL content from Watch
   - Even after deleting backups
   - DDI services still won't load on fresh pairing

4. **Multiple Re-Pairs Don't Fix It**
   - Typically unpair/re-pair fixes 95% of watchOS development issues
   - In this case, tried 4+ times with no improvement

---

## Hypothesis

Deleting the Watch app while it was in a "stuck update" state may have corrupted some watchOS system metadata that:
- Survives re-pairing
- Survives full device erase
- Blocks DDI services from loading
- Prevents any development apps from installing

This is likely a watchOS 10.6.1 bug in the app installation state machine.

---

## What Has NOT Been Tried

1. **watchOS Software Update**
   - User is on latest: 10.6.1
   - No newer version available

2. **Different Mac/Xcode**
   - Slim chance, but might work if it's a pairing-specific issue

3. **Apple Developer Support Escalation**
   - They may have internal tools to force DDI services
   - Or debug profiles to diagnose why DDI is blocked

4. **Wait for watchOS 10.6.2 or 11.0**
   - System update might clear corrupted state

---

## Workarounds

### Temporary: Use Watch Simulator
- Can develop/test in Xcode Simulator
- Not ideal - no real device testing

### Potential: Borrow Another Apple Watch
- If available, a different Watch might not have this issue
- Suggests it's Watch-specific corruption, not Mac/Xcode issue

---

## Files and Backups

All files backed up before modifications:
```
TennisSensor/WatchTennisSensor Watch App/ContentView.swift.v2.6.2.backup
TennisSensor/WatchTennisSensor Watch App/MotionManager.swift.v2.6.2.backup
TennisSensor/WatchTennisSensor Watch App/WorkoutManager.swift.v2.6.2.backup
TennisSensor/WatchTennisSensor Watch App/WatchTennisSensor Watch App.entitlements.v2.6.2.backup
```

Current Watch app: v2.5.6 (simplified, no WorkoutManager/HealthKit)

---

## Recommendation

**Contact Apple Developer Support** with this document. This is beyond community troubleshooting - it requires:
- Internal diagnostic tools
- Ability to force DDI services to load
- Or debug profile to identify what's blocking DDI

**Support URL:** https://developer.apple.com/support/technical/

**Relevant Keywords for Support:**
- DDI services won't load after unpair/re-pair
- developerModeStatus enabled but ddiServicesAvailable false
- Watch app installation hangs at 3/4
- error -25 device preparation timeout
- watchOS 10.6.1 development app installation blocked

---

## Success Criteria

When DDI services load properly:
```
• ddiServicesAvailable: true ✅
• tunnelState: connected ✅
• isWatchAppInstalled: true ✅
```

Then:
- Xcode builds won't timeout
- Watch app will install successfully
- Data collection pipeline will work

---

**This is a <1% edge case that requires Apple support intervention.**
