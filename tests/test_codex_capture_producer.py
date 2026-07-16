import unittest

from asset_library.producer_api import ProducerApiService
from asset_library.schema import validate_draft
from asset_library.writer import build_asset_note_path


class _Writer:
    def __init__(self):
        self.drafts = []

    def write(self, draft):
        self.drafts.append(draft)
        return type(
            "Result",
            (),
            {
                "asset_id": "ast_20260716_deadbeef",
                "path": "01_Agents/Codex/example.md",
                "mode": "fallback",
                "mirror_status": "upserted",
            },
        )()


def _draft(agent_id="codex"):
    return {
        "title": "Codex capture",
        "agent_id": agent_id,
        "workflow_id": "development-capture",
        "asset_type": "codex-development-summary",
        "status": "active",
        "knowledge_status": "not_indexed",
        "source_status": "grounded",
        "sensitivity": "audit_only",
        "body_markdown": "# Summary",
        "asset_id": "ast_20260716_deadbeef",
        "source_content_hash": "sha256:" + "a" * 64,
    }


class CodexCaptureProducerTests(unittest.TestCase):
    def test_codex_is_valid_schema_agent_and_uses_display_folder(self):
        draft = _draft()

        self.assertEqual(validate_draft(draft), [])
        self.assertEqual(
            build_asset_note_path(draft),
            "01_Agents/Codex/2026-07-16 - codex - Codex capture - ast_20260716_deadbeef.md",
        )

    def test_codex_can_use_normal_draft_endpoint_but_agent10_cannot(self):
        writer = _Writer()
        service = ProducerApiService(writer)
        draft = _draft()
        draft.pop("asset_id")

        result = service.ingest_draft(draft)

        self.assertEqual(result["asset_id"], "ast_20260716_deadbeef")
        self.assertEqual(writer.drafts, [draft])
        forbidden = _draft("agent10")
        forbidden.pop("asset_id")
        with self.assertRaisesRegex(ValueError, "not enabled"):
            service.ingest_draft(forbidden)


if __name__ == "__main__":
    unittest.main()
