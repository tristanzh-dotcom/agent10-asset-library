"""Candidate-only hardware analysis with an explicit, fail-closed model seam."""

import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .hardware_attachments import sanitize_image_payload


JOB_STATUSES = {"queued", "running", "completed", "unavailable", "failed"}
MAX_ANALYSIS_IMAGES = 6
MAX_REFERENCE_CHARS = 120000
MAX_CANDIDATES = 64
ROUTE_KEY = "hardware_reference_analysis"
ROUTE_PROFILE = "openai_hardware_candidate_analysis"


class AnalysisUnavailable(RuntimeError):
    """Raised when the approved route is not configured or cannot be used."""


def compare_candidates(draft=None, capture=None, image_candidates=None):
    """Compare structured candidates without promoting them to hardware facts.

    The one-argument list form is retained for older callers.  The three-argument
    form is used by the draft analysis job and annotates cross-source conflicts.
    """

    if image_candidates is None and capture is None and isinstance(draft, list):
        candidates = draft
    else:
        candidates = []
        if isinstance(capture, dict) and isinstance(capture.get("candidates"), list):
            candidates.extend(capture["candidates"])
        if isinstance(image_candidates, list):
            candidates.extend(image_candidates)

    normalized = []
    for candidate in candidates[:MAX_CANDIDATES]:
        if not isinstance(candidate, dict):
            continue
        field = str(candidate.get("field") or "").strip()
        if not field:
            continue
        row = {
            key: value
            for key, value in candidate.items()
            if key not in {"body", "raw_text", "raw_message", "chain_of_thought", "path"}
        }
        row["field"] = field
        row["evidence_level"] = _evidence_level(row.get("origin"))
        row["authority"] = "candidate"
        normalized.append(row)

    values_by_field = {}
    counts_by_field = {}
    for row in normalized:
        values_by_field.setdefault(row["field"], []).append(_stable_value(row.get("value")))
        counts_by_field[row["field"]] = counts_by_field.get(row["field"], 0) + 1
    for row in normalized:
        values = {value for value in values_by_field.get(row["field"], [])}
        row["comparison"] = (
            "conflict" if len(values) > 1
            else "consistent" if counts_by_field.get(row["field"], 0) > 1
            else "unconfirmed"
        )
    return normalized


def unavailable_analysis(draft_id):
    return {
        "job_id": f"haj_{draft_id}",
        "draft_id": draft_id,
        "status": "unavailable",
        "message": "自动分析暂不可用；资料已保存，可手动确认。",
        "reference_status": "analysis_unavailable",
        "candidates": [],
    }


