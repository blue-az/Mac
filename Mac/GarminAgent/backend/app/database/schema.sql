-- GarminTennisAgent Database Schema
-- SQLite database for storing Garmin activity and heart rate data

-- Activities table: stores activity metadata from FIT files
CREATE TABLE IF NOT EXISTS activities (
    activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
    fit_file_path TEXT UNIQUE NOT NULL,
    activity_type TEXT,
    start_time DATETIME NOT NULL,
    end_time DATETIME,
    duration_seconds INTEGER,
    distance_meters REAL,
    calories INTEGER,
    avg_hr INTEGER,
    max_hr INTEGER,
    min_hr INTEGER,
    hr_zones_json TEXT,
    data_json TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Heart rate samples: individual HR readings from activities
CREATE TABLE IF NOT EXISTS heart_rate_samples (
    sample_id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id INTEGER NOT NULL,
    timestamp DATETIME NOT NULL,
    heart_rate INTEGER NOT NULL,
    FOREIGN KEY (activity_id) REFERENCES activities(activity_id) ON DELETE CASCADE
);

-- Sync log: tracks import operations
CREATE TABLE IF NOT EXISTS sync_log (
    sync_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sync_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    activities_synced INTEGER DEFAULT 0,
    files_found INTEGER DEFAULT 0,
    files_skipped INTEGER DEFAULT 0,
    status TEXT DEFAULT 'success',
    error_message TEXT,
    device_info TEXT
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_activities_start_time ON activities(start_time);
CREATE INDEX IF NOT EXISTS idx_activities_type ON activities(activity_type);
CREATE INDEX IF NOT EXISTS idx_hr_samples_activity ON heart_rate_samples(activity_id);
CREATE INDEX IF NOT EXISTS idx_hr_samples_timestamp ON heart_rate_samples(timestamp);
CREATE INDEX IF NOT EXISTS idx_sync_log_time ON sync_log(sync_time);

-- View: Activity summary with HR stats
CREATE VIEW IF NOT EXISTS v_activity_summary AS
SELECT
    a.activity_id,
    a.activity_type,
    a.start_time,
    a.duration_seconds,
    a.distance_meters,
    a.calories,
    a.avg_hr,
    a.max_hr,
    a.min_hr,
    COUNT(h.sample_id) as hr_sample_count
FROM activities a
LEFT JOIN heart_rate_samples h ON a.activity_id = h.activity_id
GROUP BY a.activity_id;
