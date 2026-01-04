#!/usr/bin/env python3
"""
Sprint 17: Prep USB for Desktop Transfer

Run on Mac to copy essential files to USB drive.
Desktop needs these to generate full Sprint 16 artifacts.

Usage:
    python prep_usb.py /Volumes/USB_DRIVE_NAME
"""

import sys
import shutil
from pathlib import Path

# Source locations on Mac
TENNIS_DIR = Path.home() / "Tennis"
FRAMES_DIR = TENNIS_DIR / "frames"
VIDEOS_DIR = Path.home() / "Movies" / "Tennis"  # Or wherever videos live
ZEPP_DB = Path.home() / "Tennis" / "data" / "ztennis.db"

# What to copy
REQUIRED_FILES = {
    "frames": FRAMES_DIR,           # Extracted JPGs with labels
    "videos": VIDEOS_DIR,           # Raw .MOV files
    "ztennis.db": ZEPP_DB,          # Zepp database
}

def prep_usb(usb_path: str):
    usb = Path(usb_path)

    if not usb.exists():
        print(f"ERROR: USB path not found: {usb}")
        sys.exit(1)

    dest = usb / "Tennis_Transfer"
    dest.mkdir(exist_ok=True)

    print(f"Preparing USB at: {dest}")
    print("=" * 50)

    # Copy frames (with labels and manifests)
    if FRAMES_DIR.exists():
        print(f"\n📁 Copying frames...")
        for session_dir in FRAMES_DIR.iterdir():
            if session_dir.is_dir():
                session_dest = dest / "frames" / session_dir.name
                if session_dest.exists():
                    print(f"   Skipping {session_dir.name} (already exists)")
                else:
                    print(f"   {session_dir.name}...")
                    shutil.copytree(session_dir, session_dest)
    else:
        print(f"⚠️  No frames directory at {FRAMES_DIR}")

    # Copy videos
    if VIDEOS_DIR.exists():
        print(f"\n🎬 Copying videos...")
        video_dest = dest / "videos"
        video_dest.mkdir(exist_ok=True)
        for video in VIDEOS_DIR.glob("*.MOV"):
            target = video_dest / video.name
            if target.exists():
                print(f"   Skipping {video.name} (already exists)")
            else:
                print(f"   {video.name} ({video.stat().st_size // 1024 // 1024} MB)...")
                shutil.copy2(video, target)
    else:
        print(f"⚠️  No videos directory at {VIDEOS_DIR}")

    # Copy Zepp database
    if ZEPP_DB.exists():
        print(f"\n🗄️  Copying ztennis.db...")
        data_dest = dest / "data"
        data_dest.mkdir(exist_ok=True)
        shutil.copy2(ZEPP_DB, data_dest / "ztennis.db")
        print(f"   {ZEPP_DB.stat().st_size // 1024 // 1024} MB")
    else:
        print(f"⚠️  No Zepp database at {ZEPP_DB}")

    # Summary
    print("\n" + "=" * 50)
    print("✅ USB prep complete!")
    print(f"\nContents of {dest}:")
    for item in dest.rglob("*"):
        if item.is_file():
            rel = item.relative_to(dest)
            size = item.stat().st_size // 1024
            print(f"   {rel} ({size} KB)")

    print(f"\n📌 On Desktop, run:")
    print(f"   cp -r /run/media/blueaz/USB_NAME/Tennis_Transfer/* ~/Tennis/")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        print("\nAvailable volumes:")
        volumes = Path("/Volumes")
        if volumes.exists():
            for v in volumes.iterdir():
                if v.name not in ["Macintosh HD", "Recovery"]:
                    print(f"   {v}")
        sys.exit(1)

    prep_usb(sys.argv[1])
