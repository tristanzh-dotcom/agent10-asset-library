from dataclasses import dataclass

from .frontmatter import _render_scalar, _render_yaml_value
from .naming import sanitize_short_title
from .hardware_store import record_id_for


CATEGORY_FOLDERS = {
    "controller": "Controllers",
    "sensor": "Sensors",
    "power": "Power",
    "wiring": "Wiring",
    "connector": "Connectors",
    "enclosure": "Enclosures",
    "tool": "Tools",
    "consumable": "Consumables",
}


@dataclass(frozen=True)
class HardwarePublishResult:
    status: str
    record_id: str
    path: str
    mode: str
    mirror_status: str


def hardware_note_path(record):
    record_type = record.get("record_type")
    record_id = record_id_for(record)
    if record_type == "hardware_model":
        folder = CATEGORY_FOLDERS.get(str(record.get("category", "other")).lower(), "Other")
        root = f"02_Hardware/10_Models/{folder}"
        prefix = "HWM"
        title = record.get("canonical_name") or record_id
    elif record_type == "hardware_unit":
        root = f"02_Hardware/20_Units/{record.get('ownership_scope', 'shared')}"
        prefix = "HWU"
        scope = record.get("ownership_scope", "shared")
        title = f"{scope} - {record.get('canonical_name') or record.get('model_ref') or record_id}"
    elif record_type == "assembly_layout":
        root = f"02_Hardware/30_Layouts/{record.get('scope', 'cross-agent')}"
        prefix = "LAY"
        scope = record.get("scope", "cross-agent")
        target = record.get("target") or "layout"
        title = f"{scope} - {target} - {record.get('title') or record_id}"
    else:
        raise ValueError("unsupported hardware record type")
    safe_title = sanitize_short_title(title, record_id)
    return f"{root}/{prefix} - {safe_title} - {record_id}.md"


