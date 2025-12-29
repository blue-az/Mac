"""
Pydantic models for Garmin activity data.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class HeartRateSample(BaseModel):
    """Individual heart rate measurement."""
    timestamp: datetime
    heart_rate: int = Field(ge=0, le=300)

    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2024-01-15T10:30:45",
                "heart_rate": 142
            }
        }


class HeartRateZone(BaseModel):
    """Time spent in a heart rate zone."""
    zone_name: str
    min_hr: int
    max_hr: int
    seconds: int = 0

    @property
    def minutes(self) -> float:
        return self.seconds / 60.0


class HeartRateZones(BaseModel):
    """Heart rate zone breakdown for an activity."""
    zone1_recovery: HeartRateZone
    zone2_easy: HeartRateZone
    zone3_aerobic: HeartRateZone
    zone4_threshold: HeartRateZone
    zone5_vo2max: HeartRateZone
    zone6_anaerobic: HeartRateZone

    @classmethod
    def from_dict(cls, zones: Dict[str, Any]) -> "HeartRateZones":
        """Create HeartRateZones from parser output."""
        return cls(
            zone1_recovery=HeartRateZone(
                zone_name="Recovery",
                min_hr=zones["zone1"]["range"][0],
                max_hr=zones["zone1"]["range"][1],
                seconds=zones["zone1"]["seconds"]
            ),
            zone2_easy=HeartRateZone(
                zone_name="Easy",
                min_hr=zones["zone2"]["range"][0],
                max_hr=zones["zone2"]["range"][1],
                seconds=zones["zone2"]["seconds"]
            ),
            zone3_aerobic=HeartRateZone(
                zone_name="Aerobic",
                min_hr=zones["zone3"]["range"][0],
                max_hr=zones["zone3"]["range"][1],
                seconds=zones["zone3"]["seconds"]
            ),
            zone4_threshold=HeartRateZone(
                zone_name="Threshold",
                min_hr=zones["zone4"]["range"][0],
                max_hr=zones["zone4"]["range"][1],
                seconds=zones["zone4"]["seconds"]
            ),
            zone5_vo2max=HeartRateZone(
                zone_name="VO2max",
                min_hr=zones["zone5"]["range"][0],
                max_hr=zones["zone5"]["range"][1],
                seconds=zones["zone5"]["seconds"]
            ),
            zone6_anaerobic=HeartRateZone(
                zone_name="Anaerobic",
                min_hr=zones["zone6"]["range"][0],
                max_hr=zones["zone6"]["range"][1],
                seconds=zones["zone6"]["seconds"]
            )
        )


class ActivityData(BaseModel):
    """Activity metadata from a Garmin FIT file."""
    activity_id: Optional[int] = None
    fit_file_path: str
    activity_type: str = "unknown"
    sub_type: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    distance_meters: Optional[float] = None
    calories: Optional[int] = None
    avg_hr: Optional[int] = None
    max_hr: Optional[int] = None
    min_hr: Optional[int] = None
    hr_zones_json: Optional[str] = None
    data_json: Optional[str] = None

    @property
    def duration_minutes(self) -> Optional[float]:
        if self.duration_seconds:
            return self.duration_seconds / 60.0
        return None

    @property
    def distance_km(self) -> Optional[float]:
        if self.distance_meters:
            return self.distance_meters / 1000.0
        return None

    class Config:
        json_schema_extra = {
            "example": {
                "fit_file_path": "2024-01-15_Tennis.fit",
                "activity_type": "tennis",
                "start_time": "2024-01-15T10:00:00",
                "end_time": "2024-01-15T11:30:00",
                "duration_seconds": 5400,
                "calories": 450,
                "avg_hr": 135,
                "max_hr": 172
            }
        }


class SyncResult(BaseModel):
    """Result of a sync operation."""
    success: bool
    sync_time: datetime
    files_found: int = 0
    files_imported: int = 0
    files_skipped: int = 0
    activities: List[ActivityData] = []
    errors: List[str] = []
    device_info: Optional[Dict[str, str]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "sync_time": "2024-01-15T12:00:00",
                "files_found": 10,
                "files_imported": 3,
                "files_skipped": 7,
                "activities": [],
                "errors": []
            }
        }


class ActivityListResponse(BaseModel):
    """Response for listing activities."""
    total: int
    activities: List[ActivityData]


class ActivityDetailResponse(BaseModel):
    """Detailed activity response with HR samples."""
    activity: ActivityData
    hr_samples: List[HeartRateSample]
    hr_zones: Optional[HeartRateZones] = None
