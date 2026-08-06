"""Pure Markdown projections for the user-facing hardware library indexes."""

from dataclasses import dataclass
from datetime import datetime, timezone

from .hardware_notes import (
    _category_label,
    _display_name,
    _scope_label,
    _status_label,
    hardware_note_path,
)
from .hardware_store import record_id_for


INDEX_PATHS = (
    "02_Hardware/00_Index/Hardware Home.md",
    "02_Hardware/00_Index/Inventory.md",
    "02_Hardware/00_Index/Models by Category.md",
    "02_Hardware/00_Index/Inventory by Scope.md",
    "02_Hardware/00_Index/Layouts.md",
    "02_Hardware/00_Index/Needs Verification.md",
)


@dataclass(frozen=True)
class HardwareIndexPublishResult:
    status: str
    written: tuple
    mode: str
    error: str = ""


def render_hardware_index_bundle(records, generated_at=None):
    records = [dict(record) for record in records if isinstance(record, dict)]
    models = sorted(
        (record for record in records if record.get("record_type") == "hardware_model"),
        key=lambda record: (_record_label(record).lower(), record_id_for(record)),
    )
    units = [record for record in records if record.get("record_type") == "hardware_unit"]
    layouts = sorted(
        (record for record in records if record.get("record_type") == "assembly_layout"),
        key=lambda record: (_record_label(record).lower(), record_id_for(record)),
    )
    units_by_model = _group_units(units)
    paths = {record_id_for(record): _note_link_path(record) for record in records}
    generated = generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    summaries = {
        record_id_for(model): _inventory_summary(model, units_by_model.get(record_id_for(model), []))
        for model in models
    }
    return {
        INDEX_PATHS[0]: _render_home(models, summaries, paths, generated),
        INDEX_PATHS[1]: _render_inventory(models, summaries, paths, generated),
        INDEX_PATHS[2]: _render_models_by_category(models, paths, generated),
        INDEX_PATHS[3]: _render_inventory_by_scope(models, units, summaries, paths, generated),
        INDEX_PATHS[4]: _render_layouts(layouts, paths, generated),
        INDEX_PATHS[5]: _render_needs_verification(records, paths, generated),
    }


class HardwareIndexPublisher:
    """Write a complete index bundle through the existing REST-first boundary."""

    def __init__(self, rest_client, fallback_writer, operation_lock_factory=None):
        self.rest_client = rest_client
        self.fallback_writer = fallback_writer
        self.operation_lock_factory = operation_lock_factory

    def publish(self, records, generated_at=None):
        bundle = render_hardware_index_bundle(records, generated_at=generated_at)
        written = []
        mode = "rest"
        lock = self.operation_lock_factory("hardware-indexes") if self.operation_lock_factory else _NoopLock()
        with lock:
            for path in INDEX_PATHS:
                try:
                    self.rest_client.write_note(path, bundle[path])
                except Exception as exc:
                    if self.fallback_writer is None:
                        return HardwareIndexPublishResult("partial", tuple(written), mode, str(exc))
                    try:
                        self.fallback_writer.write_note(path, bundle[path])
                    except Exception as fallback_exc:
                        return HardwareIndexPublishResult("partial", tuple(written), "fallback", str(fallback_exc))
                    mode = "fallback"
                written.append(path)
        return HardwareIndexPublishResult("published", tuple(written), mode)


def _group_units(units):
    grouped = {}
    for unit in units:
        model_ref = unit.get("model_ref")
        if model_ref:
            grouped.setdefault(model_ref, []).append(unit)
    return grouped


def _inventory_summary(model, units):
    total = sum(_count(unit.get("quantity_total")) for unit in units)
    available = sum(_count(unit.get("quantity_available")) for unit in units)
    if not units:
        total = available = 0
    if available:
        status = "可用"
    elif total:
        status = "不可用"
    else:
        status = "无库存"
    return {"total": total, "available": available, "status": status}


