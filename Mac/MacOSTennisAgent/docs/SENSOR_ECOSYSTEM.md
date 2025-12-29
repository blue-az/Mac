# Tennis Sensor Ecosystem

**Audience:** Py AI (Implementation)
**Purpose:** Operational reference for understanding sensor capabilities
**Date:** 2025-11-11

---

## Sensor Inventory

### 1. Zepp U Tennis Sensor
**Status:** ✅ Operational (Primary Data Source)
**Device Type:** Smart tennis racket sensor
**Placement:** Mounted at racket butt cap

**Capabilities:**
- **Two Operating Modes:**
  1. **Serve Mode**: Dedicated serve analysis
  2. **Stroke Mode**: Groundstroke and rally analysis

- **Data Types:**
  - **Real-time Data**: Continuous IMU sensor readings during swing
    - Accelerometer (3-axis)
    - Gyroscope (3-axis)
    - Available in `dbg_acc_1/2/3` and `dbg_gyro_1/2/3` columns
  - **Summary Data**: Post-processed metrics per swing
    - Impact velocity (mph)
    - Ball velocity (mph)
    - Ball spin (RPM)
    - Swing type classification
    - Impact position on racket face

**Data Collection Method:**
- Manual sync via Zepp Tennis mobile app
- Export from rooted Android phone
- Database: `ztennis.db` (SQLite)

**Current Integration Status:**
- ✅ 16,715 swings imported into `tennis_watch.db`
- ✅ 117 sessions (2022-2025)
- ✅ Import pipeline validated

---

### 2. Babolat Play Sensor
**Status:** ✅ Operational (Secondary Data Source)
**Device Type:** Smart tennis racket sensor
**Placement:** Embedded in racket handle

**Capabilities:**
- **Summary Data Only**: No raw sensor access
  - Session-level aggregates
  - Shot counts by type (forehand, backhand, serve)
  - Average speeds per stroke type
  - PIQ score (proprietary performance metric)
  - Impact heat maps

- **Match Context:**
  - Session duration
  - Active time vs total time
  - Best rally length
  - Activity level score

**Data Collection Method:**
- Manual sync via Babolat Play mobile app
- Export from rooted Android phone
- Database: Part of unified system

**Current Integration Status:**
- ✅ 302 sessions in `tennis_unified.db`
- ✅ Full session reports with JSON metadata

**Limitations:**
- No access to raw IMU data
- Cannot retrieve swing-by-swing timestamps
- Summary statistics only

---

### 3. Apple Watch (Development)
**Status:** ⚠️ In Development (Blocked)
**Device Type:** Wrist-worn smartwatch
**Placement:** Dominant wrist

**Target Capabilities:**
- **Continuous Real-time Streaming:**
  - Core Motion data at 100 Hz
  - Rotation rate (gyroscope)
  - Acceleration
  - Gravity vector
  - Quaternion orientation

- **Real-time Transmission:**
  - Watch → iPhone via WatchConnectivity
  - iPhone → Backend WebSocket (192.168.8.185:8000)

**Current State:**
- App Version: v2.5.5 (on Watch), v2.6.2 (development)
- **BLOCKING ISSUE**: DDI tunnel instability prevents installation
- Temporary workaround: TestFlight (Apple Developer Program enrollment in progress)

**Data Collection Method (Planned):**
- Real-time streaming to backend database
- Session recording triggered by user
- Continuous buffer during tennis play

**Current Integration Status:**
- ⚠️ 5 sessions in `tennis_watch.db` (development/testing only)
- ⚠️ Data quality: Fragmented (sensor cut-outs)
- ⚠️ Swing detection: 23% accuracy (needs tuning)

**Alternative Data Source:**
- **SensorLogger App**: Manual CSV export
  - Proven reliable (June 14, 2024 session: 100 swings, 98,430 samples)
  - Max rotation rate: 39.61 rad/s (validates real tennis swings)
  - **Limitation**: Not real-time, manual export required

---

### 4. Garmin Fitness Watch
**Status:** ⚠️ Auxiliary Data Source
**Device Type:** Fitness tracker
**Placement:** Wrist

