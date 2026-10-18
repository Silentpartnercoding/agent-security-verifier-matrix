import shutil
import tempfile
import unittest
from pathlib import Path

from verify import verify_clean_freeze, verify_evidence


ROOT = Path(__file__).resolve().parents[1]


class ProvenanceGateTests(unittest.TestCase):
    def copy_package(self):
        holder = tempfile.TemporaryDirectory(prefix="moltrust-provenance-")
        target = Path(holder.name) / "experiment"
        shutil.copytree(ROOT, target)
        self.addCleanup(holder.cleanup)
        return target

    def test_committed_evidence_and_bundle_verify(self):
        verify_evidence(ROOT)

    def test_missing_source_pins_fails_closed(self):
        target = self.copy_package()
        (target / "SOURCE-PINS.json").unlink()
        with self.assertRaises((FileNotFoundError, ValueError)):
            verify_evidence(target)

    def test_missing_history_bundle_fails_closed(self):
        target = self.copy_package()
        (target / "artifacts" / "clean-room-history.bundle").unlink()
        with self.assertRaises((FileNotFoundError, ValueError, RuntimeError)):
            verify_evidence(target)

    def test_tampered_frozen_output_fails_closed(self):
        target = self.copy_package()
        with (target / "artifacts" / "lars-run.jsonl").open("a") as stream:
            stream.write("{}\n")
        with self.assertRaises(ValueError):
            verify_evidence(target)

    def test_clean_hash_ledger_is_checked_not_silently_rebased(self):
        target = self.copy_package()
        ledger = (target / "clean-room" / "ARTIFACT-SHA256SUMS").read_bytes()
        record = (target / "clean-room" / "VERIFICATION.json").read_bytes()
        with (target / "clean-room" / "reader.py").open("a") as stream:
            stream.write("\n# unauthorized drift\n")
        for _ in range(2):
            with self.assertRaises(ValueError):
                verify_clean_freeze(target)
            self.assertEqual((target / "clean-room" / "ARTIFACT-SHA256SUMS").read_bytes(), ledger)
            self.assertEqual((target / "clean-room" / "VERIFICATION.json").read_bytes(), record)


if __name__ == "__main__":
    unittest.main()
