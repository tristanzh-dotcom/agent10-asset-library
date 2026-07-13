from datetime import datetime
import re


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

ASSET_ID_PATTERN = re.compile(r"^ast_\d{8}_[0-9a-f]{8}$")
AGENT_ID_PATTERN = re.compile(r"^agent\d{2,}$")
SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
REFERENCE_FIELDS = (
    "source_refs",
    "input_refs",
    "file_refs",
    "export_refs",
    "subject_refs",
    "collection_refs",
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

    _validate_pattern(errors, draft, "asset_id", ASSET_ID_PATTERN, "asset_id must match ast_YYYYMMDD_<8hex>")
    asset_id = draft.get("asset_id")
    if isinstance(asset_id, str) and ASSET_ID_PATTERN.fullmatch(asset_id):
        try:
            datetime.strptime(asset_id.split("_")[1], "%Y%m%d")
        except ValueError:
            errors.append("asset_id date must be a valid calendar date")
    if "asset_schema_version" in draft and draft.get("asset_schema_version") != 1:
        errors.append("asset_schema_version must be 1")
    _validate_pattern(errors, draft, "agent_id", AGENT_ID_PATTERN, "agent_id must match agent followed by two digits")
    _validate_pattern(
        errors,
        draft,
        "workflow_id",
        SLUG_PATTERN,
        "workflow_id must contain only lowercase letters, digits, underscores, or hyphens",
    )
    _validate_pattern(
        errors,
        draft,
        "asset_type",
        SLUG_PATTERN,
        "asset_type must contain only lowercase letters, digits, underscores, or hyphens",
    )
    _validate_pattern(
        errors,
        draft,
        "source_content_hash",
        HASH_PATTERN,
        "source_content_hash must match sha256:<64hex>",
    )

    for field in ("created_at", "updated_at"):
        if field in draft and draft[field] not in (None, "") and not _is_iso_timestamp(draft[field]):
            errors.append(f"{field} must be an ISO 8601 timestamp")

    for field in REFERENCE_FIELDS:
        _validate_reference_list(errors, draft, field)

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


def _validate_pattern(errors, draft, field, pattern, message):
    value = draft.get(field)
    if value in (None, ""):
        return
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        errors.append(message)


def _is_iso_timestamp(value):
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _validate_reference_list(errors, draft, field):
    if field not in draft:
        return
    value = draft[field]
    if not isinstance(value, list):
        errors.append(f"{field} must be a list")
        return
    for index, item in enumerate(value):
        if field in {"subject_refs", "collection_refs"}:
            if not isinstance(item, (str, dict)):
                errors.append(f"{field}[{index}] must be a string or object")
        elif not isinstance(item, dict):
            errors.append(f"{field}[{index}] must be an object")
