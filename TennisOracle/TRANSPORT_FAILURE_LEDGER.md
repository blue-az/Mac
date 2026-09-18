# TennisOracle Watch↔iPhone↔Mac Transport Failure Ledger

Durable incident ledger. Append-only: preserve raw sensor/Zepp databases and never silently discard a failed run. Times are UTC (`Z`) unless noted. `unknown` means the pre-Phase-1 binary did not carry or persist that field.

## Schema

Each incident records: backend session, Watch `session_uuid`, app/backend versions, lifecycle timestamps, last/expected `batch_seq`, gaps/reordering, WC/WS state, observed counts, root-cause status, loss scope, remediation/test, and classification.

## Incidents

### 2026-09-17 — `oracle_20260917_001002`

- **Classification:** transport-diagnostic; calibration labels not silently accepted.
- **Versions:** pre-Phase-1 Watch/iPhone binary; backend pre-observability process PID 1551.
- **Watch UUID:** unknown (old binary).
- **Lifecycle:** WS accepted `07:10:02Z`; final raw IMU `07:15:45.723Z`; last shot `07:15:29Z`; WS/session finalized `07:23:00Z`.
- **Observed:** 592 batches, 29,568 samples, 25 persisted AW detections; user verified 23 Watch buzzes from 24 recorded strokes.
- **Sequence:** batch sequence unavailable; all persisted batches were complete 50-sample batches.
- **WC/WS:** backend received continuous batches, then clean disconnect; backend did not crash.
- **Zepp comparison:** fresh Zepp snapshot z21699–z21722; 23 time-pairs, 20 matches, 7 ambiguous, 2 AW-only (o54/o55 before Zepp start), 1 Zepp-only.
- **Root cause status:** Watch app returned to Save; likely Watch lifecycle/transport interruption, not backend failure. Exact Watch termination reason unavailable.
- **Loss scope:** any partial/in-flight Watch buffer after `07:15:45.723Z` is unknowable; persisted raw data is safe.
- **Remediation/test:** Phase-1 observability implemented afterward; this run predates it and is not a transport success criterion.

### 2026-09-17 — `oracle_20260917_155530`

- **Classification:** transport-diagnostic; calibration-invalid (no AW data reached Mac).
- **Versions:** iPhone TennisOracle v1.0 installed; Watch binary presence not verifiable at incident time; backend PID 2801 after restart.
- **Watch UUID:** unknown (no batches/Phase-1 journal evidence).
- **Lifecycle:** WS accepted `22:55:30Z`; cleanly finalized `23:23:38Z` with no payloads.
- **Observed:** 0 batches, 0 samples, 0 shots persisted; user observed approximately 8 local Watch readings/haptics.
- **Sequence:** none observed; expected first batch unavailable.
- **WC/WS:** iPhone↔Mac WS established and healthy; no backend batch lines; iPhone WC receive counter reportedly remained 0.
- **Root cause status:** Watch-local detector ran, but Watch→iPhone delivery was not evidenced. Backend ruled out; WC state/logs unavailable.
- **Loss scope:** local-only readings and any unsent Watch batches were not recoverable at Mac; no Mac raw data was lost.
- **Remediation/test:** AppIcon blocker fixed; iPhone installed; Watch deployment attempts timed out. Later successful 203522 run provides transport regression evidence.

### 2026-09-18 — `oracle_20260917_203522` (active/recovered)

- **Classification:** transport-diagnostic; calibration-invalid until Zepp pairing is explicitly bounded.
- **Versions:** Phase-1 backend PID 2801; iPhone TennisOracle v1.0; Watch Phase-1 binary believed running (device tooling visibility intermittent).
- **Watch UUID:** `645C75BA-C002-4B37-9D6C-DA5BD49E3D65`.
- **Lifecycle:** WS accepted `03:35:22Z`; initially 0 batches; transfer resumed during the same session at approximately `03:39Z`; session remained active at last inspection.
- **Observed at ledger entry:** 43 batches, 2,150 samples, 1 AW shot; latest shot `03:39:28Z` (100.7 mph); raw end `03:39:28.987Z`.
- **Sequence:** latest observed `batch_seq=154`; log showed a jump from 115 to 146, indicating delayed/queued delivery or missing sequences. Exact expected sequence cannot be reconstructed without Watch journal.
- **WC/WS:** WS stayed ESTABLISHED (`192.168.8.165:63618`); backend received batches after recovery, proving Watch→iPhone→WS path can work.
- **Root cause status:** intermittent WatchConnectivity delivery/lifecycle issue remains unresolved; backend is not implicated.
- **Loss scope:** possible missing/delayed batches 116–145 (not yet proven lost); do not backfill or discard without sequence evidence.
- **Remediation/test:** no ACK/outbox or sequence recovery implemented yet. This is the first positive Phase-1 transport test; retain raw DB and logs.

## Planned separate phases

1. **Phase 1 (implemented):** lifecycle journal, session UUID, batch metadata, WC/WS logging; no detector changes.
2. **Phase 2 (not implemented):** durable outbox, explicit ACKs, idempotent batch persistence, sequence-gap/reorder recovery, and regression tests for delayed delivery and gaps.

## Evidence locations

- Backend log: `/tmp/tennisoracle_backend.log`
- Oracle DB: `/Users/blueaz/Python/Mac/tennis_sessions.db`
- Zepp snapshots: `/Users/blueaz/Downloads/SensorDownload/Current/`
- Crystal: `TennisOracle/CRYSTAL_2026-09-16.md`
