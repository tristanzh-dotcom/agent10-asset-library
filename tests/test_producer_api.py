import json
import tempfile
import unittest
from pathlib import Path

from asset_library.producer_api import ProducerApiService, producer_response


class FakeWriter:
    def __init__(self):
        self.drafts = []

    def write(self, draft):
        self.drafts.append(draft)
        return type(
            "Result",
            (),
            {
                "mode": "rest",
                "path": "01_Agents/Agent10/example.md",
                "asset_id": "ast_20260704_test0001",
                "mirror_status": "upserted",
                "error": "",
            },
        )()

    def write_migration(self, draft):
        self.drafts.append(draft)
        return self.write({**draft, "migration": True})


class ProducerApiTests(unittest.TestCase):
    def test_post_drafts_writes_unified_draft(self):
        writer = FakeWriter()
        service = ProducerApiService(writer=writer)
        draft = {
            "title": "Direct Draft",
            "agent_id": "agent06",
            "workflow_id": "smoke",
            "asset_type": "audit",
            "status": "active",
            "knowledge_status": "not_indexed",
            "source_status": "grounded",
            "sensitivity": "normal",
            "body_markdown": "# Direct Draft",
        }

        status, headers, body = producer_response(
            "POST",
            "/api/asset-library/drafts",
            json.dumps(draft),
            service,
        )

        self.assertEqual(status, 201)
        self.assertEqual(headers["content-type"], "application/json; charset=utf-8")
        self.assertEqual(json.loads(body)["asset_id"], "ast_20260704_test0001")
        self.assertEqual(writer.drafts[0]["agent_id"], "agent06")

    def test_post_agent06_producer_asset_uses_agent10_adapter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            asset_dir = Path(tmpdir) / "ans_a"
            asset_dir.mkdir()
            (asset_dir / "answer.md").write_text("# Answer", encoding="utf-8")
            (asset_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "title": "Answer",
                        "question": "Q",
                        "source_status": "grounded",
                        "rag_status": "not_indexed",
                        "created_at": "2026-07-04T12:00:00",
                        "updated_at": "2026-07-04T12:00:00",
                    }
                ),
                encoding="utf-8",
            )
            writer = FakeWriter()
            service = ProducerApiService(writer=writer)

            status, _headers, body = producer_response(
                "POST",
                "/api/asset-library/producers/agent06/assets",
                json.dumps({"source_asset_path": str(asset_dir)}),
                service,
            )

            self.assertEqual(status, 201)
            self.assertEqual(json.loads(body)["producer_id"], "agent06")
            self.assertEqual(writer.drafts[0]["agent_id"], "agent06")
            self.assertEqual(writer.drafts[0]["asset_type"], "agent06_pka_answer")

    def test_unknown_producer_returns_404(self):
        status, _headers, body = producer_response(
            "POST",
            "/api/asset-library/producers/agent99/assets",
            "{}",
            ProducerApiService(writer=FakeWriter()),
        )

        self.assertEqual(status, 404)
        self.assertEqual(json.loads(body)["error"], "unknown_producer")

    def test_normal_draft_rejects_caller_supplied_asset_id(self):
        writer = FakeWriter()
        service = ProducerApiService(writer=writer)

        status, _headers, body = producer_response(
            "POST",
            "/api/asset-library/drafts",
            json.dumps({"asset_id": "ast_20260711_deadbeef"}),
            service,
        )

        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["message"], "normal producer drafts must not include asset_id")
        self.assertEqual(writer.drafts, [])

    def test_controlled_migration_uses_separate_endpoint_and_writer_method(self):
        writer = FakeWriter()
        service = ProducerApiService(writer=writer)

        status, _headers, body = producer_response(
            "POST",
            "/api/asset-library/migrations/drafts",
            json.dumps({"asset_id": "ast_20260711_deadbeef", "agent_id": "agent06"}),
            service,
            migration_authorized=True,
        )

        self.assertEqual(status, 201)
        self.assertEqual(json.loads(body)["asset_id"], "ast_20260704_test0001")
        self.assertEqual(writer.drafts[0]["asset_id"], "ast_20260711_deadbeef")

    def test_controlled_migration_endpoint_denies_by_default(self):
        writer = FakeWriter()

        status, _headers, body = producer_response(
            "POST",
            "/api/asset-library/migrations/drafts",
            json.dumps({"asset_id": "ast_20260711_deadbeef", "agent_id": "agent06"}),
            ProducerApiService(writer=writer),
        )

        self.assertEqual(status, 403)
        self.assertEqual(json.loads(body)["error"], "migration_authorization_required")
        self.assertEqual(writer.drafts, [])

    def test_v1_rejects_direct_drafts_from_non_agent06_producers(self):
        writer = FakeWriter()

        status, _headers, body = producer_response(
            "POST",
            "/api/asset-library/drafts",
            json.dumps({"agent_id": "agent10"}),
            ProducerApiService(writer=writer),
        )

        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["message"], "producer agent_id is not enabled for V1: agent10")
        self.assertEqual(writer.drafts, [])


if __name__ == "__main__":
    unittest.main()
