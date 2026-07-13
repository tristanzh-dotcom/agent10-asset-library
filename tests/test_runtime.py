import tempfile
import unittest
import json
from pathlib import Path

from asset_library.runtime import build_runtime


class RuntimeTests(unittest.TestCase):
    def test_build_runtime_rejects_non_local_or_non_https_rest_url(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {
                "AGENT_ASSET_VAULT_PATH": tmpdir,
                "OBSIDIAN_REST_API_KEY": "secret",
                "OBSIDIAN_REST_BASE_URL": "https://example.com:27124",
            }

            with self.assertRaisesRegex(ValueError, "localhost HTTPS"):
                build_runtime(env=env)

    def test_build_runtime_requires_api_key_without_exposing_it(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {
                "AGENT_ASSET_VAULT_PATH": tmpdir,
                "OBSIDIAN_REST_BASE_URL": "https://127.0.0.1:27124",
            }

            with self.assertRaisesRegex(ValueError, "OBSIDIAN_REST_API_KEY is required"):
                build_runtime(env=env)

    def test_build_runtime_reads_api_key_from_ignored_obsidian_runtime_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "data.json"
            config_path.write_text(json.dumps({"apiKey": "runtime-secret"}), encoding="utf-8")
            runtime = build_runtime(
                env={
                    "AGENT_ASSET_VAULT_PATH": tmpdir,
                    "OBSIDIAN_REST_CONFIG_PATH": str(config_path),
                    "OBSIDIAN_REST_BASE_URL": "https://127.0.0.1:27124",
                }
            )

            self.assertEqual(runtime.rest_client.api_key, "runtime-secret")

    def test_build_runtime_assembles_agent06_only_with_shared_writer_lock(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = build_runtime(
                env={
                    "AGENT_ASSET_VAULT_PATH": tmpdir,
                    "OBSIDIAN_REST_API_KEY": "secret",
                    "OBSIDIAN_REST_BASE_URL": "https://127.0.0.1:27124",
                }
            )

            self.assertEqual(set(runtime.producer_service.adapters), {"agent06"})
            self.assertIsNotNone(runtime.writer.collision_checker)
            self.assertIsNotNone(runtime.writer.operation_lock_factory)
            self.assertFalse(runtime.fallback_writer.use_internal_lock)
            self.assertEqual(runtime.vault_path, Path(tmpdir).resolve())

    def test_recovery_is_explicit_and_not_run_during_runtime_construction(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = Path(tmpdir) / "vault"
            runtime = build_runtime(
                env={
                    "AGENT_ASSET_VAULT_PATH": str(vault),
                    "OBSIDIAN_REST_API_KEY": "secret",
                    "OBSIDIAN_REST_BASE_URL": "https://localhost:27124",
                }
            )

            self.assertFalse(vault.exists())
            snapshot = runtime.governance_service.snapshot()

            self.assertEqual(snapshot["writer_health"]["mirror_asset_count"], 0)
            self.assertFalse(vault.exists())
            result = runtime.governance_service.run_mutation("recover-writer")

            self.assertEqual(result["action"], "recover-writer")
            self.assertIn("writer_state", result)


if __name__ == "__main__":
    unittest.main()
