import json

from .hashing import compute_body_hash, compute_non_body_hash


FRONTMATTER_FIELDS = (
    "asset_id",
    "asset_schema_version",
    "title",
    "agent_id",
    "workflow_id",
    "asset_type",
    "status",
    "knowledge_status",
    "knowledge_index_id",
    "knowledge_promoted_at",
    "source_status",
    "sensitivity",
    "source_content_hash",
    "hash_source",
    "created_at",
    "updated_at",
    "source_asset_path",
    "source_refs",
    "input_refs",
    "file_refs",
    "export_refs",
    "model_route",
    "subject_refs",
    "collection_refs",
    "tags",
    "capture_kind",
    "task_id",
    "continuity_key",
    "task_status",
    "capture_status",
    "quality_state",
    "quality_score",
    "evidence_state",
    "readability_state",
    "publication_eligibility",
    "verification_state",
    "project_id",
    "project_name",
    "project_path",
    "started_at",
    "last_activity_at",
    "ended_at",
    "previous_task",
    "next_task",
    "report_date",
    "task_count",
)

LIST_FIELDS = {
    "source_refs",
    "input_refs",
    "file_refs",
    "export_refs",
    "subject_refs",
    "collection_refs",
    "tags",
}


def render_note(draft):
    working = prepare_frontmatter_fields(draft)
    working["file_refs"] = [
        {key: value for key, value in ref.items() if key != "bytes"}
        for ref in working.get("file_refs", [])
        if isinstance(ref, dict)
    ]
    body = working.get("body_markdown", "")

    lines = ["---"]
    for field in FRONTMATTER_FIELDS:
        if field not in working:
            continue
        value = working[field]
        if field in LIST_FIELDS:
            lines.extend(_render_list(field, value))
        else:
            lines.append(f"{field}: {_render_scalar(value)}")
    lines.append("---")
    lines.append("")
    lines.append(str(body).rstrip("\n"))
    lines.append("")
    return "\n".join(lines)


def prepare_frontmatter_fields(draft):
    working = dict(draft)
    working.setdefault("asset_schema_version", 1)
    if "source_content_hash" not in working or not working["source_content_hash"]:
        if working.get("body_markdown") not in (None, ""):
            working["source_content_hash"] = compute_body_hash(working.get("body_markdown", ""))
        else:
            digest, hash_source = compute_non_body_hash(working)
            working["source_content_hash"] = digest
            working.setdefault("hash_source", hash_source)
    working.setdefault("hash_source", "")
    return working


def _render_scalar(value):
    if value == "":
        return '""'
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=True)


def _render_list(field, value):
    if value in (None, []):
        return [f"{field}: []"]
    lines = [f"{field}:"]
    for item in value:
        lines.extend(_render_yaml_value(item, indent=2, list_item=True))
    return lines


def _render_yaml_value(value, indent=0, list_item=False):
    prefix = " " * indent
    if isinstance(value, dict):
        items = list(value.items())
        if not items:
            return [f"{prefix}- {{}}" if list_item else f"{prefix}{{}}"]
        lines = []
        first_key, first_value = items[0]
        first_key = _render_key(first_key)
        if _is_scalar(first_value):
            lines.append(f"{prefix}- {first_key}: {_render_scalar(first_value)}" if list_item else f"{prefix}{first_key}: {_render_scalar(first_value)}")
        else:
            lines.append(f"{prefix}- {first_key}:" if list_item else f"{prefix}{first_key}:")
            lines.extend(_render_yaml_value(first_value, indent=indent + 2))
        for key, item_value in items[1:]:
            key = _render_key(key)
            if _is_scalar(item_value):
                lines.append(f"{prefix}  {key}: {_render_scalar(item_value)}" if list_item else f"{prefix}{key}: {_render_scalar(item_value)}")
            else:
                lines.append(f"{prefix}  {key}:" if list_item else f"{prefix}{key}:")
                lines.extend(_render_yaml_value(item_value, indent=indent + 2))
        return lines
    if isinstance(value, list):
        if not value:
            return [f"{prefix}[]"]
        lines = []
        for item in value:
            lines.extend(_render_yaml_value(item, indent=indent, list_item=True))
        return lines
    return [f"{prefix}- {_render_scalar(value)}" if list_item else f"{prefix}{_render_scalar(value)}"]


def _is_scalar(value):
    return not isinstance(value, (dict, list))


def _render_key(value):
    return json.dumps(str(value), ensure_ascii=True)
