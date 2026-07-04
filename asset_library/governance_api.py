import json


GOVERNANCE_ENDPOINT = "/api/asset-library/governance"


def governance_response(path, service):
    if path != GOVERNANCE_ENDPOINT:
        return _json_response(404, {"error": "not_found"})
    return _json_response(200, service.snapshot())


def _json_response(status, payload):
    return (
        status,
        {"content-type": "application/json; charset=utf-8"},
        json.dumps(payload, ensure_ascii=False, sort_keys=True),
    )
