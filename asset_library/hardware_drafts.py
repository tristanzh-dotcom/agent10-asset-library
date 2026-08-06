"""Compile the simple hardware intake fields into governed hardware records."""

from .hardware_schema import validate_hardware_draft


_ACTIONS = {"new", "merge"}
_CATEGORIES = {
    "controller",
    "sensor",
    "actuator",
    "power",
    "wiring",
    "connector",
    "enclosure",
    "tool",
    "consumable",
    "other",
}


def compile_draft_to_records(draft, model_id_factory, unit_id_factory):
    """Return a new model plus batch, or a batch for a selected existing model."""

    if not isinstance(draft, dict):
        raise ValueError("hardware draft must be an object")
    draft_id = _require_text(draft.get("draft_id"), "draft_id")
    action = draft.get("inventory_action")
    if action not in _ACTIONS:
        raise ValueError("inventory_action must be new or merge")
    quantity = draft.get("quantity")
    if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 1:
        raise ValueError("quantity must be a positive integer")

    if action == "merge":
        model_id = _require_model_id(draft.get("merge_target_id"))
        model = None
    else:
        display_name = _require_text(draft.get("display_name"), "display_name")
        model_id = _require_model_id(model_id_factory(draft))
        model = _model_record(draft, model_id, display_name, draft_id)

    unit = _unit_record(draft, _require_unit_id(unit_id_factory(draft, model_id)), model_id, draft_id)
    _validate_compiled(model)
    _validate_compiled(unit)
    return {"model": model, "unit": unit}


def _model_record(draft, model_id, display_name, draft_id):
    note = _clean_text(draft.get("note"))
    reference = _reference_document(draft)
    photo_refs = _photo_refs(draft)
    analysis = _analysis_summary(draft)
    return {
        "record_type": "hardware_model",
        "hardware_model_id": model_id,
        "canonical_name": display_name,
        "manufacturer": _clean_text(draft.get("manufacturer")) or "Unknown",
        "model_or_sku": _clean_text(draft.get("model_or_sku")) or "Unspecified",
        "category": _category(draft.get("category")),
        "lifecycle_status": "candidate",
        "status": "active",
        "nominal_dimensions": {},
        "interfaces": [],
        "electrical": {},
        "installation_constraints": {},
        "compatibility": {},
        "technical_documents": [reference] if reference else [],
        "photo_refs": photo_refs,
        "analysis": analysis,
        "scope_refs": ["shared"],
        "relations": [],
        "evidence_records": _evidence_records(draft, draft_id, "new hardware entry"),
        "last_verified_at": None,
        "summary": note or "资料已登记；请以字段证据和最后核验状态为准。",
    }


def _unit_record(draft, unit_id, model_id, draft_id):
    photo_refs = _photo_refs(draft)
    reference = _reference_document(draft)
    return {
        "record_type": "hardware_unit",
        "hardware_unit_id": unit_id,
        "model_ref": model_id,
        "inventory_kind": "batch",
        "quantity_total": draft["quantity"],
        "quantity_available": draft["quantity"],
        "quantity_reserved": 0,
        "ownership_scope": "shared",
        "storage_location": "unspecified",
        "condition": "unknown",
        "availability_status": "available",
        "measured_dimensions": [],
        "weight_g": None,
        "photo_refs": photo_refs,
        "technical_documents": [reference] if reference else [],
        "analysis": _analysis_summary(draft),
        "layout_refs": [],
        "relations": [],
        "evidence_records": _evidence_records(draft, draft_id, "inventory quantity supplied during entry"),
        "last_verified_at": None,
        "status": "active",
    }


def _reported_evidence(draft_id, claim):
    return {"claim": claim, "level": "reported", "source_ref": f"draft:{draft_id}"}


def _evidence_records(draft, draft_id, claim):
    records = [_reported_evidence(draft_id, claim)]
    reference = draft.get("reference") if isinstance(draft.get("reference"), dict) else {}
    reference_hash = _clean_text(reference.get("content_sha256"))
    if reference_hash:
        records.append({
            "claim": "technical reference supplied",
            "level": "reported",
            "source_ref": f"reference:{reference_hash}",
        })
    for attachment_id in _photo_refs(draft):
        records.append({
            "claim": "appearance supplied by uploaded photo",
            "level": "label_or_photo",
            "source_ref": f"attachment:{attachment_id}",
        })
    return records


def _reference_document(draft):
    reference = draft.get("reference") if isinstance(draft.get("reference"), dict) else {}
    url = _clean_text(reference.get("url"))
    if not url:
        return None
    return {
        "title": _clean_text(reference.get("title")) or "User supplied technical reference",
        "url": url,
        "status": _clean_text(reference.get("status")) or "link_only",
        "content_type": _clean_text(reference.get("content_type")) or "unknown",
        "content_sha256": _clean_text(reference.get("content_sha256")),
        "retrieved_at": _clean_text(reference.get("retrieved_at")) or None,
        "user_context": _clean_text(reference.get("user_context")),
    }


def _analysis_summary(draft):
    analysis = draft.get("analysis") if isinstance(draft.get("analysis"), dict) else {}
    if not analysis:
        return {"status": "not_run", "candidates": []}
    return {
        "job_id": _clean_text(analysis.get("job_id")),
        "status": _clean_text(analysis.get("status")) or "unavailable",
        "reference_status": _clean_text(analysis.get("reference_status")),
        "candidates": analysis.get("candidates") if isinstance(analysis.get("candidates"), list) else [],
        "receipt": analysis.get("receipt") if isinstance(analysis.get("receipt"), dict) else {},
    }


def _photo_refs(draft):
    attachments = draft.get("attachments") if isinstance(draft.get("attachments"), list) else []
    return [
        item["attachment_id"]
        for item in attachments
        if isinstance(item, dict) and _clean_text(item.get("attachment_id"))
    ]


def _validate_compiled(record):
    if record is None:
        return
    errors = validate_hardware_draft(record)
    if errors:
        raise ValueError("; ".join(errors))


def _require_text(value, field):
    value = _clean_text(value)
    if not value:
        raise ValueError(f"{field} is required")
    return value


def _require_model_id(value):
    value = _require_text(value, "hardware model ID")
    if not value.startswith("hwm_"):
        raise ValueError("hardware model ID must start with hwm_")
    return value


def _require_unit_id(value):
    value = _require_text(value, "hardware unit ID")
    if not value.startswith("hwu_"):
        raise ValueError("hardware unit ID must start with hwu_")
    return value


def _category(value):
    normalized = _clean_text(value).lower() or "other"
    return normalized if normalized in _CATEGORIES else "other"


def _clean_text(value):
    return value.strip() if isinstance(value, str) else ""
