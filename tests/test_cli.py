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


class FakeHardwareService:
    def __init__(self):
        self.calls = []

    def submit(self, payload):
        self.calls.append(("submit", payload))
        return {
            "intake_id": "hwi_cli",
            "record_type": payload["draft"]["record_type"],
            "record_id": payload["draft"]["hardware_model_id"],
            "snapshot_hash": "sha256:" + "a" * 64,
            "draft_revision": 1,
            "intake_status": "review_pending",
            "status": "review_pending",
            "outcome": "created",
        }

    def accept(self, intake_id, accepted_by, expected_snapshot_hash):
        self.calls.append(("accept", intake_id, accepted_by, expected_snapshot_hash))
        return {
            "status": "published",
            "record_id": "hwm_cli",
            "path": "02_Hardware/10_Models/Controllers/HWM - CLI - hwm_cli.md",
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

    def test_prepare_hardware_uses_shared_intake_service(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            draft_path = Path(tmpdir) / "hardware.json"
            draft_path.write_text(json.dumps(valid_model()), encoding="utf-8")
            service = FakeHardwareService()

            status, output = run_cli(
                ["prepare-hardware", str(draft_path), "codex", "TZ", "op-cli"],
                service=service,
            )

            self.assertEqual(status, 0)
            self.assertEqual(service.calls[0][0], "submit")
            self.assertEqual(service.calls[0][1]["operation_key"], "op-cli")
            self.assertEqual(json.loads(output)["intake_id"], "hwi_cli")

    def test_accept_hardware_uses_shared_acceptance_service(self):
        service = FakeHardwareService()
        expected_hash = "sha256:" + "a" * 64

        status, output = run_cli(
            ["accept-hardware", "hwi_cli", "TZ", expected_hash],
            service=service,
        )

        self.assertEqual(status, 0)
        self.assertEqual(service.calls[0], ("accept", "hwi_cli", "TZ", expected_hash))
        self.assertEqual(json.loads(output)["status"], "published")


if __name__ == "__main__":
    unittest.main()