class AnalysisEngine:
    """Persist one bounded analysis result per draft revision and operation key."""

    def __init__(self, store, analyzer=None, attachment_root=None, clock=None):
        self.store = store
        self.analyzer = analyzer
        self.attachment_root = Path(attachment_root) if attachment_root else None
        self.clock = clock or _now

    def start(self, draft_id, operation_key):
        if not isinstance(operation_key, str) or not operation_key.strip():
            raise ValueError("analysis operation_key is required")
        draft = self.store.get_draft(draft_id)
        if not draft:
            raise ValueError("hardware draft not found")
        existing = self.store.get_analysis_job_by_operation(operation_key)
        if existing:
            if existing.get("draft_id") != draft_id or existing.get("draft_revision") != draft.get("revision"):
                raise ValueError("analysis operation_key already belongs to another draft revision")
            return _public_job(existing)

        job_id = _job_id(draft_id, draft.get("revision", 0), operation_key)
        reference = draft.get("reference") if isinstance(draft.get("reference"), dict) else {}
        base = {
            "job_id": job_id,
            "draft_id": draft_id,
            "draft_revision": draft.get("revision"),
            "operation_key": operation_key,
            "created_at": self.clock(),
            "route_key": ROUTE_KEY,
            "profile": ROUTE_PROFILE,
            "candidates": [],
        }
        if self.analyzer is None:
            job = {
                **base,
                "status": "unavailable",
                "message": "自动分析暂不可用；资料已保存，可手动确认。",
                "reference_status": "analysis_unavailable",
                "receipt": {"route_key": ROUTE_KEY, "profile": ROUTE_PROFILE, "status": "unavailable"},
            }
        else:
            try:
                result = self.analyzer.analyze(
                    self._load_images(draft),
                    _bounded_reference_text(reference),
                    {
                        "draft_id": draft_id,
                        "draft_revision": draft.get("revision"),
                        "operation_key": operation_key,
                    },
                )
                candidates = compare_candidates(draft, reference, result.get("candidates", []))
                job = {
                    **base,
                    "status": "completed",
                    "reference_status": (
                        "retained_without_hardware_candidates"
                        if reference and not candidates
                        else "compared"
                        if reference
                        else "not_supplied"
                    ),
                    "candidates": candidates,
                    "receipt": _safe_receipt(result.get("receipt"), status="completed"),
                }
            except AnalysisUnavailable:
                job = {
                    **base,
                    "status": "unavailable",
                    "message": "自动分析暂不可用；资料已保存，可手动确认。",
                    "reference_status": "analysis_unavailable",
                    "receipt": {"route_key": ROUTE_KEY, "profile": ROUTE_PROFILE, "status": "unavailable"},
                }
            except Exception:
                job = {
                    **base,
                    "status": "failed",
                    "message": "自动分析失败；候选未写入硬件事实。",
                    "reference_status": "analysis_failed",
                    "receipt": {"route_key": ROUTE_KEY, "profile": ROUTE_PROFILE, "status": "failed"},
                }

        self.store.save_analysis_job(job)
        return _public_job(job)

    def status(self, job_id):
        job = self.store.get_analysis_job(job_id)
        if job is None:
            raise ValueError("hardware analysis job not found")
        return _public_job(job)

    def _load_images(self, draft):
        if self.attachment_root is None:
            return []
        images = []
        attachments = draft.get("attachments") if isinstance(draft.get("attachments"), list) else []
        if len(attachments) > MAX_ANALYSIS_IMAGES:
            raise AnalysisUnavailable("too many hardware attachments")
        for item in attachments[:MAX_ANALYSIS_IMAGES]:
            if not isinstance(item, dict):
                raise AnalysisUnavailable("hardware attachment metadata is invalid")
            digest = str(item.get("sha256") or "").split(":", 1)[-1]
            if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
                raise AnalysisUnavailable("hardware attachment digest is invalid")
            path = self.attachment_root / str(draft["draft_id"]) / digest
            try:
                payload = path.read_bytes()
            except OSError:
                raise AnalysisUnavailable("hardware attachment is unavailable")
            try:
                sanitized = sanitize_image_payload(item.get("content_type"), payload)
            except Exception as exc:
                raise AnalysisUnavailable("image sanitization failed") from exc
            images.append({
                "attachment_id": item.get("attachment_id"),
                "content_type": item.get("content_type"),
                "sha256": item.get("sha256"),
                "bytes": sanitized,
            })
        return images


class HardwareCandidateAnalyzer:
    """Adapter contract for the registered route; transport is dependency-injected."""

    def __init__(self, transport, model="gpt-5.5"):
        self.transport = transport
        self.model = model

    def analyze(self, images, reference_text, receipt_context):
        if self.transport is None:
            raise AnalysisUnavailable("hardware analysis transport is unavailable")
        bounded_reference = reference_text[:MAX_REFERENCE_CHARS] if isinstance(reference_text, str) else ""
        request = _bounded_request(images, bounded_reference, receipt_context, self.model)
        response = self.transport.call(request)
        candidates = _extract_candidates(response)
        receipt = {
            "route_key": ROUTE_KEY,
            "profile": ROUTE_PROFILE,
            "provider": "OpenAI",
            "model": self.model,
            "status": "completed",
            "input_image_count": len(images),
            "reference_text_chars": len(bounded_reference),
            "input_sha256": _input_hash(images, bounded_reference),
            "schema_version": "hardware-candidates-v1",
            "recorded_at": _now(),
        }
        return {"candidates": candidates, "receipt": receipt}