def _render_home(models, summaries, paths, generated):
    available_models = sum(1 for model in models if summaries[record_id_for(model)]["available"])
    available_total = sum(summaries[record_id_for(model)]["available"] for model in models)
    needs = sum(1 for model in models if _needs_verification(model))
    lines = [
        "---",
        "record_type: hardware_index",
        "index_kind: hardware_home",
        "namespace: 02_Hardware",
        f'generated_at: "{generated}"',
        "---",
        "",
        "# Hardware Home",
        "",
        f"生成时间：{generated}",
        "",
        "| 指标 | 数值 |",
        "| --- | ---: |",
        f"| 硬件型号数 | {len(models)} |",
        f"| 有库存的型号数 | {available_models} |",
        f"| 可用件总数 | {available_total} |",
        f"| 待核验 / 待补资料 | {needs} |",
        "",
        "## 我的硬件",
        "",
        "| 名称 | 分类 | 可用 / 总数 | 用途 | 使用范围 | 状态 |",
        "| --- | --- | ---: | --- | --- | --- |",
    ]
    for model in models:
        summary = summaries[record_id_for(model)]
        lines.append(_inventory_row(model, summary, paths))
    if not models:
        lines.append("| 暂无硬件记录 | - | 0 / 0 | - | - | 待录入 |")
    lines.extend(_home_links())
    return _finish(lines)


def _render_inventory(models, summaries, paths, generated):
    lines = [
        "---",
        "record_type: hardware_index",
        "index_kind: inventory",
        "namespace: 02_Hardware",
        f'generated_at: "{generated}"',
        "---",
        "",
        "# Inventory",
        "",
        f"生成时间：{generated}",
        "",
        "| 名称 | 品牌 / 型号 | 可用 / 总数 | 状态 |",
        "| --- | --- | ---: | --- |",
    ]
    for model in models:
        summary = summaries[record_id_for(model)]
        label = _record_label(model)
        link = _record_link(model, label, paths)
        brand_model = " / ".join(filter(None, [model.get("manufacturer"), model.get("model_or_sku")])) or "未提供"
        lines.append(f"| {link} | {brand_model} | {summary['available']} / {summary['total']} | {summary['status']} |")
    if not models:
        lines.append("| 暂无库存 | - | 0 / 0 | 待录入 |")
    return _finish(lines)


def _render_models_by_category(models, paths, generated):
    grouped = {}
    for model in models:
        grouped.setdefault(_category_label(model.get("category")), []).append(model)
    lines = ["---", "record_type: hardware_index", "index_kind: models_by_category", "namespace: 02_Hardware", f'generated_at: "{generated}"', "---", "", "# Models by Category", ""]
    for category in sorted(grouped):
        lines.extend([f"## {category}", ""])
        for model in grouped[category]:
            lines.append(f"- {_record_link(model, _record_label(model), paths)}")
        lines.append("")
    if not grouped:
        lines.append("暂无型号记录。")
    return _finish(lines)


def _render_inventory_by_scope(models, units, summaries, paths, generated):
    model_by_id = {record_id_for(model): model for model in models}
    grouped = {}
    for unit in units:
        model = model_by_id.get(unit.get("model_ref"))
        if not model:
            continue
        scope = unit.get("ownership_scope") or "shared"
        grouped.setdefault(scope, {}).setdefault(unit["model_ref"], []).append(unit)
    lines = ["---", "record_type: hardware_index", "index_kind: inventory_by_scope", "namespace: 02_Hardware", f'generated_at: "{generated}"', "---", "", "# Inventory by Scope", ""]
    for scope in sorted(grouped):
        lines.extend([f"## {scope}", "", "| 名称 | 可用 / 总数 |", "| --- | ---: |"])
        for model_id, scoped_units in sorted(grouped[scope].items(), key=lambda item: _record_label(model_by_id[item[0]]).lower()):
            model = model_by_id[model_id]
            summary = _inventory_summary(model, scoped_units)
            lines.append(f"| {_record_link(model, _record_label(model), paths)} | {summary['available']} / {summary['total']} |")
        lines.append("")
    if not grouped:
        lines.append("暂无库存范围记录。")
    return _finish(lines)


