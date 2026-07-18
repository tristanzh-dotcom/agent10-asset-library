import unittest

import yaml

from asset_library.frontmatter import render_note
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

    def test_codex_task_summary_renders_flat_capture_properties(self):
        draft = _draft()
        draft.update({
            "asset_type": "codex-development-task-summary",
            "capture_kind": "task",
            "task_id": "tsk_" + "a" * 32,
            "continuity_key": "cty_" + "b" * 32,
            "task_status": "completed",
            "capture_status": "published",
            "quality_state": "publishable",
            "quality_score": 95,
            "verification_state": "reported",
            "project_id": "prj_123456789abc",
            "project_name": "web",
            "project_path": "/Users/tristanzh/agent/web",
            "started_at": "2026-07-17T09:00:00+08:00",
            "last_activity_at": "2026-07-17T10:00:00+08:00",
            "ended_at": "2026-07-17T10:00:00+08:00",
            "previous_task": "",
            "next_task": "",
        })
        self.assertEqual([], validate_draft(draft))
        parsed = yaml.safe_load(render_note(draft).split("---", 2)[1])
        self.assertEqual("completed", parsed["task_status"])
        self.assertEqual(95, parsed["quality_score"])
        self.assertEqual("reported", parsed["verification_state"])

    def test_codex_task_summary_preserves_v2_quality_properties(self):
        draft = _draft()
        draft.update({
            "asset_type": "codex-development-task-summary", "capture_kind": "task",
            "task_id": "tsk_" + "a" * 32, "continuity_key": "cty_" + "b" * 32,
            "task_status": "completed", "capture_status": "published", "quality_state": "publishable",
            "quality_score": 90, "verification_state": "reported", "project_id": "prj_123456789abc",
            "project_name": "web", "project_path": "/tmp/web", "started_at": "2026-07-17T00:00:00+00:00",
            "last_activity_at": "2026-07-17T00:00:00+00:00", "evidence_state": "sufficient",
            "readability_state": "clear", "publication_eligibility": "published",
        })
        self.assertEqual([], validate_draft(draft))
        parsed = yaml.safe_load(render_note(draft).split("---", 2)[1])
        self.assertEqual("sufficient", parsed["evidence_state"])
        self.assertEqual("clear", parsed["readability_state"])

    def test_codex_task_summary_accepts_cancelled_but_rejects_local_only_states(self):
        base = _draft()
        base.update({
            "asset_type": "codex-development-task-summary", "capture_kind": "task",
            "task_id": "tsk_" + "a" * 32, "continuity_key": "cty_" + "b" * 32,
            "capture_status": "published", "quality_state": "publishable", "quality_score": 90,
            "verification_state": "not_applicable", "project_id": "prj_123456789abc",
            "project_name": "web", "project_path": "/tmp/web",
            "started_at": "2026-07-17T00:00:00+00:00",
            "last_activity_at": "2026-07-17T00:00:00+00:00",
            "ended_at": "2026-07-17T00:00:00+00:00",
        })
        cancelled = dict(base, task_status="cancelled")
        self.assertEqual([], validate_draft(cancelled))
        for state in ("in_progress", "blocked", "pending_acceptance", "paused"):
            with self.subTest(state=state):
                self.assertTrue(any("task_status" in error for error in validate_draft(dict(base, task_status=state))))


if __name__ == "__main__":
    unittest.main()
