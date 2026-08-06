import tempfile
import unittest
from pathlib import Path

from asset_library.hardware_bootstrap import HARDWARE_DIRECTORIES, HARDWARE_NOTES, HardwareNamespaceBootstrapper


class FakeRest:
    def __init__(self, fail_write=False):
        self.notes = {}
        self.writes = []
        self.fail_write = fail_write

    def read_note(self, path):
        if path not in self.notes:
            raise RuntimeError("HTTP 404: missing")
        return self.notes[path]

    def write_note(self, path, content):
        if self.fail_write:
            raise ConnectionError("rest unavailable")
        self.notes[path] = content
        self.writes.append(path)


class FakeFallback:
    def __init__(self):
        self.notes = {}

    def write_note(self, path, content):
        self.notes[path] = content


class HardwareBootstrapTests(unittest.TestCase):
    def test_bootstrap_creates_namespace_and_reuses_existing_notes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rest = FakeRest()
            bootstrapper = HardwareNamespaceBootstrapper(tmpdir, rest)

            first = bootstrapper.bootstrap()
            second = bootstrapper.bootstrap()

            self.assertEqual(set(first.written), set(HARDWARE_NOTES))
            self.assertEqual(second.written, ())
            self.assertEqual(set(second.reused), set(HARDWARE_NOTES))
            self.assertEqual(len(rest.writes), len(HARDWARE_NOTES))
            for directory in HARDWARE_DIRECTORIES:
                self.assertTrue((Path(tmpdir) / directory).is_dir())

    def test_bootstrap_falls_back_without_overwriting_local_existing_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rest = FakeRest(fail_write=True)
            fallback = FakeFallback()
            existing_path = Path(tmpdir) / "02_Hardware/00_Index/Hardware Home.md"
            existing_path.parent.mkdir(parents=True)
            existing_path.write_text("human edit", encoding="utf-8")

            result = HardwareNamespaceBootstrapper(tmpdir, rest, fallback).bootstrap()

            self.assertEqual(existing_path.read_text(encoding="utf-8"), "human edit")
            self.assertNotIn("02_Hardware/00_Index/Hardware Home.md", fallback.notes)
            self.assertEqual(len(result.written), len(HARDWARE_NOTES) - 1)
            self.assertEqual(len(result.reused), 1)


if __name__ == "__main__":
    unittest.main()
