import re
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

TEXT_TRANSLATIONS = {
    "low-voltage controller": "低压控制器",
    "low-voltage temperature sensing": "低压温度感知",
    "offline reminder terminal": "离线提醒终端",
    "low-voltage prototype only": "仅限低压原型",
    "dry enclosure; keep USB and wiring strain-relieved": "放在干燥盒内；USB 与线缆需做应力释放",
    "dry side separated from wet interfaces": "放在干区，与湿区接口分隔",
    "prototype interconnect; do not infer signal role from insulation color": "原型连接用途；不能仅凭绝缘层颜色推断信号角色",
    "single external DATA pull-up": "单个外置 DATA 上拉电阻",
    "stripped copper conductors only; keep junction dry": "仅用于剥皮铜导体；接线点需保持干燥",
    "measure both runs and leave service/drip-loop allowance": "两段走线都需实测，并预留维护余量和滴水弯",
    "not a substitute for a sealed underwater splice": "不能替代密封的水下接头",
    "dry placement; keep cable and power away from splash zones": "放置在干燥处；线缆和电源远离溅水区",
    "body": "主体",
    "power_and_data": "供电与数据",
}

SOURCE_STATUS_LABELS = {
    "link_only": "仅保存链接",
    "verified": "已核验",
    "pending": "待确认",
}

CLAIM_TRANSLATIONS = {
    "appearance or label": "外观或标签",
    "project hardware role": "项目用途",
    "quantity and intended stock role": "数量与库存用途",
    "prototype component roles and dry/wet boundary": "原型部件角色与干湿分界",
    "dry placement and viewing-distance requirements": "干燥放置与观看距离要求",
    "cross-Agent model/reference boundary": "跨 Agent 型号与引用边界",
    "StickS3 physical model and project role": "StickS3 实物型号与项目用途",
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


def render_hardware_note(record, related_paths=None, related_records=None):
    record_map, path_map = _record_context(record, related_paths, related_records)
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
    lines.extend(_quick_info_lines(record, path_map, record_map, related_records is not None))
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
            "Evidence and source summaries are shown below; unknown claims remain explicitly unverified.",
            "",
            "## Related",
            "",
            "Use the links below to browse the related model, stock, and layout records.",
        ]
    )
    lines.extend(_reference_lines(record))
    lines.extend(_related_lines(record, path_map, record_map))
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
    if record.get("record_type") == "assembly_layout":
        return record.get("title") or record_id
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
                return _human_text(value.strip())
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
        if isinstance(value, str) and value.strip():
            label = _human_scope(value.strip())
            if label not in values:
                values.append(label)
    return "、".join(values) or "共享"


def _safe_cell(value):
    if value is None or value == "":
        return "未提供"
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def _record_context(record, related_paths=None, related_records=None):
    record_map = {}
    path_map = dict(related_paths or {})
    candidates = [record, *(related_records or [])]
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        try:
            record_id = record_id_for(candidate)
        except ValueError:
            continue
        record_map[record_id] = candidate
        path_map.setdefault(record_id, hardware_note_path(candidate).removesuffix(".md"))
    return record_map, path_map


def _human_scope(value):
    value = str(value or "").strip()
    match = re.fullmatch(r"agent(\d+)", value, flags=re.IGNORECASE)
    if match:
        return f"Agent{match.group(1)}"
    return value.replace("_", " ") or "共享"


def _model_for(record, record_map):
    model_ref = record.get("model_ref")
    return record_map.get(model_ref) if model_ref else None


def _units_for_model(model_id, record_map):
    return sorted(
        (
            candidate
            for candidate in record_map.values()
            if candidate.get("record_type") == "hardware_unit" and candidate.get("model_ref") == model_id
        ),
        key=lambda candidate: (str(candidate.get("ownership_scope") or "").lower(), record_id_for(candidate)),
    )


def _layouts_for_record(record_id, record_map):
    return sorted(
        (
            candidate
            for candidate in record_map.values()
            if candidate.get("record_type") == "assembly_layout"
            and (
                record_id in (candidate.get("member_refs") or [])
                or record_id in (candidate.get("layout_refs") or [])
            )
        ),
        key=lambda candidate: (_display_name(candidate).lower(), record_id_for(candidate)),
    )


def _inventory_totals(units):
    total = sum(_safe_count(unit.get("quantity_total")) for unit in units)
    available = sum(_safe_count(unit.get("quantity_available")) for unit in units)
    return available, total


