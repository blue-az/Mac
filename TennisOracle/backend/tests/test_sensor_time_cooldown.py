"""Sensor-time timestamps and cooldown (SENSOR_TIME_FIX).

Does not rewrite persisted oracle_shots / 194708 rows.
"""
from __future__ import annotations

import csv
import io
import sqlite3
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.services.tennis_oracle import TennisOracle, TennisShotDetector  # noqa: E402
from tests.test_serve_cross_batch import _batch  # noqa: E402

DB_PATH = Path("/Users/blueaz/Python/Mac/tennis_sessions.db")
SESSION_ID = "oracle_20260916_194708"

# Cluster that wall-clock cooldown ate; sensor Δt between these is >2.5s.
# z21692/z21695 stay inside 2.5s of the previous *sensor* peak — still refractory.
EXPECT_RECOVERED = [
    (1789613731.556, 17.81, 21686),
    (1789613734.754, 16.89, 21687),
    (1789613739.223, 16.63, 21688),
    (1789613744.436, 13.49, 21689),
    (1789613747.406, 15.84, 21690),
]
STILL_REFRACTORY = [
    (1789613754.019, 13.78, 21692),
    (1789613761.447, 15.63, 21695),
]


def _parse_ts(iso: str) -> float:
    return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()


class SyntheticSensorCooldown(unittest.TestCase):
    def test_one_second_sensor_gap_one_wall_clock_flush_single_shot(self):
        det = TennisShotDetector(TennisOracle())
        det._timefn = lambda: 1_000_000.0  # same receipt time
        a = _batch(t0=50.0, n=50, peak_n=20, mag=16.0, dominance=0.55, mode="strokes")
        b = _batch(t0=51.0, n=50, peak_n=20, mag=16.0, dominance=0.55, mode="strokes")
        shots = det.process_samples(a, "strokes") + det.process_samples(b, "strokes")
        self.assertEqual(len(shots), 1)

    def test_three_second_sensor_gap_one_wall_clock_flush_both_fire(self):
        det = TennisShotDetector(TennisOracle())
        det._timefn = lambda: 1_000_000.0
        a = _batch(t0=50.0, n=50, peak_n=20, mag=16.0, dominance=0.55, mode="strokes")
        b = _batch(t0=53.0, n=50, peak_n=20, mag=16.0, dominance=0.55, mode="strokes")
        shots = det.process_samples(a, "strokes") + det.process_samples(b, "strokes")
        self.assertEqual(len(shots), 2)
        t0, t1 = _parse_ts(shots[0]["timestamp"]), _parse_ts(shots[1]["timestamp"])
        self.assertGreaterEqual(t1 - t0, 2.5)

    def test_shot_iso_uses_peak_sample_not_wall_clock(self):
        det = TennisShotDetector(TennisOracle())
        det._timefn = lambda: 9_999_999.0
        a = _batch(t0=1_780_000_000.0, n=50, peak_n=20, mag=16.0, dominance=0.55, mode="strokes")
        shots = det.process_samples(a, "strokes")
        self.assertEqual(len(shots), 1)
        ts = _parse_ts(shots[0]["timestamp"])
        # ISO stamp is second-resolution (time.gmtime); must not be wall clock 9999999.
        self.assertAlmostEqual(ts, 1_780_000_000.0, delta=1.0)
        self.assertNotAlmostEqual(ts, 9_999_999.0, delta=10)


@unittest.skipUnless(DB_PATH.exists(), "tennis_sessions.db missing")
class Replay194708SensorTime(unittest.TestCase):
    def test_historical_db_rows_unchanged(self):
        con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        rows = con.execute(
            "SELECT id, ts, round(peak_rad,2) FROM oracle_shots WHERE id BETWEEN 41 AND 53 ORDER BY id"
        ).fetchall()
        self.assertEqual(len(rows), 13)
        o48 = [r for r in rows if r[0] == 48][0]
        self.assertEqual(o48[1], "2026-09-17T02:55:53Z")  # historical receipt ts

    def test_replay_recovers_delayed_cluster(self):
        con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        rows = con.execute(
            """SELECT compressed_data FROM raw_sensor_buffer
               WHERE session_id=? ORDER BY start_timestamp""",
            (SESSION_ID,),
        ).fetchall()
        det = TennisShotDetector(TennisOracle())
        shots = []
        for (blob,) in rows:
            text = blob.decode("utf-8") if isinstance(blob, (bytes, bytearray)) else blob
            samples = []
            for rec in csv.DictReader(io.StringIO(text)):
                rec["rotationRateX"] = float(rec["rotationRateX"])
                rec["rotationRateY"] = float(rec["rotationRateY"])
                rec["rotationRateZ"] = float(rec["rotationRateZ"])
                rec["timestamp"] = float(rec["timestamp"])
                rec["heartRate"] = float(rec.get("heartRate") or 70)
                samples.append(rec)
            if samples:
                shots.extend(det.process_samples(samples, mode=samples[0].get("mode") or "strokes"))

        # 17.81 must be at IMU time ~02:55:31, not receipt 02:55:53
        peak_1781 = [s for s in shots if 17.6 < s["peak_rad"] < 18.0]
        self.assertTrue(peak_1781, f"missing 17.81-class shot in {[round(s['peak_rad'],2) for s in shots]}")
        t_1781 = _parse_ts(peak_1781[0]["timestamp"])
        self.assertAlmostEqual(t_1781, 1789613731.556, delta=1.0)
        self.assertNotEqual(peak_1781[0]["timestamp"], "2026-09-17T02:55:53Z")

        shot_ts = [_parse_ts(s["timestamp"]) for s in shots]
        for expect_ts, mag, zid in EXPECT_RECOVERED:
            close = [t for t in shot_ts if abs(t - expect_ts) <= 1.0]
            self.assertTrue(
                close,
                f"z{zid} IMU peak {expect_ts} mag~{mag} suppressed; shot_ts={shot_ts}",
            )
        # Document 2.5s sensor cooldown: these peaks are <2.5s after the prior stroke.
        for expect_ts, mag, zid in STILL_REFRACTORY:
            close = [t for t in shot_ts if abs(t - expect_ts) <= 0.6]
            self.assertFalse(
                close,
                f"z{zid} should remain cooldown-suppressed at {expect_ts}; shot_ts={shot_ts}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
