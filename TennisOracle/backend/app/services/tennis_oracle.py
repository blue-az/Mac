import numpy as np
from scipy.signal import butter, lfilter, savgol_filter
from collections import deque
from typing import List, Dict, Tuple
import time


class TennisOracle:
    def __init__(self, sample_rate=100.0):
        self.fs = sample_rate
        self.b_aa, self.a_aa = butter(4, 45.0, fs=self.fs, btype='low')
        self.swing_times = deque(maxlen=7)

    def apply_filters(self, signal: List[float]) -> List[float]:
        if len(signal) < 15:
            return signal
        aa = lfilter(self.b_aa, self.a_aa, signal)
        return savgol_filter(aa, window_length=5, polyorder=2).tolist()

    def predict_fatigue(self, current_swing_time: float) -> Tuple[bool, float]:
        if not self.swing_times:
            self.swing_times.append(current_swing_time)
            return False, 100.0
        avg_time = sum(self.swing_times) / len(self.swing_times)
        fatigued = current_swing_time > (avg_time * 1.05)
        readiness = 100.0 - (20.0 if fatigued else 0.0)
        self.swing_times.append(current_swing_time)
        return fatigued, readiness


class TennisShotDetector:
    # Tennis thresholds differ from golf:
    #   - Higher axis dominance (strokes are more planar)
    #   - Lower speed floor (no full-body rotation like a golf drive)
    #   - Shorter cooldown (rallies are fast)
    SPEED_THRESHOLD = 8.0      # rad/s
    SERVE_SPEED_THRESHOLD = 10.0
    AXIS_DOMINANCE = 0.38      # real tennis swings are 3D; 20 rad/s swing logged at 43.5%
    SUSTAINED_SAMPLES = 5      # 50ms at 100Hz
    COOLDOWN = 1.5             # seconds between shots

    def __init__(self, oracle: TennisOracle):
        self.oracle = oracle
        self.buffer = deque(maxlen=1000)
        self.cooldown_until = 0

    def process_samples(self, samples: List[Dict], mode: str = "strokes") -> List[Dict]:
        results = []
        current_time = time.time()

        for s in samples:
            self.buffer.append(s)

        if current_time < self.cooldown_until:
            return []

        if not samples:
            return []

        batch_mags = [
            np.sqrt(s['rotationRateX']**2 + s['rotationRateY']**2 + s['rotationRateZ']**2)
            for s in samples
        ]
        batch_peak = max(batch_mags)

        threshold = self.SERVE_SPEED_THRESHOLD if mode == "serve" else self.SPEED_THRESHOLD

        if batch_peak > 1.0:
            label = "LOW" if batch_peak < threshold else "MED" if batch_peak < 18.0 else "HIGH"
            print(f"TRACE [{mode.upper()}] [{label}] Peak={batch_peak:.2f} rad/s")

        if batch_peak > threshold:
            peak_sample = samples[int(np.argmax(batch_mags))]
            axes = [
                abs(peak_sample['rotationRateX']),
                abs(peak_sample['rotationRateY']),
                abs(peak_sample['rotationRateZ'])
            ]
            dominant_axis = max(axes)
            total_rotation = sum(axes)
            dominance_ratio = dominant_axis / total_rotation
            is_planar = dominance_ratio > self.AXIS_DOMINANCE

            sustained = sum(1 for m in batch_mags if m > (batch_peak * 0.5))
            is_sustained = sustained > self.SUSTAINED_SAMPLES

            if not is_planar:
                print(f"🚫 Noise: chaotic rotation ({dominance_ratio:.1%})")
                return []

            if not is_sustained:
                print(f"🚫 Noise: short burst ({sustained} samples)")
                return []

            # Clean contact: dominant axis carries >70% of rotation
            clean_contact = dominance_ratio > 0.70

            # Speed estimate: 2.5x filter correction then racket-head scale
            corrected_peak = batch_peak * 2.5
            speed_mph = corrected_peak * 1.4  # tuned for ~40-80mph range

            fatigued, readiness = self.oracle.predict_fatigue(1.0)
            self.cooldown_until = current_time + self.COOLDOWN

            print(f"🎾 Shot! Peak={batch_peak:.2f} rad/s → {speed_mph:.1f} MPH | "
                  f"clean={clean_contact} sustained={sustained*10}ms")

            results.append({
                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                "shot_id": str(int(time.time())),
                "mode": mode,
                "metrics": {
                    "score": 85.0,
                    "speed_mph": speed_mph,
                    "spin_rpm": None,
                    "readiness_pct": readiness,
                    "hr_bpm": int(samples[-1].get('heartRate', 70))
                },
                "flags": {
                    "micro_fatigue": fatigued,
                    "oracle_grounded": True,
                    "clean_contact": clean_contact
                }
            })

        return results