def _safe_count(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _unit_label(unit):
    scope = _human_scope(unit.get("ownership_scope") or unit.get("scope") or "共享")
    return f"{scope} 库存"


def _relation_label(record_id, record_map):
    related = record_map.get(record_id)
    if not related:
        return "关联记录"
    if related.get("record_type") == "hardware_unit":
        return _unit_label(related)
    return _display_name(related)


def _quick_info_lines(record, related_paths=None, record_map=None, has_context=False):
    record_map = record_map or {}
    model = _model_for(record, record_map)
    category = record.get("category") or (model or {}).get("category")
    rows = [("分类", _category_label(category))]
    if record.get("manufacturer"):
        rows.append(("品牌", record["manufacturer"]))
    if record.get("model_or_sku"):
        rows.append(("型号", record["model_or_sku"]))
    if record.get("record_type") == "hardware_unit":
        total = record.get("quantity_total")
        available = record.get("quantity_available")
        quantity = f"{available} / {total}" if isinstance(available, int) and isinstance(total, int) else "待补"
        rows.append(("可用 / 总数", quantity))
        if model:
            rows.append(
                (
                    "所属型号",
                    _related_link(record_id_for(model), _display_name(model), related_paths or {}, markdown=True),
                )
            )
    elif record.get("record_type") == "hardware_model" and has_context:
        available, total = _inventory_totals(_units_for_model(record_id_for(record), record_map))
        rows.append(("当前库存", f"{available} / {total}"))
    rows.extend(
        [
            ("使用范围", _scope_label(record)),
            ("资料状态", "已入库" if (record.get("acceptance") or {}).get("status") == "accepted" else "待确认"),
            ("当前状态", _status_label(record)),
            ("核验状态", _evidence_label(record)),
        ]
    )
    return ["| 项目 | 内容 |", "| --- | --- |", *[f"| {label} | {_safe_cell(value)} |" for label, value in rows]]


FIELD_LABELS = {
    "length_mm": "长",
    "width_mm": "宽",
    "height_mm": "高",
    "measurement_scope": "测量范围",
    "source_ref": "来源",
    "logic_voltage": "逻辑电平",
    "mains_control": "市电控制",
    "power_mode": "供电方式",
    "project_role": "用途",
    "resistance_ohm": "电阻",
    "power_rating_w": "额定功率",
    "placement": "放置要求",
    "layout": "布局要求",
    "use": "用途",
    "routing": "走线要求",
    "probe_body": "探头说明",
    "waterproof_claim": "防水说明",
    "cable_bend_radius": "线缆弯折半径",
    "internal_clearance": "内部净空",
    "thermal_spacing": "热间距",
    "usb_service_access": "USB 维护空间",
    "wet_dry_boundary": "干湿分界",
    "kind": "类型",
    "name": "名称",
    "power_and_data": "供电与数据",
}


def _field_label(key):
    return FIELD_LABELS.get(str(key), str(key).replace("_", " "))


def _format_scalar(value, key=""):
    if value is None:
        return "未提供"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, (int, float)):
        suffix = {
            "length_mm": " mm",
            "width_mm": " mm",
            "height_mm": " mm",
            "weight_g": " g",
            "resistance_ohm": " Ω",
            "power_rating_w": " W",
        }.get(key, "")
        return f"{value}{suffix}"
    return _human_text(str(value).replace("\n", " ").strip())


def _human_text(value):
    return TEXT_TRANSLATIONS.get(value, value)


def _readable_value(value, key=""):
    if value is None:
        return "未提供"
    if isinstance(value, dict):
        pairs = []
        for child_key, child_value in value.items():
            if child_key in {"source_ref", "content_sha256", "url"}:
                continue
            pairs.append(f"{_field_label(child_key)}：{_readable_value(child_value, child_key)}")
        return "；".join(pairs) or "未提供"
    if isinstance(value, list):
        if key == "interfaces":
            values = []
            for item in value:
                if isinstance(item, dict):
                    name = item.get("name") or item.get("kind")
                    kind = item.get("kind")
                    values.append(
                        f"{_format_scalar(name, 'name')}（{_field_label(kind)}）"
                        if name and kind and name != kind
                        else _format_scalar(name or item, key)
                    )
                else:
                    values.append(_format_scalar(item, key))
            return "、".join(values) or "未提供"
        return "、".join(_readable_value(item, key) for item in value) or "未提供"
    return _format_scalar(value, key)


def _spec_lines(record):
    lines = []
    for label, key in (("标称尺寸", "nominal_dimensions"), ("实物尺寸", "measured_dimensions"), ("接口", "interfaces"), ("供电与电气", "electrical")):
        value = record.get(key)
        if value not in (None, {}, []):
            lines.append(f"- {label}：{_readable_value(value, key)}")
    return lines or ["- 暂无已确认规格。"]


def _constraint_lines(record):
    constraints = record.get("installation_constraints")
    if not isinstance(constraints, dict) or not constraints:
        return ["- 暂无已确认限制；未知项保持待核验。"]
    return [f"- {_field_label(key)}：{_readable_value(value, key)}" for key, value in constraints.items()]


