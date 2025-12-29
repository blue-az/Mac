# GarminTennisAgent Setup Guide

Import Garmin activity data (including heart rate) from your iPhone using libimobiledevice.

## Prerequisites

### 1. Install libimobiledevice

```bash
brew install libimobiledevice ifuse
```

### 2. Install macFUSE (required for ifuse)

Download and install from: https://osxfuse.github.io/

Or via Homebrew:
```bash
brew install --cask macfuse
```

**Note:** You may need to allow the kernel extension in System Preferences → Security & Privacy → General.

### 3. Python Environment

```bash
cd ~/Python/project-phoenix/domains/TennisAgent

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt
```

## First-Time Setup

### 1. Initialize Database

```bash
cd backend/scripts
python init_database.py
```

This creates `database/tennis_garmin.db` with the required tables.

### 2. Trust Your iPhone

1. Connect iPhone to Mac via USB cable
2. Unlock iPhone
3. Tap "Trust" when prompted on iPhone
4. Enter iPhone passcode if requested

Verify connection:
```bash
idevice_id -l
```

Should output your device UDID.

### 3. Ensure Garmin Connect is Installed

The Garmin Connect app must be installed on your iPhone with synced activity data.

## Usage

### Sync Activities

Connect iPhone and run:

```bash
cd ~/Python/project-phoenix/domains/TennisAgent/backend/scripts
source ../../venv/bin/activate

# Import all new activities
python sync_iphone.py

# List available FIT files without importing
python sync_iphone.py --list

# Re-import all (overwrite existing)
python sync_iphone.py --force

# Import only first 10 files
python sync_iphone.py --limit 10
```

### Query Data

```bash
# Open database with sqlite3
sqlite3 ../../database/tennis_garmin.db

# List all activities
SELECT activity_id, activity_type, start_time, duration_seconds/60 as minutes, avg_hr, max_hr
FROM activities ORDER BY start_time DESC;

# Get HR samples for an activity
SELECT timestamp, heart_rate FROM heart_rate_samples
WHERE activity_id = 1 ORDER BY timestamp;

# View activity summary
SELECT * FROM v_activity_summary;
```

## Troubleshooting

### "No iPhone connected"

1. Check USB cable is connected
2. Unlock iPhone
3. Trust the computer when prompted
4. Try a different USB port
5. Restart usbmuxd: `sudo launchctl stop com.apple.usbmuxd`

### "Failed to mount Garmin container"

1. Ensure Garmin Connect app is installed
2. Open Garmin Connect app on iPhone and sync some activities
3. Check ifuse is installed: `which ifuse`
4. Check macFUSE is installed and kernel extension is allowed
5. Try manual mount:
   ```bash
   mkdir -p /tmp/garmin_mount
   ifuse --container com.garmin.connect.mobile /tmp/garmin_mount
   ls /tmp/garmin_mount
   ```

### "fitparse not installed"

```bash
pip install fitparse
```

### Permission Errors

If you see permission errors when mounting:
1. System Preferences → Security & Privacy → Privacy → Full Disk Access
2. Add Terminal (or your terminal app)

### No FIT Files Found

FIT files may be stored in different locations depending on Garmin Connect version. The script searches recursively for `*.fit` and `*.FIT` files.

If no files are found:
1. Open Garmin Connect app on iPhone
2. Ensure activities are synced
3. Try manual exploration:
   ```bash
   ifuse --container com.garmin.connect.mobile ./mnt
   find ./mnt -name "*.fit" -o -name "*.FIT"
   ```

## Project Structure

```
TennisAgent/
├── backend/
│   ├── app/
│   │   ├── services/
│   │   │   ├── iphone_mount.py   # libimobiledevice wrapper
│   │   │   └── fit_parser.py     # FIT file parser
│   │   ├── models/
│   │   │   └── activity_data.py  # Pydantic models
│   │   └── database/
│   │       └── schema.sql        # SQLite schema
│   ├── scripts/
│   │   ├── init_database.py      # DB setup
│   │   └── sync_iphone.py        # Main sync script
│   └── requirements.txt
├── database/
│   └── tennis_garmin.db          # SQLite database
├── mnt/                          # iPhone mount point
└── docs/
    └── SETUP.md                  # This file
```

## Database Schema

### activities
| Column | Type | Description |
|--------|------|-------------|
| activity_id | INTEGER | Primary key |
| fit_file_path | TEXT | Source FIT filename |
| activity_type | TEXT | Sport type (running, cycling, etc.) |
| start_time | DATETIME | Activity start |
| duration_seconds | INTEGER | Total duration |
| avg_hr | INTEGER | Average heart rate |
| max_hr | INTEGER | Maximum heart rate |
| hr_zones_json | TEXT | Time in each HR zone |

### heart_rate_samples
| Column | Type | Description |
|--------|------|-------------|
| sample_id | INTEGER | Primary key |
| activity_id | INTEGER | FK to activities |
| timestamp | DATETIME | Sample time |
| heart_rate | INTEGER | HR value (bpm) |

### sync_log
| Column | Type | Description |
|--------|------|-------------|
| sync_id | INTEGER | Primary key |
| sync_time | DATETIME | When sync occurred |
| activities_synced | INTEGER | Number imported |
| status | TEXT | success/partial/failed |
