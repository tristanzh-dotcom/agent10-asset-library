import json
import tempfile
import unittest
from pathlib import Path

from asset_library.locking import VaultWriteLock, recover_writer_state


class VaultWriteLockTests(unittest.TestCase):
    def test_lock_writes_holder_metadata_and_clears_it_on_release(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "99_System" / "audit" / ".asset-writer.lock"

            with VaultWriteLock(
                lock_path,
                operation_id="op-1",
                pid=123,
                hostname="host",
                clock=lambda: "2026-07-04T12:00:00+08:00",
            ):
                metadata = json.loads(lock_path.read_text(encoding="utf-8"))
                self.assertEqual(metadata["pid"], 123)
                self.assertEqual(metadata["hostname"], "host")
                self.assertEqual(metadata["operation_id"], "op-1")
                self.assertEqual(metadata["started_at"], "2026-07-04T12:00:00+08:00")

            self.assertEqual(lock_path.read_text(encoding="utf-8"), "")

    def test_lock_timeout_fails_without_breaking_active_lock(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "99_System" / "audit" / ".asset-writer.lock"
            first = VaultWriteLock(lock_path, operation_id="op-1")
            first.acquire()
            try:
                with self.assertRaises(TimeoutError):
                    VaultWriteLock(lock_path, operation_id="op-2", timeout_seconds=0).acquire()
            finally:
                first.release()

    def test_recover_writer_state_reports_tmp_files_and_stale_lock(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = Path(tmpdir)
            audit = vault / "99_System" / "audit"
            audit.mkdir(parents=True)
            lock_path = audit / ".asset-writer.lock"
            lock_path.write_text(
                json.dumps(
                    {
                        "pid": 999999,
                        "hostname": "host",
                        "started_at": "2026-07-04T12:00:00+08:00",
                        "operation_id": "op-stale",
                    }
                ),
                encoding="utf-8",
            )
            tmp_file = vault / "01_Agents" / "Agent10" / ".note.md.abcd.tmp"
            tmp_file.parent.mkdir(parents=True)
            tmp_file.write_text("partial", encoding="utf-8")

            report = recover_writer_state(
                vault,
                pid_exists=lambda pid: False,
                clock=lambda: "2026-07-04T12:10:00+08:00",
            )

            self.assertEqual(report["stale_locks"][0]["pid"], 999999)
            self.assertEqual(report["tmp_files"], ["01_Agents/Agent10/.note.md.abcd.tmp"])
            events = list(audit.glob("stale-lock-*.json"))
            self.assertEqual(len(events), 1)
            event = json.loads(events[0].read_text(encoding="utf-8"))
            self.assertEqual(event["operation_id"], "op-stale")
            self.assertEqual(event["recovered_at"], "2026-07-04T12:10:00+08:00")


if __name__ == "__main__":
    unittest.main()