def _photo_lines(record):
    refs = record.get("photo_refs") if isinstance(record.get("photo_refs"), list) else []
    safe_refs = [
        ref for ref in refs
        if isinstance(ref, str) and ref.startswith("02_Hardware/") and not ref.startswith("/") and not ref.startswith("attachment:")
    ]
    if not safe_refs:
        return []
    return ["", "## 参考照片", "", *[f"![[{ref}]]" for ref in safe_refs], ""]


def _related_lines(record, related_paths, record_map):
    related_paths = related_paths or {}
    lines = []
    model = _model_for(record, record_map)
    if model:
        lines.extend(
            [
                "",
                "## 所属型号",
                "",
                f"- {_display_name(model)}：{_related_link(record_id_for(model), _display_name(model), related_paths)}",
            ]
        )

    if record.get("record_type") == "hardware_model":
        units = _units_for_model(record_id_for(record), record_map)
        lines.extend(["", "## 相关库存", ""])
        if units:
            lines.extend(
                f"- {_unit_label(unit)}：{_related_link(record_id_for(unit), _unit_label(unit), related_paths)}"
                for unit in units
            )
        else:
            lines.append("- 暂无关联库存记录。")

        layouts = _layouts_for_record(record_id_for(record), record_map)
        lines.extend(["", "## 关联布局", ""])
        if layouts:
            lines.extend(
                f"- {_display_name(layout)}：{_related_link(record_id_for(layout), _display_name(layout), related_paths)}"
                for layout in layouts
            )
        else:
            lines.append("- 暂无关联布局记录。")

    if record.get("record_type") == "assembly_layout":
        members = [ref for ref in (record.get("member_refs") or []) if ref]
        lines.extend(["", "## 布局成员", ""])
        if members:
            lines.extend(
                f"- {_relation_label(ref, record_map)}：{_related_link(ref, _relation_label(ref, record_map), related_paths)}"
                for ref in members
            )
        else:
            lines.append("- 暂无成员记录。")

    if record.get("record_type") == "hardware_unit":
        layouts = _layouts_for_record(record_id_for(record), record_map)
        if layouts:
            lines.extend(["", "## 关联布局", ""])
            lines.extend(
                f"- {_display_name(layout)}：{_related_link(record_id_for(layout), _display_name(layout), related_paths)}"
                for layout in layouts
            )

    for ref in record.get("layout_refs") or []:
        if not any(ref == record_id_for(layout) for layout in _layouts_for_record(record_id_for(record), record_map)):
            label = _relation_label(ref, record_map) if ref in record_map else "装配布局"
            lines.append(f"- 关联布局：{_related_link(ref, label, related_paths)}")
    for relation in record.get("relations") or []:
        if not isinstance(relation, dict) or not relation.get("ref"):
            continue
        relation_type = relation.get("relation_type") or "相关记录"
        ref = relation["ref"]
        if relation_type == "used_by":
            label = _human_scope(ref)
            lines.append(f"- 使用范围：{label}")
            continue
        label = "装配布局" if relation_type == "part_of_layout" else relation_type
        lines.append(f"- {label}：{_related_link(ref, label, related_paths)}")
    return lines


def _related_link(record_id, label, related_paths, markdown=False):
    path = related_paths.get(record_id)
    if path:
        return f"[{label}](<{path}>)" if markdown else f"[[{path}|{label}]]"
    return label or "关联记录"


def _reference_lines(record):
    documents = record.get("technical_documents") if isinstance(record.get("technical_documents"), list) else []
    references = [item for item in documents if isinstance(item, dict)]
    evidence = [item for item in record.get("evidence_records") or [] if isinstance(item, dict)]
    evidence_refs = [item for item in record.get("evidence_refs") or [] if isinstance(item, str) and item.strip()]
    analysis = record.get("analysis") if isinstance(record.get("analysis"), dict) else {}
    candidates = analysis.get("candidates") if isinstance(analysis.get("candidates"), list) else []
    if not references and not evidence and not evidence_refs:
        return []
    lines = ["", "## 来源与核验", ""]
    for item in references:
        title = item.get("title") or _source_label(item.get("source_ref")) or "已登记资料"
        status = SOURCE_STATUS_LABELS.get(item.get("status") or "link_only", item.get("status") or "link_only")
        url = item.get("url")
        if isinstance(url, str) and url.startswith(("https://", "http://")):
            lines.append(f"- [{title}]({url})（{status}）")
        else:
            lines.append(f"- {title}（{status}）")
    for item in evidence:
        claim = _safe_cell(CLAIM_TRANSLATIONS.get(item.get("claim"), item.get("claim") or "已登记证据"))
        level = EVIDENCE_LABELS.get(item.get("level"), EVIDENCE_LABELS["unverified"])
        lines.append(f"- {claim}：{level}")
    for ref in evidence_refs:
        lines.append(f"- {_source_label(ref)}")
    if not candidates:
        lines.extend(["", "资料已保存，未形成硬件候选。"])
    return lines


