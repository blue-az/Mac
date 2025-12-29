#!/usr/bin/env python3
"""
Swing Detector - Real-time tennis swing detection from Apple Watch sensor data
Adapted from swing_analyzer.py for streaming data processing

Uses sliding window buffer and scipy peak detection to identify swings in real-time
"""

import numpy as np
from collections import deque
from typing import List, Dict, Optional, Tuple
from scipy.signal import find_peaks
import time


class SensorSample:
    """Represents a single sensor reading from Apple Watch."""

    def __init__(self, timestamp: float, rotation_rate: Tuple[float, float, float],
                 gravity: Tuple[float, float, float], acceleration: Tuple[float, float, float],
                 quaternion: Tuple[float, float, float, float]):
        """
        Initialize sensor sample.

        Args:
            timestamp: Unix timestamp (seconds)
            rotation_rate: Gyroscope (x, y, z) in rad/s
            gravity: Gravity vector (x, y, z) normalized
            acceleration: User acceleration (x, y, z) in g
            quaternion: Device orientation (w, x, y, z)
        """
        self.timestamp = timestamp
        self.rotation_x, self.rotation_y, self.rotation_z = rotation_rate
        self.gravity_x, self.gravity_y, self.gravity_z = gravity
        self.accel_x, self.accel_y, self.accel_z = acceleration
        self.quat_w, self.quat_x, self.quat_y, self.quat_z = quaternion

    @property
    def rotation_magnitude(self) -> float:
        """Calculate magnitude of rotation vector (rad/s)."""
        return np.sqrt(self.rotation_x**2 + self.rotation_y**2 + self.rotation_z**2)

    @property
    def acceleration_magnitude(self) -> float:
        """Calculate magnitude of acceleration vector (g)."""
        return np.sqrt(self.accel_x**2 + self.accel_y**2 + self.accel_z**2)

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'timestamp': self.timestamp,
            'rotation_rate': {
                'x': self.rotation_x,
                'y': self.rotation_y,
                'z': self.rotation_z,
                'magnitude': self.rotation_magnitude
            },
            'gravity': {
                'x': self.gravity_x,
                'y': self.gravity_y,
                'z': self.gravity_z
            },
            'acceleration': {
                'x': self.accel_x,
                'y': self.accel_y,
                'z': self.accel_z,
                'magnitude': self.acceleration_magnitude
            },
            'quaternion': {
                'w': self.quat_w,
                'x': self.quat_x,
                'y': self.quat_y,
                'z': self.quat_z
            }
        }


class SwingPeak:
    """Represents a detected swing peak."""

    def __init__(self, timestamp: float, peak_index: int, rotation_magnitude: float,
                 acceleration_magnitude: float, sensor_data: SensorSample):
        """
        Initialize swing peak.

        Args:
            timestamp: Timestamp of peak detection
            peak_index: Index in buffer where peak occurred
            rotation_magnitude: Rotation magnitude at peak
            acceleration_magnitude: Acceleration magnitude at peak
            sensor_data: Full sensor data at peak
        """
        self.timestamp = timestamp
        self.peak_index = peak_index
        self.rotation_magnitude = rotation_magnitude
        self.acceleration_magnitude = acceleration_magnitude
        self.sensor_data = sensor_data

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'timestamp': self.timestamp,
            'peak_index': self.peak_index,
            'rotation_magnitude': self.rotation_magnitude,
            'acceleration_magnitude': self.acceleration_magnitude,
            'sensor_data': self.sensor_data.to_dict()
        }


class SwingDetector:
    """
    Real-time tennis swing detector using sliding window and peak detection.

    Based on swing_analyzer.py but adapted for streaming data.
    Uses scipy.find_peaks() to identify swings in rotation magnitude signal.
    """

    def __init__(self, buffer_size: int = 300, threshold: float = 2.0,
                 min_distance: int = 50, height_multiplier: float = 1.0):
        """
        Initialize swing detector.

        Args:
            buffer_size: Size of sliding window buffer (samples). Default 300 = 3s at 100Hz
            threshold: Minimum rotation magnitude (rad/s) to detect as swing. Default 2.0
            min_distance: Minimum samples between detected peaks (prevents duplicates). Default 50 = 0.5s
            height_multiplier: Multiplier for adaptive threshold. Default 1.0
        """
        self.buffer_size = buffer_size
        self.threshold = threshold
        self.min_distance = min_distance
        self.height_multiplier = height_multiplier

        # Sliding window buffer
        self.buffer: deque[SensorSample] = deque(maxlen=buffer_size)

        # Track detected peaks to avoid duplicates
        self.last_peak_timestamp = 0.0
        self.min_peak_interval = 0.5  # seconds

        # Statistics
        self.total_samples_processed = 0
        self.total_peaks_detected = 0
        self.session_start_time = time.time()

    def process_sample(self, sample: SensorSample) -> List[SwingPeak]:
        """
        Process a single sensor sample and detect any new swings.

        Args:
            sample: SensorSample to process

        Returns:
            List of newly detected SwingPeak objects (usually 0 or 1)
        """
        return self.process_batch([sample])

    def process_batch(self, samples: List[SensorSample]) -> List[SwingPeak]:
        """
        Process a batch of sensor samples and detect swings.

        This is the main entry point for real-time detection.

        Args:
            samples: List of SensorSample objects to process

        Returns:
            List of detected SwingPeak objects
        """
        if not samples:
            return []

        # Add samples to buffer
        self.buffer.extend(samples)
        self.total_samples_processed += len(samples)

        # Need minimum buffer size to detect peaks
        if len(self.buffer) < self.min_distance * 2:
            return []

        # Extract rotation magnitudes from buffer
        magnitudes = np.array([s.rotation_magnitude for s in self.buffer])
        timestamps = np.array([s.timestamp for s in self.buffer])

        # Detect peaks using scipy
        peaks, properties = find_peaks(
            magnitudes,
            height=self.threshold,
            distance=self.min_distance
        )

        # Filter peaks that are too close to previous detections
        detected_swings = []
        for peak_idx in peaks:
            peak_timestamp = timestamps[peak_idx]

            # Skip if too close to last detected peak
            if peak_timestamp - self.last_peak_timestamp < self.min_peak_interval:
                continue

            # Create SwingPeak object
            sample_at_peak = list(self.buffer)[peak_idx]
            swing_peak = SwingPeak(
                timestamp=peak_timestamp,
                peak_index=peak_idx,
                rotation_magnitude=magnitudes[peak_idx],
                acceleration_magnitude=sample_at_peak.acceleration_magnitude,
                sensor_data=sample_at_peak
            )

            detected_swings.append(swing_peak)
            self.last_peak_timestamp = peak_timestamp
            self.total_peaks_detected += 1

        return detected_swings

    def reset(self):
        """Reset detector state (clears buffer and statistics)."""
        self.buffer.clear()
        self.last_peak_timestamp = 0.0
        self.total_samples_processed = 0
        self.total_peaks_detected = 0
        self.session_start_time = time.time()

    def get_statistics(self) -> Dict:
        """Get detector statistics."""
        elapsed_time = time.time() - self.session_start_time
        sample_rate = self.total_samples_processed / elapsed_time if elapsed_time > 0 else 0

        return {
            'total_samples_processed': self.total_samples_processed,
            'total_peaks_detected': self.total_peaks_detected,
            'buffer_size': len(self.buffer),
            'buffer_capacity': self.buffer_size,
            'elapsed_time_seconds': elapsed_time,
            'sample_rate_hz': sample_rate,
            'threshold': self.threshold,
            'min_distance': self.min_distance
        }


