from datetime import datetime
import re
from typing import Any, Mapping


HARDWARE_RECORD_TYPES = ("hardware_model", "hardware_unit", "assembly_layout")
EVIDENCE_LEVELS = ("official", "measured", "label_or_photo", "reported", "unverified")
RELATION_TYPES = (
    "used_by",
    "owned_by",
    "part_of_layout",
    "compatible_with",
    "incompatible_with",
    "replacement_for",
    "reserved_for",
)
MODEL_LIFECYCLE_STATUSES = ("draft", "candidate", "verified", "retired")
MODEL_STATUSES = ("active", "archived", "superseded")
UNIT_AVAILABILITY_STATUSES = (
    "planned",
    "available",
    "reserved",
    "in_use",
    "consumed",
    "retired",
)
UNIT_CONDITIONS = ("new", "good", "worn", "damaged", "unknown")
LAYOUT_STATUSES = ("draft", "measured", "approved", "superseded")
SENSITIVE_KEYS = {
    "token",
    "api_key",
    "secret",
    "private_key",
    "password",
    "wifi_password",
    "mac",
    "mac_address",
    "serial",
    "serial_number",
    "device_id",
}
_ID_PATTERNS = {
    "hardware_model": re.compile(r"^hwm_[a-z0-9][a-z0-9_-]*$"),
    "hardware_unit": re.compile(r"^hwu_[a-z0-9][a-z0-9_-]*$"),
    "assembly_layout": re.compile(r"^lay_[a-z0-9][a-z0-9_-]*$"),
}
_SCOPE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def validate_hardware_draft(draft: Mapping[str, Any]) -> list[str]:
    """Return deterministic validation errors without mutating or reading IO."""

    errors = []
    if not isinstance(draft, Mapping):
        return ["hardware draft must be an object"]

    _validate_sensitive_keys(errors, draft)
    record_type = draft.get("record_type")
    if record_type not in HARDWARE_RECORD_TYPES:
        errors.append(
            "record_type must be one of hardware_model, hardware_unit, assembly_layout"
        )
        return errors

    _validate_id(errors, draft, record_type)
    if record_type == "hardware_model":
        _validate_model(errors, draft)
    elif record_type == "hardware_unit":
        _validate_unit(errors, draft)
    else:
        _validate_layout(errors, draft)

    _validate_evidence(errors, draft)
    _validate_relations(errors, draft)
    _validate_scopes(errors, draft)
    _validate_timestamp(errors, draft, "last_verified_at")
    return errors


def _validate_model(errors, draft):
    for field in ("canonical_name", "manufacturer", "model_or_sku", "category"):
        _require_text(errors, draft, field)
    _validate_enum(errors, draft, "lifecycle_status", MODEL_LIFECYCLE_STATUSES)
    _validate_enum(errors, draft, "status", MODEL_STATUSES)
    _validate_dimensions(errors, draft.get("nominal_dimensions"), "nominal_dimensions")


def _validate_unit(errors, draft):
    for field in ("model_ref", "inventory_kind", "ownership_scope"):
        _require_text(errors, draft, field)
    _validate_enum(errors, draft, "availability_status", UNIT_AVAILABILITY_STATUSES)
    _validate_enum(errors, draft, "condition", UNIT_CONDITIONS)
    _validate_enum(errors, draft, "status", MODEL_STATUSES)
    counts = {}
    for field in ("quantity_total", "quantity_available", "quantity_reserved"):
        value = draft.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            errors.append(f"{field} must be a non-negative integer")
        else:
            counts[field] = value
    if counts and counts.get("quantity_available", 0) + counts.get("quantity_reserved", 0) > counts.get("quantity_total", 0):
        errors.append("quantity_available plus quantity_reserved must not exceed quantity_total")
    _validate_measurement_list(errors, draft.get("measured_dimensions"), "measured_dimensions")
    _validate_non_negative_number(errors, draft, "weight_g")


def _validate_layout(errors, draft):
    for field in ("title", "scope", "target"):
        _require_text(errors, draft, field)
    _validate_enum(errors, draft, "status", LAYOUT_STATUSES)
    members = draft.get("member_refs")
    if not isinstance(members, list) or not members or any(not isinstance(item, str) or not item.strip() for item in members):
        errors.append("member_refs must contain at least one non-empty reference")
    if not isinstance(draft.get("constraints"), Mapping):
        errors.append("constraints must be an object")


def _validate_id(errors, draft, record_type):
    field = {
        "hardware_model": "hardware_model_id",
        "hardware_unit": "hardware_unit_id",
        "assembly_layout": "layout_id",
    }[record_type]
    value = draft.get(field)
    if not isinstance(value, str) or _ID_PATTERNS[record_type].fullmatch(value) is None:
        errors.append(f"{field} must use the {record_type} stable ID prefix and lowercase slug")


