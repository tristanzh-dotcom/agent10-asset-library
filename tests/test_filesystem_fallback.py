import tempfile
import unittest
from pathlib import Path

from asset_library.filesystem_fallback import DirectFilesystemFallbackWriter


class DirectFilesystemFallbackWriterTests(unittest.TestCase):
    def test_write_note_creates_parent_directories_and_replaces_atomically(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            writer = DirectFilesystemFallbackWriter(vault)

            writer.write_note("01_Agents/Agent10/note.md", "# One\n")
            writer.write_note("01_Agents/Agent10/note.md", "# Two\n")

            target = vault / "01_Agents" / "Agent10" / "note.md"
            self.assertEqual(target.read_text(encoding="utf-8"), "# Two\n")
            self.assertEqual(list(target.parent.glob("*.tmp")), [])
            self.assertTrue((vault / "99_System" / "audit" / ".asset-writer.lock").exists())

    def test_write_note_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            writer = DirectFilesystemFallbackWriter(Path(tmp))

            with self.assertRaises(ValueError):
                writer.write_note("../escape.md", "bad")


if __name__ == "__main__":
    unittest.main()
