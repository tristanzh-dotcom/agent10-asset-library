ASSET_STATUSES = ("active", "archived", "deleted_in_vault", "source_deleted")
KNOWLEDGE_STATUSES = (
    "indexed",
    "not_indexed",
    "promoting",
    "promotion_failed",
    "promotion_requires_manual_review",
)
SOURCE_STATUSES = ("grounded", "pending", "uncertain", "unverified")
SENSITIVITIES = ("audit_only", "normal", "restricted", "sensitive")

REQUIRED_FIELDS = (
    "title",
    "agent_id",
    "workflow_id",
    "asset_type",
    "status",
    "knowledge_status",
    "source_status",
    "sensitivity",
)


def validate_draft(draft):
    errors = []
    for field in REQUIRED_FIELDS:
        if field not in draft or draft[field] in (None, ""):
            errors.append(f"{field} is required")

    _validate_enum(errors, draft, "status", ASSET_STATUSES)
    _validate_enum(errors, draft, "knowledge_status", KNOWLEDGE_STATUSES)
    _validate_enum(errors, draft, "source_status", SOURCE_STATUSES)
    _validate_enum(errors, draft, "sensitivity", SENSITIVITIES)
    _validate_content(errors, draft)

    tags = draft.get("tags", [])
    if not isinstance(tags, list):
        errors.append("tags must be a list")
    else:
        for index, tag in enumerate(tags):
            if not isinstance(tag, str):
                errors.append(f"tags[{index}] must be a string")
            elif any(ch.isspace() for ch in tag):
                errors.append(f"tags[{index}] must not contain whitespace")

    return errors


def _validate_enum(errors, draft, field, allowed):
    value = draft.get(field)
    if value is not None and value not in allowed:
        errors.append(f"{field} must be one of {', '.join(allowed)}")


def _validate_content(errors, draft):
    if draft.get("body_markdown") not in (None, ""):
        return
    file_refs = draft.get("file_refs", [])
    if any(ref.get("primary") is True or ref.get("identity") is True for ref in file_refs if isinstance(ref, dict)):
        return
    errors.append("body_markdown or identity file_refs is required")
