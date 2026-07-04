import unittest

from asset_library.obsidian_rest import ObsidianRestError
from asset_library.writer import RestFirstAssetWriter


class FakeRestClient:
    def __init__(self, fail=False):
        self.fail = fail
        self.writes = []

    def write_note(self, path, markdown):
        if self.fail:
            raise ObsidianRestError("REST unavailable")
        self.writes.append((path, markdown))


class FakeFallbackWriter:
    def __init__(self):
        self.writes = []

    def write_note(self, path, markdown):
        self.writes.append((path, markdown))


class FakeMirror:
    def __init__(self, fail=False):
        self.fail = fail
        self.upserts = []

    def upsert_asset(self, draft, vault_path):
        if self.fail:
            raise RuntimeError("database is locked")
        self.upserts.append((dict(draft), vault_path))


class FakeCollisionChecker:
    def __init__(self, result=None):
        self.result = result
        self.checks = []

    def check(self, draft, vault_path):
        self.checks.append((dict(draft), vault_path))
        return self.result


class FakeGapJournal:
    def __init__(self):
        self.gaps = []

    def append_gap(self, asset_id, vault_path, fail_reason):
        self.gaps.append(
            {
                "asset_id": asset_id,
                "vault_path": vault_path,
                "fail_reason": fail_reason,
            }
        )


def valid_draft():
    return {
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
        "source_refs": [],
        "input_refs": [],
        "file_refs": [],
        "export_refs": [],
        "model_route": "local_only",
        "subject_refs": ["Mantou"],
        "collection_refs": [],
        "tags": ["agent/agent06"],
        "body_markdown": "# PKA Answer Smoke\n",
    }


