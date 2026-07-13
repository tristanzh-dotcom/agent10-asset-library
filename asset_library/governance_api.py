import json


GOVERNANCE_ENDPOINT = "/api/asset-library/governance"
GOVERNANCE_ACTION_PREFIX = "/api/asset-library/governance/actions/"
ALLOWED_ACTIONS = {
    "recover-writer",
    "compact-mirror-gaps",
}


def governance_response(method, path, service, mutation_authorized=False):
    if path == GOVERNANCE_ENDPOINT:
        if method != "GET":
            return _json_response(405, {"error": "method_not_allowed"})
        return _json_response(200, service.snapshot())
    if path.startswith(GOVERNANCE_ACTION_PREFIX):
        if method != "POST":
            return _json_response(405, {"error": "method_not_allowed"})
        if not mutation_authorized:
            return _json_response(403, {"error": "mutation_authorization_required"})
        action = path[len(GOVERNANCE_ACTION_PREFIX) :]
        if action not in ALLOWED_ACTIONS:
            return _json_response(404, {"error": "unknown_action"})
        return _json_response(200, service.run_mutation(action))
    return _json_response(404, {"error": "not_found"})


def _json_response(status, payload):
    return (
        status,
        {"content-type": "application/json; charset=utf-8"},
        json.dumps(payload, ensure_ascii=False, sort_keys=True),
    )
