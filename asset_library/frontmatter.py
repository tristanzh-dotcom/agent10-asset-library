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
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _render_list(field, value):
    if value in (None, []):
        return [f"{field}: []"]
    lines = [f"{field}:"]
    for item in value:
        lines.append(f"  - {item}")
    return lines