def estimate_swing_speed(peak: SwingPeak) -> float:
    """
    Estimate racket speed from sensor data.

    This is a simplified estimation based on rotation magnitude.
    More sophisticated models could use acceleration, quaternion, and machine learning.

    Args:
        peak: SwingPeak object

    Returns:
        Estimated speed in mph
    """
    # Simplified conversion: rotation_magnitude (rad/s) * arm_length * conversion
    # Assuming average arm length ~0.6m and racket extension
    arm_length_m = 0.6
    racket_length_m = 0.7
    total_length_m = arm_length_m + racket_length_m  # ~1.3m

    # Linear velocity = angular_velocity * radius
    linear_velocity_ms = peak.rotation_magnitude * total_length_m

    # Convert m/s to mph
    mph = linear_velocity_ms * 2.237

    return mph


def classify_swing_type(peak: SwingPeak) -> str:
    """
    Classify swing type based on sensor data.

    This is a placeholder for future ML-based classification.
    Currently returns 'unknown' pending proper training data.

    Args:
        peak: SwingPeak object

    Returns:
        Swing type: 'forehand', 'backhand', 'serve', 'volley', or 'unknown'
    """
    # TODO: Implement ML-based classification
    # Could use quaternion orientation, acceleration patterns, etc.
    return 'unknown'


# Example usage
if __name__ == '__main__':
    print("SwingDetector Example\n" + "="*50)

    # Create detector
    detector = SwingDetector(
        buffer_size=300,    # 3 seconds at 100Hz
        threshold=2.0,      # rad/s
        min_distance=50     # 0.5 seconds between peaks
    )

    # Simulate sensor data
    print("Simulating sensor data stream...\n")

    for i in range(500):
        # Generate synthetic data with occasional peaks
        t = i * 0.01  # 100Hz = 10ms per sample

        # Create a swing peak around t=2.0s
        if 1.5 < t < 2.5:
            rotation_mag = 3.0 * np.sin((t - 1.5) * 3.14 / 1.0)
        else:
            rotation_mag = 0.5 + 0.2 * np.random.randn()

        # Decompose into x, y, z (simplified)
        rotation_x = rotation_mag * 0.7
        rotation_y = rotation_mag * 0.3
        rotation_z = rotation_mag * 0.1

        # Create sample
        sample = SensorSample(
            timestamp=time.time() + t,
            rotation_rate=(rotation_x, rotation_y, rotation_z),
            gravity=(0.0, -1.0, 0.0),
            acceleration=(0.1, 0.2, 0.05),
            quaternion=(1.0, 0.0, 0.0, 0.0)
        )

        # Process sample
        detected_peaks = detector.process_sample(sample)

        # Print detected swings
        for peak in detected_peaks:
            print(f"🎾 Swing Detected!")
            print(f"   Timestamp: {peak.timestamp:.3f}")
            print(f"   Rotation Magnitude: {peak.rotation_magnitude:.2f} rad/s")
            print(f"   Acceleration Magnitude: {peak.acceleration_magnitude:.2f} g")
            print(f"   Estimated Speed: {estimate_swing_speed(peak):.1f} mph")
            print()

    # Print statistics
    stats = detector.get_statistics()
    print(f"\nDetector Statistics:")
    print(f"   Total Samples: {stats['total_samples_processed']}")
    print(f"   Total Peaks: {stats['total_peaks_detected']}")
    print(f"   Sample Rate: {stats['sample_rate_hz']:.1f} Hz")
    print(f"   Buffer Usage: {stats['buffer_size']}/{stats['buffer_capacity']}")
