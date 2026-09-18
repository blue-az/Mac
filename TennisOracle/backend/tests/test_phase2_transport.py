"""Phase 2a idempotency/ACK persistence tests (no detector behavior)."""
import importlib
import sqlite3
import tempfile
import unittest
from pathlib import Path


class Phase2TransportTests(unittest.TestCase):
    def test_duplicate_watch_batch_is_persisted_once(self):
        import app.main as main

        with tempfile.TemporaryDirectory() as td:
            old_path = main.DB_PATH
            main.DB_PATH = str(Path(td) / "transport.db")
            try:
                main.init_db()
                samples = [{"timestamp": 1.0, "mode": "strokes"}]
                self.assertTrue(main.persist_batch("oracle_test", 1, samples, "watch-1", 7))
                self.assertFalse(main.persist_batch("oracle_test", 2, samples, "watch-1", 7))
                con = sqlite3.connect(main.DB_PATH)
                self.assertEqual(con.execute("SELECT count(*) FROM raw_sensor_buffer").fetchone()[0], 1)
                self.assertEqual(
                    con.execute("SELECT watch_session_uuid,batch_seq FROM raw_sensor_buffer").fetchone(),
                    ("watch-1", 7),
                )
                con.close()
            finally:
                main.DB_PATH = old_path


if __name__ == "__main__":
    unittest.main()
