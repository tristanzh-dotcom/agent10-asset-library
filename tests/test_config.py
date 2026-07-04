import json
import os
import tempfile
import unittest
from pathlib import Path

from asset_library.config import resolve_vault_path


class ConfigTests(unittest.TestCase):
    def test_resolve_vault_path_prefers_environment_variable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {"AGENT_ASSET_VAULT_PATH": "/tmp/env-vault"}
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(json.dumps({"vault_path": "/tmp/config-vault"}), encoding="utf-8")

            resolved = resolve_vault_path(config_path=config_path, env=env)

            self.assertEqual(str(resolved.path), "/tmp/env-vault")
            self.assertEqual(resolved.source, "env:AGENT_ASSET_VAULT_PATH")

    def test_resolve_vault_path_uses_config_before_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(json.dumps({"vault_path": "/tmp/config-vault"}), encoding="utf-8")

            resolved = resolve_vault_path(config_path=config_path, env={})

            self.assertEqual(str(resolved.path), "/tmp/config-vault")
            self.assertEqual(resolved.source, f"config:{config_path}")

    def test_resolve_vault_path_falls_back_to_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_config = Path(tmpdir) / "missing.json"

            resolved = resolve_vault_path(config_path=missing_config, env={})

            self.assertEqual(str(resolved.path), "/Users/tristanzh/agent/AgentAssetVault")
            self.assertEqual(resolved.source, "default")


if __name__ == "__main__":
    unittest.main()
