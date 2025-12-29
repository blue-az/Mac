# Tennis Database Schema Reference

**Audience:** Py AI (Implementation)
**Purpose:** Programmatic reference for querying tennis sensor data
**Date:** 2025-11-11

---

## Database Overview

### Primary Database: tennis_unified.db
**Location:** `/home/blueaz/Python/warrior-tau-bench/domains/TennisAgent/data/unified/`
**Size:** 212 MB
**Purpose:** Single source of truth for TennisAgent V1-V6 variations
**Sessions:** 454 total (Babolat: 302, Zepp: 150, AppleWatch: 2)

### Secondary Database: tennis_watch.db
**Location:** `/home/blueaz/MacOSTennisAgent/database/`
**Size:** 14 MB
**Purpose:** Development database for Apple Watch integration + Zepp U imports
**Sessions:** 123 total (ZeppU: 117, AppleWatch: 5, SimulatedWatch: 1)

### Consolidation Status
⚠️ **Database fragmentation exists**. Plan to merge tennis_watch.db → tennis_unified.db

---

## tennis_unified.db Schema

### Core Tables

#### sessions
**Purpose:** Session-level metadata and aggregates

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| session_id | TEXT | Yes (PK) | Unique session identifier (e.g., "zepp_20241103") |
| device | TEXT | Yes | Device type ("Zepp", "Babolat", "AppleWatch") |
| type | TEXT | No | Session type (match, practice, drill) |
| start_time | INTEGER | Yes | Unix timestamp (seconds) |
| end_time | INTEGER | No | Unix timestamp (seconds) |
| date | TEXT | Yes | ISO date (YYYY-MM-DD) |
| duration_minutes | INTEGER | No | Session duration in minutes |
| data_json | TEXT | Yes | JSON blob with session-specific metrics |
| created_at | INTEGER | No | Record creation timestamp |

**Sample data_json structure (Zepp):**
```json
{
  "total_shot_count": 145,
  "serves_count": 23,
  "forehand_count": 67,
  "backhand_count": 55,
  "piq_score": 732,
  "max_piq_score": 850,
  "avg_serve_speed": 87.5,
  "max_serve_speed": 105.2,
  "avg_power": 0.78,
  "best_rally": 12
}
```

**Sample data_json structure (Babolat):**
```json
{
  "session_score": 75,
  "activity_level": 68,
  "total_shot_count": 289,
  "serves_count": 42,
  "forehand_count": 124,
  "backhand_count": 98,
  "volley_count": 18,
  "smash_count": 7,
  "forehand_avg_score": 72,
  "backhand_avg_score": 68,
  "serve_avg_score": 80,
  "best_rally_swings": 15,
  "active_time": 2340,
  "total_time": 3600
}
```

---

#### shots
**Purpose:** Individual swing/shot data

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| shot_id | TEXT | Yes (PK) | Unique shot identifier |
| session_id | TEXT | Yes (FK) | References sessions.session_id |
| timestamp | INTEGER | Yes | Unix timestamp (milliseconds) |
| shot_type | TEXT | No | "FOREHAND", "BACKHAND", "SERVE", etc. |
| spin_type | TEXT | No | "FLAT", "TOPSPIN", "SLICE" |
| speed_mph | REAL | No | Shot speed in mph |
| power | REAL | No | Power rating (0-1) |
| data_json | TEXT | Yes | JSON blob with shot-specific data |

**Sample data_json structure:**
```json
{
  "impact_position_x": -0.45,
  "impact_position_y": 0.23,
  "impact_region": 1,
  "impact_velocity_mph": 87.3,
  "ball_velocity_mph": 65.2,
  "ball_spin": 1450,
  "racket_speed_ms": 23.5,
  "backswing_time": 0.82,
  "swing_type": 2,
  "swing_side": 0
}
```

---

#### calculated_metrics
**Purpose:** Computed analytics from sessions/shots

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| calc_id | TEXT | Yes (PK) | Deterministic ID ("calc_1", "calc_2", "calc_3") |
| session_id | TEXT | Yes (FK) | References sessions.session_id |
| metric_type | TEXT | Yes | Type of calculation ("serve_metrics", "stroke_metrics", etc.) |
| values_json | TEXT | Yes | JSON blob with calculated values |
| created_at | INTEGER | No | Calculation timestamp |

