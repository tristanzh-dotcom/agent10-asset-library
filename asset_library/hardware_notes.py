import json
from dataclasses import dataclass

from .frontmatter import _render_scalar, _render_yaml_value
from .naming import sanitize_short_title
from .hardware_store import record_id_for
from .hardware_labels import localized_hardware_name


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

CATEGORY_LABELS = {
    "controller": "开发板",
    "sensor": "传感器",
    "actuator": "执行器",
    "power": "电源",
    "wiring": "连接件",
    "connector": "连接件",
    "enclosure": "结构件",
    "tool": "工具",
    "consumable": "耗材",
}

MODEL_STATUS_LABELS = {
    "draft": "草稿",
    "candidate": "候选",
    "verified": "已核验",
    "retired": "已退役",
}

UNIT_STATUS_LABELS = {
    "planned": "计划中",
    "available": "可用",
    "reserved": "预留",
    "in_use": "使用中",
    "consumed": "已耗尽",
    "retired": "已报废",
}

LAYOUT_STATUS_LABELS = {
    "draft": "草稿",
    "measured": "已测量",
    "approved": "已批准",
    "superseded": "已替代",
}

EVIDENCE_LABELS = {
    "official": "官方资料",
    "measured": "实物实测",
    "label_or_photo": "照片确认",
    "reported": "人工转述",
    "unverified": "未核验",
}


@dataclass(frozen=True)
class HardwarePublishResult:
    status: str
    record_id: str
    path: str
    mode: str
    mirror_status: str
    index_status: str = "not_requested"


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


