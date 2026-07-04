import re
import unittest
from datetime import datetime, timezone, timedelta

from asset_library.frontmatter import render_note
from asset_library.hashing import compute_body_hash, compute_non_body_hash
from asset_library.naming import generate_asset_id, sanitize_short_title
from asset_library.schema import validate_draft


class ContractRenderingTests(unittest.TestCase):
    def test_validate_draft_accepts_required_enums(self):
        draft = {
            "title": "PKA Answer Smoke",
            "agent_id": "agent06",
            "workflow_id": "ask",
            "asset_type": "agent06_pka_answer",
            "status": "active",
            "knowledge_status": "not_indexed",
            "source_status": "grounded",
            "sensitivity": "normal",
            "body_markdown": "# Answer\n\nBody",
            "tags": ["agent/agent06", "workflow/ask"],
        }

        self.assertEqual(validate_draft(draft), [])

    def test_validate_draft_rejects_invalid_enums_and_tags_with_spaces(self):
        draft = {
            "title": "Bad Draft",
            "agent_id": "agent06",
            "workflow_id": "ask",
            "asset_type": "agent06_pka_answer",
            "status": "live",
            "knowledge_status": "done",
            "source_status": "maybe",
            "sensitivity": "private",
            "body_markdown": "Body",
            "tags": ["agent/agent06", "bad tag"],
        }

        errors = validate_draft(draft)

        self.assertIn("status must be one of active, archived, deleted_in_vault, source_deleted", errors)
        self.assertIn("knowledge_status must be one of indexed, not_indexed, promoting, promotion_failed, promotion_requires_manual_review", errors)
        self.assertIn("source_status must be one of grounded, pending, uncertain, unverified", errors)
        self.assertIn("sensitivity must be one of audit_only, normal, restricted, sensitive", errors)
        self.assertIn("tags[1] must not contain whitespace", errors)

    def test_generate_asset_id_uses_utc_plus_8_date_and_8_hex(self):
        now = datetime(2026, 7, 3, 18, 30, tzinfo=timezone.utc)

        asset_id = generate_asset_id(now=now, token_hex=lambda n: "a1b2c3d4")

        self.assertEqual(asset_id, "ast_20260704_a1b2c3d4")
        self.assertRegex(asset_id, r"^ast_\d{8}_[0-9a-f]{8}$")

    def test_sanitize_short_title_is_filesystem_safe(self):
        title = ' / bad:title*with?chars"<>| and spaces \x00 '

        safe = sanitize_short_title(title, "ast_20260704_a1b2c3d4")

        self.assertEqual(safe, "bad-title-with-chars-and spaces")

    def test_sanitize_short_title_falls_back_to_asset_id(self):
        self.assertEqual(
            sanitize_short_title(" /:*?<>| ", "ast_20260704_a1b2c3d4"),
            "ast_20260704_a1b2c3d4",
        )

    def test_compute_body_hash_normalizes_bom_and_line_endings(self):
        left = compute_body_hash("\ufeff# Title\r\n\r\nBody\r\n")
        right = compute_body_hash("# Title\n\nBody\n")

        self.assertEqual(left, right)
        self.assertRegex(left, r"^sha256:[0-9a-f]{64}$")

    def test_compute_non_body_hash_uses_canonical_metadata_and_identity_files(self):
        draft = {
            "title": "Attachment Asset",
            "agent_id": "agent05",
            "workflow_id": "ppt",
            "asset_type": "ppt_export",
            "source_asset_path": "/tmp/task",
            "file_refs": [
                {"path": "b.pptx", "identity": True, "bytes": b"bbb"},
                {"path": "ignored.png", "identity": False, "bytes": b"ignored"},
                {"path": "a.md", "identity": True, "bytes": b"aaa"},
            ],
        }
        equivalent = {
            "workflow_id": "ppt",
            "source_asset_path": "/tmp/task",
            "asset_type": "ppt_export",
            "agent_id": "agent05",
            "title": "Attachment Asset",
            "file_refs": list(reversed(draft["file_refs"])),
        }

        digest, hash_source = compute_non_body_hash(draft)
        equivalent_digest, equivalent_hash_source = compute_non_body_hash(equivalent)

        self.assertEqual(digest, equivalent_digest)
        self.assertEqual(hash_source, "metadata_v1_plus_identity_attachment_sha256_list")
        self.assertEqual(equivalent_hash_source, hash_source)
        self.assertRegex(digest, r"^sha256:[0-9a-f]{64}$")

    def test_compute_non_body_hash_prefers_primary_file_when_present(self):
        base = {
            "title": "Attachment Asset",
            "agent_id": "agent05",
            "workflow_id": "ppt",
            "asset_type": "ppt_export",
            "source_asset_path": "/tmp/task",
            "file_refs": [
                {"path": "primary.pptx", "primary": True, "bytes": b"same"},
                {"path": "ignored.md", "identity": True, "bytes": b"old"},
            ],
        }
        changed_non_primary = dict(base)
        changed_non_primary["file_refs"] = [
            {"path": "primary.pptx", "primary": True, "bytes": b"same"},
            {"path": "ignored.md", "identity": True, "bytes": b"new"},
        ]

        self.assertEqual(compute_non_body_hash(base), compute_non_body_hash(changed_non_primary))

    def test_render_note_outputs_flat_yaml_and_body(self):
        draft = {
            "asset_id": "ast_20260704_a1b2c3d4",
            "asset_schema_version": 1,
            "title": "PKA Answer Smoke",
            "agent_id": "agent06",
            "workflow_id": "ask",
            "asset_type": "agent06_pka_answer",
            "status": "active",
            "knowledge_status": "not_indexed",
            "source_status": "grounded",
            "sensitivity": "normal",
            "created_at": "2026-07-04T10:00:00+08:00",
            "updated_at": "2026-07-04T10:00:00+08:00",
            "source_asset_path": "/tmp/source",
            "source_refs": [{"chunk_id": "Offer.md#13", "source_name": "Offer.md"}],
            "input_refs": [{"type": "question", "text": "Who is Marcus?"}],
            "file_refs": [],
            "export_refs": [],
            "model_route": "local_only",
            "subject_refs": ["Mantou"],
            "collection_refs": [],
            "tags": ["agent/agent06", "workflow/ask"],
            "body_markdown": "# PKA Answer Smoke\n\nSee [[Mantou]].",
        }

        note = render_note(draft)

        self.assertTrue(note.startswith("---\n"))
        self.assertIn("asset_id: ast_20260704_a1b2c3d4\n", note)
        self.assertIn("source_content_hash: sha256:", note)
        self.assertIn('hash_source: ""\n', note)
        self.assertIn("source_refs:\n  - chunk_id: Offer.md#13\n    source_name: Offer.md\n", note)
        self.assertIn("input_refs:\n  - type: question\n    text: Who is Marcus?\n", note)
        self.assertIn("tags:\n  - agent/agent06\n  - workflow/ask\n", note)
        self.assertTrue(note.endswith("# PKA Answer Smoke\n\nSee [[Mantou]].\n"))
        self.assertIsNone(re.search(r"^source_refs:\n  - \\{", note, re.MULTILINE))


if __name__ == "__main__":
    unittest.main()
