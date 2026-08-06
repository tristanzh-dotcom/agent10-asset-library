import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class HardwareStore:
    """SQLite-backed intake and public hardware-record mirror."""

    def __init__(self, db_path):
        self.db_path = Path(db_path)

    def save_intake(self, intake):
        payload = _dump(intake)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            _ensure_schema(conn)
            existing = conn.execute(
                "select payload_json, snapshot_hash from hardware_intakes where operation_key = ?",
                (intake["operation_key"],),
            ).fetchone()
            if existing:
                if existing[1] != intake["snapshot_hash"]:
                    raise ValueError("operation_key already exists with a different hardware snapshot")
                return json.loads(existing[0]), True
            now = _now()
            conn.execute(
                """
                insert into hardware_intakes (
                    intake_id, operation_key, snapshot_hash, intake_status,
                    payload_json, created_at, updated_at
                ) values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    intake["intake_id"],
                    intake["operation_key"],
                    intake["snapshot_hash"],
                    intake["intake_status"],
                    payload,
                    now,
                    now,
                ),
            )
        return dict(intake), False

    def get_intake(self, intake_id):
        if not self.db_path.exists():
            return None
        with sqlite3.connect(self.db_path) as conn:
            _ensure_schema(conn)
            row = conn.execute(
                "select payload_json from hardware_intakes where intake_id = ?",
                (intake_id,),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def update_intake(self, intake):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            _ensure_schema(conn)
            changed = conn.execute(
                """
                update hardware_intakes
                set intake_status = ?, payload_json = ?, updated_at = ?
                where intake_id = ?
                """,
                (intake["intake_status"], _dump(intake), _now(), intake["intake_id"]),
            ).rowcount
            if changed != 1:
                raise ValueError("hardware intake does not exist")
        return dict(intake)

    def count_intakes(self):
        if not self.db_path.exists():
            return 0
        with sqlite3.connect(self.db_path) as conn:
            _ensure_schema(conn)
            return conn.execute("select count(*) from hardware_intakes").fetchone()[0]

    def save_draft(self, draft):
        if not isinstance(draft, dict) or not draft.get("draft_id"):
            raise ValueError("hardware draft must have draft_id")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            _ensure_schema(conn)
            try:
                conn.execute(
                    "insert into hardware_drafts (draft_id, revision, status, payload_json, created_at, updated_at) values (?, ?, ?, ?, ?, ?)",
                    (draft["draft_id"], draft["revision"], draft["status"], _dump(draft), _now(), _now()),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("hardware draft already exists") from exc
        return dict(draft)

    def get_draft(self, draft_id):
        if not self.db_path.exists():
            return None
        with sqlite3.connect(self.db_path) as conn:
            _ensure_schema(conn)
            row = conn.execute("select payload_json from hardware_drafts where draft_id = ?", (draft_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def update_draft(self, draft, expected_revision):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            _ensure_schema(conn)
            changed = conn.execute(
                "update hardware_drafts set revision = ?, status = ?, payload_json = ?, updated_at = ? where draft_id = ? and revision = ?",
                (draft["revision"], draft["status"], _dump(draft), _now(), draft["draft_id"], expected_revision),
            ).rowcount
        if changed != 1:
            raise ValueError("stale draft revision")
        return dict(draft)

    def save_analysis_job(self, job):
        if not isinstance(job, dict) or not job.get("job_id") or not job.get("operation_key"):
            raise ValueError("hardware analysis job must have stable identifiers")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            _ensure_schema(conn)
            existing = conn.execute(
                "select payload_json from hardware_analysis_jobs where operation_key = ?",
                (job["operation_key"],),
            ).fetchone()
            if existing:
                stored = json.loads(existing[0])
                if stored.get("job_id") != job.get("job_id"):
                    raise ValueError("analysis operation_key already exists with a different job")
                return stored
            conn.execute(
                "insert into hardware_analysis_jobs (job_id, operation_key, draft_id, draft_revision, status, payload_json, created_at, updated_at) values (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    job["job_id"],
                    job["operation_key"],
                    job["draft_id"],
                    job["draft_revision"],
                    job["status"],
                    _dump(job),
                    job.get("created_at") or _now(),
                    _now(),
                ),
            )
        return dict(job)

    def get_analysis_job_by_operation(self, operation_key):
        if not self.db_path.exists():
            return None
        with sqlite3.connect(self.db_path) as conn:
            _ensure_schema(conn)
            row = conn.execute(
                "select payload_json from hardware_analysis_jobs where operation_key = ?",
                (operation_key,),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def get_analysis_job(self, job_id):
        if not self.db_path.exists():
            return None
        with sqlite3.connect(self.db_path) as conn:
            _ensure_schema(conn)
            row = conn.execute(
                "select payload_json from hardware_analysis_jobs where job_id = ?",
                (job_id,),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def upsert_record(self, record, vault_path, updated_at=None):
        record_id = record_id_for(record)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            _ensure_schema(conn)
            conn.execute(
                """
                insert into hardware_records (
                    record_id, record_type, vault_path, scope, record_json,
                    acceptance_hash, updated_at
                ) values (?, ?, ?, ?, ?, ?, ?)
                on conflict(record_id) do update set
                    record_type = excluded.record_type,
                    vault_path = excluded.vault_path,
                    scope = excluded.scope,
                    record_json = excluded.record_json,
                    acceptance_hash = excluded.acceptance_hash,
                    updated_at = excluded.updated_at
                """,
                (
                    record_id,
                    record["record_type"],
                    vault_path,
                    _scope_for(record),
                    _dump(record),
                    record.get("acceptance", {}).get("snapshot_hash", ""),
                    updated_at or _now(),
                ),
            )

    def get_record(self, record_id):
        if not self.db_path.exists():
            return None
        with sqlite3.connect(self.db_path) as conn:
            _ensure_schema(conn)
            row = conn.execute(
                "select record_json from hardware_records where record_id = ?",
                (record_id,),
            ).fetchone()
        return _public_record(json.loads(row[0])) if row else None

    def list_records(self, query="", record_type=None, scope=None):
        if not self.db_path.exists():
            return []
        with sqlite3.connect(self.db_path) as conn:
            _ensure_schema(conn)
            rows = conn.execute(
                "select record_json from hardware_records order by updated_at desc, record_id"
            ).fetchall()
        records = [_public_record(json.loads(row[0])) for row in rows]
        query = str(query or "").strip().lower()
        filtered = []
        for record in records:
            if record_type and record.get("record_type") != record_type:
                continue
            if scope and scope not in _scopes_for(record):
                continue
            haystack = json.dumps(record, ensure_ascii=False, sort_keys=True).lower()
            if query and query not in haystack:
                continue
            filtered.append(record)
        return filtered

    def inventory_summary(self, query="", category=None):
        """Return one user-facing inventory row per published hardware model."""

        records = self.list_records()
        units_by_model = {}
        for record in records:
            if record.get("record_type") != "hardware_unit" or not record.get("model_ref"):
                continue
            units_by_model.setdefault(record["model_ref"], []).append(record)

        normalized_query = str(query or "").strip().lower()
        normalized_category = str(category or "").strip()
        items = []
        for model in records:
            if model.get("record_type") != "hardware_model":
                continue
            item = _inventory_item(model, units_by_model.get(model.get("hardware_model_id"), []))
            if normalized_category and item["category"] != normalized_category:
                continue
            haystack = " ".join(
                str(item.get(field) or "")
                for field in ("display_name", "manufacturer", "model_or_sku", "category")
            ).lower()
            if normalized_query and normalized_query not in haystack:
                continue
            items.append(item)
        return sorted(items, key=lambda item: (item["display_name"].lower(), item["item_id"]))

    def count_records(self):
        if not self.db_path.exists():
            return 0
        with sqlite3.connect(self.db_path) as conn:
            _ensure_schema(conn)
            return conn.execute("select count(*) from hardware_records").fetchone()[0]

    def record_gap(self, record_id, vault_path, fail_reason):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            _ensure_schema(conn)
            conn.execute(
                "insert into hardware_mirror_gaps (record_id, vault_path, fail_reason, created_at) values (?, ?, ?, ?)",
                (record_id, vault_path, fail_reason, _now()),
            )

    def open_gap_count(self):
        if not self.db_path.exists():
            return 0
        with sqlite3.connect(self.db_path) as conn:
            _ensure_schema(conn)
            return conn.execute("select count(*) from hardware_mirror_gaps where resolved_at is null").fetchone()[0]


def record_id_for(record):
    field = {
        "hardware_model": "hardware_model_id",
        "hardware_unit": "hardware_unit_id",
        "assembly_layout": "layout_id",
    }.get(record.get("record_type"))
    if not field or not record.get(field):
        raise ValueError("hardware record has no stable record ID")
    return record[field]


def _public_record(record):
    hidden = {
        "intake_id",
        "intake_channel",
        "submitted_by",
        "operation_key",
        "captured_at",
        "snapshot_hash",
        "draft_revision",
        "intake_status",
    }
    return {key: value for key, value in record.items() if key not in hidden}


def _scope_for(record):
    return record.get("ownership_scope") or record.get("scope") or (record.get("scope_refs") or [""])[0]


def _scopes_for(record):
    values = set(record.get("scope_refs") or [])
    for key in ("ownership_scope", "scope"):
        if record.get(key):
            values.add(record[key])
    return values


def _inventory_item(model, units):
    totals_known = bool(units)
    total = sum(unit.get("quantity_total", 0) for unit in units) if totals_known else None
    available = sum(unit.get("quantity_available", 0) for unit in units) if totals_known else None
    return {
        "item_id": model["hardware_model_id"],
        "display_name": model.get("canonical_name") or model["hardware_model_id"],
        "manufacturer": model.get("manufacturer") or "",
        "model_or_sku": model.get("model_or_sku") or "",
        "category": _inventory_category(model.get("category")),
        "quantity_total": total,
        "quantity_available": available,
        "status": "needs_info" if not totals_known else "ready" if available else "unavailable",
    }


def _inventory_category(category):
    return {
        "controller": "开发板",
        "sensor": "传感器",
        "actuator": "执行器",
        "power": "电源",
        "enclosure": "结构件",
        "wiring": "连接件",
        "connector": "连接件",
    }.get(str(category or "").lower(), "其他")


def _dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _ensure_schema(conn):
    conn.executescript(
        """
        create table if not exists hardware_intakes (
            intake_id text primary key,
            operation_key text not null unique,
            snapshot_hash text not null,
            intake_status text not null,
            payload_json text not null,
            created_at text not null,
            updated_at text not null
        );
        create table if not exists hardware_records (
            record_id text primary key,
            record_type text not null,
            vault_path text not null,
            scope text not null,
            record_json text not null,
            acceptance_hash text not null,
            updated_at text not null
        );
        create table if not exists hardware_drafts (
            draft_id text primary key,
            revision integer not null,
            status text not null,
            payload_json text not null,
            created_at text not null,
            updated_at text not null
        );
        create table if not exists hardware_analysis_jobs (
            job_id text primary key,
            operation_key text not null unique,
            draft_id text not null,
            draft_revision integer not null,
            status text not null,
            payload_json text not null,
            created_at text not null,
            updated_at text not null
        );
        create table if not exists hardware_mirror_gaps (
            id integer primary key autoincrement,
            record_id text not null,
            vault_path text not null,
            fail_reason text not null,
            created_at text not null,
            resolved_at text
        );
        create index if not exists idx_hardware_records_type on hardware_records(record_type);
        create index if not exists idx_hardware_records_scope on hardware_records(scope);
        """
    )
