"""
Pydantic models for sensor data and swings.
Defines data structures for API requests/responses and database storage.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class SensorSampleModel(BaseModel):
    """Sensor sample from Apple Watch CMMotionManager."""

    timestamp: float = Field(..., description="Unix timestamp in seconds")
    rotationRateX: float = Field(..., description="Gyroscope X (rad/s)")
    rotationRateY: float = Field(..., description="Gyroscope Y (rad/s)")
    rotationRateZ: float = Field(..., description="Gyroscope Z (rad/s)")
    gravityX: float = Field(..., description="Gravity vector X (normalized)")
    gravityY: float = Field(..., description="Gravity vector Y (normalized)")
    gravityZ: float = Field(..., description="Gravity vector Z (normalized)")
    accelerationX: float = Field(..., description="User acceleration X (g)")
    accelerationY: float = Field(..., description="User acceleration Y (g)")
    accelerationZ: float = Field(..., description="User acceleration Z (g)")
    quaternionW: float = Field(..., description="Quaternion W component")
    quaternionX: float = Field(..., description="Quaternion X component")
    quaternionY: float = Field(..., description="Quaternion Y component")
    quaternionZ: float = Field(..., description="Quaternion Z component")

    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": 1718329315.629,
                "rotationRateX": 0.208,
                "rotationRateY": 0.033,
                "rotationRateZ": -0.130,
                "gravityX": 0.424,
                "gravityY": 0.722,
                "gravityZ": -0.546,
                "accelerationX": -0.025,
                "accelerationY": -0.023,
                "accelerationZ": -0.050,
                "quaternionW": 0.879,
                "quaternionX": -0.411,
                "quaternionY": 0.241,
                "quaternionZ": 0.000
            }
        }


class SensorBatchMessage(BaseModel):
    """WebSocket message containing a batch of sensor samples."""

    type: str = Field(default="sensor_batch", description="Message type")
    session_id: str = Field(..., description="Session identifier")
    device: str = Field(default="AppleWatch", description="Device name")
    samples: List[SensorSampleModel] = Field(..., description="Array of sensor samples")

    class Config:
        json_schema_extra = {
            "example": {
                "type": "sensor_batch",
                "session_id": "watch_20241107_143025",
                "device": "AppleWatch",
                "samples": [
                    {
                        "timestamp": 1718329315.629,
                        "rotationRateX": 0.208,
                        "rotationRateY": 0.033,
                        "rotationRateZ": -0.130,
                        "gravityX": 0.424,
                        "gravityY": 0.722,
                        "gravityZ": -0.546,
                        "accelerationX": -0.025,
                        "accelerationY": -0.023,
                        "accelerationZ": -0.050,
                        "quaternionW": 0.879,
                        "quaternionX": -0.411,
                        "quaternionY": 0.241,
                        "quaternionZ": 0.000
                    }
                ]
            }
        }


class SwingDetectedMessage(BaseModel):
    """WebSocket message sent when a swing is detected."""

    type: str = Field(default="swing_detected", description="Message type")
    session_id: str = Field(..., description="Session identifier")
    swing: Dict[str, Any] = Field(..., description="Detected swing data")

    class Config:
        json_schema_extra = {
            "example": {
                "type": "swing_detected",
                "session_id": "watch_20241107_143025",
                "swing": {
                    "swing_id": "shot_20241107_143201_001",
                    "timestamp": 1718329321.453,
                    "rotation_magnitude": 4.23,
                    "acceleration_magnitude": 2.15,
                    "estimated_speed_mph": 58.3
                }
            }
        }


class SessionStartMessage(BaseModel):
    """WebSocket message to start a session."""

    type: str = Field(default="session_start", description="Message type")
    session_id: str = Field(..., description="Session identifier")
    device: str = Field(default="AppleWatch", description="Device name")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional metadata")


class SessionEndMessage(BaseModel):
    """WebSocket message to end a session."""

    type: str = Field(default="session_end", description="Message type")
    session_id: str = Field(..., description="Session identifier")


class SessionSummaryResponse(BaseModel):
    """Response model for session summary."""

    session_id: str
    device: str
    date: str
    start_time: int
    end_time: Optional[int]
    duration_minutes: Optional[int]
    shot_count: int
    metadata: Dict[str, Any]


class SwingResponse(BaseModel):
    """Response model for individual swing/shot."""

    shot_id: str
    session_id: str
    timestamp: float
    sequence_number: int
    rotation_magnitude: float
    acceleration_magnitude: float
    shot_type: Optional[str]
    spin_type: Optional[str]
    speed_mph: Optional[float]
    power: Optional[float]
    consistency: Optional[float]
    data: Dict[str, Any]


class DetectorStatistics(BaseModel):
    """Statistics from the swing detector."""

    total_samples_processed: int
    total_peaks_detected: int
    buffer_size: int
    buffer_capacity: int
    elapsed_time_seconds: float
    sample_rate_hz: float
    threshold: float
    min_distance: int
