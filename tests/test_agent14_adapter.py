import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from asset_library.adapters.agent14 import agent14_snapshot_to_draft
from asset_library.schema import validate_draft


def _sha256(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def build_snapshot(root, *, snapshot_root_name="snapshots"):
    snapshot_base = root / "projects" / "doc-demo" / "archive" / snapshot_root_name
    snapshot_base.mkdir(parents=True)
    payload = snapshot_base / "snap-placeholder" / "payload"
    (payload / "assets").mkdir(parents=True)
    files = {
        "payload/assets/test.png": b"asset-fixture",
        "payload/content.md": b"# Demo\n\nHello\n",
        "payload/index.html": b"<!doctype html><html><body>Hello</body></html>\n",
        "payload/manifest.json": b'{"version":"1.0"}\n',
    }
    for relative, data in files.items():
        path = snapshot_base / "snap-placeholder" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    file_entries = [
        {
            "path": relative,
            "role": "asset" if "/assets/" in relative else {
                "payload/content.md": "content_markdown",
                "payload/index.html": "editable_html",
                "payload/manifest.json": "document_manifest",
            }[relative],
            "mediaType": {
                "payload/assets/test.png": "image/png",
                "payload/content.md": "text/markdown",
                "payload/index.html": "text/html",
                "payload/manifest.json": "application/json",
            }[relative],
            "bytes": len(data),
            "sha256": _sha256(data),
        }
        for relative, data in sorted(files.items())
    ]
    source = {
        "fileName": "demo.pptx",
        "mediaType": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "sha256": "sha256:" + "a" * 64,
        "originalIncluded": False,
    }
    content_hash = _sha256(files["payload/content.md"])
    core = {
        "contractVersion": "agent14-archive:v1",
        "documentId": "doc-demo",
        "snapshotRevision": 1,
        "source": source,
        "document": {"pageCount": 1, "warningCodes": [], "contentSha256": content_hash},
        "files": file_entries,
    }
    bundle_hash = _sha256(_canonical(core))
    snapshot_id = "snap-r1-" + bundle_hash.split(":", 1)[1][:12]
    snapshot_dir = snapshot_base / snapshot_id
    (snapshot_base / "snap-placeholder").rename(snapshot_dir)
    manifest = {
        **core,
        "snapshotId": snapshot_id,
        "operationKey": f"agent14:doc-demo:r1:sha256:{bundle_hash.split(':', 1)[1]}",
        "createdAt": "2026-08-19T12:00:00+08:00",
        "document": {**core["document"], "bundleSha256": bundle_hash},
    }
    (snapshot_dir / "archive-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return snapshot_dir, snapshot_base


class Agent14AdapterTests(unittest.TestCase):
    def test_valid_snapshot_maps_to_restricted_normal_draft_without_asset_id(self):
        with tempfile.TemporaryDirectory() as tempdir:
            snapshot_dir, snapshot_root = build_snapshot(Path(tempdir))

            draft = agent14_snapshot_to_draft(snapshot_dir, snapshot_root=snapshot_root)
            manifest = json.loads((snapshot_dir / "archive-manifest.json").read_text(encoding="utf-8"))

            self.assertNotIn("asset_id", draft)
            self.assertEqual(draft["agent_id"], "agent14")
            self.assertEqual(draft["workflow_id"], "ppt2html_archive")
            self.assertEqual(draft["asset_type"], "agent14_document_snapshot")
            self.assertEqual(draft["sensitivity"], "restricted")
            self.assertEqual(draft["knowledge_status"], "not_indexed")
            self.assertEqual(draft["source_asset_path"], "agent14://doc-demo/" + snapshot_dir.name)
            self.assertEqual(draft["source_content_hash"], manifest["document"]["bundleSha256"])
            self.assertIn("## Archive Summary", draft["body_markdown"])
            self.assertIn("payload/index.html", draft["body_markdown"])
            self.assertEqual(
                [ref["path"] for ref in draft["file_refs"]],
                ["payload/assets/test.png", "payload/content.md", "payload/index.html", "payload/manifest.json"],
            )
            self.assertEqual(validate_draft(draft), [])

    def test_rejects_tampered_payload_and_unsafe_source_root(self):
        with tempfile.TemporaryDirectory() as tempdir:
            snapshot_dir, snapshot_root = build_snapshot(Path(tempdir))
            (snapshot_dir / "payload" / "content.md").write_text("tampered\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "content hash"):
                agent14_snapshot_to_draft(snapshot_dir, snapshot_root=snapshot_root)

            outbox_dir = snapshot_root.parent / "outbox"
            outbox_dir.mkdir()
            with self.assertRaisesRegex(ValueError, "snapshots root"):
                agent14_snapshot_to_draft(outbox_dir, snapshot_root=snapshot_root)

    def test_rejects_symlink_and_contract_version_mismatch(self):
        with tempfile.TemporaryDirectory() as tempdir:
            snapshot_dir, snapshot_root = build_snapshot(Path(tempdir))
            (snapshot_dir / "payload" / "assets" / "link.png").symlink_to(snapshot_dir / "payload" / "assets" / "test.png")
            with self.assertRaisesRegex(ValueError, "symlink"):
                agent14_snapshot_to_draft(snapshot_dir, snapshot_root=snapshot_root)

            (snapshot_dir / "payload" / "assets" / "link.png").unlink()
            linked_snapshot = Path(tempdir) / "linked-snapshot"
            linked_snapshot.symlink_to(snapshot_dir, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "snapshots root"):
                agent14_snapshot_to_draft(linked_snapshot, snapshot_root=snapshot_root)

            manifest_path = snapshot_dir / "archive-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["contractVersion"] = "agent14-archive:v2"
            manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "contract version"):
                agent14_snapshot_to_draft(snapshot_dir, snapshot_root=snapshot_root)


if __name__ == "__main__":
    unittest.main()
