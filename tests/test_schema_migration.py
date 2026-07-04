import unittest

from asset_library.schema_migration import normalize_asset_frontmatter


class SchemaMigrationTests(unittest.TestCase):
    def test_normalize_v1_adds_defaults_without_mutating_input(self):
        original = {
            "asset_id": "ast_20260704_a1b2c3d4",
            "title": "Legacy Note",
            "agent_id": "agent06",
            "workflow_id": "ask",
            "asset_type": "pka_answer",
            "source_content_hash": "sha256:abc",
        }

        normalized, changes = normalize_asset_frontmatter(original)

        self.assertNotIn("asset_schema_version", original)
        self.assertEqual(normalized["asset_schema_version"], 1)
        self.assertEqual(normalized["status"], "active")
        self.assertEqual(normalized["knowledge_status"], "not_indexed")
        self.assertEqual(normalized["source_status"], "unverified")
        self.assertEqual(normalized["sensitivity"], "normal")
        self.assertEqual(normalized["hash_source"], "")
        self.assertIn("added default status=active", changes)

    def test_normalize_maps_legacy_rag_status_to_knowledge_status(self):
        legacy = {
            "asset_id": "ast_20260704_a1b2c3d4",
            "title": "Legacy Note",
            "agent_id": "agent06",
            "workflow_id": "ask",
            "asset_type": "pka_answer",
            "rag_status": "indexed",
        }

        normalized, changes = normalize_asset_frontmatter(legacy)

        self.assertEqual(normalized["knowledge_status"], "indexed")
        self.assertIn("mapped rag_status to knowledge_status", changes)

    def test_normalize_rejects_unknown_schema_version(self):
        with self.assertRaises(ValueError) as context:
            normalize_asset_frontmatter({"asset_schema_version": 99})

        self.assertIn("unsupported asset_schema_version", str(context.exception))


if __name__ == "__main__":
    unittest.main()
