import json
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

from .collision import idempotent_key
from .hashing import compute_body_hash


class SQLiteAssetMirror:
    def __init__(self, db_path):
        self.db_path = Path(db_path)

    def upsert_asset(self, draft, vault_path):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        record = _mirror_record(draft, vault_path)
        with sqlite3.connect(self.db_path) as conn:
            _ensure_schema(conn)
            conn.execute(_UPSERT_ASSET_SQL, record)

    def get_asset(self, asset_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            _ensure_schema(conn)
            row = conn.execute(
                "select * from assets where asset_id = ?",
                (asset_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_by_asset_id(self, asset_id):
        return self.get_asset(asset_id)

    def get_by_idempotent_key(self, key):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            _ensure_schema(conn)
            row = conn.execute(
                "select * from assets where idempotent_key = ?",
                (key,),
            ).fetchone()
        return dict(row) if row else None

    def path_exists(self, vault_path):
        with sqlite3.connect(self.db_path) as conn:
            _ensure_schema(conn)
            row = conn.execute(
                "select 1 from assets where vault_path = ? limit 1",
                (vault_path,),
            ).fetchone()
        return row is not None

    def count_assets(self):
        with sqlite3.connect(self.db_path) as conn:
            _ensure_schema(conn)
            return conn.execute("select count(*) from assets").fetchone()[0]

    def list_asset_frontmatter(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            _ensure_schema(conn)
            rows = conn.execute(
                """
                select asset_id, asset_schema_version, status, knowledge_status,
                       source_status, sensitivity, source_content_hash, hash_source
                from assets
                order by asset_id
                """
            ).fetchall()
        return [dict(row) for row in rows]


class MirrorGapJournal:
    def __init__(self, journal_path, clock=None, archive_path=None):
        self.journal_path = Path(journal_path)
        self.archive_path = Path(archive_path) if archive_path else self.journal_path.with_name(
            ".mirror-gap.resolved.jsonl"
        )
        self.clock = clock or _now_utc8_iso

    def append_gap(self, asset_id, vault_path, fail_reason):
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "asset_id": asset_id,
            "vault_path": vault_path,
            "fail_reason": fail_reason,
            "timestamp": self.clock(),
        }
        with self.journal_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            handle.write("\n")

    def read_gaps(self):
        if not self.journal_path.exists():
            return []
        records = []
        for line in self.journal_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
        return records

    def replace_gaps(self, records):
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        with self.journal_path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
                handle.write("\n")

    def compact_resolved(self):
        records = self.read_gaps()
        resolved = [record for record in records if record.get("resolved_at")]
        remaining = [record for record in records if not record.get("resolved_at")]
        if resolved:
            self.archive_path.parent.mkdir(parents=True, exist_ok=True)
            with self.archive_path.open("a", encoding="utf-8") as handle:
                for record in resolved:
                    handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
                    handle.write("\n")
        self.replace_gaps(remaining)
        return {"archived": len(resolved), "remaining": len(remaining)}


class MirrorGapScanner:
    def __init__(self, journal, mirror, draft_resolver, clock=None):
        self.journal = journal
        self.mirror = mirror
        self.draft_resolver = draft_resolver
        self.clock = clock or _now_utc8_iso

    def retry_gaps(self):
        records = self.journal.read_gaps()
        updated = []
        repaired = 0
        for record in records:
            if record.get("resolved_at"):
                updated.append(record)
                continue
            try:
                draft = self.draft_resolver(record["asset_id"], record["vault_path"])
                self.mirror.upsert_asset(draft, record["vault_path"])
                record = dict(record)
                record["resolved_at"] = self.clock()
                updated.append(record)
                repaired += 1
            except Exception as exc:
                record = dict(record)
                record["last_retry_error"] = str(exc)
                record["last_retry_at"] = self.clock()
                record["retry_count"] = int(record.get("retry_count", 0)) + 1
                updated.append(record)
        self.journal.replace_gaps(updated)
        remaining = [record for record in updated if not record.get("resolved_at")]
        return {
            "attempted": len(records),
            "repaired": repaired,
            "remaining": len(remaining),
        }


_CREATE_ASSETS_SQL = """
create table if not exists assets (
    asset_id text primary key,
    vault_path text not null,
    asset_schema_version integer not null,
    title text not null,
    agent_id text not null,
    workflow_id text not null,
    asset_type text not null,
    status text not null,
    knowledge_status text not null,
    source_status text not null,
    sensitivity text not null,
    source_content_hash text not null,
    hash_source text not null,
    created_at text,
    updated_at text,
    source_asset_path text,
    tags_json text not null,
    idempotent_key text not null unique
)
"""

_UPSERT_ASSET_SQL = """
insert into assets (
    asset_id,
    vault_path,
    asset_schema_version,
    title,
    agent_id,
    workflow_id,
    asset_type,
    status,
    knowledge_status,
    source_status,
    sensitivity,
    source_content_hash,
    hash_source,
    created_at,
    updated_at,
    source_asset_path,
    tags_json,
    idempotent_key
) values (
    :asset_id,
    :vault_path,
    :asset_schema_version,
    :title,
    :agent_id,
    :workflow_id,
    :asset_type,
    :status,
    :knowledge_status,
    :source_status,
    :sensitivity,
    :source_content_hash,
    :hash_source,
    :created_at,
    :updated_at,
    :source_asset_path,
    :tags_json,
    :idempotent_key
)
on conflict(asset_id) do update set
    vault_path = excluded.vault_path,
    asset_schema_version = excluded.asset_schema_version,
    title = excluded.title,
    agent_id = excluded.agent_id,
    workflow_id = excluded.workflow_id,
    asset_type = excluded.asset_type,
    status = excluded.status,
    knowledge_status = excluded.knowledge_status,
    source_status = excluded.source_status,
    sensitivity = excluded.sensitivity,
    source_content_hash = excluded.source_content_hash,
    hash_source = excluded.hash_source,
    created_at = excluded.created_at,
    updated_at = excluded.updated_at,
    source_asset_path = excluded.source_asset_path,
    tags_json = excluded.tags_json,
    idempotent_key = excluded.idempotent_key
"""


def _mirror_record(draft, vault_path):
    record = {
        "asset_id": draft["asset_id"],
        "vault_path": vault_path,
        "asset_schema_version": draft.get("asset_schema_version", 1),
        "title": draft["title"],
        "agent_id": draft["agent_id"],
        "workflow_id": draft["workflow_id"],
        "asset_type": draft["asset_type"],
        "status": draft["status"],
        "knowledge_status": draft["knowledge_status"],
        "source_status": draft["source_status"],
        "sensitivity": draft["sensitivity"],
        "source_content_hash": draft.get("source_content_hash")
        or compute_body_hash(draft.get("body_markdown", "")),
        "hash_source": draft.get("hash_source", ""),
        "created_at": draft.get("created_at"),
        "updated_at": draft.get("updated_at"),
        "source_asset_path": draft.get("source_asset_path"),
        "tags_json": json.dumps(draft.get("tags", []), ensure_ascii=False, sort_keys=True),
    }
    record["idempotent_key"] = idempotent_key(record)
    return record


def _ensure_schema(conn):
    conn.execute(_CREATE_ASSETS_SQL)
    columns = {row[1] for row in conn.execute("pragma table_info(assets)").fetchall()}
    if "idempotent_key" not in columns:
        conn.execute("alter table assets add column idempotent_key text")
        conn.execute(
            """
            update assets
            set idempotent_key = agent_id || char(31) || workflow_id || char(31)
                || coalesce(source_asset_path, '') || char(31) || source_content_hash
            """
        )
    conn.execute("create unique index if not exists idx_assets_idempotent_key on assets(idempotent_key)")
    conn.execute("create index if not exists idx_assets_vault_path on assets(vault_path)")


def _now_utc8_iso():
    return datetime.now(timezone(timedelta(hours=8))).replace(microsecond=0).isoformat()