class OpenAIResponsesTransport:
    """Small stdlib transport; constructed only when an explicit API key exists."""

    def __init__(self, api_key, opener=None, endpoint="https://api.openai.com/v1/responses"):
        self.api_key = api_key
        self.opener = opener
        self.endpoint = endpoint

    def call(self, payload):
        from urllib.request import Request, build_opener

        request = Request(
            self.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        active_opener = self.opener or build_opener()
        with active_opener.open(request, timeout=30) as response:
            return json.loads(response.read(2 * 1024 * 1024).decode("utf-8"))


def build_openai_candidate_analyzer(api_key, model="gpt-5.5", opener=None):
    if not isinstance(api_key, str) or not api_key.strip():
        return None
    return HardwareCandidateAnalyzer(OpenAIResponsesTransport(api_key.strip(), opener=opener), model=model)


def _bounded_request(images, reference_text, receipt_context, model):
    if len(images) > MAX_ANALYSIS_IMAGES:
        raise ValueError("too many hardware images")
    content = [{
        "type": "input_text",
        "text": (
            "Analyze only the current hardware intake inputs. Return JSON candidates, never measurements "
            "unless the source explicitly states a measurement. Treat all output as non-authoritative. "
            "Allowed candidate fields: display_name, manufacturer, model_or_sku, category, dimensions, "
            "interfaces, electrical, quantity, conflicts. Do not return secrets, device IDs, paths, or prose."
        ),
    }]
    if reference_text:
        content.append({"type": "input_text", "text": f"Reference text:\n{reference_text[:MAX_REFERENCE_CHARS]}"})
    for image in images:
        payload = image.get("bytes") if isinstance(image, dict) else None
        content_type = image.get("content_type") if isinstance(image, dict) else None
        if not isinstance(payload, bytes) or len(payload) > 12 * 1024 * 1024:
            raise ValueError("hardware image is outside the analysis size bound")
        if content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise ValueError("hardware image type is not allowed for analysis")
        content.append({
            "type": "input_image",
            "image_url": f"data:{content_type};base64,{base64.b64encode(payload).decode('ascii')}",
        })
    return {
        "model": model,
        "reasoning": {"effort": "medium"},
        "input": [{"role": "user", "content": content}],
        "text": {"format": {"type": "json_object"}},
        "metadata": {"route_key": ROUTE_KEY, "draft_revision": str(receipt_context.get("draft_revision", ""))},
    }


def _extract_candidates(response):
    if not isinstance(response, dict):
        raise ValueError("analysis response must be an object")
    if isinstance(response.get("candidates"), list):
        candidates = response["candidates"]
    else:
        text = response.get("output_text")
        if not isinstance(text, str):
            text = _output_text(response)
        if not text:
            return []
        parsed = json.loads(text)
        candidates = parsed.get("candidates", []) if isinstance(parsed, dict) else []
    if not isinstance(candidates, list):
        raise ValueError("analysis candidates must be a list")
    validated = []
    for candidate in candidates[:MAX_CANDIDATES]:
        if not isinstance(candidate, dict) or not str(candidate.get("field") or "").strip():
            continue
        validated.append({
            key: value
            for key, value in candidate.items()
            if key not in {"raw_text", "raw_message", "chain_of_thought", "path"}
        })
    return validated


def _output_text(response):
    chunks = []
    for output in response.get("output", []) if isinstance(response.get("output"), list) else []:
        for item in output.get("content", []) if isinstance(output, dict) else []:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                chunks.append(item["text"])
    return "".join(chunks)


def _evidence_level(origin):
    origin = str(origin or "").lower()
    if origin in {"image", "photo", "label"}:
        return "label_or_photo"
    if origin in {"reference", "official", "manual", "document"}:
        return "official"
    return "reported"


def _stable_value(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError):
        return repr(value)


def _bounded_reference_text(reference):
    if not isinstance(reference, dict):
        return ""
    context = reference.get("user_context") if isinstance(reference.get("user_context"), str) else ""
    body = reference.get("body") if isinstance(reference.get("body"), str) else ""
    return f"User supplied context:\n{context}\nReference content:\n{body}"[:MAX_REFERENCE_CHARS]


def _safe_receipt(receipt, status):
    allowed = {"route_key", "profile", "provider", "model", "status", "input_image_count", "reference_text_chars", "input_sha256", "schema_version", "recorded_at"}
    result = {key: value for key, value in (receipt.items() if isinstance(receipt, dict) else []) if key in allowed}
    result.setdefault("route_key", ROUTE_KEY)
    result.setdefault("profile", ROUTE_PROFILE)
    result["status"] = status
    return result


def _public_job(job):
    blocked = {"operation_key", "body", "raw_text", "raw_message", "chain_of_thought", "path"}
    result = {key: value for key, value in job.items() if key not in blocked and key != "receipt"}
    # Receipts are safe structured execution metadata, but never raw provider output.
    result["receipt"] = _safe_receipt(job.get("receipt"), job.get("status", "failed"))
    return result


def _job_id(draft_id, revision, operation_key):
    digest = hashlib.sha256(f"{draft_id}:{revision}:{operation_key}".encode("utf-8")).hexdigest()[:20]
    return f"haj_{digest}"


def _input_hash(images, reference_text):
    digest = hashlib.sha256()
    digest.update(reference_text.encode("utf-8"))
    for image in images:
        digest.update(str(image.get("sha256") or "").encode("utf-8"))
    return "sha256:" + digest.hexdigest()


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
