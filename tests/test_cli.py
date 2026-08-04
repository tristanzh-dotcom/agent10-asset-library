import json
import tempfile
import unittest
from pathlib import Path

from asset_library.cli import run_cli
from asset_library.__main__ import main
from tests.test_hardware_schema import valid_model


class FakeProducerService:
    def __init__(self):
        self.calls = []

    def ingest_draft(self, draft):
        self.calls.append(("draft", draft))
        return {
            "asset_id": "ast_cli",
            "path": "note.md",
            "mode": "rest",
            "mirror_status": "upserted",
        }

    def ingest_producer_asset(self, producer_id, payload):
        self.calls.append((producer_id, payload))
        return {
            "producer_id": producer_id,
            "asset_id": "ast_agent06",
            "path": "note.md",
            "mode": "rest",
            "mirror_status": "upserted",
        }

    def ingest_migration_draft(self, draft):
        self.calls.append(("migration", draft))
        return {
            "asset_id": draft["asset_id"],
            "path": "note.md",
            "mode": "rest",
            "mirror_status": "upserted",
        }


class CliTests(unittest.TestCase):
    def test_main_validate_draft_does_not_require_runtime_credentials(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            draft_path = Path(tmpdir) / "draft.json"
            draft_path.write_text(
                json.dumps(
                    {
                        "title": "Draft",
                        "agent_id": "agent06",
                        "workflow_id": "ask",
                        "asset_type": "agent06_pka_answer",
                        "status": "active",
                        "knowledge_status": "not_indexed",
                        "source_status": "grounded",
                        "sensitivity": "normal",
                        "body_markdown": "# Draft",
                    }
                ),
                encoding="utf-8",
            )

            status = main(["validate-draft", str(draft_path)])

            self.assertEqual(status, 0)

    def test_validate_draft_reads_json_and_returns_errors(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            draft_path = Path(tmpdir) / "draft.json"
            draft_path.write_text(json.dumps({"title": "Missing Fields"}), encoding="utf-8")

            status, output = run_cli(["validate-draft", str(draft_path)], service=FakeProducerService())

            self.assertEqual(status, 1)
            self.assertIn("agent_id is required", output)

    def test_main_validate_hardware_does_not_require_runtime_credentials(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            draft_path = Path(tmpdir) / "hardware.json"
            draft_path.write_text(json.dumps(valid_model()), encoding="utf-8")

            status = main(["validate-hardware", str(draft_path)])

            self.assertEqual(status, 0)

    def test_validate_hardware_reads_json_and_returns_errors(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            valid_path = Path(tmpdir) / "hardware.json"
            valid_path.write_text(json.dumps(valid_model()), encoding="utf-8")
            invalid_path = Path(tmpdir) / "invalid-hardware.json"
            invalid_path.write_text(json.dumps({"record_type": "device"}), encoding="utf-8")

            valid_status, valid_output = run_cli(
                ["validate-hardware", str(valid_path)], service=FakeProducerService()
            )
            invalid_status, invalid_output = run_cli(
                ["validate-hardware", str(invalid_path)], service=FakeProducerService()
            )

            self.assertEqual(valid_status, 0)
            self.assertEqual(valid_output, "OK")
            self.assertEqual(invalid_status, 1)
            self.assertIn("record_type", invalid_output)

    def test_ingest_draft_uses_producer_service(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            draft_path = Path(tmpdir) / "draft.json"
            draft_path.write_text(
                json.dumps(
                    {
                        "title": "Draft",
                        "agent_id": "agent10",
                        "workflow_id": "smoke",
                        "asset_type": "audit",
                        "status": "active",
                        "knowledge_status": "not_indexed",
                        "source_status": "grounded",
                        "sensitivity": "normal",
                        "body_markdown": "# Draft",
                    }
                ),
                encoding="utf-8",
            )
            service = FakeProducerService()

            status, output = run_cli(["ingest-draft", str(draft_path)], service=service)

            self.assertEqual(status, 0)
            self.assertEqual(service.calls[0][0], "draft")
            self.assertEqual(json.loads(output)["asset_id"], "ast_cli")

    def test_ingest_agent06_builds_producer_payload(self):
        service = FakeProducerService()

        status, output = run_cli(["ingest-agent06", "/tmp/answer-asset"], service=service)

        self.assertEqual(status, 0)
        self.assertEqual(service.calls[0], ("agent06", {"source_asset_path": "/tmp/answer-asset"}))
        self.assertEqual(json.loads(output)["producer_id"], "agent06")

    def test_ingest_migration_uses_controlled_service_method(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            draft_path = Path(tmpdir) / "draft.json"
            draft_path.write_text(
                json.dumps({"asset_id": "ast_20260711_deadbeef"}),
                encoding="utf-8",
            )
            service = FakeProducerService()

            status, output = run_cli(["ingest-migration", str(draft_path)], service=service)

            self.assertEqual(status, 0)
            self.assertEqual(service.calls[0][0], "migration")
            self.assertEqual(json.loads(output)["asset_id"], "ast_20260711_deadbeef")


if __name__ == "__main__":
    unittest.main()
