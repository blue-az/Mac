import numpy as np
from scipy.signal import butter, lfilter, savgol_filter
from collections import deque
from typing import List, Dict, Optional, Tuple
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
    SPEED_THRESHOLD = 9.5      # rad/s — raised from 8.0 to match Zepp floor
    SERVE_SPEED_THRESHOLD = 20.0
    SERVE_STRONG_PEAK = 28.0
    AXIS_DOMINANCE = 0.38      # real tennis swings are 3D; 20 rad/s swing logged at 43.5%
    SERVE_AXIS_DOMINANCE = 0.55
    SUSTAINED_SAMPLES = 5      # 50ms at 100Hz
    SERVE_SUSTAINED_SAMPLES = 10
    SERVE_MEDIUM_SUSTAINED_SAMPLES = 17
    COOLDOWN = 2.5             # seconds — raised from 1.5 to suppress double-fires
    # Not a detection threshold: how far to look in self.buffer when a serve is
    # split across the Watch's ~50-sample (~0.5s) batches.
    SERVE_MERGE_WINDOW_SEC = 0.35

    def __init__(self, oracle: TennisOracle):
        self.oracle = oracle
        self.buffer = deque(maxlen=1000)
        self.cooldown_until = 0
        self._timefn = time.time
        self._pending_medium = None  # serve split across batches; axis already passed

    @staticmethod
    def _rotation_mag(sample: Dict) -> float:
        return float(np.sqrt(
            sample['rotationRateX']**2 + sample['rotationRateY']**2 + sample['rotationRateZ']**2
        ))

    @staticmethod
    def _sample_ts(sample: Optional[Dict]) -> Optional[float]:
        if not sample:
            return None
        ts = sample.get('timestamp')
        try:
            return float(ts) if ts is not None else None
        except (TypeError, ValueError):
            return None

    def _sensor_now(self, samples: List[Dict], peak_sample: Optional[Dict] = None) -> float:
        for s in (peak_sample, samples[-1] if samples else None):
            ts = self._sample_ts(s)
            if ts is not None:
                return ts
        return self._timefn()

    def _merged_sustained(self, peak_sample: Dict, batch_peak: float) -> int:
        """Count samples near the peak that stay above 50% of batch_peak.

        Live detection is per ~50-sample batch; a real serve often straddles two.
        Only used to re-evaluate the medium-serve sustained gate.
        """
        half = self.SERVE_MERGE_WINDOW_SEC
        thresh = batch_peak * 0.5
        peak_ts = peak_sample.get('timestamp')
        try:
            peak_ts = float(peak_ts) if peak_ts is not None else None
        except (TypeError, ValueError):
            peak_ts = None

        if peak_ts is None:
            window = list(self.buffer)[-80:]
            return sum(1 for s in window if self._rotation_mag(s) > thresh)

        count = 0
        for s in self.buffer:
            ts = s.get('timestamp')
            try:
                ts = float(ts) if ts is not None else None
            except (TypeError, ValueError):
                continue
            if ts is None or abs(ts - peak_ts) > half:
                continue
            if self._rotation_mag(s) > thresh:
                count += 1
        return count

    def _emit_shot(self, *, peak_sample: Dict, batch_peak: float, dominance_ratio: float,
                   sustained: int, mode: str, hr_bpm: int, current_time: float) -> Dict:
        clean_contact = dominance_ratio > 0.70
        corrected_peak = batch_peak * 2.5
        speed_mph = corrected_peak * 1.4
        fatigued, readiness = self.oracle.predict_fatigue(1.0)
        event_ts = self._sample_ts(peak_sample)
        if event_ts is None:
            event_ts = current_time
        self.cooldown_until = event_ts + self.COOLDOWN
        print(f"🎾 Shot! Peak={batch_peak:.2f} rad/s → {speed_mph:.1f} MPH | "
              f"clean={clean_contact} sustained={sustained*10}ms")
        return {
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(event_ts)),
            "shot_id": str(int(event_ts)),
            "mode": mode,
            "metrics": {
                "score": 85.0,
                "speed_mph": speed_mph,
                "spin_rpm": None,
                "readiness_pct": readiness,
                "hr_bpm": int(hr_bpm),
            },
            "flags": {
                "micro_fatigue": fatigued,
                "oracle_grounded": True,
                "clean_contact": clean_contact,
            },
            "peak_rad": batch_peak,
            "peak_sample": {
                "quat_w": peak_sample.get('quaternionW'),
                "quat_x": peak_sample.get('quaternionX'),
                "quat_y": peak_sample.get('quaternionY'),
                "quat_z": peak_sample.get('quaternionZ'),
                "rot_x":  peak_sample.get('rotationRateX'),
                "rot_y":  peak_sample.get('rotationRateY'),
                "rot_z":  peak_sample.get('rotationRateZ'),
            },
        }

    def _resolve_pending_medium(self, samples: List[Dict], current_time: float):
        pending = self._pending_medium
        if not pending:
            return None
        merged = self._merged_sustained(pending["peak_sample"], pending["batch_peak"])
        if merged >= self.SERVE_MEDIUM_SUSTAINED_SAMPLES:
            self._pending_medium = None
            hr = samples[-1].get("heartRate", 70) if samples else 70
            return self._emit_shot(
                peak_sample=pending["peak_sample"],
                batch_peak=pending["batch_peak"],
                dominance_ratio=pending["dominance_ratio"],
                sustained=merged,
                mode=pending["mode"],
                hr_bpm=hr,
                current_time=current_time,
            )
        peak_ts = pending["peak_sample"].get("timestamp")
        last_ts = samples[-1].get("timestamp") if samples else None
        try:
            peak_ts = float(peak_ts) if peak_ts is not None else None
            last_ts = float(last_ts) if last_ts is not None else None
        except (TypeError, ValueError):
            peak_ts = last_ts = None
        if peak_ts is None or last_ts is None or (last_ts - peak_ts) > (self.SERVE_MERGE_WINDOW_SEC * 2):
            print(
                f"🚫 Noise: medium serve peak without sustained motion "
                f"({pending.get('batch_sustained', 0)} samples)"
            )
            self._pending_medium = None
        return None

    def process_samples(self, samples: List[Dict], mode: str = "strokes") -> List[Dict]:
        results = []
        current_time = self._sensor_now(samples)

        for s in samples:
            self.buffer.append(s)

        if not samples:
            return []

        current_time = self._sensor_now(samples)
        if current_time >= self.cooldown_until:
            resolved = self._resolve_pending_medium(samples, current_time)
            if resolved:
                results.append(resolved)

        if self._sensor_now(samples) < self.cooldown_until:
            return results

        batch_mags = [self._rotation_mag(s) for s in samples]
        batch_peak = max(batch_mags)

        is_serve = mode == "serve"
        threshold = self.SERVE_SPEED_THRESHOLD if is_serve else self.SPEED_THRESHOLD
        axis_dominance_threshold = self.SERVE_AXIS_DOMINANCE if is_serve else self.AXIS_DOMINANCE
        sustained_threshold = self.SERVE_SUSTAINED_SAMPLES if is_serve else self.SUSTAINED_SAMPLES

        if batch_peak > 1.0:
            label = "LOW" if batch_peak < threshold else "MED" if batch_peak < 18.0 else "HIGH"
            print(f"TRACE [{mode.upper()}] [{label}] Peak={batch_peak:.2f} rad/s")

        if batch_peak > threshold:
            peak_sample = samples[int(np.argmax(batch_mags))]
            peak_ts = self._sample_ts(peak_sample)
            if peak_ts is not None and peak_ts < self.cooldown_until:
                return results
            axes = [
                abs(peak_sample['rotationRateX']),
                abs(peak_sample['rotationRateY']),
                abs(peak_sample['rotationRateZ'])
            ]
            dominant_axis = max(axes)
            total_rotation = sum(axes)
            dominance_ratio = dominant_axis / total_rotation
            is_planar = dominance_ratio > axis_dominance_threshold

            sustained = sum(1 for m in batch_mags if m > (batch_peak * 0.5))
            is_sustained = sustained > sustained_threshold

            if not is_planar:
                print(f"🚫 Noise: chaotic rotation ({dominance_ratio:.1%})")
                return results

            if not is_sustained:
                print(f"🚫 Noise: short burst ({sustained} samples)")
                return results

            if is_serve and batch_peak < self.SERVE_STRONG_PEAK and sustained < self.SERVE_MEDIUM_SUSTAINED_SAMPLES:
                merged = self._merged_sustained(peak_sample, batch_peak)
                if merged >= self.SERVE_MEDIUM_SUSTAINED_SAMPLES:
                    sustained = merged
                else:
                    # Tail often arrives in the next ~50-sample batch. Hold axis-clean
                    # candidate; resolve after the adjacent batch is in self.buffer.
                    self._pending_medium = {
                        "peak_sample": peak_sample,
                        "batch_peak": batch_peak,
                        "dominance_ratio": dominance_ratio,
                        "mode": mode,
                        "batch_sustained": sustained,
                    }
                    return results

            results.append(self._emit_shot(
                peak_sample=peak_sample,
                batch_peak=batch_peak,
                dominance_ratio=dominance_ratio,
                sustained=sustained,
                mode=mode,
                hr_bpm=samples[-1].get("heartRate", 70),
                current_time=current_time,
            ))

        return results