**Capabilities:**
- **Physiological Data:**
  - Heart rate (avg, max)
  - Calories burned
  - Activity duration
  - GPS tracking (if enabled)

**Data Collection Method:**
- Export from Garmin Connect
- Manual import to database

**Current Integration Status:**
- ✅ `garmin_activities` table exists in `tennis_unified.db`
- ⚠️ Integration incomplete

**Use Case:**
- Correlate performance metrics with cardiovascular exertion
- Analyze training load over time
- Match intensity analysis

---

### 5. Weather Data (Planned)
**Status:** 📋 Future Integration
**Data Source:** Weather API (to be determined)

**Target Capabilities:**
- Temperature (avg, max, min)
- Humidity
- Wind speed
- Conditions (clear, cloudy, rain)

**Use Case:**
- Correlate performance with environmental conditions
- Identify optimal playing conditions
- Weather impact on swing mechanics

**Current Integration Status:**
- ✅ `weather` table exists in `tennis_unified.db`
- ⚠️ Migration script exists but incomplete
- 📋 API integration not yet implemented

---

## Sensor Comparison Matrix

| Sensor | Real-time | Summary | Swing Detection | Court Position | Heart Rate | Status |
|--------|-----------|---------|-----------------|----------------|------------|--------|
| **Zepp U** | ✅ Yes | ✅ Yes | ✅ Yes | ❌ No | ❌ No | ✅ Operational |
| **Babolat** | ❌ No | ✅ Yes | ✅ Yes | ❌ No | ❌ No | ✅ Operational |
| **Apple Watch** | ✅ Yes (planned) | ⚠️ Partial | ⚠️ Development | ❌ No | ❌ No | ⚠️ Blocked |
| **Garmin** | ❌ No | ✅ Yes | ❌ No | ✅ GPS | ✅ Yes | ⚠️ Partial |
| **Weather** | ❌ No | ✅ Yes | N/A | N/A | N/A | 📋 Planned |

---

## Data Richness Hierarchy

### Tier 1: High-Fidelity Data (Zepp U)
- Real-time + summary
- 16,715 swings over 3+ years
- Ground truth for swing detection algorithms
- Primary data source for analysis

### Tier 2: Summary-Only Data (Babolat)
- Session aggregates
- 302 sessions
- Match context and performance scores
- Complementary to Zepp U

### Tier 3: Development Data (Apple Watch)
- Potential real-time streaming
- Currently unreliable (fragmented)
- Future primary real-time source (when stable)

### Tier 4: Contextual Data (Garmin, Weather)
- Physiological and environmental context
- Enriches analysis but not core metrics
- Integration incomplete

---

## Key Insights for Implementation

### For Querying Data:
1. **Use Zepp U for:**
   - Historical analysis (3+ years)
   - Swing detection ground truth
   - Longitudinal trends
   - Real-time signal processing validation

2. **Use Babolat for:**
   - Session-level summaries
   - PIQ score analysis
   - Match performance tracking

3. **Avoid Apple Watch for:**
   - Production analysis (until stable)
   - Ground truth validation (23% accuracy)
   - Current state: Development only

### For Building Tools:
1. **Multi-device support required:**
   - Tools must handle both Zepp and Babolat
   - Device-specific logic for data extraction
   - Graceful degradation when data missing

2. **Real-time vs Summary:**
   - Zepp U: Can analyze both modes
   - Babolat: Summary only
   - Apple Watch: Real-time (when working)

3. **Data Quality Flags:**
   - Zepp U: High confidence
   - Babolat: High confidence
   - Apple Watch: Low confidence (flag for exclusion)

---

## Import Priority

**Current Focus:**
1. ✅ **Zepp U**: Fully imported (16,715 swings)
2. 🔜 **Database Consolidation**: Merge tennis_watch.db → tennis_unified.db
3. 📋 **Apple Watch**: After TestFlight working + more data collected

**Deferred:**
- Garmin integration (low priority)
- Weather API (future enhancement)

---

**Last Updated:** 2025-11-11
**Maintained By:** Py AI
**Next Review:** After TestFlight deployment complete
