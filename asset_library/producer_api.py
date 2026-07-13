import json
from pathlib import Path

from .adapters.agent06 import agent06_answer_to_draft


DRAFTS_ENDPOINT = "/api/asset-library/drafts"
MIGRATIONS_ENDPOINT = "/api/asset-library/migrations/drafts"
PRODUCER_PREFIX = "/api/asset-library/producers/"


class ProducerApiService:
    def __init__(self, writer, adapters=None, allowed_agent_ids=None):
        self.writer = writer
        self.adapters = adapters or {"agent06": agent06_answer_to_draft}
        self.allowed_agent_ids = set(allowed_agent_ids or {"agent06"})

    def ingest_draft(self, draft):
        if "asset_id" in draft:
            raise ValueError("normal producer drafts must not include asset_id")
        self._validate_agent_scope(draft)
        result = self.writer.write(draft)
        return _write_result(result)

    def ingest_migration_draft(self, draft):
        if not draft.get("asset_id"):
            raise ValueError("controlled migration drafts must include asset_id")
        self._validate_agent_scope(draft)
        result = self.writer.write_migration(draft)
        return _write_result(result)

    def ingest_producer_asset(self, producer_id, payload):
        adapter = self.adapters.get(producer_id)
        if adapter is None:
            raise UnknownProducerError(producer_id)
        source_asset_path = payload.get("source_asset_path")
        if not source_asset_path:
            raise ValueError("source_asset_path is required")
        draft = adapter(Path(source_asset_path))
        result = self.writer.write(draft)
        response = _write_result(result)
        response["producer_id"] = producer_id
        return response

    def _validate_agent_scope(self, draft):
        agent_id = draft.get("agent_id")
        if agent_id not in self.allowed_agent_ids:
            raise ValueError(f"producer agent_id is not enabled for V1: {agent_id}")


class UnknownProducerError(Exception):
    pass


def producer_response(method, path, body, service, migration_authorized=False):
    if method != "POST":
        return _json_response(405, {"error": "method_not_allowed"})
    try:
        payload = json.loads(body or "{}")
        if path == DRAFTS_ENDPOINT:
            return _json_response(201, service.ingest_draft(payload))
        if path == MIGRATIONS_ENDPOINT:
            if not migration_authorized:
                return _json_response(403, {"error": "migration_authorization_required"})
            return _json_response(201, service.ingest_migration_draft(payload))
        producer_id = _producer_id_from_path(path)
        if producer_id:
            return _json_response(201, service.ingest_producer_asset(producer_id, payload))
        return _json_response(404, {"error": "not_found"})
    except UnknownProducerError:
        return _json_response(404, {"error": "unknown_producer"})
    except ValueError as exc:
        return _json_response(400, {"error": "bad_request", "message": str(exc)})


def _producer_id_from_path(path):
    if not path.startswith(PRODUCER_PREFIX) or not path.endswith("/assets"):
        return ""
    return path[len(PRODUCER_PREFIX) : -len("/assets")]


def _write_result(result):
    return {
        "asset_id": result.asset_id,
        "path": result.path,
        "mode": result.mode,
        "mirror_status": result.mirror_status,
    }


def _json_response(status, payload):
    return (
        status,
        {"content-type": "application/json; charset=utf-8"},
        json.dumps(payload, ensure_ascii=False, sort_keys=True),
    )