def _render_layouts(layouts, paths, generated):
    lines = ["---", "record_type: hardware_index", "index_kind: layouts", "namespace: 02_Hardware", f'generated_at: "{generated}"', "---", "", "# Layouts", ""]
    for layout in layouts:
        lines.append(f"## {_record_link(layout, _record_label(layout), paths)}")
        lines.append("")
        members = layout.get("member_refs") or []
        if members:
            lines.append("成员：" + "、".join(_related_record_link(ref, paths) for ref in members))
        else:
            lines.append("成员：暂无")
        lines.append("")
    if not layouts:
        lines.append("暂无装配布局。")
    return _finish(lines)


def _render_needs_verification(records, paths, generated):
    lines = ["---", "record_type: hardware_index", "index_kind: needs_verification", "namespace: 02_Hardware", f'generated_at: "{generated}"', "---", "", "# Needs Verification", "", "| 记录 | 类型 | 原因 |", "| --- | --- | --- |"]
    found = False
    for record in sorted(records, key=lambda item: (_record_label(item).lower(), record_id_for(item))):
        if not _needs_verification(record):
            continue
        found = True
        reason = "缺少独立核验时间或证据等级仍为候选"
        lines.append(f"| {_record_link(record, _record_label(record), paths)} | {_record_type_label(record)} | {reason} |")
    if not found:
        lines.append("| 暂无 | - | 当前没有待核验记录 |")
    return _finish(lines)


def _inventory_row(model, summary, paths):
    use = _usage(model)
    return f"| {_record_link(model, _record_label(model), paths)} | {_category_label(model.get('category'))} | {summary['available']} / {summary['total']} | {use} | {_scope_label(model)} | {summary['status']} |"


def _usage(record):
    for source_key in ("electrical", "installation_constraints"):
        source = record.get(source_key) if isinstance(record.get(source_key), dict) else {}
        for key in ("project_role", "use", "placement", "layout"):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return "待补用途"


def _needs_verification(record):
    levels = {item.get("level") for item in record.get("evidence_records") or [] if isinstance(item, dict)}
    if levels.intersection({"reported", "label_or_photo", "unverified"}):
        return True
    return not (record.get("last_verified_at") or record.get("last_reviewed_at"))


def _record_label(record):
    if record.get("record_type") == "assembly_layout":
        return record.get("display_name") or record.get("title") or record_id_for(record)
    if record.get("record_type") == "hardware_unit":
        model_ref = record.get("model_ref")
        return localized_model_label(model_ref) or record.get("display_name") or record.get("canonical_name") or record_id_for(record)
    return _display_name(record)


def localized_model_label(model_ref):
    if not model_ref:
        return ""
    from .hardware_labels import localized_hardware_name

    return localized_hardware_name(model_ref)


def _record_link(record, label, paths):
    record_id = record_id_for(record)
    path = paths.get(record_id) or _note_link_path(record)
    return f"[[{path}|{label}]]"


def _related_record_link(record_id, paths):
    path = paths.get(record_id)
    return f"[[{path}|{record_id}]]" if path else f"`{record_id}`"


def _note_link_path(record):
    return hardware_note_path(record).removesuffix(".md")


def _record_type_label(record):
    return {
        "hardware_model": "型号",
        "hardware_unit": "库存",
        "assembly_layout": "布局",
    }.get(record.get("record_type"), "记录")


def _count(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _home_links():
    return [
        "",
        "## 导航",
        "",
        "- [[Inventory]]",
        "- [[Models by Category]]",
        "- [[Inventory by Scope]]",
        "- [[Layouts]]",
        "- [[Needs Verification]]",
    ]


def _finish(lines):
    return "\n".join(lines).rstrip() + "\n"


class _NoopLock:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False