**Deterministic calc_id mapping:**
```
compute_serve_metrics     → calc_1
compute_stroke_metrics    → calc_2
compute_session_summary   → calc_3
compute_metric_volatility → calc_4
compute_performance_trend → calc_3 (in audit context)
```

**Sample values_json:**
```json
{
  "avg_speed": 92.3,
  "max_speed": 108.5,
  "consistency_score": 0.82,
  "power_rating": 0.75,
  "total_count": 23
}
```

---

#### performance_reports
**Purpose:** Formatted reports with template-based output

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| report_id | TEXT | Yes (PK) | Deterministic ID ("report_1", "report_2") |
| session_id | TEXT | Yes (FK) | References sessions.session_id |
| template_id | TEXT | Yes | Template used ("serve_analysis", "comprehensive", etc.) |
| content_json | TEXT | Yes | JSON blob with report content |
| created_at | INTEGER | No | Report generation timestamp |

**CRITICAL: Use "content" key, NOT "template_data"**

**Sample content_json:**
```json
{
  "title": "Serve Analysis Report",
  "session_id": "zepp_20241103",
  "device": "Zepp",
  "date": "2024-11-03",
  "serves_count": 23,
  "avg_serve_speed": 92.3,
  "max_serve_speed": 108.5,
  "avg_power": 0.75
}
```

---

### Auxiliary Tables

#### garmin_activities
**Purpose:** Heart rate and physiological data from Garmin watch

| Column | Type | Description |
|--------|------|-------------|
| activity_id | TEXT | Unique Garmin activity ID |
| activity_type | TEXT | "Tennis", "Training", etc. |
| date | TEXT | ISO date |
| avg_hr | INTEGER | Average heart rate (bpm) |
| max_hr | INTEGER | Maximum heart rate (bpm) |
| calories | INTEGER | Calories burned |
| duration_seconds | INTEGER | Activity duration |

---

#### match_history
**Purpose:** Match context and opponent data

| Column | Type | Description |
|--------|------|-------------|
| match_id | TEXT | Unique match identifier |
| session_id | TEXT | References sessions.session_id |
| opponent | TEXT | Opponent name |
| result | TEXT | "W" or "L" |
| score | TEXT | Match score |
| date | TEXT | ISO date |

---

#### weather
**Purpose:** Environmental conditions during sessions

| Column | Type | Description |
|--------|------|-------------|
| date | TEXT | ISO date (joins with sessions.date) |
| location | TEXT | Location name |
| temperature_avg_f | REAL | Average temperature (Fahrenheit) |
| humidity_avg_pct | REAL | Average humidity (%) |
| wind_speed_avg_mph | REAL | Average wind speed (mph) |

---

## tennis_watch.db Schema

### Core Tables

#### sessions
**Purpose:** Session metadata (similar to unified, with minor differences)

| Column | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| session_id | TEXT | Yes (PK) | - | Unique session identifier |
| device | TEXT | Yes | 'AppleWatch' | Device type |
| date | TEXT | Yes | - | ISO date |
| start_time | INTEGER | Yes | - | Unix timestamp (seconds) |
| end_time | INTEGER | No | - | Unix timestamp (seconds) |
| duration_minutes | INTEGER | No | - | Duration in minutes |
| shot_count | INTEGER | No | 0 | Total shots in session |
| data_json | TEXT | Yes | - | JSON blob with metrics |
| created_at | INTEGER | No | now() | Record creation timestamp |
| updated_at | INTEGER | No | now() | Record update timestamp |

---

#### shots
**Purpose:** Individual swing data with sensor magnitudes

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| shot_id | TEXT | Yes (PK) | Unique shot identifier |
| session_id | TEXT | Yes (FK) | References sessions.session_id |
| timestamp | REAL | Yes | Unix timestamp (seconds with decimals) |
| sequence_number | INTEGER | Yes | Shot number in session (1, 2, 3...) |
| rotation_magnitude | REAL | Yes | Gyroscope magnitude (rad/s) |
| acceleration_magnitude | REAL | Yes | Accelerometer magnitude (g) |
| shot_type | TEXT | No | "FOREHAND", "BACKHAND", "SERVE", etc. |
| spin_type | TEXT | No | "FLAT", "TOPSPIN", "SLICE" |
| speed_mph | REAL | No | Estimated racket speed |
| power | REAL | No | Power rating (0-1) |
| consistency | REAL | No | Consistency score (0-1) |
| data_json | TEXT | Yes | Full JSON blob with all metrics |
| created_at | INTEGER | No | Record creation timestamp |