def render_hardware_note(record, related_paths=None):
    display_name = _display_name(record)
    title = display_name or record.get("title") or record_id_for(record)
    canonical_name = record.get("canonical_name") or record.get("title") or record_id_for(record)
    projected = dict(record)
    projected["display_name"] = title
    projected["aliases"] = _aliases(record, title)
    body_summary = _summary(record, title)
    fields = _frontmatter_fields(projected)
    lines = ["---"]
    for key in fields:
        value = _safe_note_value(projected[key], key)
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
            *( [f"> {canonical_name}", ""] if canonical_name != title else [] ),
        ]
    )
    lines.extend(_photo_lines(record))
    lines.extend(
        [
            "## 一句话说明",
            "",
            body_summary,
            "",
            "## 快速信息",
            "",
        ]
    )
    lines.extend(_quick_info_lines(record))
    lines.extend(
        [
            "",
            "## 已知规格",
            "",
        ]
    )
    lines.extend(_spec_lines(record))
    lines.extend(
        [
            "",
            "## 适用与限制",
            "",
        ]
    )
    lines.extend(_constraint_lines(record))
    lines.extend(
        [
            "",
            "## Summary",
            "",
            body_summary,
            "",
            "## Sources",
            "",
            "Evidence is recorded in `evidence_records`; unknown claims remain explicitly unverified.",
            "",
            "## Related",
            "",
            "Relations and scope references are recorded below and in frontmatter.",
        ]
    )
    lines.extend(_reference_lines(record))
    lines.extend(_related_lines(record, related_paths))
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
        "display_name_zh",
    }
    preferred = [
        "record_type",
        "hardware_model_id",
        "hardware_unit_id",
        "layout_id",
        "canonical_name",
        "display_name",
        "aliases",
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
    if isinstance(value, str) and value.startswith("attachment:"):
        return None
    if isinstance(value, str) and value.startswith("/"):
        return "[local reference redacted]"
    return value


def _display_name(record):
    explicit = record.get("display_name") or record.get("display_name_zh")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    record_id = record_id_for(record)
    return localized_hardware_name(record_id, record) or record.get("canonical_name") or record_id


def _aliases(record, display_name):
    aliases = record.get("aliases") if isinstance(record.get("aliases"), list) else []
    values = [item.strip() for item in aliases if isinstance(item, str) and item.strip()]
    for candidate in (record.get("canonical_name"), record.get("model_or_sku")):
        if isinstance(candidate, str) and candidate.strip() and candidate.strip() != display_name:
            values.append(candidate.strip())
    result = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _summary(record, display_name):
    explicit = record.get("summary")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    if record.get("record_type") == "hardware_unit":
        available = record.get("quantity_available")
        total = record.get("quantity_total")
        if isinstance(available, int) and isinstance(total, int):
            return f"{display_name}库存批次，当前可用 {available} / {total}。"
        return f"{display_name}库存批次，数量待补。"
    if record.get("record_type") == "assembly_layout":
        return "装配布局记录；请以约束、假设和证据为准。"
    electrical = record.get("electrical") if isinstance(record.get("electrical"), dict) else {}
    constraints = record.get("installation_constraints") if isinstance(record.get("installation_constraints"), dict) else {}
    for source in (electrical, constraints):
        for key in ("project_role", "use", "placement", "layout"):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return "资料已登记；请以字段证据和最后核验状态为准。"


def _category_label(value):
    return CATEGORY_LABELS.get(str(value or "").lower(), "其他")


def _evidence_label(record):
    levels = {
        item.get("level")
        for item in (record.get("evidence_records") or [])
        if isinstance(item, dict) and item.get("level")
    }
    for level in ("official", "measured", "label_or_photo", "reported", "unverified"):
        if level in levels:
            return EVIDENCE_LABELS[level]
    return EVIDENCE_LABELS["unverified"]


def _status_label(record):
    record_type = record.get("record_type")
    if record_type == "hardware_unit":
        return UNIT_STATUS_LABELS.get(record.get("availability_status"), "待核验")
    if record_type == "assembly_layout":
        return LAYOUT_STATUS_LABELS.get(record.get("status"), "待核验")
    return MODEL_STATUS_LABELS.get(record.get("lifecycle_status"), "待核验")


def _scope_label(record):
    values = []
    for value in [record.get("ownership_scope"), record.get("scope"), *(record.get("scope_refs") or [])]:
        if isinstance(value, str) and value.strip() and value.strip() not in values:
            values.append(value.strip())
    return "、".join(values) or "共享"


def _safe_cell(value):
    if value is None or value == "":
        return "未提供"
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def _quick_info_lines(record):
    rows = [("分类", _category_label(record.get("category")))]
    if record.get("manufacturer"):
        rows.append(("品牌", record["manufacturer"]))
    if record.get("model_or_sku"):
        rows.append(("型号", record["model_or_sku"]))
    if record.get("record_type") == "hardware_unit":
        total = record.get("quantity_total")
        available = record.get("quantity_available")
        quantity = f"{available} / {total}" if isinstance(available, int) and isinstance(total, int) else "待补"
        rows.append(("可用 / 总数", quantity))
    rows.extend(
        [
            ("使用范围", _scope_label(record)),
            ("资料状态", "已入库" if (record.get("acceptance") or {}).get("status") == "accepted" else "待确认"),
            ("当前状态", _status_label(record)),
            ("核验状态", _evidence_label(record)),
        ]
    )
    return ["| 项目 | 内容 |", "| --- | --- |", *[f"| {label} | {_safe_cell(value)} |" for label, value in rows]]


def _compact(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _spec_lines(record):
    lines = []
    for label, key in (("标称尺寸", "nominal_dimensions"), ("实物尺寸", "measured_dimensions"), ("接口", "interfaces"), ("供电与电气", "electrical")):
        value = record.get(key)
        if value not in (None, {}, []):
            lines.append(f"- {label}：{_compact(value)}")
    return lines or ["- 暂无已确认规格。"]


def _constraint_lines(record):
    constraints = record.get("installation_constraints")
    if not isinstance(constraints, dict) or not constraints:
        return ["- 暂无已确认限制；未知项保持待核验。"]
    return [f"- {_safe_cell(key)}：{_safe_cell(value)}" for key, value in constraints.items()]


def _photo_lines(record):
    refs = record.get("photo_refs") if isinstance(record.get("photo_refs"), list) else []
    safe_refs = [
        ref for ref in refs
        if isinstance(ref, str) and ref.startswith("02_Hardware/") and not ref.startswith("/") and not ref.startswith("attachment:")
    ]
    if not safe_refs:
        return []
    return ["", "## 参考照片", "", *[f"![[{ref}]]" for ref in safe_refs], ""]


def _related_lines(record, related_paths):
    related_paths = related_paths or {}
    links = []
    model_ref = record.get("model_ref")
    if model_ref:
        links.append(f"- 所属型号：{_related_link(model_ref, '型号', related_paths)}")
    for ref in record.get("layout_refs") or []:
        links.append(f"- 关联布局：{_related_link(ref, '装配布局', related_paths)}")
    for relation in record.get("relations") or []:
        if not isinstance(relation, dict) or not relation.get("ref"):
            continue
        relation_type = relation.get("relation_type") or "相关记录"
        label = "装配布局" if relation_type == "part_of_layout" else relation_type
        links.append(f"- {label}：{_related_link(relation['ref'], label, related_paths)}")
    return ["", *links] if links else []


def _related_link(record_id, label, related_paths):
    path = related_paths.get(record_id)
    if path:
        return f"[[{path}|{label}]]"
    return f"`{record_id}`"


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
    def __init__(self, rest_client, fallback_writer, store, operation_lock_factory=None, index_publisher=None):
        self.rest_client = rest_client
        self.fallback_writer = fallback_writer
        self.store = store
        self.operation_lock_factory = operation_lock_factory
        self.index_publisher = index_publisher

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
        if self.index_publisher is not None:
            index_status = "partial"
            try:
                index_result = self.index_publisher.publish(self.store.list_records())
                index_status = getattr(index_result, "status", "partial")
                if index_status == "published":
                    return HardwarePublishResult("published", record_id_for(accepted), path, mode, "upserted", "published")
                reason = getattr(index_result, "error", "") or f"index publication status: {index_status}"
            except Exception as exc:
                reason = str(exc)
            self.store.record_gap(
                "hardware-indexes",
                "02_Hardware/00_Index",
                reason,
            )
            return HardwarePublishResult("partial", record_id_for(accepted), path, mode, "index_gap", "partial")
        return HardwarePublishResult("published", record_id_for(accepted), path, mode, "upserted")


class _NoopLock:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False