def _validate_evidence(errors, draft):
    records = draft.get("evidence_records")
    if not isinstance(records, list) or not records:
        errors.append("evidence_records must contain at least one record")
        return
    for index, evidence in enumerate(records):
        if not isinstance(evidence, Mapping):
            errors.append(f"evidence_records[{index}] must be an object")
            continue
        if not isinstance(evidence.get("claim"), str) or not evidence["claim"].strip():
            errors.append(f"evidence_records[{index}].claim is required")
        level = evidence.get("level")
        if level not in EVIDENCE_LEVELS:
            errors.append(f"evidence_records[{index}].level must be one of {', '.join(EVIDENCE_LEVELS)}")
        if not isinstance(evidence.get("source_ref"), str) or not evidence["source_ref"].strip():
            errors.append(f"evidence_records[{index}].source_ref is required")
        if level == "measured":
            for field in ("tool", "method", "measured_at"):
                if not isinstance(evidence.get(field), str) or not evidence[field].strip():
                    errors.append(f"evidence_records[{index}].{field} is required for measured evidence")
            _validate_timestamp(errors, evidence, "measured_at", prefix=f"evidence_records[{index}]")


def _validate_relations(errors, draft):
    relations = draft.get("relations", [])
    if not isinstance(relations, list):
        errors.append("relations must be a list")
        return
    for index, relation in enumerate(relations):
        if not isinstance(relation, Mapping):
            errors.append(f"relations[{index}] must be an object")
            continue
        if relation.get("relation_type") not in RELATION_TYPES:
            errors.append(f"relations[{index}].relation_type is invalid")
        if not isinstance(relation.get("ref"), str) or not relation["ref"].strip():
            errors.append(f"relations[{index}].ref is required")


def _validate_scopes(errors, draft):
    scope_refs = draft.get("scope_refs")
    if scope_refs is not None:
        if not isinstance(scope_refs, list):
            errors.append("scope_refs must be a list")
        else:
            for index, scope in enumerate(scope_refs):
                _validate_scope(errors, scope, f"scope_refs[{index}]")
    if "ownership_scope" in draft:
        _validate_scope(errors, draft.get("ownership_scope"), "ownership_scope")
    if "scope" in draft:
        _validate_scope(errors, draft.get("scope"), "scope")


def _validate_scope(errors, value, field):
    if not isinstance(value, str) or _SCOPE_PATTERN.fullmatch(value) is None:
        errors.append(f"{field} must be a lowercase scoped ID")


def _validate_dimensions(errors, value, field):
    if value in (None, {}):
        return
    if not isinstance(value, Mapping):
        errors.append(f"{field} must be an object")
        return
    for dimension in ("length_mm", "width_mm", "height_mm"):
        _validate_non_negative_number(errors, value, dimension, prefix=field)


def _validate_measurement_list(errors, value, field):
    if value is None:
        return
    if not isinstance(value, list):
        errors.append(f"{field} must be a list")
        return
    for index, measurement in enumerate(value):
        if not isinstance(measurement, Mapping):
            errors.append(f"{field}[{index}] must be an object")
            continue
        _validate_dimensions(errors, measurement, f"{field}[{index}]")


def _validate_non_negative_number(errors, mapping, field, prefix=""):
    if field not in mapping or mapping[field] is None:
        return
    value = mapping[field]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        label = f"{prefix}.{field}" if prefix else field
        errors.append(f"{label} must be a non-negative number")


def _require_text(errors, mapping, field):
    if not isinstance(mapping.get(field), str) or not mapping[field].strip():
        errors.append(f"{field} is required")


def _validate_enum(errors, mapping, field, allowed):
    value = mapping.get(field)
    if value not in allowed:
        errors.append(f"{field} must be one of {', '.join(allowed)}")


def _validate_timestamp(errors, mapping, field, prefix=""):
    value = mapping.get(field)
    if value in (None, ""):
        return
    if not isinstance(value, str):
        errors.append(f"{prefix + '.' if prefix else ''}{field} must be an ISO 8601 timestamp")
        return
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{prefix + '.' if prefix else ''}{field} must be an ISO 8601 timestamp")


def _validate_sensitive_keys(errors, value):
    seen = set()

    def walk(node):
        if isinstance(node, Mapping):
            for key, child in node.items():
                normalized = str(key).lower().replace("-", "_")
                if normalized in SENSITIVE_KEYS and normalized not in seen:
                    errors.append(f"{normalized} is not allowed in hardware records")
                    seen.add(normalized)
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(value)
