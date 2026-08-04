from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Callable, Mapping, Optional

from .hardware_schema import validate_hardware_draft


INTAKE_CHANNELS = ("codex", "web", "obsidian", "agent_adapter")
_INTAKE_METADATA_KEYS = {
    "intake_id",
    "intake_channel",
    "submitted_by",
    "operation_key",
    "intake_status",
    "draft_revision",
    "captured_at",
    "snapshot_hash",
    "acceptance",
}


def snapshot_hash(payload: Mapping[str, Any]) -> str:
    """Return a stable SHA-256 hash for a JSON-compatible mapping."""

    try:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"hardware snapshot is not JSON serializable: {exc}") from exc
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def prepare_hardware_intake(
    draft: Mapping[str, Any],
    channel: str,
    submitted_by: str,
    operation_key: str,
    intake_id_factory: Optional[Callable[[], str]] = None,
    clock: Optional[Callable[[], str]] = None,
) -> dict:
    """Normalize a hardware draft into a reviewable, immutable-snapshot envelope."""

    if channel not in INTAKE_CHANNELS:
        raise ValueError(f"intake channel must be one of {', '.join(INTAKE_CHANNELS)}")
    _require_text(submitted_by, "submitted_by")
    _require_text(operation_key, "operation_key")
    if not isinstance(draft, Mapping):
        raise ValueError("hardware draft must be an object")
    reserved = sorted(_INTAKE_METADATA_KEYS & set(draft))
    if reserved:
        raise ValueError(f"hardware draft contains reserved intake fields: {', '.join(reserved)}")
    errors = validate_hardware_draft(draft)
    if errors:
        raise ValueError("; ".join(errors))

    captured_at = (clock or _now)()
    _validate_timestamp(captured_at, "captured_at")
    intake_id = (intake_id_factory or (lambda: _default_intake_id(operation_key)))()
    _require_text(intake_id, "intake_id")
    result = deepcopy(dict(draft))
    result.update(
        {
            "intake_id": intake_id,
            "intake_channel": channel,
            "submitted_by": submitted_by,
            "operation_key": operation_key,
            "intake_status": "review_pending",
            "draft_revision": 1,
            "captured_at": captured_at,
            "snapshot_hash": snapshot_hash(draft),
        }
    )
    return result


def accept_hardware_intake(
    intake: Mapping[str, Any],
    accepted_by: str,
    expected_snapshot_hash: str,
    accepted_at: Optional[str] = None,
) -> dict:
    """Accept only an unchanged review-pending intake snapshot."""

    if not isinstance(intake, Mapping):
        raise ValueError("hardware intake must be an object")
    if intake.get("intake_status") != "review_pending":
        raise ValueError("hardware intake must be review_pending before acceptance")
    _require_text(accepted_by, "accepted_by")
    _require_text(expected_snapshot_hash, "expected_snapshot_hash")
    current_hash = snapshot_hash(_draft_fields(intake))
    if current_hash != expected_snapshot_hash or current_hash != intake.get("snapshot_hash"):
        raise ValueError("hardware intake snapshot changed after review")
    timestamp = accepted_at or _now()
    _validate_timestamp(timestamp, "accepted_at")

    result = deepcopy(dict(intake))
    result["intake_status"] = "accepted"
    result["acceptance"] = {
        "status": "accepted",
        "accepted_revision": intake.get("draft_revision", 1),
        "accepted_by": accepted_by,
        "accepted_at": timestamp,
        "snapshot_hash": current_hash,
        "evidence_refs": list(intake.get("evidence_refs", [])),
    }
    return result


def _draft_fields(intake):
    return {key: value for key, value in intake.items() if key not in _INTAKE_METADATA_KEYS}


def _default_intake_id(operation_key):
    digest = hashlib.sha256(operation_key.encode("utf-8")).hexdigest()[:16]
    return f"hwi_{digest}"


def _require_text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")


def _validate_timestamp(value, field):
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO 8601 timestamp")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO 8601 timestamp") from exc


def _now():
    return datetime.now(timezone.utc).isoformat()
