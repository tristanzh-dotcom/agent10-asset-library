import json
import unittest

from asset_library.governance_api import governance_response


class FakeGovernanceService:
    def __init__(self):
        self.mutations = []

    def snapshot(self):
        return {"writer_health": {"mirror_asset_count": 1}, "mirror_gaps": {"open_count": 0}}

    def run_mutation(self, action):
        self.mutations.append(action)
        return {"action": action, "status": "completed"}


class GovernanceApiTests(unittest.TestCase):
    def test_governance_endpoint_returns_snapshot_json(self):
        status, headers, body = governance_response("GET", "/api/asset-library/governance", FakeGovernanceService())

        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "application/json; charset=utf-8")
        self.assertEqual(json.loads(body), {"writer_health": {"mirror_asset_count": 1}, "mirror_gaps": {"open_count": 0}})

    def test_unknown_endpoint_returns_404(self):
        status, headers, body = governance_response("GET", "/api/asset-library/assets", FakeGovernanceService())

        self.assertEqual(status, 404)
        self.assertEqual(json.loads(body)["error"], "not_found")

    def test_governance_get_rejects_mutation_method(self):
        service = FakeGovernanceService()

        status, _headers, body = governance_response("POST", "/api/asset-library/governance", service)

        self.assertEqual(status, 405)
        self.assertEqual(json.loads(body)["error"], "method_not_allowed")
        self.assertEqual(service.mutations, [])

    def test_explicit_mutation_endpoint_runs_named_action(self):
        service = FakeGovernanceService()

        status, _headers, body = governance_response(
            "POST",
            "/api/asset-library/governance/actions/recover-writer",
            service,
            mutation_authorized=True,
        )

        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"action": "recover-writer", "status": "completed"})
        self.assertEqual(service.mutations, ["recover-writer"])

    def test_mutation_endpoint_denies_by_default(self):
        service = FakeGovernanceService()

        status, _headers, body = governance_response(
            "POST",
            "/api/asset-library/governance/actions/recover-writer",
            service,
        )

        self.assertEqual(status, 403)
        self.assertEqual(json.loads(body)["error"], "mutation_authorization_required")
        self.assertEqual(service.mutations, [])


if __name__ == "__main__":
    unittest.main()
