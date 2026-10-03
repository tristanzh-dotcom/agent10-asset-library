from dataclasses import dataclass
from contextlib import nullcontext
import hashlib

from .collision import idempotent_key

from .frontmatter import prepare_frontmatter_fields, render_note
from .naming import generate_asset_id, sanitize_short_title
from .schema import validate_draft


@dataclass(frozen=True)
class AssetWriteResult:
    mode: str
    path: str
    asset_id: str
    mirror_status: str = "not_configured"
    error: str = ""


class RestFirstAssetWriter:
    def __init__(
        self,
        rest_client,
        fallback_writer=None,
        mirror=None,
        mirror_gap_journal=None,
        asset_id_factory=None,
        collision_checker=None,
        operation_lock_factory=None,
    ):
        self.rest_client = rest_client
        self.fallback_writer = fallback_writer
        self.mirror = mirror
        self.mirror_gap_journal = mirror_gap_journal
        self.asset_id_factory = asset_id_factory or generate_asset_id
        self.collision_checker = collision_checker
        self.operation_lock_factory = operation_lock_factory

    def write(self, draft):
        if draft.get("asset_id"):
            raise ValueError("normal drafts must not include asset_id")
        return self._write(draft)

    def write_migration(self, draft):
        if not draft.get("asset_id"):
            raise ValueError("controlled migration drafts must include asset_id")
        return self._write(draft)

    def _write(self, draft):
        base = dict(draft)
        caller_supplied_id = bool(base.get("asset_id"))
        for attempt in range(5):
            working = dict(base)
            if not caller_supplied_id:
                working["asset_id"] = self.asset_id_factory()
            working = prepare_frontmatter_fields(working)
            errors = validate_draft(working)
            if errors:
                raise ValueError("; ".join(errors))

            path = build_asset_note_path(working)
            lock = self._operation_lock(working["asset_id"])
            with lock:
                initialize = getattr(self.mirror, "initialize", None)
                if initialize:
                    initialize()
                journal = self.mirror_gap_journal
                get_operation = getattr(journal, "get_operation", None)
                operation = get_operation(idempotent_key(working)) if get_operation else None
                if operation:
                    reused = self._resume_operation(operation)
                    if reused is not None:
                        return reused
                    # A durable intent with no primary note retries its original identity.
                    working["asset_id"] = operation["asset_id"]
                    path = operation["vault_path"]
                    if _note_hash(render_note(working)) != operation["note_hash"]:
                        raise ValueError("unfinished asset write requires the original draft")
                collision = self._check_collision(working, path)
                if collision:
                    if collision.get("action") == "reuse_existing":
                        return AssetWriteResult(
                            mode="idempotent_reuse",
                            path=collision["vault_path"],
                            asset_id=collision["asset_id"],
                            mirror_status="reused",
                        )
                    retryable = collision.get("action") in {"retry_asset_id", "reject"}
                    if retryable and not caller_supplied_id and attempt < 4:
                        continue
                    raise ValueError(collision.get("reason", "asset collision rejected"))

                markdown = render_note(working)
                if get_operation:
                    operation = {
                        "idempotent_key": idempotent_key(working),
                        "asset_id": working["asset_id"], "vault_path": path,
                        "note_hash": _note_hash(markdown), "state": "intended",
                        "draft": _mirror_metadata(working),
                    }
                    journal.save_operation(operation)
                mode, error = "rest", ""
                try:
                    self.rest_client.write_note(path, markdown)
                except Exception as exc:
                    if self.fallback_writer is None:
                        raise
                    self.fallback_writer.write_note(path, markdown)
                    mode, error = "fallback", str(exc)
                if operation:
                    operation.update(state="primary_written", mode=mode)
                    journal.save_operation(operation)
                mirror_status = self._upsert_mirror(working, path)
                if operation and mirror_status == "upserted":
                    operation["state"] = "complete"
                    journal.save_operation(operation)
                return AssetWriteResult(
                    mode=mode,
                    path=path,
                    asset_id=working["asset_id"],
                    mirror_status=mirror_status,
                    error=error,
                )
        raise ValueError("asset_id collision retry limit exhausted")

    def _resume_operation(self, operation):
        probe = getattr(self.collision_checker, "vault_probe", None)
        if probe is None:
            raise ValueError("cannot verify unfinished asset write without a Vault probe")
        note = probe.read_note_if_exists(operation["vault_path"])
        if note is None:
            if operation["state"] == "intended":
                return None
            raise ValueError("previously written Vault note is missing")
        if operation["state"] == "intended":
            if _note_hash(note) != operation["note_hash"]:
                raise ValueError("unfinished asset write conflicts with the existing Vault note")
            operation["state"] = "primary_written"
            self.mirror_gap_journal.save_operation(operation)
        existing = self.mirror.get_by_asset_id(operation["asset_id"]) if self.mirror else None
        if operation["state"] == "complete" and existing:
            # Complete operations and user-edited notes are immutable on resubmission.
            self.mirror_gap_journal.resolve_asset_gaps(operation["asset_id"], operation["vault_path"])
            return AssetWriteResult("idempotent_reuse", operation["vault_path"], operation["asset_id"], "reused")
        mirror_status = self._upsert_mirror(operation["draft"], operation["vault_path"])
        if mirror_status == "upserted":
            operation["state"] = "complete"
            self.mirror_gap_journal.save_operation(operation)
            self.mirror_gap_journal.resolve_asset_gaps(operation["asset_id"], operation["vault_path"])
        return AssetWriteResult("idempotent_reuse", operation["vault_path"], operation["asset_id"], mirror_status)

    def _upsert_mirror(self, draft, path):
        if self.mirror is None:
            return "not_configured"
        try:
            self.mirror.upsert_asset(draft, path)
            return "upserted"
        except Exception as exc:
            if self.mirror_gap_journal is None:
                raise
            self.mirror_gap_journal.append_gap(
                asset_id=draft["asset_id"],
                vault_path=path,
                fail_reason=str(exc),
            )
            return "gap_recorded"

    def _check_collision(self, draft, path):
        if self.collision_checker is None:
            return None
        return self.collision_checker.check(draft, path)

    def _operation_lock(self, asset_id):
        if self.operation_lock_factory is None:
            return nullcontext()
        return self.operation_lock_factory(f"asset-write:{asset_id}")


