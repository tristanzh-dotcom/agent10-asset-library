import unittest

from asset_library.collision import CollisionChecker, idempotent_key


class FakeRegistry:
    def __init__(self, by_asset_id=None, by_idempotent_key=None, existing_paths=None):
        self.by_asset_id = by_asset_id or {}
        self.by_idempotent_key = by_idempotent_key or {}
        self.existing_paths = set(existing_paths or [])

    def get_by_asset_id(self, asset_id):
        return self.by_asset_id.get(asset_id)

    def get_by_idempotent_key(self, key):
        return self.by_idempotent_key.get(key)

    def path_exists(self, vault_path):
        return vault_path in self.existing_paths


def draft():
    return {
        "asset_id": "ast_20260704_a1b2c3d4",
        "agent_id": "agent06",
        "workflow_id": "ask",
        "source_asset_path": "/tmp/source",
        "source_content_hash": "sha256:abc",
    }


class CollisionCheckerTests(unittest.TestCase):
    def test_idempotent_key_uses_agent_workflow_source_path_and_hash(self):
        self.assertEqual(
            idempotent_key(draft()),
            "agent06\x1fask\x1f/tmp/source\x1fsha256:abc",
        )

    def test_reuses_existing_asset_for_same_idempotent_key(self):
        registry = FakeRegistry(
            by_idempotent_key={
                idempotent_key(draft()): {
                    "asset_id": "ast_20260704_existing",
                    "vault_path": "01_Agents/Agent06/existing.md",
                }
            }
        )

        result = CollisionChecker(registry).check(draft(), "new.md")

        self.assertEqual(result["action"], "reuse_existing")
        self.assertEqual(result["asset_id"], "ast_20260704_existing")

    def test_rejects_asset_id_collision_with_different_hash(self):
        registry = FakeRegistry(
            by_asset_id={
                "ast_20260704_a1b2c3d4": {
                    "asset_id": "ast_20260704_a1b2c3d4",
                    "source_content_hash": "sha256:different",
                }
            }
        )

        result = CollisionChecker(registry).check(draft(), "new.md")

        self.assertEqual(result["action"], "reject")
        self.assertIn("asset_id collision", result["reason"])

    def test_rejects_target_path_collision(self):
        registry = FakeRegistry(existing_paths={"01_Agents/Agent06/example.md"})

        result = CollisionChecker(registry).check(draft(), "01_Agents/Agent06/example.md")

        self.assertEqual(result["action"], "reject")
        self.assertIn("target path already exists", result["reason"])

    def test_allows_new_asset_when_no_collision_exists(self):
        self.assertIsNone(CollisionChecker(FakeRegistry()).check(draft(), "new.md"))


if __name__ == "__main__":
    unittest.main()