def _source_label(source_ref):
    if not isinstance(source_ref, str) or not source_ref.strip():
        return ""
    value = source_ref.strip()
    if value.startswith(("https://", "http://")):
        return "外部资料"
    if ":" in value and "/" not in value:
        prefix, suffix = value.split(":", 1)
        prefix_label = {"photo": "照片", "vendor": "厂商资料", "inventory": "库存记录"}.get(prefix, prefix)
        return f"{prefix_label} {suffix.replace('_', ' ')}".strip()
    filename = re.split(r"[\\/]", value)[-1]
    filename = re.sub(r"\.[^.]+$", "", filename)
    return re.sub(r"[-_]+", " ", filename).strip() or "已登记来源"


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
        context_records = [accepted]
        if self.index_publisher is not None:
            try:
                context_records = _merge_records(self.store.list_records(), accepted)
            except Exception:
                context_records = [accepted]
        path = hardware_note_path(accepted)
        markdown = render_hardware_note(
            accepted,
            related_records=context_records if self.index_publisher is not None else None,
        )
        lock = self.operation_lock_factory(f"hardware-write:{record_id_for(accepted)}") if self.operation_lock_factory else _NoopLock()
        with lock:
            try:
                mode = self._write_note(path, markdown)
            except Exception:
                raise
            try:
                self.store.upsert_record(accepted, path)
            except Exception as exc:
                self.store.record_gap(record_id_for(accepted), path, str(exc))
                return HardwarePublishResult("partial", record_id_for(accepted), path, mode, "gap_recorded")
        if self.index_publisher is not None:
            related_gap = False
            index_status = "partial"
            try:
                records = self.store.list_records()
                for related in records:
                    related_id = record_id_for(related)
                    if related_id == record_id_for(accepted) or related_id not in _related_record_ids(accepted, records):
                        continue
                    related_path = hardware_note_path(related)
                    related_markdown = render_hardware_note(related, related_records=records)
                    related_lock = self.operation_lock_factory(f"hardware-write:{related_id}") if self.operation_lock_factory else _NoopLock()
                    try:
                        with related_lock:
                            related_mode = self._write_note(related_path, related_markdown)
                        if related_mode == "fallback":
                            mode = "fallback"
                    except Exception as exc:
                        related_gap = True
                        self.store.record_gap(related_id, related_path, str(exc))
                index_result = self.index_publisher.publish(records)
                index_status = getattr(index_result, "status", "partial")
                if index_status == "published" and not related_gap:
                    return HardwarePublishResult("published", record_id_for(accepted), path, mode, "upserted", "published")
                reason = getattr(index_result, "error", "") or f"index publication status: {index_status}"
                if related_gap:
                    reason = f"{reason}; related card publication was partial"
            except Exception as exc:
                reason = str(exc)
            self.store.record_gap(
                "hardware-indexes",
                "02_Hardware/00_Index",
                reason,
            )
            return HardwarePublishResult("partial", record_id_for(accepted), path, mode, "index_gap", "partial")
        return HardwarePublishResult("published", record_id_for(accepted), path, mode, "upserted")

    def _write_note(self, path, markdown):
        try:
            self.rest_client.write_note(path, markdown)
        except Exception:
            if self.fallback_writer is None:
                raise
            self.fallback_writer.write_note(path, markdown)
            return "fallback"
        return "rest"


def _merge_records(records, accepted):
    merged = {}
    for record in records or []:
        if not isinstance(record, dict):
            continue
        merged[record_id_for(record)] = dict(record)
    merged[record_id_for(accepted)] = dict(accepted)
    return list(merged.values())


def _related_record_ids(accepted, records):
    accepted_id = record_id_for(accepted)
    related = set()
    if accepted.get("record_type") == "hardware_model":
        related.update(
            record_id_for(record)
            for record in records
            if record.get("record_type") == "hardware_unit" and record.get("model_ref") == accepted_id
        )
        related.update(
            record_id_for(record)
            for record in records
            if record.get("record_type") == "assembly_layout"
            and accepted_id in (record.get("member_refs") or [])
        )
    elif accepted.get("record_type") == "hardware_unit":
        model_ref = accepted.get("model_ref")
        if model_ref:
            related.add(model_ref)
            related.update(
                record_id_for(record)
                for record in records
                if record.get("record_type") == "assembly_layout"
                and model_ref in (record.get("member_refs") or [])
            )
    elif accepted.get("record_type") == "assembly_layout":
        members = set(accepted.get("member_refs") or [])
        related.update(members)
        related.update(
            record_id_for(record)
            for record in records
            if record.get("record_type") == "hardware_unit"
            and record.get("model_ref") in members
        )
    return related


class _NoopLock:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False
