"""Keep the append-only transport incident ledger structurally reviewable."""
from pathlib import Path
import unittest


LEDGER = Path(__file__).resolve().parents[2] / "TRANSPORT_FAILURE_LEDGER.md"


class TransportFailureLedgerTests(unittest.TestCase):
    def test_required_incidents_and_fields_are_present(self):
        text = LEDGER.read_text(encoding="utf-8")
        for session in (
            "oracle_20260917_001002",
            "oracle_20260917_155530",
            "oracle_20260917_203522",
        ):
            self.assertIn(session, text)
        for field in (
            "Classification:",
            "Versions:",
            "Lifecycle:",
            "Observed:",
            "Sequence:",
            "WC/WS:",
            "Root cause status:",
            "Loss scope:",
            "Remediation/test:",
        ):
            self.assertIn(field, text)

    def test_phase_two_is_not_claimed_as_implemented(self):
        text = LEDGER.read_text(encoding="utf-8")
        self.assertIn("Phase 2 (not implemented)", text)
        self.assertNotIn("Phase 2 (implemented)", text)


if __name__ == "__main__":
    unittest.main()
