import json
import stat
import tempfile
import unittest
from pathlib import Path

from asset_library.http_server import Agent10HttpApp, ensure_control_token


class FakeGovernanceService:
    def __init__(self):
        self.mutations = []

    def snapshot(self):
        return {"writer_health": {"mirror_asset_count": 2}}

    def run_mutation(self, action):
        self.mutations.append(action)
        return {"action": action, "status": "completed"}


class FakeProducerService:
    def ingest_draft(self, draft):
        return {"asset_id": "ast_20260712_deadbeef", "mode": "rest", "path": "note.md"}

    def ingest_producer_asset(self, producer_id, payload):
        return {"producer_id": producer_id, "asset_id": "ast_20260712_deadbeef", "mode": "rest", "path": "note.md"}

    def ingest_migration_draft(self, draft):
        return {"asset_id": draft["asset_id"], "mode": "rest", "path": "note.md"}


class FakeRuntime:
    def __init__(self):
        self.governance_service = FakeGovernanceService()
        self.producer_service = FakeProducerService()


class Agent10HttpAppTests(unittest.TestCase):
    def setUp(self):
        self.runtime = FakeRuntime()
        self.app = Agent10HttpApp(runtime=self.runtime, control_token="token-value")

    def test_governance_requires_loopback_bearer_token(self):
        status, _headers, body = self.app.dispatch(
            method="GET",
            path="/api/agent10/governance",
            headers={},
            body=b"",
            client_host="127.0.0.1",
        )
        self.assertEqual(status, 403)
        self.assertEqual(json.loads(body)["error"], "control_authorization_required")

        status, _headers, body = self.app.dispatch(
            method="GET",
            path="/api/agent10/governance",
            headers={"authorization": "Bearer token-value"},
            body=b"",
            client_host="192.168.1.7",
        )
        self.assertEqual(status, 403)
        self.assertEqual(json.loads(body)["error"], "loopback_required")

    def test_governance_returns_side_effect_free_snapshot_for_authorized_loopback(self):
        status, headers, body = self.app.dispatch(
            method="GET",
            path="/api/agent10/governance",
            headers={"authorization": "Bearer token-value"},
            body=b"",
            client_host="127.0.0.1",
        )
        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "application/json; charset=utf-8")
        self.assertEqual(json.loads(body)["writer_health"]["mirror_asset_count"], 2)

    def test_explicit_mutation_and_agent06_producer_are_authorized(self):
        headers = {"authorization": "Bearer token-value"}
        status, _headers, body = self.app.dispatch(
            method="POST",
            path="/api/agent10/governance/actions/recover-writer",
            headers=headers,
            body=b"{}",
            client_host="127.0.0.1",
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["action"], "recover-writer")
        self.assertEqual(self.runtime.governance_service.mutations, ["recover-writer"])

        status, _headers, body = self.app.dispatch(
            method="POST",
            path="/api/agent10/producers/agent06/assets",
            headers=headers,
            body=json.dumps({"source_asset_path": "/tmp/asset"}).encode("utf-8"),
            client_host="127.0.0.1",
        )
        self.assertEqual(status, 201)
        self.assertEqual(json.loads(body)["producer_id"], "agent06")

    def test_token_file_is_generated_with_owner_only_permissions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / ".agent10-control.token"
            first = ensure_control_token(path)
            second = ensure_control_token(path)

            self.assertEqual(first, second)
            self.assertRegex(first, r"^[0-9a-f]{64}$")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()