class RestFirstAssetWriterTests(unittest.TestCase):
    def test_write_uses_rest_client_first(self):
        rest = FakeRestClient()
        fallback = FakeFallbackWriter()
        writer = RestFirstAssetWriter(rest_client=rest, fallback_writer=fallback)

        result = writer.write(valid_draft())

        self.assertEqual(result.mode, "rest")
        self.assertEqual(len(rest.writes), 1)
        self.assertEqual(fallback.writes, [])
        path, markdown = rest.writes[0]
        self.assertEqual(path, "01_Agents/Agent06/2026-07-04 - agent06 - PKA Answer Smoke - ast_20260704_a1b2c3d4.md")
        self.assertIn("asset_id: ast_20260704_a1b2c3d4", markdown)

    def test_write_generates_asset_id_when_draft_does_not_provide_final_id(self):
        rest = FakeRestClient()
        draft = valid_draft()
        del draft["asset_id"]
        writer = RestFirstAssetWriter(
            rest_client=rest,
            asset_id_factory=lambda: "ast_20260704_deadbeef",
        )

        result = writer.write(draft)

        self.assertEqual(result.asset_id, "ast_20260704_deadbeef")
        self.assertIn("ast_20260704_deadbeef", result.path)
        self.assertIn("asset_id: ast_20260704_deadbeef", rest.writes[0][1])

    def test_write_computes_source_content_hash_before_collision_check(self):
        rest = FakeRestClient()
        checker = FakeCollisionChecker()
        draft = valid_draft()
        writer = RestFirstAssetWriter(rest_client=rest, collision_checker=checker)

        writer.write(draft)

        checked_draft, _ = checker.checks[0]
        self.assertRegex(checked_draft["source_content_hash"], r"^sha256:[0-9a-f]{64}$")

    def test_write_accepts_non_body_asset_and_sets_hash_source(self):
        rest = FakeRestClient()
        draft = valid_draft()
        del draft["body_markdown"]
        draft["asset_type"] = "ppt_export"
        draft["file_refs"] = [{"path": "deck.pptx", "identity": True, "bytes": b"ppt"}]
        writer = RestFirstAssetWriter(rest_client=rest)

        writer.write(draft)

        markdown = rest.writes[0][1]
        self.assertIn("hash_source: metadata_v1_plus_identity_attachment_sha256_list", markdown)
        self.assertIn("source_content_hash: sha256:", markdown)

    def test_write_returns_existing_asset_without_rewriting_for_same_idempotent_key(self):
        rest = FakeRestClient()
        checker = FakeCollisionChecker(
            {
                "action": "reuse_existing",
                "asset_id": "ast_20260704_existing",
                "vault_path": "01_Agents/Agent06/existing.md",
            }
        )
        writer = RestFirstAssetWriter(rest_client=rest, collision_checker=checker)

        result = writer.write(valid_draft())

        self.assertEqual(result.mode, "idempotent_reuse")
        self.assertEqual(result.path, "01_Agents/Agent06/existing.md")
        self.assertEqual(result.asset_id, "ast_20260704_existing")
        self.assertEqual(rest.writes, [])

    def test_write_rejects_collision_before_any_io(self):
        rest = FakeRestClient()
        checker = FakeCollisionChecker(
            {
                "action": "reject",
                "reason": "asset_id collision with different source_content_hash",
            }
        )
        writer = RestFirstAssetWriter(rest_client=rest, collision_checker=checker)

        with self.assertRaises(ValueError) as context:
            writer.write(valid_draft())

        self.assertIn("asset_id collision", str(context.exception))
        self.assertEqual(rest.writes, [])

    def test_write_updates_mirror_after_successful_note_write(self):
        rest = FakeRestClient()
        mirror = FakeMirror()
        writer = RestFirstAssetWriter(rest_client=rest, mirror=mirror)

        result = writer.write(valid_draft())

        self.assertEqual(result.mode, "rest")
        self.assertEqual(len(mirror.upserts), 1)
        mirrored_draft, mirrored_path = mirror.upserts[0]
        self.assertEqual(mirrored_draft["asset_id"], "ast_20260704_a1b2c3d4")
        self.assertEqual(mirrored_path, result.path)

    def test_write_records_mirror_gap_when_note_write_succeeds_but_mirror_fails(self):
        rest = FakeRestClient()
        mirror = FakeMirror(fail=True)
        journal = FakeGapJournal()
        writer = RestFirstAssetWriter(
            rest_client=rest,
            mirror=mirror,
            mirror_gap_journal=journal,
        )

        result = writer.write(valid_draft())

        self.assertEqual(result.mode, "rest")
        self.assertEqual(result.mirror_status, "gap_recorded")
        self.assertEqual(
            journal.gaps,
            [
                {
                    "asset_id": "ast_20260704_a1b2c3d4",
                    "vault_path": result.path,
                    "fail_reason": "database is locked",
                }
            ],
        )

    def test_mirror_failure_after_rest_success_does_not_trigger_fallback(self):
        rest = FakeRestClient()
        fallback = FakeFallbackWriter()
        mirror = FakeMirror(fail=True)
        writer = RestFirstAssetWriter(
            rest_client=rest,
            fallback_writer=fallback,
            mirror=mirror,
        )

        with self.assertRaises(RuntimeError) as context:
            writer.write(valid_draft())

        self.assertEqual(str(context.exception), "database is locked")
        self.assertEqual(len(rest.writes), 1)
        self.assertEqual(fallback.writes, [])

    def test_write_falls_back_when_rest_fails(self):
        rest = FakeRestClient(fail=True)
        fallback = FakeFallbackWriter()
        writer = RestFirstAssetWriter(rest_client=rest, fallback_writer=fallback)

        result = writer.write(valid_draft())

        self.assertEqual(result.mode, "fallback")
        self.assertEqual(result.error, "REST unavailable")
        self.assertEqual(len(fallback.writes), 1)

    def test_write_rejects_invalid_draft_before_any_io(self):
        rest = FakeRestClient()
        fallback = FakeFallbackWriter()
        writer = RestFirstAssetWriter(rest_client=rest, fallback_writer=fallback)
        draft = valid_draft()
        draft["status"] = "live"

        with self.assertRaises(ValueError) as context:
            writer.write(draft)

        self.assertIn("status must be one of", str(context.exception))
        self.assertEqual(rest.writes, [])
        self.assertEqual(fallback.writes, [])


if __name__ == "__main__":
    unittest.main()
