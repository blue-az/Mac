"""
iPhone access service using pymobiledevice3.

Provides functionality to:
- Detect connected iPhone devices
- Access Garmin Connect app container
- Find and download FIT files

Uses pymobiledevice3 (pure Python) instead of libimobiledevice CLI tools.
"""

import os
import tempfile
from pathlib import Path
from typing import List, Optional, Dict, Any
import shutil

try:
    from pymobiledevice3.lockdown import create_using_usbmux
    from pymobiledevice3.services.afc import AfcService
    from pymobiledevice3.services.house_arrest import HouseArrestService
    from pymobiledevice3.exceptions import PyMobileDevice3Exception
    PYMOBILEDEVICE3_AVAILABLE = True
except ImportError:
    PYMOBILEDEVICE3_AVAILABLE = False
    print("Warning: pymobiledevice3 not installed. Run: pip install pymobiledevice3")


class iPhoneMounter:
    """Access iPhone app data using pymobiledevice3."""

    GARMIN_BUNDLE_ID = "com.garmin.connect.mobile"

    def __init__(self, download_dir: str = "./downloads"):
        self.download_dir = Path(download_dir).resolve()
        self._lockdown = None
        self._device_info: Dict[str, Any] = {}

    def is_device_connected(self) -> bool:
        """Check if an iPhone is connected via USB."""
        if not PYMOBILEDEVICE3_AVAILABLE:
            print("pymobiledevice3 not available")
            return False

        try:
            self._lockdown = create_using_usbmux()
            self._device_info = {
                "DeviceName": self._lockdown.display_name,
                "ProductVersion": self._lockdown.product_version,
                "ProductType": self._lockdown.product_type,
                "UniqueDeviceID": self._lockdown.udid,
            }
            return True
        except PyMobileDevice3Exception as e:
            print(f"No device connected: {e}")
            return False
        except Exception as e:
            print(f"Error connecting to device: {e}")
            return False

    def get_device_info(self) -> Dict[str, Any]:
        """Get information about the connected iPhone."""
        if not self._lockdown:
            if not self.is_device_connected():
                return {}
        return self._device_info

    def _get_house_arrest_service(self) -> Optional[Any]:
        """Get HouseArrest service for app container access."""
        if not self._lockdown:
            if not self.is_device_connected():
                return None

        try:
            return HouseArrestService(self._lockdown, bundle_id=self.GARMIN_BUNDLE_ID)
        except PyMobileDevice3Exception as e:
            print(f"Error accessing Garmin container: {e}")
            print("Ensure Garmin Connect is installed on the device")
            return None

    def find_fit_files(self) -> List[Dict[str, Any]]:
        """Find all FIT files in the Garmin Connect container."""
        house_arrest = self._get_house_arrest_service()
        if not house_arrest:
            return []

        fit_files = []
        try:
            afc = house_arrest.afc

            def scan_directory(path: str):
                """Recursively scan for FIT files."""
                try:
                    entries = afc.listdir(path)
                    for entry in entries:
                        if entry in (".", ".."):
                            continue
                        full_path = f"{path}/{entry}" if path != "/" else f"/{entry}"
                        try:
                            info = afc.stat(full_path)
                            if info.get("st_ifmt") == "S_IFDIR":
                                scan_directory(full_path)
                            elif entry.lower().endswith(".fit"):
                                fit_files.append({
                                    "path": full_path,
                                    "name": entry,
                                    "size": info.get("st_size", 0),
                                    "mtime": info.get("st_mtime", 0)
                                })
                        except Exception:
                            continue
                except Exception as e:
                    print(f"Error scanning {path}: {e}")

            # Scan Documents and other common locations
            for base in ["/Documents", "/Library", "/"]:
                try:
                    scan_directory(base)
                except Exception:
                    continue

        except Exception as e:
            print(f"Error finding FIT files: {e}")

        # Sort by modification time (newest first)
        fit_files.sort(key=lambda x: x.get("mtime", 0), reverse=True)
        return fit_files

    def download_fit_file(self, remote_path: str, local_path: Optional[Path] = None) -> Optional[Path]:
        """Download a single FIT file from the device."""
        house_arrest = self._get_house_arrest_service()
        if not house_arrest:
            return None

        try:
            afc = house_arrest.afc

            # Determine local path
            if local_path is None:
                self.download_dir.mkdir(parents=True, exist_ok=True)
                filename = Path(remote_path).name
                local_path = self.download_dir / filename

            # Download file
            data = afc.get_file_contents(remote_path)
            local_path.write_bytes(data)
            print(f"Downloaded: {remote_path} -> {local_path}")
            return local_path

        except Exception as e:
            print(f"Error downloading {remote_path}: {e}")
            return None

    def download_all_fit_files(self, limit: Optional[int] = None) -> List[Path]:
        """Download all FIT files from the device."""
        fit_files = self.find_fit_files()
        if limit:
            fit_files = fit_files[:limit]

        self.download_dir.mkdir(parents=True, exist_ok=True)
        downloaded = []

        for fit_info in fit_files:
            local_path = self.download_dir / fit_info["name"]

            # Skip if already downloaded and same size
            if local_path.exists():
                if local_path.stat().st_size == fit_info["size"]:
                    print(f"Skipped (exists): {fit_info['name']}")
                    downloaded.append(local_path)
                    continue

            result = self.download_fit_file(fit_info["path"], local_path)
            if result:
                downloaded.append(result)

        return downloaded

    def list_fit_files(self) -> None:
        """Print list of FIT files on device."""
        fit_files = self.find_fit_files()
        print(f"\nFound {len(fit_files)} FIT files:\n")

        for i, f in enumerate(fit_files, 1):
            size_kb = f["size"] / 1024
            print(f"  {i:3}. {f['name']} ({size_kb:.1f} KB)")
            print(f"       Path: {f['path']}")


# Fallback to CLI tools if pymobiledevice3 not available
class iPhoneMounterCLI:
    """Fallback using libimobiledevice CLI tools."""

    GARMIN_BUNDLE_ID = "com.garmin.connect.mobile"

    def __init__(self, mount_point: str = "./mnt"):
        self.mount_point = Path(mount_point).resolve()
        self._device_udid: Optional[str] = None

    def is_device_connected(self) -> bool:
        """Check if an iPhone is connected via USB."""
        import subprocess
        try:
            result = subprocess.run(
                ["idevice_id", "-l"],
                capture_output=True,
                text=True,
                timeout=10
            )
            devices = result.stdout.strip().split("\n")
            devices = [d for d in devices if d]
            if devices:
                self._device_udid = devices[0]
                return True
            return False
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"Error checking device: {e}")
            return False

    def get_device_info(self) -> dict:
        """Get information about the connected iPhone."""
        import subprocess
        if not self._device_udid:
            if not self.is_device_connected():
                return {}

        try:
            result = subprocess.run(
                ["ideviceinfo", "-u", self._device_udid],
                capture_output=True,
                text=True,
                timeout=30
            )
            info = {}
            for line in result.stdout.strip().split("\n"):
                if ": " in line:
                    key, value = line.split(": ", 1)
                    info[key.strip()] = value.strip()
            return info
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"Error getting device info: {e}")
            return {}
