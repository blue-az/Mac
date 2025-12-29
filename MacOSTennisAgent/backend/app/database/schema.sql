-- MacOSTennisAgent Database Schema
-- SQLite database for storing tennis session and swing data from Apple Watch

-- ============================================================================
-- Sessions Table
-- Tracks tennis practice/match sessions
-- ============================================================================
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,              -- Format: watch_YYYYMMDD_HHMMSS
    device TEXT NOT NULL DEFAULT 'AppleWatch', -- Device name
    date TEXT NOT NULL,                        -- ISO date: YYYY-MM-DD
    start_time INTEGER NOT NULL,               -- Unix timestamp (seconds)
    end_time INTEGER,                          -- Unix timestamp (seconds)
    duration_minutes INTEGER,                  -- Calculated duration
    shot_count INTEGER DEFAULT 0,              -- Total shots detected
    data_json TEXT NOT NULL,                   -- JSON: session metadata
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER DEFAULT (strftime('%s', 'now'))
);

-- Index for date queries
CREATE INDEX IF NOT EXISTS idx_sessions_date ON sessions(date DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_start_time ON sessions(start_time DESC);

-- ============================================================================
-- Shots Table
-- Individual detected swings/shots within sessions
-- ============================================================================
CREATE TABLE IF NOT EXISTS shots (
    shot_id TEXT PRIMARY KEY,                  -- Format: shot_YYYYMMDD_HHMMSS_NNN
    session_id TEXT NOT NULL,                  -- Foreign key to sessions
    timestamp REAL NOT NULL,                   -- Unix timestamp with milliseconds
    sequence_number INTEGER NOT NULL,          -- Shot number within session

    -- Detection metrics
    rotation_magnitude REAL NOT NULL,          -- Peak gyro magnitude (rad/s)
    acceleration_magnitude REAL NOT NULL,      -- Peak accel magnitude (g)

    -- Estimated properties (optional)
    shot_type TEXT,                            -- 'forehand', 'backhand', 'serve', 'volley'
    spin_type TEXT,                            -- 'topspin', 'slice', 'flat'
    speed_mph REAL,                            -- Estimated racket speed
    power REAL,                                -- Power rating (0.0-1.0)
    consistency REAL,                          -- Consistency score (0.0-1.0)

    -- Full sensor data at peak
    data_json TEXT NOT NULL,                   -- JSON: full sensor readings at peak

    created_at INTEGER DEFAULT (strftime('%s', 'now')),

    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

-- Indexes for shot queries
CREATE INDEX IF NOT EXISTS idx_shots_session ON shots(session_id, sequence_number);
CREATE INDEX IF NOT EXISTS idx_shots_timestamp ON shots(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_shots_type ON shots(shot_type);

-- ============================================================================
-- Calculated Metrics Table
-- Aggregated statistics per session
-- ============================================================================
CREATE TABLE IF NOT EXISTS calculated_metrics (
    calc_id TEXT PRIMARY KEY,                  -- Format: calc_UUID
    session_id TEXT NOT NULL,                  -- Foreign key to sessions
    metric_type TEXT NOT NULL,                 -- Metric identifier
    values_json TEXT NOT NULL,                 -- JSON: metric values
    created_at INTEGER DEFAULT (strftime('%s', 'now')),

    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

-- Index for metric queries
CREATE INDEX IF NOT EXISTS idx_metrics_session ON calculated_metrics(session_id, metric_type);

-- ============================================================================
-- Raw Sensor Buffer Table (Optional - for debugging/reprocessing)
-- Stores compressed chunks of raw sensor data
-- ============================================================================
CREATE TABLE IF NOT EXISTS raw_sensor_buffer (
    buffer_id TEXT PRIMARY KEY,                -- Format: buffer_UUID
    session_id TEXT NOT NULL,                  -- Foreign key to sessions
    start_timestamp REAL NOT NULL,             -- First sample timestamp
    end_timestamp REAL NOT NULL,               -- Last sample timestamp
    sample_count INTEGER NOT NULL,             -- Number of samples in chunk
    compressed_data BLOB,                      -- Gzipped CSV data
    created_at INTEGER DEFAULT (strftime('%s', 'now')),

    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

-- Index for buffer queries
CREATE INDEX IF NOT EXISTS idx_buffer_session ON raw_sensor_buffer(session_id, start_timestamp);

-- ============================================================================
-- Device Info Table (Optional - track multiple devices)
-- ============================================================================
CREATE TABLE IF NOT EXISTS devices (
    device_id TEXT PRIMARY KEY,                -- Device identifier
    device_type TEXT NOT NULL,                 -- 'AppleWatch', 'Zepp', etc.
    model TEXT,                                -- Watch model
    os_version TEXT,                           -- WatchOS version
    first_seen INTEGER DEFAULT (strftime('%s', 'now')),
    last_seen INTEGER DEFAULT (strftime('%s', 'now')),
    total_sessions INTEGER DEFAULT 0,
    metadata_json TEXT                         -- JSON: additional device info
);

-- ============================================================================
-- Views for Common Queries
-- ============================================================================

-- Session summary view
CREATE VIEW IF NOT EXISTS v_session_summary AS
SELECT
    s.session_id,
    s.date,
    s.device,
    datetime(s.start_time, 'unixepoch') as start_datetime,
    datetime(s.end_time, 'unixepoch') as end_datetime,
    s.duration_minutes,
    s.shot_count,
    COUNT(sh.shot_id) as actual_shot_count,
    AVG(sh.rotation_magnitude) as avg_rotation,
    MAX(sh.rotation_magnitude) as max_rotation,
    AVG(sh.acceleration_magnitude) as avg_acceleration,
    MAX(sh.acceleration_magnitude) as max_acceleration
FROM sessions s
LEFT JOIN shots sh ON s.session_id = sh.session_id
GROUP BY s.session_id;

-- Daily statistics view
CREATE VIEW IF NOT EXISTS v_daily_stats AS
SELECT
    date,
    COUNT(DISTINCT session_id) as session_count,
    SUM(shot_count) as total_shots,
    SUM(duration_minutes) as total_minutes
FROM sessions
GROUP BY date
ORDER BY date DESC;
