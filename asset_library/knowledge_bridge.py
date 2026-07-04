import json
from datetime import datetime, timezone, timedelta
from pathlib import Path


class KnowledgeBridge:
    def __init__(self, note_store, ingest_adapter, promotion_journal=None, clock=None):
        self.note_store = note_store
        self.ingest_adapter = ingest_adapter
        self.promotion_journal = promotion_journal
        self.clock = clock or _now_utc8_iso

    def promote(self, vault_path, confirmed=False):
        if not confirmed:
            raise PermissionError("promotion requires explicit confirmation")

        self.note_store.update_fields(vault_path, {"knowledge_status": "promoting"})
        try:
            result = self.ingest_adapter.ingest(vault_path)
        except Exception as exc:
            self.note_store.update_fields(
                vault_path,
                {"knowledge_status": "promotion_failed", "promotion_error": str(exc)},
            )
            raise

        indexed_fields = {
            "knowledge_status": "indexed",
            "knowledge_index_id": result["knowledge_index_id"],
            "knowledge_promoted_at": self.clock(),
        }
        try:
            self.note_store.update_fields(vault_path, indexed_fields)
        except Exception as exc:
            if self.promotion_journal is not None:
                self.promotion_journal.append(
                    {
                        "vault_path": vault_path,
                        "knowledge_index_id": result["knowledge_index_id"],
                        "chunk_ids": result.get("chunk_ids", []),
                        "fail_reason": str(exc),
                        "retry_count": 0,
                    }
                )
            raise
        return result


class PromotionJournal:
    def __init__(self, path, clock=None):
        self.path = Path(path)
        self.clock = clock or _now_utc8_iso

    def append(self, record):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        working = dict(record)
        working.setdefault("timestamp", self.clock())
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(working, ensure_ascii=False, sort_keys=True))
            handle.write("\n")

    def read(self):
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def replace(self, records):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
                handle.write("\n")


class ReconciliationJob:
    def __init__(self, promotion_journal, note_store, max_retries=3, clock=None):
        self.promotion_journal = promotion_journal
        self.note_store = note_store
        self.max_retries = max_retries
        self.clock = clock or _now_utc8_iso

    def run_once(self):
        records = self.promotion_journal.read()
        remaining = []
        repaired = 0
        manual_review = 0
        for record in records:
            if int(record.get("retry_count", 0)) >= self.max_retries:
                self.note_store.update_fields(
                    record["vault_path"],
                    {"knowledge_status": "promotion_requires_manual_review"},
                )
                record = dict(record)
                record["manual_review_at"] = self.clock()
                remaining.append(record)
                manual_review += 1
                continue
            try:
                self.note_store.update_fields(
                    record["vault_path"],
                    {
                        "knowledge_status": "indexed",
                        "knowledge_index_id": record["knowledge_index_id"],
                        "knowledge_promoted_at": self.clock(),
                    },
                )
                repaired += 1
            except Exception as exc:
                record = dict(record)
                record["retry_count"] = int(record.get("retry_count", 0)) + 1
                record["last_retry_error"] = str(exc)
                record["last_retry_at"] = self.clock()
                remaining.append(record)
        self.promotion_journal.replace(remaining)
        return {
            "attempted": len(records),
            "repaired": repaired,
            "manual_review": manual_review,
        }


def _now_utc8_iso():
    return datetime.now(timezone(timedelta(hours=8))).replace(microsecond=0).isoformat()