**Sample data_json (Zepp U import):**
```json
{
  "impact_velocity_mph": 60.6,
  "ball_velocity_mph": 45.0,
  "ball_spin": 1200,
  "swing_type": 0,
  "swing_side": 1,
  "impact_position_x": -0.35,
  "impact_position_y": 0.18,
  "impact_region": 1,
  "power": 0.72,
  "client_created": 1699734562000
}
```

---

#### raw_sensor_buffer
**Purpose:** Compressed raw IMU data for Apple Watch sessions

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| buffer_id | TEXT | Yes (PK) | Unique buffer identifier |
| session_id | TEXT | Yes (FK) | References sessions.session_id |
| start_timestamp | REAL | Yes | Buffer start time |
| end_timestamp | REAL | Yes | Buffer end time |
| sample_count | INTEGER | Yes | Number of samples in buffer |
| sample_rate_hz | REAL | Yes | Sampling frequency (typically 100 Hz) |
| compressed_data | BLOB | Yes | Gzipped binary sensor data |
| created_at | INTEGER | No | Record creation timestamp |

**Data Format:** Gzipped binary array of IMU samples (rotation, acceleration, gravity, quaternion)

---

#### calculated_metrics
**Purpose:** Computed analytics (same structure as unified db)

| Column | Type | Description |
|--------|------|-------------|
| calc_id | TEXT (PK) | Deterministic ID |
| session_id | TEXT (FK) | References sessions.session_id |
| metric_type | TEXT | Calculation type |
| values_json | TEXT | JSON with calculated values |
| created_at | INTEGER | Timestamp |

---

#### devices
**Purpose:** Device registry

| Column | Type | Description |
|--------|------|-------------|
| device_id | TEXT (PK) | Device identifier |
| device_type | TEXT | "AppleWatch", "ZeppU", etc. |
| device_name | TEXT | Human-readable name |
| last_sync | INTEGER | Last sync timestamp |
| metadata_json | TEXT | Device-specific metadata |

---

## Common Query Patterns

### Get Session Summary
```sql
SELECT
    session_id,
    device,
    date,
    duration_minutes,
    json_extract(data_json, '$.total_shot_count') as shot_count,
    json_extract(data_json, '$.piq_score') as piq_score
FROM sessions
WHERE device = 'Zepp'
ORDER BY date DESC
LIMIT 10;
```

### Get Shots for Session
```sql
SELECT
    shot_id,
    timestamp,
    shot_type,
    speed_mph,
    json_extract(data_json, '$.impact_velocity_mph') as racket_speed
FROM shots
WHERE session_id = 'zepp_20241103'
ORDER BY timestamp;
```

### Join Sessions with Calculated Metrics
```sql
SELECT
    s.session_id,
    s.device,
    s.date,
    cm.metric_type,
    cm.values_json
FROM sessions s
JOIN calculated_metrics cm ON s.session_id = cm.session_id
WHERE s.device = 'Zepp'
AND cm.metric_type = 'serve_metrics';
```

### Join Sessions with Weather
```sql
SELECT
    s.session_id,
    s.date,
    json_extract(s.data_json, '$.piq_score') as piq_score,
    w.temperature_avg_f,
    w.humidity_avg_pct
FROM sessions s
LEFT JOIN weather w ON s.date = w.date
WHERE s.device = 'Babolat'
AND w.temperature_avg_f IS NOT NULL
ORDER BY s.date DESC;
```

### Count Sessions by Device
```sql
-- tennis_unified.db
SELECT device, COUNT(*) as sessions
FROM sessions
GROUP BY device;
-- Result: Babolat: 302, Zepp: 150, AppleWatch: 2

-- tennis_watch.db
SELECT device, COUNT(*) as sessions
FROM sessions
GROUP BY device;
-- Result: ZeppU: 117, AppleWatch: 5, SimulatedWatch: 1
```