def build_asset_note_path(draft):
    agent_folder = _agent_folder(draft["agent_id"])
    date_part = _date_from_asset_id(draft["asset_id"])
    title = sanitize_short_title(draft["title"], draft["asset_id"])
    filename = f"{date_part} - {draft['agent_id']} - {title} - {draft['asset_id']}.md"
    return f"01_Agents/{agent_folder}/{filename}"


def _agent_folder(agent_id):
    if agent_id == "codex":
        return "Codex"
    if agent_id.startswith("agent") and len(agent_id) >= 7:
        suffix = agent_id[5:7]
        if suffix.isdigit():
            return f"Agent{suffix}"
    return agent_id


def _date_from_asset_id(asset_id):
    parts = asset_id.split("_")
    if len(parts) >= 3 and len(parts[1]) == 8:
        raw = parts[1]
        return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
    raise ValueError(f"asset_id has invalid date format: {asset_id}")


def _note_hash(markdown):
    return hashlib.sha256(markdown.encode("utf-8")).hexdigest()


def _mirror_metadata(draft):
    # No body or source reference content in the private recovery journal.
    fields = ("asset_id", "asset_schema_version", "title", "agent_id", "workflow_id", "asset_type",
              "status", "knowledge_status", "source_status", "sensitivity", "source_content_hash",
              "hash_source", "created_at", "updated_at", "source_asset_path", "tags")
    return {field: draft[field] for field in fields if field in draft}