def render_hardware_note(record):
    title = record.get("canonical_name") or record.get("title") or record_id_for(record)
    body_summary = record.get("summary") or "资料已登记；请以字段证据和最后核验状态为准。"
    fields = _frontmatter_fields(record)
    lines = ["---"]
    for key in fields:
        value = _safe_note_value(record[key], key)
        if isinstance(value, (dict, list)):
            lines.append(f"{key}:")
            lines.extend(_render_yaml_value(value, indent=2))
        else:
            lines.append(f"{key}: {_render_scalar(value)}")
    lines.extend(
        [
            "---",
            "",
            f"# {title}",
            "",
            "## Summary",
            "",
            str(body_summary).rstrip(),
            "",
            "## Sources",
            "",
            "Evidence is recorded in `evidence_records`; unknown claims remain explicitly unverified.",
            "",
            "## Related",
            "",
            "Relations and scope references are recorded in frontmatter.",
        ]
    )
    lines.extend(_reference_lines(record))
    lines.extend(_unknown_physical_lines(record))
    if record.get("acceptance"):
        lines.extend(
            [
                "",
                "## Acceptance",
                "",
                "The record was accepted from an immutable intake snapshot.",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def _frontmatter_fields(record):
    hidden = {
        "body_markdown",
        "summary",
        "intake_id",
        "intake_channel",
        "submitted_by",
        "operation_key",
        "captured_at",
        "snapshot_hash",
        "draft_revision",
        "intake_status",
    }
    preferred = [
        "record_type",
        "hardware_model_id",
        "hardware_unit_id",
        "layout_id",
        "canonical_name",
        "title",
        "manufacturer",
        "model_or_sku",
        "category",
        "scope",
        "scope_refs",
        "ownership_scope",
        "status",
        "lifecycle_status",
        "availability_status",
        "condition",
        "quantity_total",
        "quantity_available",
        "quantity_reserved",
        "model_ref",
        "member_refs",
        "nominal_dimensions",
        "measured_dimensions",
        "weight_g",
        "interfaces",
        "electrical",
        "installation_constraints",
        "compatibility",
        "relations",
        "evidence_records",
        "technical_documents",
        "photo_refs",
        "layout_refs",
        "constraints",
        "assumptions",
        "open_questions",
        "evidence_refs",
        "last_verified_at",
        "last_reviewed_at",
        "acceptance",
    ]
    keys = [key for key in preferred if key in record and key not in hidden]
    keys.extend(sorted(key for key in record if key not in hidden and key not in keys))
    return keys


def _safe_note_value(value, key=""):
    normalized = str(key).lower().replace("-", "_")
    if normalized in {"body", "raw_text", "raw_message", "chain_of_thought", "source_asset_path", "vault_path", "absolute_path", "token", "api_key", "secret"}:
        return None
    if isinstance(value, dict):
        return {
            child_key: child_value
            for child_key, child in value.items()
            if (child_value := _safe_note_value(child, child_key)) is not None
        }
    if isinstance(value, list):
        return [_safe_note_value(item, key) for item in value]
    if isinstance(value, str) and value.startswith("/"):
        return "[local reference redacted]"
    return value


def _reference_lines(record):
    documents = record.get("technical_documents") if isinstance(record.get("technical_documents"), list) else []
    references = [item for item in documents if isinstance(item, dict) and item.get("url")]
    analysis = record.get("analysis") if isinstance(record.get("analysis"), dict) else {}
    candidates = analysis.get("candidates") if isinstance(analysis.get("candidates"), list) else []
    if not references:
        return []
    lines = ["", "## 参考资料", ""]
    for item in references:
        url = item.get("url") or "[link unavailable]"
        title = item.get("title") or "User supplied technical reference"
        status = item.get("status") or "link_only"
        lines.append(f"- {title}: {url}（{status}）")
    if not candidates:
        lines.extend(["", "资料已保存，未形成硬件候选。"])
    return lines


def _unknown_physical_lines(record):
    missing = []
    if record.get("record_type") == "hardware_model":
        dimensions = record.get("nominal_dimensions")
        constraints = record.get("installation_constraints")
        if not dimensions:
            missing.append("标称外形尺寸（长、宽、高）")
        if not isinstance(constraints, dict) or not constraints.get("hole_pattern"):
            missing.append("孔位")
        if not isinstance(constraints, dict) or not constraints.get("bend_radius"):
            missing.append("弯折半径")
        if not isinstance(constraints, dict) or not constraints.get("thermal_spacing"):
            missing.append("热间距")
        if not isinstance(constraints, dict) or not constraints.get("clearance"):
            missing.append("净空")
    elif record.get("record_type") == "hardware_unit":
        if not record.get("measured_dimensions"):
            missing.append("实物尺寸")
        if record.get("weight_g") is None:
            missing.append("重量")
    if not missing:
        return []
    return ["", "## 待补物理信息", "", "- " + "；".join(missing) + "（保持未核验，需照片标注或工具实测）"]


class HardwareNotePublisher:
    def __init__(self, rest_client, fallback_writer, store, operation_lock_factory=None):
        self.rest_client = rest_client
        self.fallback_writer = fallback_writer
        self.store = store
        self.operation_lock_factory = operation_lock_factory

    def publish(self, accepted):
        if accepted.get("intake_status") != "accepted":
            raise ValueError("hardware record must be accepted before publication")
        acceptance = accepted.get("acceptance") or {}
        if acceptance.get("snapshot_hash") != accepted.get("snapshot_hash"):
            raise ValueError("hardware acceptance snapshot does not match intake snapshot")
        path = hardware_note_path(accepted)
        markdown = render_hardware_note(accepted)
        lock = self.operation_lock_factory(f"hardware-write:{record_id_for(accepted)}") if self.operation_lock_factory else _NoopLock()
        with lock:
            mode = "rest"
            try:
                self.rest_client.write_note(path, markdown)
            except Exception as exc:
                if self.fallback_writer is None:
                    raise
                self.fallback_writer.write_note(path, markdown)
                mode = "fallback"
            try:
                self.store.upsert_record(accepted, path)
            except Exception as exc:
                self.store.record_gap(record_id_for(accepted), path, str(exc))
                return HardwarePublishResult("partial", record_id_for(accepted), path, mode, "gap_recorded")
        return HardwarePublishResult("published", record_id_for(accepted), path, mode, "upserted")


class _NoopLock:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False
