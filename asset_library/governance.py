import json
from pathlib import Path

from .locking import inspect_writer_state, recover_writer_state
from .schema_migration import normalize_asset_frontmatter


class GovernanceService:
    def __init__(
        self,
        vault_path,
        mirror,
        mirror_gap_journal,
        promotion_journal_path,
        pid_exists=None,
        clock=None,
        mutation_handlers=None,
    ):
        self.vault_path = Path(vault_path)
        self.mirror = mirror
        self.mirror_gap_journal = mirror_gap_journal
        self.promotion_journal_path = Path(promotion_journal_path)
        self.pid_exists = pid_exists
        self.clock = clock
        self.mutation_handlers = dict(mutation_handlers or {})

    def snapshot(self):
        writer_state = inspect_writer_state(
            self.vault_path,
            pid_exists=self.pid_exists,
        )
        mirror_gaps = self.mirror_gap_journal.read_gaps()
        promotions = _read_jsonl(self.promotion_journal_path)
        return {
            "writer_health": {
                "mirror_asset_count": self.mirror.count_assets(),
                "tmp_file_count": len(writer_state["tmp_files"]),
                "stale_lock_count": len(writer_state["stale_locks"]),
                "active_lock_count": len(writer_state["active_locks"]),
            },
            "mirror_gaps": {
                "open_count": len([record for record in mirror_gaps if not record.get("resolved_at")]),
                "resolved_count": len([record for record in mirror_gaps if record.get("resolved_at")]),
                "records": _without_body_fields(mirror_gaps),
            },
            "promotion_journal": {
                "open_count": len(promotions),
                "records": _without_body_fields(promotions),
            },
            "schema_drift": self._schema_drift(),
        }

    def _schema_drift(self):
        unsupported = []
        list_frontmatter = getattr(self.mirror, "list_asset_frontmatter", None)
        if list_frontmatter is None:
            return {"unsupported_count": 0, "unsupported_assets": []}
        for row in list_frontmatter():
            try:
                normalize_asset_frontmatter(row)
            except ValueError:
                unsupported.append(row.get("asset_id", ""))
        return {
            "unsupported_count": len(unsupported),
            "unsupported_assets": unsupported,
        }

    def run_mutation(self, action):
        if action == "recover-writer":
            return {
                "action": action,
                "status": "completed",
                "writer_state": recover_writer_state(
                    self.vault_path,
                    pid_exists=self.pid_exists,
                    clock=self.clock,
                ),
            }
        handler = self.mutation_handlers.get(action)
        if handler is None:
            raise ValueError(f"unsupported governance mutation: {action}")
        return {"action": action, "status": "completed", "result": handler()}


def _read_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _without_body_fields(records):
    body_fields = {"body", "body_markdown", "answer", "content", "markdown"}
    sanitized = []
    for record in records:
        sanitized.append({key: value for key, value in record.items() if key not in body_fields})
    return sanitized
