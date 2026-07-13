import json
import tempfile
import unittest
from pathlib import Path

from asset_library.governance import GovernanceService
from asset_library.sqlite_mirror import MirrorGapJournal


class FakeMirror:
    def count_assets(self):
        return 3


class GovernanceTests(unittest.TestCase):
    def test_snapshot_reports_agent_governance_without_note_body(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = Path(tmpdir) / "vault"
            audit = vault / "99_System" / "audit"
            audit.mkdir(parents=True)
            mirror_gap = MirrorGapJournal(audit / ".mirror-gap.jsonl", clock=lambda: "2026-07-04T12:00:00+08:00")
            mirror_gap.append_gap("ast_gap", "note.md", "database locked")
            promotion_journal = audit / ".promotion-journal.jsonl"
            promotion_journal.write_text(
                json.dumps({"vault_path": "note.md", "retry_count": 1}) + "\n",
                encoding="utf-8",
            )

            service = GovernanceService(
                vault_path=vault,
                mirror=FakeMirror(),
                mirror_gap_journal=mirror_gap,
                promotion_journal_path=promotion_journal,
                pid_exists=lambda pid: False,
                clock=lambda: "2026-07-04T12:05:00+08:00",
            )

            snapshot = service.snapshot()

            self.assertEqual(snapshot["writer_health"]["mirror_asset_count"], 3)
            self.assertEqual(snapshot["mirror_gaps"]["open_count"], 1)
            self.assertEqual(snapshot["promotion_journal"]["open_count"], 1)
            self.assertEqual(snapshot["schema_drift"]["unsupported_count"], 0)
            self.assertNotIn("body_markdown", json.dumps(snapshot))

    def test_schema_drift_counts_unsupported_versions_from_mirror_rows(self):
        class DriftMirror:
            def count_assets(self):
                return 1

            def list_asset_frontmatter(self):
                return [{"asset_id": "ast_bad", "asset_schema_version": 99}]

        with tempfile.TemporaryDirectory() as tmpdir:
            vault = Path(tmpdir) / "vault"
            service = GovernanceService(
                vault_path=vault,
                mirror=DriftMirror(),
                mirror_gap_journal=MirrorGapJournal(vault / "99_System" / "audit" / ".mirror-gap.jsonl"),
                promotion_journal_path=vault / "99_System" / "audit" / ".promotion-journal.jsonl",
            )

            snapshot = service.snapshot()

            self.assertEqual(snapshot["schema_drift"]["unsupported_count"], 1)
            self.assertEqual(snapshot["schema_drift"]["unsupported_assets"], ["ast_bad"])

    def test_snapshot_does_not_create_or_modify_vault_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = Path(tmpdir) / "missing-vault"
            service = GovernanceService(
                vault_path=vault,
                mirror=FakeMirror(),
                mirror_gap_journal=MirrorGapJournal(vault / "99_System" / "audit" / ".mirror-gap.jsonl"),
                promotion_journal_path=vault / "99_System" / "audit" / ".promotion-journal.jsonl",
            )

            service.snapshot()

            self.assertFalse(vault.exists())


if __name__ == "__main__":
    unittest.main()
