# GarminAgent

Imports Garmin activity data (HR timeseries) into SQLite database.

**Status:** 336 activities, 373k HR samples. Database synced to Desktop via git.

## Workflow

```
Garmin Connect (web) → Export Your Data → Wait for email (~72hr cooldown)
         ↓
Download zip → Extract FIT files → imports/*.fit
         ↓
sync_local.py → tennis_garmin.db
         ↓
Git push → Desktop pulls for TennisAgent analysis
```

## Usage

```bash
cd ~/Mac/GarminAgent
source venv/bin/activate
python backend/scripts/sync_local.py        # Import from imports/ folder
```

## Data Import Options

| Method | Coverage | Notes |
|--------|----------|-------|
| **Bulk export** | All history | Request via Garmin account settings, ~72hr cooldown |
| AirDrop per file | Single activity | Garmin Connect → Activity → ⋮ → Export Original |

## Bulk Export Steps

1. Log into Garmin Connect web → Account Settings → Export Your Data
2. Wait for email with download link (can take hours)
3. Download and extract zip
4. Find .fit files in `DI_CONNECT/DI-Connect-Uploaded-Files/`
5. Unzip nested archives to `imports/`
6. Run `python backend/scripts/sync_local.py`

## Dependencies

- **fitparse**: Parse Garmin FIT binary files
