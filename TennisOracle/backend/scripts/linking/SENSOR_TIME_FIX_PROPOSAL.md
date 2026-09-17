# Sensor-time shot timestamps + cooldown (proposal, not applied)

**Scope is larger than 194708** — live serve and strokes, `persist_shot` ts, pending medium-serve path, existing `_timefn` tests, and later linking. Reporting before applying.

## Cause

`TennisShotDetector._emit_shot` stamps `time.gmtime(current_time)` where `current_time = self._timefn()` (`time.time()` live). Cooldown is `current_time + 2.5`. A delayed Watch/iPhone flush at 02:55:53 collapsed IMU peaks 02:55:31–48 into one shot (`o48` peak_rad **17.81** = IMU 02:55:31.556) and wall-clock cooldown suppressed z21687–90, 21692, 21695.

## Minimal diff (`backend/app/services/tennis_oracle.py` only)

No threshold constants change. Batch size / `batch_seq` dedupe / pending-medium merge unchanged.

1. `_sample_ts(sample) -> Optional[float]` from `sample["timestamp"]`.
2. `_sensor_now(samples, peak_sample=None)`: peak ts, else last sample ts, else `_timefn()` fallback if IMU ts missing.
3. `process_samples`: compare `cooldown_until` to **sensor_now**, not wall clock. Pending resolve uses the pending peak’s sample ts.
4. `_emit_shot`: `event_ts = _sample_ts(peak_sample) or fallback`; `cooldown_until = event_ts + COOLDOWN`; ISO timestamp and `shot_id` from `event_ts`.

## Tests (add, don’t weaken ss1/ss2 linker gold)

`tests/test_sensor_time_cooldown.py` (replay `oracle_20260916_194708` IMU, sample-time detector):

- A shot with `peak_rad ≈ 17.81` at **02:55:31Z** (not 02:55:53) — would pair **z21686**, not z21691.
- Additional shots near 02:55:35, :39, :44, :47 (z21687–90) **not** suppressed.
- Shots near 02:55:54 (z21692) and 02:56:01 (z21695) **not** suppressed (`|Δt_sensor|` vs prior peak ≥ 2.5s).
- Synthetic: two DETECT-level bursts 1.0s apart in sensor time, delivered in one wall-clock second → only first fires (cooldown still works).
- Synthetic: same bursts 3.0s apart in sensor time, delivered in one wall-clock second → **both** fire (the 194708 bug).
- Existing `test_serve_cross_batch` uses sample timestamps already (`t0=10` / `100` / `127`); switch cooldown asserts to sensor time, keep pending-medium behavior.

## Out of scope this change

- Retune `COOLDOWN` / axis / speed.
- Rewrite persisted o41–o53 or gold serve links.
- Auto-link 194708.
- Watch/iPhone batching (preserve current 50-sample batches).
