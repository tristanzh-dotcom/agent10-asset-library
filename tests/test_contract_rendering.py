import re
import unittest
from datetime import datetime, timezone, timedelta

import yaml

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

    def test_validate_draft_rejects_path_shaping_agent_id_and_invalid_identity_fields(self):
        draft = {
            "asset_id": "ast_20260711_not-hex",
            "asset_schema_version": 2,
            "title": "Bad identity",
            "agent_id": "../../99_System",
            "workflow_id": "ask/../../audit",
            "asset_type": "agent06 pka answer",
            "status": "active",
            "knowledge_status": "not_indexed",
            "source_status": "grounded",
            "sensitivity": "normal",
            "body_markdown": "Body",
            "source_content_hash": "sha256:not-a-hash",
            "tags": [],
        }

        errors = validate_draft(draft)

        self.assertIn("asset_id must match ast_YYYYMMDD_<8hex>", errors)
        self.assertIn("asset_schema_version must be 1", errors)
        self.assertIn("agent_id must match agent followed by two digits", errors)
        self.assertIn("workflow_id must contain only lowercase letters, digits, underscores, or hyphens", errors)
        self.assertIn("asset_type must contain only lowercase letters, digits, underscores, or hyphens", errors)
        self.assertIn("source_content_hash must match sha256:<64hex>", errors)

    def test_validate_draft_rejects_asset_id_with_impossible_calendar_date(self):
        draft = {
            "asset_id": "ast_20260231_deadbeef",
            "title": "Impossible date",
            "agent_id": "agent06",
            "workflow_id": "ask",
            "asset_type": "agent06_pka_answer",
            "status": "active",
            "knowledge_status": "not_indexed",
            "source_status": "grounded",
            "sensitivity": "normal",
            "body_markdown": "Body",
            "tags": [],
        }

        self.assertIn("asset_id date must be a valid calendar date", validate_draft(draft))

    def test_validate_draft_rejects_malformed_reference_lists_and_timestamps(self):
        draft = {
            "title": "Bad refs",
            "agent_id": "agent06",
            "workflow_id": "ask",
            "asset_type": "agent06_pka_answer",
            "status": "active",
            "knowledge_status": "not_indexed",
            "source_status": "grounded",
            "sensitivity": "normal",
            "body_markdown": "Body",
            "created_at": "July 11",
            "updated_at": 123,
            "source_refs": "not-a-list",
            "file_refs": ["not-an-object"],
            "tags": [],
        }

        errors = validate_draft(draft)

        self.assertIn("created_at must be an ISO 8601 timestamp", errors)
        self.assertIn("updated_at must be an ISO 8601 timestamp", errors)
        self.assertIn("source_refs must be a list", errors)
        self.assertIn("file_refs[0] must be an object", errors)

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
            "agent_id": "agent06",
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
            "agent_id": "agent06",
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
            "agent_id": "agent06",
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
        self.assertIn('asset_id: "ast_20260704_a1b2c3d4"\n', note)
        self.assertIn('source_content_hash: "sha256:', note)
        self.assertIn('hash_source: ""\n', note)
        self.assertIn('source_refs:\n  - "chunk_id": "Offer.md#13"\n    "source_name": "Offer.md"\n', note)
        self.assertIn('input_refs:\n  - "type": "question"\n    "text": "Who is Marcus?"\n', note)
        self.assertIn('tags:\n  - "agent/agent06"\n  - "workflow/ask"\n', note)
        self.assertTrue(note.endswith("# PKA Answer Smoke\n\nSee [[Mantou]].\n"))
        self.assertIsNone(re.search(r"^source_refs:\n  - \\{", note, re.MULTILINE))

    def test_render_note_round_trips_yaml_sensitive_strings(self):
        draft = {
            "asset_id": "ast_20260711_deadbeef",
            "asset_schema_version": 1,
            "title": "report: final # yes",
            "agent_id": "agent06",
            "workflow_id": "ask",
            "asset_type": "agent06_pka_answer",
            "status": "active",
            "knowledge_status": "not_indexed",
            "source_status": "grounded",
            "sensitivity": "normal",
            "source_refs": [{"source_name": "true", "url": "https://example.com/a:b"}],
            "tags": ["agent/agent06"],
            "body_markdown": "Body",
        }

        note = render_note(draft)
        frontmatter = yaml.safe_load(note.split("---", 2)[1])

        self.assertEqual(frontmatter["title"], "report: final # yes")
        self.assertEqual(frontmatter["source_refs"][0]["source_name"], "true")
        self.assertEqual(frontmatter["source_refs"][0]["url"], "https://example.com/a:b")

    def test_render_note_round_trips_all_yaml_implicit_and_whitespace_scalars(self):
        values = ["foo:", " leading", ".nan", "0x10", "line\u0085break"]
        for value in values:
            with self.subTest(value=value):
                draft = {
                    "asset_id": "ast_20260711_deadbeef",
                    "title": value,
                    "agent_id": "agent06",
                    "workflow_id": "ask",
                    "asset_type": "agent06_pka_answer",
                    "status": "active",
                    "knowledge_status": "not_indexed",
                    "source_status": "grounded",
                    "sensitivity": "normal",
                    "body_markdown": "Body",
                    "tags": [],
                }

                frontmatter = yaml.safe_load(render_note(draft).split("---", 2)[1])

                self.assertEqual(frontmatter["title"], value)

    def test_render_note_quotes_reference_mapping_keys_to_prevent_frontmatter_injection(self):
        draft = {
            "asset_id": "ast_20260711_deadbeef",
            "title": "Safe",
            "agent_id": "agent06",
            "workflow_id": "ask",
            "asset_type": "agent06_pka_answer",
            "status": "active",
            "knowledge_status": "not_indexed",
            "source_status": "grounded",
            "sensitivity": "normal",
            "body_markdown": "Body",
            "source_refs": [{"x\nstatus": "deleted_in_vault", "x: injected": "value"}],
            "tags": [],
        }

        frontmatter = yaml.safe_load(render_note(draft).split("---", 2)[1])

        self.assertEqual(frontmatter["status"], "active")
        self.assertEqual(frontmatter["source_refs"][0]["x\nstatus"], "deleted_in_vault")
        self.assertEqual(frontmatter["source_refs"][0]["x: injected"], "value")


if __name__ == "__main__":
    unittest.main()
