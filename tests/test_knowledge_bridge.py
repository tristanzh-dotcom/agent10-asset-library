import json
import tempfile
import unittest
from pathlib import Path

from asset_library.knowledge_bridge import KnowledgeBridge, PromotionJournal, ReconciliationJob


class FakeNoteStore:
    def __init__(self):
        self.updates = []

    def update_fields(self, vault_path, fields):
        self.updates.append((vault_path, dict(fields)))


class FakeIngestAdapter:
    def __init__(self, fail=False):
        self.fail = fail
        self.ingests = []

    def ingest(self, vault_path):
        if self.fail:
            raise RuntimeError("ingest failed")
        self.ingests.append(vault_path)
        return {"knowledge_index_id": "idx-123", "chunk_ids": ["c1", "c2"]}


class KnowledgeBridgeTests(unittest.TestCase):
    def test_promotion_requires_explicit_confirmation(self):
        bridge = KnowledgeBridge(FakeNoteStore(), FakeIngestAdapter(), clock=lambda: "2026-07-04T12:00:00+08:00")

        with self.assertRaises(PermissionError):
            bridge.promote("note.md", confirmed=False)

    def test_promote_uses_two_phase_status_updates(self):
        note_store = FakeNoteStore()
        ingest = FakeIngestAdapter()
        bridge = KnowledgeBridge(note_store, ingest, clock=lambda: "2026-07-04T12:00:00+08:00")

        result = bridge.promote("note.md", confirmed=True)

        self.assertEqual(result["knowledge_index_id"], "idx-123")
        self.assertEqual(
            note_store.updates,
            [
                ("note.md", {"knowledge_status": "promoting"}),
                (
                    "note.md",
                    {
                        "knowledge_status": "indexed",
                        "knowledge_index_id": "idx-123",
                        "knowledge_promoted_at": "2026-07-04T12:00:00+08:00",
                    },
                ),
            ],
        )

    def test_promote_marks_failed_ingest_as_retryable_failure(self):
        note_store = FakeNoteStore()
        bridge = KnowledgeBridge(note_store, FakeIngestAdapter(fail=True), clock=lambda: "2026-07-04T12:00:00+08:00")

        with self.assertRaises(RuntimeError):
            bridge.promote("note.md", confirmed=True)

        self.assertEqual(note_store.updates[-1], ("note.md", {"knowledge_status": "promotion_failed", "promotion_error": "ingest failed"}))

    def test_rag_success_with_failed_note_write_records_promotion_journal(self):
        class FailingSecondWriteStore(FakeNoteStore):
            def update_fields(self, vault_path, fields):
                if fields.get("knowledge_status") == "indexed":
                    raise RuntimeError("note write failed")
                super().update_fields(vault_path, fields)

        with tempfile.TemporaryDirectory() as tmpdir:
            journal = PromotionJournal(Path(tmpdir) / ".promotion-journal.jsonl", clock=lambda: "2026-07-04T12:00:00+08:00")
            bridge = KnowledgeBridge(
                FailingSecondWriteStore(),
                FakeIngestAdapter(),
                promotion_journal=journal,
                clock=lambda: "2026-07-04T12:00:00+08:00",
            )

            with self.assertRaises(RuntimeError):
                bridge.promote("note.md", confirmed=True)

            records = [json.loads(line) for line in journal.path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(records[0]["vault_path"], "note.md")
            self.assertEqual(records[0]["knowledge_index_id"], "idx-123")
            self.assertEqual(records[0]["fail_reason"], "note write failed")


class ReconciliationJobTests(unittest.TestCase):
    def test_reconciliation_escalates_after_retry_limit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            journal = PromotionJournal(Path(tmpdir) / ".promotion-journal.jsonl", clock=lambda: "2026-07-04T12:00:00+08:00")
            journal.append(
                {
                    "vault_path": "note.md",
                    "knowledge_index_id": "idx-123",
                    "fail_reason": "note write failed",
                    "retry_count": 3,
                }
            )
            note_store = FakeNoteStore()

            result = ReconciliationJob(journal, note_store, max_retries=3).run_once()

            self.assertEqual(result, {"attempted": 1, "repaired": 0, "manual_review": 1})
            self.assertEqual(note_store.updates[-1], ("note.md", {"knowledge_status": "promotion_requires_manual_review"}))


if __name__ == "__main__":
    unittest.main()
