# GarminAgent

Imports Garmin activity data (HR, etc.) into SQLite database.

**Status (2024-12-29):** 336 activities imported, 373k HR samples. Database at `database/tennis_garmin.db`.

## Dependencies

- **fitparse**: Parse Garmin FIT binary files

## Usage

```bash
cd ~/Python/Mac/GarminAgent
source venv/bin/activate
python backend/scripts/init_database.py     # First time only
python backend/scripts/sync_local.py        # Import from imports/ folder
```

## Data Import Options

| Method | Coverage | Notes |
|--------|----------|-------|
| Garmin bulk export | All history | Request via Garmin account settings, ~72hr cooldown |
| AirDrop per file | Single activity | Garmin Connect → Activity → ⋮ → Export Original |
| iPhone backup | Recently viewed only | Cached activities, not full history |

## Bulk Export Workflow (recommended for historical data)

1. Log into Garmin Connect web → Account Settings → Export Your Data
2. Wait for email with download link
3. Download and extract zip
4. Find .fit files in `DI_CONNECT/DI-Connect-Uploaded-Files/`
5. Unzip to `imports/`
6. Run `python backend/scripts/sync_local.py`

## Future: Direct Android Access (roadmap)

Galaxy S10e (SM-G970x) has unlocked bootloader. To enable direct .fit file access:

### Step 1: Get TWRP for your exact model

- Check model: Settings → About Phone → Model Number
- Download from https://twrp.me/samsung/samsunggalaxys10e.html

### Step 2: Flash TWRP (from Linux or Windows)

```bash
# Linux - install heimdall
sudo apt install heimdall-flash

# Boot phone to Download Mode:
# Power off → hold Volume Down + Bixby → plug USB cable

# Flash TWRP
heimdall flash --RECOVERY twrp.img --no-reboot
```

Or use Odin on Windows (more reliable for Samsung).

### Step 3: Boot to TWRP immediately

- Hold Volume Up + Bixby + Power (before stock recovery overwrites TWRP)

### Step 4: Flash Magisk

- Copy Magisk APK to phone, rename to .zip
- In TWRP: Install → select Magisk.zip → swipe to flash
- Reboot, install Magisk Manager app

### Step 5: Grant root to shell

```bash
adb shell "su -c 'ls /data/data/com.garmin.connect.mobile/files/'"
```

### Notes

- Heimdall on macOS has install issues (system volume protection)
- Use Linux (`sudo apt install heimdall-flash`) or Windows (Odin)
- Samsung tries to restore stock recovery on first boot - go straight to TWRP
