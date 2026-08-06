import re
import hashlib
from pathlib import Path
from uuid import uuid4

from .hardware_drafts import compile_draft_to_records
from .hardware_intake import accept_hardware_intake, prepare_hardware_intake, snapshot_hash
from .hardware_sources import capture_reference, fetch_reference, parse_reference_input
from .hardware_attachments import decode_image_payload, sanitize_image_payload, validate_image_payload
from .hardware_analysis import AnalysisEngine
from .hardware_labels import localized_hardware_name
from .hardware_layouts import relation_projection


class HardwareService:
    """Coordinates intake persistence, acceptance, and hardware publication."""

    def __init__(self, store, publisher, intake_id_factory=None, clock=None, attachment_root=None, operator_id="TZ", analysis_engine=None, media_service=None):
        self.store = store
        self.publisher = publisher
        self.intake_id_factory = intake_id_factory
        self.clock = clock
        self.attachment_root = Path(attachment_root) if attachment_root else None
        self.operator_id = operator_id if isinstance(operator_id, str) and operator_id.strip() else "TZ"
        self.media_service = media_service
        self.analysis_engine = analysis_engine or AnalysisEngine(
            store,
            attachment_root=self.attachment_root,
            clock=self.clock,
        )

    def submit(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("hardware request must be an object")
        draft = payload.get("draft")
        intake = prepare_hardware_intake(
            draft,
            payload.get("channel"),
            payload.get("submitted_by"),
            payload.get("operation_key"),
            intake_id_factory=self.intake_id_factory,
            clock=self.clock,
        )
        stored, reused = self.store.save_intake(intake)
        response = _public_intake(stored)
        response["status"] = stored["intake_status"]
        response["outcome"] = "idempotent_reuse" if reused else "created"
        return response

    def accept(self, intake_id, accepted_by, expected_snapshot_hash):
        intake = self.store.get_intake(intake_id)
        if intake is None:
            raise ValueError("hardware intake not found")
        accepted = accept_hardware_intake(
            intake,
            accepted_by,
            expected_snapshot_hash,
            accepted_at=self.clock() if self.clock else None,
        )
        self.store.update_intake(accepted)
        publication = self.publisher.publish(accepted)
        response = {
            "status": publication.status,
            "record_id": publication.record_id,
            "path": publication.path,
            "mode": publication.mode,
            "mirror_status": publication.mirror_status,
        }
        if publication.status == "published":
            accepted["intake_status"] = "published"
            accepted["publication"] = response
            self.store.update_intake(accepted)
        else:
            response["intake_status"] = "accepted"
        return response

    def create_draft(self, base_record_id=None, draft_id_factory=None):
        draft_id = (draft_id_factory or _draft_id)()
        if not isinstance(draft_id, str) or not re.fullmatch(r"hwd_[a-z0-9_-]+", draft_id):
            raise ValueError("draft_id must use the hwd_ stable ID prefix")
        return self.store.save_draft(
            {
                "draft_id": draft_id,
                "revision": 1,
                "status": "editing",
                "base_record_id": base_record_id or "",
                "display_name": "",
                "quantity": None,
                "inventory_action": "",
                "merge_target_id": base_record_id or "",
                "category": "other",
                "note": "",
            }
        )

    def patch_draft(self, draft_id, expected_revision, changes):
        current = self.store.get_draft(draft_id)
        if current is None:
            raise ValueError("hardware draft not found")
        if current.get("revision") != expected_revision:
            raise ValueError("stale draft revision")
        if current.get("status") != "editing":
            raise ValueError("hardware draft is not editable")
        if not isinstance(changes, dict):
            raise ValueError("draft changes must be an object")
        allowed = {"display_name", "quantity", "inventory_action", "merge_target_id", "category", "note"}
        unexpected = sorted(set(changes) - allowed)
        if unexpected:
            raise ValueError(f"unsupported draft fields: {', '.join(unexpected)}")
        updated = {**current, **changes, "revision": current["revision"] + 1}
        return self.store.update_draft(updated, expected_revision)

    def prepare_draft(self, draft_id, expected_revision, submitted_by=None):
        draft = self.store.get_draft(draft_id)
        if draft is None:
            raise ValueError("hardware draft not found")
        if draft.get("status") == "prepared" and draft.get("revision") == expected_revision and draft.get("bundle"):
            return {"status": "review_pending", **draft["bundle"]}
        if draft.get("status") != "editing":
            raise ValueError("hardware draft is not editable")
        if draft.get("revision") != expected_revision:
            raise ValueError("stale draft revision")
        records = compile_draft_to_records(
            draft,
            model_id_factory=lambda value: _model_id(value["display_name"]),
            unit_id_factory=lambda value, model_id: _unit_id(model_id, value["revision"]),
        )
        intakes = []
        if records["model"] is not None:
            intakes.append(self.submit({
                "channel": "web", "submitted_by": self.operator_id,
                "operation_key": f"{draft_id}:r{draft['revision']}:model", "draft": records["model"],
            }))
        intakes.append(self.submit({
            "channel": "web", "submitted_by": self.operator_id,
            "operation_key": f"{draft_id}:r{draft['revision']}:unit", "draft": records["unit"],
        }))
        bundle = {
            "draft_id": draft_id,
            "draft_revision": draft["revision"],
            "intakes": intakes,
        }
        bundle["bundle_hash"] = snapshot_hash(bundle)
        updated = {**draft, "status": "prepared", "bundle": bundle}
        self.store.update_draft(updated, expected_revision)
        return {"status": "review_pending", **bundle}

    def accept_draft(self, draft_id, expected_bundle_hash, accepted_by=None):
        draft = self.store.get_draft(draft_id)
        bundle = (draft or {}).get("bundle") or {}
        if draft and draft.get("status") in {"published", "partial"}:
            return {"status": draft["status"], "draft_id": draft_id, "results": list(draft.get("publication") or [])}
        if not draft or draft.get("status") != "prepared":
            raise ValueError("hardware draft is not prepared")
        if bundle.get("bundle_hash") != expected_bundle_hash:
            raise ValueError("hardware confirmation bundle changed")
        results = []
        for item in bundle.get("intakes", []):
            try:
                results.append(self.accept(item["intake_id"], self.operator_id, item["snapshot_hash"]))
            except Exception:
                results.append({"status": "failed", "intake_id": item.get("intake_id"), "error": "publication_failed"})
        status = "published" if results and all(item.get("status") == "published" for item in results) else "partial"
        self.store.update_draft({**draft, "status": status, "publication": results}, draft["revision"])
        return {"status": status, "draft_id": draft_id, "results": results}

    def reference_draft(self, draft_id, expected_revision, value):
        draft = self.store.get_draft(draft_id)
        if not draft:
            raise ValueError("hardware draft not found")
        if draft.get("status") != "editing":
            raise ValueError("hardware draft is not editable")
        if draft.get("revision") != expected_revision:
            raise ValueError("stale draft revision")
        request = parse_reference_input(value)
        canonical = request["url"]
        try:
            reference = fetch_reference(canonical)
        except OSError:
            reference = capture_reference(canonical, b"", "text/html")
            reference["fetch_error"] = "unavailable"
        reference["user_context"] = request["context"]
        updated = {**draft, "revision": expected_revision + 1, "reference": reference}
        return self.store.update_draft(updated, expected_revision)

    def attach_draft(self, draft_id, expected_revision, filename, content_type, encoded):
        draft = self.store.get_draft(draft_id)
        if not draft:
            raise ValueError("hardware draft not found")
        if draft.get("status") != "editing":
            raise ValueError("hardware draft is not editable")
        if draft.get("revision") != expected_revision:
            raise ValueError("stale draft revision")
        payload = decode_image_payload(encoded)
        validate_image_payload(content_type, payload)
        original_digest = hashlib.sha256(payload).hexdigest()
        payload = sanitize_image_payload(content_type, payload)
        digest = hashlib.sha256(payload).hexdigest()
        if self.attachment_root is None:
            raise ValueError("private attachment storage is unavailable")
        target_dir = self.attachment_root / draft_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / digest
        if not target.exists():
            target.write_bytes(payload)
            target.chmod(0o600)
        attachment = {
            "attachment_id": f"hat_{digest}",
            "content_type": content_type,
            "sha256": f"sha256:{digest}",
            "original_sha256": f"sha256:{original_digest}",
            "exif_sanitized": True,
        }
        attachments = list(draft.get("attachments") or [])
        if attachment not in attachments:
            attachments.append(attachment)
        updated = {**draft, "revision": expected_revision + 1, "attachments": attachments}
        self.store.update_draft(updated, expected_revision)
        return {**updated, "attachment": attachment}

    def analyze_draft(self, draft_id, operation_key=None):
        draft = self.store.get_draft(draft_id)
        if not draft:
            raise ValueError("hardware draft not found")
        operation_key = operation_key or f"{draft_id}:r{draft.get('revision', 0)}:analysis"
        result = self.analysis_engine.start(draft_id, operation_key)
        current = self.store.get_draft(draft_id) or draft
        if current.get("status") == "editing":
            self.store.update_draft({**current, "analysis": result}, current["revision"])
        return {**result, "revision": current.get("revision")}

    def get_analysis_job(self, job_id):
        return self.analysis_engine.status(job_id)

    def list_records(self, query="", record_type=None, scope=None):
        return self.store.list_records(query=query, record_type=record_type, scope=scope)

    def get_record(self, record_id):
        record = self.store.get_record(record_id)
        if record is None:
            return None
        result = dict(record)
        display_name_zh = localized_hardware_name(record_id, result)
        if display_name_zh:
            result["display_name_zh"] = display_name_zh
        result["photos"] = self.media_service.manifest(record_id) if self.media_service else []
        return result

    def list_inventory_summary(self, query="", category=None):
        items = self.store.inventory_summary(query=query, category=category)
        items = [
            _inventory_projection(
                item,
                self.store.get_record(item["item_id"]),
                self.media_service.manifest(item["item_id"]) if self.media_service else [],
            )
            for item in items
        ]
        known_items = [item for item in items if item["quantity_total"] is not None]
        return {
            "items": items,
            "metrics": {
                "item_count": len(items),
                "quantity_total": sum(item["quantity_total"] for item in known_items),
                "quantity_available": sum(item["quantity_available"] for item in known_items),
                "needs_info_count": sum(item["status"] == "needs_info" for item in items),
            },
        }

    def read_photo(self, record_id, photo_id):
        if self.media_service is None:
            raise ValueError("hardware photo is not available")
        return self.media_service.read(record_id, photo_id)

    def list_relations(self, query="", record_type=None, scope=None):
        records = self.store.list_records(query=query, record_type=record_type, scope=scope)
        return relation_projection(records)


def _public_intake(intake):
    record_id = _record_id(intake)
    response = {
        "intake_id": intake["intake_id"],
        "record_type": intake.get("record_type"),
        "record_id": record_id,
        "snapshot_hash": intake["snapshot_hash"],
        "draft_revision": intake.get("draft_revision", 1),
        "intake_status": intake["intake_status"],
    }
    if intake.get("acceptance"):
        response["acceptance"] = intake["acceptance"]
    return response


def _inventory_projection(item, detail, photos):
    projection = {**item, "photos": photos}
    display_name_zh = localized_hardware_name(item.get("item_id"), detail)
    if display_name_zh:
        projection["display_name_zh"] = display_name_zh
    if not isinstance(detail, dict):
        return projection
    for field in (
        "nominal_dimensions",
        "measured_dimensions",
        "interfaces",
        "electrical",
        "installation_constraints",
        "compatibility",
        "scope_refs",
        "evidence_records",
        "last_verified_at",
    ):
        if field in detail:
            projection[field] = detail[field]
    return projection


def _record_id(draft):
    for field in ("hardware_model_id", "hardware_unit_id", "layout_id"):
        if draft.get(field):
            return draft[field]
    return ""


def _draft_id():
    return f"hwd_{uuid4().hex}"


def _model_id(display_name):
    return f"hwm_{_slug(display_name)}"


def _unit_id(model_id, revision):
    return f"hwu_shared-{model_id.removeprefix('hwm_')}-batch-{revision}"


def _slug(value):
    normalized = re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")
    return normalized or uuid4().hex[:12]
