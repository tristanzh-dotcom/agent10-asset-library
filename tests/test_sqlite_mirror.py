import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from asset_library.sqlite_mirror import MirrorGapJournal, MirrorGapScanner, SQLiteAssetMirror


def valid_draft():
    return {
        "asset_id": "ast_20260704_a1b2c3d4",
        "asset_schema_version": 1,
        "title": "PKA Answer Smoke",
        "agent_id": "agent06",
        "workflow_id": "ask",
        "asset_type": "agent06_pka_answer",
        "status": "active",
        "knowledge_status": "not_indexed",
        "source_status": "grounded",
        "sensitivity": "normal",
        "created_at": "2026-07-04T10:00:00+08:00",
        "updated_at": "2026-07-04T10:00:00+08:00",
        "source_asset_path": "/tmp/source",
        "tags": ["agent/agent06"],
        "body_markdown": "# PKA Answer Smoke\n",
    }


class SQLiteAssetMirrorTests(unittest.TestCase):
    def test_upsert_asset_creates_queryable_metadata_row(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mirror = SQLiteAssetMirror(Path(tmpdir) / "assets.sqlite3")
            draft = valid_draft()
            draft["tags"] = ["agent/agent06", "workflow/ask"]

            mirror.upsert_asset(draft, "01_Agents/Agent06/example.md")
            row = mirror.get_asset("ast_20260704_a1b2c3d4")

            self.assertEqual(row["asset_id"], "ast_20260704_a1b2c3d4")
            self.assertEqual(row["vault_path"], "01_Agents/Agent06/example.md")
            self.assertEqual(row["title"], "PKA Answer Smoke")
            self.assertEqual(row["agent_id"], "agent06")
            self.assertEqual(row["knowledge_status"], "not_indexed")
            self.assertEqual(json.loads(row["tags_json"]), ["agent/agent06", "workflow/ask"])

    def test_upsert_asset_replaces_existing_row_for_same_asset_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mirror = SQLiteAssetMirror(Path(tmpdir) / "assets.sqlite3")
            draft = valid_draft()
            mirror.upsert_asset(draft, "old.md")
            draft["title"] = "Updated Title"

            mirror.upsert_asset(draft, "new.md")
            row = mirror.get_asset("ast_20260704_a1b2c3d4")

            self.assertEqual(row["title"], "Updated Title")
            self.assertEqual(row["vault_path"], "new.md")

    def test_registry_queries_support_collision_checker(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mirror = SQLiteAssetMirror(Path(tmpdir) / "assets.sqlite3")
            draft = valid_draft()
            draft["source_content_hash"] = "sha256:abc"
            mirror.upsert_asset(draft, "01_Agents/Agent06/example.md")

            by_id = mirror.get_by_asset_id("ast_20260704_a1b2c3d4")
            by_key = mirror.get_by_idempotent_key(
                "agent06\x1fask\x1f/tmp/source\x1fsha256:abc"
            )

            self.assertEqual(by_id["source_content_hash"], "sha256:abc")
            self.assertEqual(by_key["vault_path"], "01_Agents/Agent06/example.md")
            self.assertTrue(mirror.path_exists("01_Agents/Agent06/example.md"))
            self.assertFalse(mirror.path_exists("missing.md"))

    def test_mirror_schema_uses_asset_id_as_unique_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mirror = SQLiteAssetMirror(Path(tmpdir) / "assets.sqlite3")
            mirror.upsert_asset(valid_draft(), "example.md")

            with sqlite3.connect(Path(tmpdir) / "assets.sqlite3") as conn:
                count = conn.execute("select count(*) from assets").fetchone()[0]

            self.assertEqual(count, 1)


class MirrorGapJournalTests(unittest.TestCase):
    def test_append_gap_writes_jsonl_record(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            journal_path = Path(tmpdir) / ".mirror-gap.jsonl"
            journal = MirrorGapJournal(journal_path, clock=lambda: "2026-07-04T12:00:00+08:00")

            journal.append_gap(
                asset_id="ast_20260704_a1b2c3d4",
                vault_path="01_Agents/Agent06/example.md",
                fail_reason="database is locked",
            )

            lines = journal_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            record = json.loads(lines[0])
            self.assertEqual(record["asset_id"], "ast_20260704_a1b2c3d4")
            self.assertEqual(record["vault_path"], "01_Agents/Agent06/example.md")
            self.assertEqual(record["fail_reason"], "database is locked")
            self.assertEqual(record["timestamp"], "2026-07-04T12:00:00+08:00")

    def test_scanner_retries_gaps_and_marks_successful_records_resolved(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mirror = SQLiteAssetMirror(Path(tmpdir) / "assets.sqlite3")
            journal_path = Path(tmpdir) / ".mirror-gap.jsonl"
            journal = MirrorGapJournal(journal_path, clock=lambda: "2026-07-04T12:00:00+08:00")
            journal.append_gap(
                asset_id="ast_20260704_a1b2c3d4",
                vault_path="01_Agents/Agent06/example.md",
                fail_reason="database is locked",
            )
            scanner = MirrorGapScanner(
                journal=journal,
                mirror=mirror,
                draft_resolver=lambda asset_id, vault_path: valid_draft(),
                clock=lambda: "2026-07-04T12:05:00+08:00",
            )

            result = scanner.retry_gaps()

            self.assertEqual(result, {"attempted": 1, "repaired": 1, "remaining": 0})
            records = [json.loads(line) for line in journal_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(records[0]["resolved_at"], "2026-07-04T12:05:00+08:00")
            row = mirror.get_asset("ast_20260704_a1b2c3d4")
            self.assertEqual(row["vault_path"], "01_Agents/Agent06/example.md")

    def test_scanner_keeps_unresolved_records_for_later_retry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mirror = SQLiteAssetMirror(Path(tmpdir) / "assets.sqlite3")
            journal_path = Path(tmpdir) / ".mirror-gap.jsonl"
            journal = MirrorGapJournal(journal_path, clock=lambda: "2026-07-04T12:00:00+08:00")
            journal.append_gap(
                asset_id="ast_20260704_a1b2c3d4",
                vault_path="01_Agents/Agent06/example.md",
                fail_reason="database is locked",
            )
            scanner = MirrorGapScanner(
                journal=journal,
                mirror=mirror,
                draft_resolver=lambda asset_id, vault_path: (_ for _ in ()).throw(RuntimeError("note missing")),
            )

            result = scanner.retry_gaps()

            self.assertEqual(result, {"attempted": 1, "repaired": 0, "remaining": 1})
            records = [json.loads(line) for line in journal_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(records[0]["asset_id"], "ast_20260704_a1b2c3d4")
            self.assertEqual(records[0]["last_retry_error"], "note missing")

    def test_compact_archives_resolved_gap_records(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            journal_path = Path(tmpdir) / ".mirror-gap.jsonl"
            archive_path = Path(tmpdir) / ".mirror-gap.resolved.jsonl"
            journal = MirrorGapJournal(journal_path, archive_path=archive_path)
            journal.replace_gaps(
                [
                    {"asset_id": "resolved", "resolved_at": "2026-07-04T12:05:00+08:00"},
                    {"asset_id": "open"},
                ]
            )

            result = journal.compact_resolved()

            self.assertEqual(result, {"archived": 1, "remaining": 1})
            self.assertEqual(
                [json.loads(line)["asset_id"] for line in journal_path.read_text(encoding="utf-8").splitlines()],
                ["open"],
            )
            self.assertEqual(
                [json.loads(line)["asset_id"] for line in archive_path.read_text(encoding="utf-8").splitlines()],
                ["resolved"],
            )


if __name__ == "__main__":
    unittest.main()
