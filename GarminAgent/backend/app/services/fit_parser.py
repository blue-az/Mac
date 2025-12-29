"""
FIT file parser for Garmin activity data.

Extracts activity metadata and heart rate samples from Garmin FIT files
using the fitparse library.
"""

from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json

try:
    from fitparse import FitFile
except ImportError:
    FitFile = None
    print("Warning: fitparse not installed. Run: pip install fitparse")


class FitFileParser:
    """Parser for Garmin FIT binary files."""

    # FIT epoch starts at 1989-12-31 00:00:00 UTC
    FIT_EPOCH = datetime(1989, 12, 31, 0, 0, 0)

    def __init__(self, fit_path: Path):
        self.fit_path = Path(fit_path)
        self._fit_file: Optional[Any] = None
        self._records: List[Dict] = []
        self._session: Optional[Dict] = None
        self._hr_samples: List[Dict] = []

    def parse(self) -> bool:
        """Parse the FIT file and extract all data."""
        if FitFile is None:
            raise ImportError("fitparse library not installed")

        try:
            self._fit_file = FitFile(str(self.fit_path))
            self._extract_data()
            return True
        except Exception as e:
            print(f"Error parsing {self.fit_path}: {e}")
            return False

    def _extract_data(self):
        """Extract records and session data from parsed FIT file."""
        for record in self._fit_file.get_messages():
            record_type = record.name

            if record_type == "record":
                self._process_record(record)
            elif record_type == "session":
                self._process_session(record)
            elif record_type == "activity":
                self._process_activity(record)

    def _process_record(self, record):
        """Process a data record (contains HR, position, etc.)."""
        data = {}
        timestamp = None

        for field in record.fields:
            if field.name == "timestamp":
                timestamp = self._convert_timestamp(field.value)
                data["timestamp"] = timestamp
            elif field.name == "heart_rate":
                data["heart_rate"] = field.value
            elif field.name == "position_lat":
                data["latitude"] = self._semicircles_to_degrees(field.value)
            elif field.name == "position_long":
                data["longitude"] = self._semicircles_to_degrees(field.value)
            elif field.name == "altitude":
                data["altitude"] = field.value
            elif field.name == "speed":
                data["speed"] = field.value
            elif field.name == "cadence":
                data["cadence"] = field.value
            elif field.name == "distance":
                data["distance"] = field.value

        self._records.append(data)

        # Extract HR sample if present
        if timestamp and "heart_rate" in data and data["heart_rate"] is not None:
            self._hr_samples.append({
                "timestamp": timestamp,
                "heart_rate": data["heart_rate"]
            })

    def _process_session(self, record):
        """Process session record (summary data)."""
        session = {}

        for field in record.fields:
            if field.name == "start_time":
                session["start_time"] = self._convert_timestamp(field.value)
            elif field.name == "timestamp":
                session["end_time"] = self._convert_timestamp(field.value)
            elif field.name == "total_elapsed_time":
                session["duration_seconds"] = int(field.value) if field.value else None
            elif field.name == "total_distance":
                session["distance_meters"] = field.value
            elif field.name == "total_calories":
                session["calories"] = field.value
            elif field.name == "avg_heart_rate":
                session["avg_hr"] = field.value
            elif field.name == "max_heart_rate":
                session["max_hr"] = field.value
            elif field.name == "min_heart_rate":
                session["min_hr"] = field.value
            elif field.name == "sport":
                session["sport"] = str(field.value)
            elif field.name == "sub_sport":
                session["sub_sport"] = str(field.value)

        self._session = session

    def _process_activity(self, record):
        """Process activity record."""
        for field in record.fields:
            if field.name == "type":
                if self._session:
                    self._session["activity_type"] = str(field.value)

    def _convert_timestamp(self, value) -> Optional[datetime]:
        """Convert FIT timestamp to Python datetime."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, (int, float)):
            return self.FIT_EPOCH + timedelta(seconds=value)
        return None

    def _semicircles_to_degrees(self, semicircles) -> Optional[float]:
        """Convert FIT semicircles to decimal degrees."""
        if semicircles is None:
            return None
        return semicircles * (180.0 / 2**31)

    def extract_heart_rate(self) -> List[Dict]:
        """Get all heart rate samples from the parsed file."""
        return self._hr_samples

    def extract_metadata(self) -> Dict[str, Any]:
        """Get activity metadata from the parsed file."""
        if not self._session:
            return {}

        return {
            "activity_type": self._session.get("sport", "unknown"),
            "sub_type": self._session.get("sub_sport"),
            "start_time": self._session.get("start_time"),
            "end_time": self._session.get("end_time"),
            "duration_seconds": self._session.get("duration_seconds"),
            "distance_meters": self._session.get("distance_meters"),
            "calories": self._session.get("calories"),
            "avg_hr": self._session.get("avg_hr"),
            "max_hr": self._session.get("max_hr"),
            "min_hr": self._session.get("min_hr"),
            "fit_file": str(self.fit_path.name),
            "record_count": len(self._records),
            "hr_sample_count": len(self._hr_samples)
        }

    def get_hr_zones(self, max_hr: int = 190) -> Dict[str, Any]:
        """Calculate time spent in each heart rate zone."""
        zones = {
            "zone1": {"range": (0, int(max_hr * 0.5)), "seconds": 0},      # Recovery
            "zone2": {"range": (int(max_hr * 0.5), int(max_hr * 0.6)), "seconds": 0},  # Easy
            "zone3": {"range": (int(max_hr * 0.6), int(max_hr * 0.7)), "seconds": 0},  # Aerobic
            "zone4": {"range": (int(max_hr * 0.7), int(max_hr * 0.8)), "seconds": 0},  # Threshold
            "zone5": {"range": (int(max_hr * 0.8), int(max_hr * 0.9)), "seconds": 0},  # VO2max
            "zone6": {"range": (int(max_hr * 0.9), max_hr + 50), "seconds": 0}        # Anaerobic
        }

        if len(self._hr_samples) < 2:
            return zones

        # Calculate time in each zone
        for i in range(1, len(self._hr_samples)):
            hr = self._hr_samples[i]["heart_rate"]
            prev_ts = self._hr_samples[i - 1]["timestamp"]
            curr_ts = self._hr_samples[i]["timestamp"]

            if prev_ts and curr_ts:
                delta = (curr_ts - prev_ts).total_seconds()
                # Cap delta at 10 seconds to handle gaps
                delta = min(delta, 10)

                for zone_name, zone_data in zones.items():
                    low, high = zone_data["range"]
                    if low <= hr < high:
                        zones[zone_name]["seconds"] += delta
                        break

        return zones

    def to_dict(self) -> Dict[str, Any]:
        """Export all parsed data as a dictionary."""
        return {
            "metadata": self.extract_metadata(),
            "hr_zones": self.get_hr_zones(),
            "hr_samples": self._hr_samples,
            "records": self._records
        }
