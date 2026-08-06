import json
from urllib.parse import parse_qs


HARDWARE_PATH = "/api/asset-library/hardware"
_BLOCKED_KEYS = {
    "body_markdown",
    "body",
    "raw_note",
    "source_asset_path",
    "vault_path",
    "absolute_path",
    "api_key",
    "token",
    "secret",
    "private_key",
    "password",
    "mac",
    "mac_address",
    "serial",
    "serial_number",
    "device_id",
    "source_ref",
    "source_refs",
    "photo_refs",
    "technical_documents",
    "evidence_refs",
    "layout_refs",
}


def hardware_response(method, path, body, service, query=""):
    try:
        if method == "GET" and path == HARDWARE_PATH:
            params = parse_qs(query, keep_blank_values=False)
            records = service.list_records(
                query=_first(params, "q"),
                record_type=_first(params, "record_type"),
                scope=_first(params, "scope"),
            )
            return _json_response(200, {"records": _redact(records)})

        if method == "GET" and path == HARDWARE_PATH + "/relations":
            params = parse_qs(query, keep_blank_values=False)
            relations = service.list_relations(
                query=_first(params, "q"),
                record_type=_first(params, "record_type"),
                scope=_first(params, "scope"),
            )
            return _json_response(200, {"relations": _redact(relations)})

        analysis_prefix = HARDWARE_PATH + "/analysis-jobs/"
        if method == "GET" and path.startswith(analysis_prefix):
            job_id = path[len(analysis_prefix):].strip("/")
            if not job_id or "/" in job_id:
                return _json_response(404, {"error": "not_found"})
            return _json_response(200, _redact(service.get_analysis_job(job_id)))

        if method == "GET" and path == HARDWARE_PATH + "/summary":
            params = parse_qs(query, keep_blank_values=False)
            summary = service.list_inventory_summary(
                query=_first(params, "q"),
                category=_first(params, "category"),
            )
            return _json_response(200, _redact(summary))

        photo_prefix = HARDWARE_PATH + "/"
        if method == "GET" and path.startswith(photo_prefix):
            parts = path[len(photo_prefix):].split("/")
            if len(parts) == 3 and parts[1] == "photos" and parts[0] and parts[2]:
                try:
                    content_type, payload = service.read_photo(parts[0], parts[2])
                except (TypeError, ValueError):
                    return _json_response(404, {"error": "not_found"})
                if content_type not in {"image/jpeg", "image/png", "image/webp"} or not isinstance(payload, bytes):
                    return _json_response(404, {"error": "not_found"})
                return _binary_response(200, content_type, payload)

        if method == "POST" and path == HARDWARE_PATH + "/drafts":
            payload = _read_json(body)
            return _json_response(201, _redact(service.create_draft(payload.get("base_record_id"))))

        draft_prefix = HARDWARE_PATH + "/drafts/"
        if path.startswith(draft_prefix):
            draft_path = path[len(draft_prefix) :]
            parts = draft_path.split("/")
            draft_id = parts[0]
            if not draft_id or len(parts) > 2:
                return _json_response(404, {"error": "not_found"})
            if method == "PATCH" and len(parts) == 1:
                payload = _read_json(body)
                return _json_response(200, _redact(service.patch_draft(
                    draft_id, payload.get("expected_revision"), payload.get("changes")
                )))
            if method == "POST" and parts[1:] == ["prepare"]:
                payload = _read_json(body)
                return _json_response(200, _redact(service.prepare_draft(
                    draft_id, payload.get("expected_revision")
                )))
            if method == "POST" and parts[1:] == ["accept"]:
                payload = _read_json(body)
                return _json_response(200, _redact(service.accept_draft(
                    draft_id, payload.get("expected_bundle_hash")
                )))
            if method == "POST" and parts[1:] == ["reference"]:
                payload = _read_json(body)
                return _json_response(200, _redact(service.reference_draft(
                    draft_id, payload.get("expected_revision"), payload.get("input", payload.get("url"))
                )))
            if method == "POST" and parts[1:] == ["attachments"]:
                payload = _read_json(body)
                return _json_response(201, _redact(service.attach_draft(
                    draft_id, payload.get("expected_revision"), payload.get("filename"),
                    payload.get("content_type"), payload.get("data_base64"),
                )))
            if method == "POST" and parts[1:] == ["analyze"]:
                payload = _read_json(body) if body else {}
                return _json_response(200, _redact(service.analyze_draft(draft_id, payload.get("operation_key"))))
            return _json_response(405, {"error": "method_not_allowed"})

        if method == "GET" and path.startswith(HARDWARE_PATH + "/"):
            record_id = path[len(HARDWARE_PATH) + 1 :]
            if "/" in record_id or not record_id:
                return _json_response(404, {"error": "not_found"})
            record = service.get_record(record_id)
            if record is None:
                return _json_response(404, {"error": "not_found"})
            return _json_response(200, _redact(record))

        if method == "POST" and path == HARDWARE_PATH + "/requests":
            payload = _read_json(body)
            result = service.submit(payload)
            return _json_response(201, _redact(result))

        accept_prefix = HARDWARE_PATH + "/intakes/"
        if method == "POST" and path.startswith(accept_prefix) and path.endswith("/accept"):
            intake_id = path[len(accept_prefix) : -len("/accept")].strip("/")
            if not intake_id or "/" in intake_id:
                return _json_response(404, {"error": "not_found"})
            payload = _read_json(body)
            result = service.accept(
                intake_id,
                getattr(service, "operator_id", None) or payload.get("accepted_by"),
                payload.get("expected_snapshot_hash"),
            )
            return _json_response(200, _redact(result))

        return _json_response(405 if path.startswith(HARDWARE_PATH) else 404, {"error": "method_not_allowed" if path.startswith(HARDWARE_PATH) else "not_found"})
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return _json_response(400, {"error": "bad_request", "message": str(exc)})


def _read_json(body):
    if not body:
        raise ValueError("JSON body is required")
    payload = json.loads(body.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("JSON body must be an object")
    return payload


def _first(params, key):
    values = params.get(key) or []
    return values[0] if values else ""


def _redact(value, key=""):
    normalized = key.lower().replace("-", "_")
    if normalized in _BLOCKED_KEYS:
        return None
    if isinstance(value, dict):
        return {
            child_key: redacted
            for child_key, child in value.items()
            if child_key.lower().replace("-", "_") not in _BLOCKED_KEYS
            for redacted in [_redact(child, child_key)]
            if redacted is not None
        }
    if isinstance(value, list):
        return [_redact(item, key) for item in value]
    if isinstance(value, str) and value.startswith("/"):
        return "[local reference redacted]"
    return value


def _json_response(status, payload):
    return (
        status,
        {"content-type": "application/json; charset=utf-8"},
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8"),
    )


def _binary_response(status, content_type, payload):
    return (
        status,
        {
            "content-type": content_type,
            "content-length": str(len(payload)),
            "cache-control": "private, max-age=300",
            "x-content-type-options": "nosniff",
        },
        payload,
    )
