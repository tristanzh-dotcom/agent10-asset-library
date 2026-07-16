from dataclasses import dataclass
from contextlib import nullcontext

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
                try:
                    self.rest_client.write_note(path, markdown)
                except Exception as exc:
                    if self.fallback_writer is None:
                        raise
                    self.fallback_writer.write_note(path, markdown)
                    mirror_status = self._upsert_mirror(working, path)
                    return AssetWriteResult(
                        mode="fallback",
                        path=path,
                        asset_id=working["asset_id"],
                        mirror_status=mirror_status,
                        error=str(exc),
                    )
                mirror_status = self._upsert_mirror(working, path)
                return AssetWriteResult(
                    mode="rest",
                    path=path,
                    asset_id=working["asset_id"],
                    mirror_status=mirror_status,
                )
        raise ValueError("asset_id collision retry limit exhausted")

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
