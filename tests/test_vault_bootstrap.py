import tempfile
import unittest
from pathlib import Path

from asset_library.vault_bootstrap import BOOTSTRAP_DIRECTORIES, bootstrap_vault


class VaultBootstrapTests(unittest.TestCase):
    def test_bootstrap_vault_creates_contract_directories_and_system_notes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = Path(tmpdir) / "AgentAssetVault"

            result = bootstrap_vault(vault)

            self.assertEqual(result.vault_path, vault)
            for directory in BOOTSTRAP_DIRECTORIES:
                self.assertTrue((vault / directory).is_dir(), directory)
            self.assertTrue((vault / ".gitignore").exists())
            self.assertTrue((vault / "99_System" / "schemas" / "asset_schema_v1.md").exists())
            self.assertTrue((vault / "99_System" / "templates" / "asset_note_template.md").exists())
            self.assertTrue((vault / "99_System" / "indexes" / "asset_library_home.md").exists())
            self.assertIn("created", result.actions)

    def test_bootstrap_copies_local_rest_plugin_without_runtime_secret(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "plugin-source"
            source.mkdir()
            (source / "main.js").write_text("main", encoding="utf-8")
            (source / "manifest.json").write_text('{"id":"obsidian-local-rest-api"}', encoding="utf-8")
            (source / "styles.css").write_text("css", encoding="utf-8")
            (source / "data.json").write_text('{"runtime_secret":"secret"}', encoding="utf-8")
            vault = root / "vault"

            bootstrap_vault(vault, plugin_source=source)

            plugin = vault / ".obsidian" / "plugins" / "obsidian-local-rest-api"
            self.assertEqual((plugin / "main.js").read_text(encoding="utf-8"), "main")
            self.assertEqual((plugin / "manifest.json").read_text(encoding="utf-8"), '{"id":"obsidian-local-rest-api"}')
            self.assertFalse((plugin / "data.json").exists())
            self.assertEqual(
                (vault / ".obsidian" / "community-plugins.json").read_text(encoding="utf-8"),
                '[\n  "obsidian-local-rest-api"\n]\n',
            )

    def test_bootstrap_is_idempotent_and_does_not_overwrite_existing_notes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = Path(tmpdir) / "vault"
            schema = vault / "99_System" / "schemas" / "asset_schema_v1.md"
            schema.parent.mkdir(parents=True)
            schema.write_text("custom schema", encoding="utf-8")

            bootstrap_vault(vault)

            self.assertEqual(schema.read_text(encoding="utf-8"), "custom schema")


if __name__ == "__main__":
    unittest.main()