### Find Sessions with Missing Data
```sql
SELECT session_id, device, date
FROM sessions
WHERE json_extract(data_json, '$.total_shot_count') = 0
OR json_extract(data_json, '$.total_shot_count') IS NULL;
```

### Extract Impact Positions from Shots
```sql
SELECT
    shot_id,
    json_extract(data_json, '$.impact_position_x') as impact_x,
    json_extract(data_json, '$.impact_position_y') as impact_y,
    json_extract(data_json, '$.impact_region') as region
FROM shots
WHERE session_id = 'zepp_20241103'
AND json_extract(data_json, '$.impact_position_x') IS NOT NULL;
```

---

## Data Contract - JSON Keys Reference

### sessions.data_json Keys (Zepp)
```
total_shot_count: INTEGER
serves_count: INTEGER
forehand_count: INTEGER
backhand_count: INTEGER
piq_score: INTEGER (0-1000)
max_piq_score: INTEGER
avg_serve_speed: REAL (mph)
max_serve_speed: REAL (mph)
avg_forehand_speed: REAL (mph)
avg_backhand_speed: REAL (mph)
avg_power: REAL (0-1)
best_rally: INTEGER (consecutive shots)
```

### sessions.data_json Keys (Babolat)
```
session_score: INTEGER (0-100)
activity_level: INTEGER (0-100)
total_shot_count: INTEGER
serves_count: INTEGER
forehand_count: INTEGER
backhand_count: INTEGER
volley_count: INTEGER
smash_count: INTEGER
forehand_avg_score: INTEGER (0-100)
backhand_avg_score: INTEGER (0-100)
serve_avg_score: INTEGER (0-100)
best_rally_swings: INTEGER
active_time: INTEGER (seconds)
total_time: INTEGER (seconds)
```

### shots.data_json Keys
```
impact_position_x: REAL (-1 to 1, racket face X coordinate)
impact_position_y: REAL (-1 to 1, racket face Y coordinate)
impact_region: INTEGER (0-9, zone on racket)
impact_velocity_mph: REAL (racket speed at impact)
ball_velocity_mph: REAL (ball speed after impact)
ball_spin: REAL (RPM)
racket_speed_ms: REAL (m/s)
backswing_time: REAL (seconds)
swing_type: INTEGER (0=unknown, 1=flat, 2=topspin, 3=slice, 4=serve)
swing_side: INTEGER (0=forehand, 1=backhand)
power: REAL (0-1)
```

---

## Key Constraints & Gotchas

### 1. Device Name Variations
- tennis_unified.db uses: "Zepp", "Babolat", "AppleWatch"
- tennis_watch.db uses: "ZeppU", "AppleWatch", "SimulatedWatch"

**Implication:** Queries must account for naming differences when consolidating.

### 2. Timestamp Precision
- tennis_unified.db: `start_time` is INTEGER (seconds)
- tennis_watch.db: `timestamp` in shots is REAL (seconds with decimals)
- Zepp U raw data: `client_created` is milliseconds

**Implication:** Timestamp conversion required when merging.

### 3. JSON vs Columns
- Summary metrics in `data_json` (not top-level columns)
- Use `json_extract()` for queries
- Performance impact on large queries (no indexing on JSON)

### 4. Session ID Format
- Pattern: `{device}_{YYYYMMDD}` or `{device}_{YYYYMMDD}_{HHMMSS}`
- Examples: "zepp_20241103", "bab_20240615_143022"

### 5. Data Quality Flags
- AppleWatch sessions: Fragmented, low confidence
- Zepp U sessions: High confidence, validated
- Babolat sessions: High confidence, summary only

---

## Write-Then-Verify Pattern (Phoenix Principle)

When modifying database state:

```python
# WRITE
result = execute_tool("compute_serve_metrics", session_id="zepp_123")
# → Returns: {"calc_id": "calc_1", "status": "success"}

# VERIFY
verify = execute_tool("verify_calculation", calc_id="calc_1")
# → Returns: {"exists": True, "metric_type": "serve_metrics", "valid": True}
```

**Never assume a write succeeded. Always verify.**

---

**Last Updated:** 2025-11-11
**Maintained By:** Py AI
**Next Review:** After database consolidation complete
