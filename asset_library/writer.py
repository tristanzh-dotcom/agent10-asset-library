from dataclasses import dataclass

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
    ):
        self.rest_client = rest_client
        self.fallback_writer = fallback_writer
        self.mirror = mirror
        self.mirror_gap_journal = mirror_gap_journal
        self.asset_id_factory = asset_id_factory or generate_asset_id
        self.collision_checker = collision_checker

    def write(self, draft):
        draft = dict(draft)
        draft.setdefault("asset_id", self.asset_id_factory())
        draft = prepare_frontmatter_fields(draft)
        errors = validate_draft(draft)
        if errors:
            raise ValueError("; ".join(errors))

        path = build_asset_note_path(draft)
        collision = self._check_collision(draft, path)
        if collision:
            if collision.get("action") == "reuse_existing":
                return AssetWriteResult(
                    mode="idempotent_reuse",
                    path=collision["vault_path"],
                    asset_id=collision["asset_id"],
                )
            if collision.get("action") == "reject":
                raise ValueError(collision.get("reason", "asset collision rejected"))

        markdown = render_note(draft)
        try:
            self.rest_client.write_note(path, markdown)
        except Exception as exc:
            if self.fallback_writer is None:
                raise
            self.fallback_writer.write_note(path, markdown)
            mirror_status = self._upsert_mirror(draft, path)
            return AssetWriteResult(
                mode="fallback",
                path=path,
                asset_id=draft["asset_id"],
                mirror_status=mirror_status,
                error=str(exc),
            )
        mirror_status = self._upsert_mirror(draft, path)
        return AssetWriteResult(
            mode="rest",
            path=path,
            asset_id=draft["asset_id"],
            mirror_status=mirror_status,
        )

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


def build_asset_note_path(draft):
    agent_folder = _agent_folder(draft["agent_id"])
    date_part = _date_from_asset_id(draft["asset_id"])
    title = sanitize_short_title(draft["title"], draft["asset_id"])
    filename = f"{date_part} - {draft['agent_id']} - {title} - {draft['asset_id']}.md"
    return f"01_Agents/{agent_folder}/{filename}"


def _agent_folder(agent_id):
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
