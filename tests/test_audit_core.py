"""Regression cases for the approved October audit, using only temporary data."""

import json
import socket
import stat
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from asset_library.collision import CollisionChecker, VaultFilesystemCollisionProbe
from asset_library.filesystem_fallback import DirectFilesystemFallbackWriter
from asset_library.http_server import Agent10HttpApp, create_http_server
from asset_library.locking import VaultWriteLock, recover_writer_state
from asset_library.producer_api import ProducerApiService, producer_response
from asset_library.runtime import build_runtime
from asset_library.sqlite_mirror import MirrorGapJournal, SQLiteAssetMirror
from asset_library.writer import RestFirstAssetWriter
from tests.test_http_server import FakeRuntime
from tests.test_writer import FakeRestClient, valid_draft


def normal_draft():
    draft = valid_draft()
    draft.pop("asset_id")
    return draft


class DiskRest(DirectFilesystemFallbackWriter):
    def __init__(self, root):
        super().__init__(root, use_internal_lock=False)
        self.writes = 0

    def write_note(self, path, markdown):
        self.writes += 1
        super().write_note(path, markdown)


class CoreAuditTests(unittest.TestCase):
    def test_complete_checkpoint_retry_still_resolves_exact_asset_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mirror = SQLiteAssetMirror(root / "assets.sqlite3")
            disk = DiskRest(root)
            journal = MirrorGapJournal(root / "audit" / ".mirror-gap.jsonl")
            writer = RestFirstAssetWriter(disk, mirror=mirror, mirror_gap_journal=journal,
                collision_checker=CollisionChecker(mirror, VaultFilesystemCollisionProbe(root)))
            with patch.object(mirror, "upsert_asset", side_effect=OSError("synthetic mirror failure")):
                first = writer.write(normal_draft())
            self.assertEqual(first.mirror_status, "gap_recorded")
            original_note = (root / first.path).read_bytes()
            journal.append_gap(asset_id="unrelated", vault_path="unrelated.md", fail_reason="synthetic unrelated gap")
            with patch.object(journal, "resolve_asset_gaps", side_effect=OSError("synthetic resolution failure")):
                with self.assertRaises(OSError):
                    writer.write(normal_draft())
            self.assertEqual(writer.write(normal_draft()).mirror_status, "reused")
            self.assertEqual((root / first.path).read_bytes(), original_note)
            self.assertEqual(disk.writes, 1)
            self.assertEqual([row["asset_id"] for row in journal.read_gaps() if not row.get("resolved_at")], ["unrelated"])

    def test_first_ingest_initializes_mirror_only_on_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            runtime = build_runtime(env={
                "AGENT_ASSET_VAULT_PATH": str(root),
                "OBSIDIAN_REST_API_KEY": "synthetic",
                "AGENT10_HARDWARE_ANALYSIS_ENABLED": "0",
            })
            runtime.writer.rest_client = DiskRest(root)
            runtime.governance_service.snapshot()
            self.assertFalse(root.exists())
            result = runtime.producer_service.ingest_draft(normal_draft())
            self.assertEqual(result["mirror_status"], "upserted")
            self.assertEqual(runtime.mirror.count_assets(), 1)

    def test_retry_after_mirror_failure_and_restart_does_not_rewrite_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "indexes").mkdir()
            mirror = SQLiteAssetMirror(root / "indexes" / "assets.sqlite3")
            disk = DiskRest(root)
            journal_path = root / "audit" / ".mirror-gap.jsonl"

            def writer():
                return RestFirstAssetWriter(
                    disk, mirror=mirror,
                    mirror_gap_journal=MirrorGapJournal(journal_path),
                    collision_checker=CollisionChecker(mirror, VaultFilesystemCollisionProbe(root)),
                )

            with patch.object(mirror, "upsert_asset", side_effect=RuntimeError("synthetic mirror failure")):
                first = writer().write(normal_draft())
            original = (root / first.path).read_bytes()
            second = writer().write(dict(normal_draft(), title="Should not update original"))
            self.assertEqual(second.asset_id, first.asset_id)
            self.assertEqual(second.mode, "idempotent_reuse")
            self.assertEqual(disk.writes, 1)
            self.assertEqual((root / first.path).read_bytes(), original)
            self.assertEqual(mirror.count_assets(), 1)
            self.assertEqual(mirror.get_asset(first.asset_id)["title"], "PKA Answer Smoke")
            self.assertTrue(all(row.get("resolved_at") for row in MirrorGapJournal(journal_path).read_gaps()))

    def test_crash_after_primary_write_recovers_the_same_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "indexes").mkdir()
            mirror = SQLiteAssetMirror(root / "indexes" / "assets.sqlite3")
            disk = DiskRest(root)
            journal = MirrorGapJournal(root / "audit" / ".mirror-gap.jsonl")
            writer = RestFirstAssetWriter(disk, mirror=mirror, mirror_gap_journal=journal,
                collision_checker=CollisionChecker(mirror, VaultFilesystemCollisionProbe(root)))
            with patch.object(writer, "_upsert_mirror", side_effect=SystemExit("simulated crash")):
                with self.assertRaises(SystemExit):
                    writer.write(normal_draft())
            restarted = RestFirstAssetWriter(disk, mirror=mirror,
                mirror_gap_journal=MirrorGapJournal(journal.journal_path),
                collision_checker=CollisionChecker(mirror, VaultFilesystemCollisionProbe(root)))
            result = restarted.write(normal_draft())
            self.assertEqual(result.mode, "idempotent_reuse")
            self.assertEqual(disk.writes, 1)
            self.assertEqual(mirror.count_assets(), 1)

    def test_lost_query_mirror_is_repaired_without_rewriting_primary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mirror = SQLiteAssetMirror(root / "indexes" / "assets.sqlite3")
            disk = DiskRest(root)
            writer = RestFirstAssetWriter(disk, mirror=mirror,
                mirror_gap_journal=MirrorGapJournal(root / "audit" / ".mirror-gap.jsonl"),
                collision_checker=CollisionChecker(mirror, VaultFilesystemCollisionProbe(root)))
            first = writer.write(normal_draft())
            mirror.db_path.unlink()
            result = writer.write(normal_draft())
            self.assertEqual(result.asset_id, first.asset_id)
            self.assertEqual(disk.writes, 1)
            self.assertEqual(mirror.count_assets(), 1)

    def test_intent_survives_crash_before_success_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mirror = SQLiteAssetMirror(root / "indexes" / "assets.sqlite3")
            disk = DiskRest(root)
            journal = MirrorGapJournal(root / "audit" / ".mirror-gap.jsonl")
            writer = RestFirstAssetWriter(disk, mirror=mirror, mirror_gap_journal=journal,
                collision_checker=CollisionChecker(mirror, VaultFilesystemCollisionProbe(root)))
            save = journal.save_operation
            def crash_on_primary(record):
                if record["state"] == "primary_written":
                    raise SystemExit("simulated checkpoint crash")
                save(record)
            with patch.object(journal, "save_operation", side_effect=crash_on_primary):
                with self.assertRaises(SystemExit):
                    writer.write(normal_draft())
            result = writer.write(normal_draft())
            self.assertEqual(result.mode, "idempotent_reuse")
            self.assertEqual(disk.writes, 1)
            self.assertEqual(mirror.count_assets(), 1)

    def test_torn_checkpoint_recovers_single_primary_and_allows_future_writes(self):
        for tail in (b'{"idempotent_key":', b'{"title":"\xe4\xb8'):
            with self.subTest(tail=tail), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                mirror = SQLiteAssetMirror(root / "indexes" / "assets.sqlite3")
                disk = DiskRest(root)
                journal = MirrorGapJournal(root / "audit" / ".mirror-gap.jsonl")
                lock_path = root / "audit" / ".asset-writer.lock"

                def writer(current_journal):
                    return RestFirstAssetWriter(disk, mirror=mirror,
                        mirror_gap_journal=current_journal,
                        collision_checker=CollisionChecker(mirror, VaultFilesystemCollisionProbe(root)),
                        operation_lock_factory=lambda operation_id: VaultWriteLock(lock_path, operation_id))

                completed_draft = dict(normal_draft(), source_asset_path="/tmp/completed")
                completed = writer(journal).write(completed_draft)
                completed_key = mirror.get_asset(completed.asset_id)["idempotent_key"]
                draft = normal_draft()
                checkpoint = {}
                save = journal.save_operation

                def tear_primary_checkpoint(record):
                    if record["state"] != "primary_written":
                        return save(record)
                    checkpoint.update(record)
                    checkpoint["prefix"] = journal.operations_path.read_bytes()
                    with journal.operations_path.open("ab") as handle:
                        handle.write(tail)
                    raise SystemExit("simulated interrupted checkpoint append")

                with patch.object(journal, "save_operation", side_effect=tear_primary_checkpoint):
                    with self.assertRaises(SystemExit):
                        writer(journal).write(draft)
                original_note = (root / checkpoint["vault_path"]).read_bytes()
                torn_log = journal.operations_path.read_bytes()
                restarted_journal = MirrorGapJournal(journal.journal_path)
                self.assertEqual(restarted_journal.get_operation(completed_key)["state"], "complete")
                self.assertIsNone(restarted_journal.get_operation("unrelated-key"))
                self.assertEqual(journal.operations_path.read_bytes(), torn_log)

                restarted = writer(restarted_journal)
                result = restarted.write(draft)
                self.assertEqual(result.asset_id, checkpoint["asset_id"])
                self.assertEqual(result.path, checkpoint["vault_path"])
                self.assertEqual(result.mode, "idempotent_reuse")
                self.assertEqual(disk.writes, 2)
                self.assertEqual((root / result.path).read_bytes(), original_note)
                self.assertEqual(restarted.write(completed_draft).asset_id, completed.asset_id)
                future = restarted.write(dict(normal_draft(), source_asset_path="/tmp/future"))
                self.assertNotEqual(future.asset_id, result.asset_id)
                self.assertEqual(disk.writes, 3)
                self.assertEqual(mirror.count_assets(), 3)
                repaired_log = journal.operations_path.read_bytes()
                self.assertTrue(repaired_log.startswith(checkpoint["prefix"]))
                self.assertTrue(repaired_log.endswith(b"\n"))
                for line in repaired_log.splitlines():
                    self.assertIsInstance(json.loads(line.decode("utf-8")), dict)
                self.assertEqual(restarted_journal.get_operation(checkpoint["idempotent_key"])["state"], "complete")
                self.assertEqual(restarted_journal.get_operation(completed_key)["asset_id"], completed.asset_id)
                self.assertEqual(stat.S_IMODE(journal.operations_path.stat().st_mode), 0o600)

    def test_committed_journal_corruption_fails_closed_without_repair(self):
        valid = b'{"idempotent_key":"saved","state":"complete"}\n'
        for corrupt, error in ((b'{"idempotent_key":\n', json.JSONDecodeError),
                               (b'{"title":"\xe4\xb8\n', UnicodeDecodeError)):
            for suffix in (b"", valid, b'{"unfinished":'):
                with self.subTest(corrupt=corrupt, suffix=suffix), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    journal = MirrorGapJournal(root / ".mirror-gap.jsonl")
                    original = valid + corrupt + suffix
                    journal.operations_path.write_bytes(original)
                    with self.assertRaises(error):
                        journal.get_operation("saved")
                    with VaultWriteLock(root / ".asset-writer.lock", "synthetic"):
                        with self.assertRaises(error):
                            journal.save_operation({"idempotent_key": "new", "state": "intended"})
                    self.assertEqual(journal.operations_path.read_bytes(), original)

    def test_crlf_primary_recovers_after_crash_before_success_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mirror = SQLiteAssetMirror(root / "indexes" / "assets.sqlite3")
            disk = DiskRest(root)
            journal = MirrorGapJournal(root / "audit" / ".mirror-gap.jsonl")
            draft = dict(normal_draft(), body_markdown="synthetic line one\r\nsynthetic line two\r\n")
            writer = RestFirstAssetWriter(disk, mirror=mirror, mirror_gap_journal=journal,
                collision_checker=CollisionChecker(mirror, VaultFilesystemCollisionProbe(root)))
            save = journal.save_operation

            def crash_on_primary(record):
                if record["state"] == "primary_written":
                    raise SystemExit("simulated checkpoint crash")
                save(record)

            with patch.object(journal, "save_operation", side_effect=crash_on_primary):
                with self.assertRaises(SystemExit):
                    writer.write(draft)
            intent = json.loads(journal.operations_path.read_bytes().splitlines()[0])
            original = (root / intent["vault_path"]).read_bytes()
            self.assertIn(b"synthetic line one\r\nsynthetic line two\r\n", original)
            restarted = RestFirstAssetWriter(disk, mirror=mirror,
                mirror_gap_journal=MirrorGapJournal(journal.journal_path),
                collision_checker=CollisionChecker(mirror, VaultFilesystemCollisionProbe(root)))
            result = restarted.write(draft)
            self.assertEqual(result.asset_id, intent["asset_id"])
            self.assertEqual(result.path, intent["vault_path"])
            self.assertEqual(result.mode, "idempotent_reuse")
            self.assertEqual(disk.writes, 1)
            self.assertEqual((root / result.path).read_bytes(), original)
            self.assertEqual(len(list((root / "01_Agents").rglob("*.md"))), 1)
            self.assertEqual(mirror.count_assets(), 1)

    def test_fallback_preserves_owner_only_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "private.md"
            target.write_text("synthetic")
            target.chmod(0o600)
            DirectFilesystemFallbackWriter(root).write_note("private.md", "replacement")
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
            DirectFilesystemFallbackWriter(root).write_note("new.md", "new")
            self.assertEqual(stat.S_IMODE((root / "new.md").stat().st_mode), 0o600)

    def test_recovery_confines_untrusted_operation_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = root / "99_System" / "audit"
            audit.mkdir(parents=True)
            outside = root / "99_System" / "outside.json"
            outside.write_text("unchanged")
            (audit / "stale-lock-x").mkdir()
            (audit / ".asset-writer.lock").write_text(json.dumps({"pid": -1, "operation_id": "x/../../outside"}))
            recover_writer_state(root, pid_exists=lambda _pid: False)
            self.assertEqual(outside.read_text(), "unchanged")
            events = list(audit.glob("stale-lock-*.json"))
            self.assertEqual(len(events), 1)
            self.assertEqual(json.loads(events[0].read_text())["operation_id"], "x/../../outside")
            self.assertEqual(stat.S_IMODE(events[0].stat().st_mode), 0o600)

    def test_recovery_does_not_truncate_a_physically_held_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "99_System" / "audit" / ".asset-writer.lock"
            with VaultWriteLock(path, operation_id="active"):
                before = path.read_bytes()
                recover_writer_state(root, pid_exists=lambda _pid: False)
                self.assertEqual(path.read_bytes(), before)
                self.assertEqual(list(path.parent.glob("stale-lock-*.json")), [])

    def test_producer_rejects_non_object_json(self):
        service = ProducerApiService(RestFirstAssetWriter(FakeRestClient()))
        for value in ([], None, 42):
            with self.subTest(value=value):
                status, _headers, _body = producer_response("POST", "/api/asset-library/drafts", json.dumps(value), service)
                self.assertEqual(status, 400)

    def test_http_rejects_non_utf8_without_dispatching(self):
        app = Agent10HttpApp(FakeRuntime(), "synthetic")
        status, _headers, _body = app.dispatch("POST", "/api/agent10/drafts",
            {"authorization": "Bearer synthetic"}, b"\xff", "127.0.0.1")
        self.assertEqual(status, 400)

    def test_codex_cannot_bypass_audit_only_capture_contract(self):
        service = ProducerApiService(RestFirstAssetWriter(FakeRestClient()))
        base = dict(normal_draft(), agent_id="codex", workflow_id="development-capture",
                    asset_type="codex-development-summary", sensitivity="audit_only")
        for changes in ({"sensitivity": "normal"}, {"knowledge_status": "indexed"},
                        {"workflow_id": "anything"}, {"asset_type": "anything"}):
            with self.subTest(changes=changes):
                status, _headers, _body = producer_response("POST", "/api/asset-library/drafts", json.dumps({**base, **changes}), service)
                self.assertEqual(status, 400)

    def test_codex_rejects_array_and_object_scope_fields_before_writer(self):
        writer = RestFirstAssetWriter(FakeRestClient())
        service = ProducerApiService(writer)
        base = dict(normal_draft(), agent_id="codex", workflow_id="development-capture",
                    asset_type="codex-development-summary", sensitivity="audit_only")
        with patch.object(writer, "write", side_effect=AssertionError("invalid scope reached writer")):
            for field in ("agent_id", "workflow_id", "asset_type", "sensitivity", "knowledge_status"):
                for value in ([], {"private": "synthetic-private-marker"}):
                    with self.subTest(field=field, value=value):
                        status, _headers, body = producer_response("POST", "/api/asset-library/drafts",
                            json.dumps({**base, field: value}), service)
                        self.assertEqual(status, 400)
                        self.assertEqual(json.loads(body)["error"], "bad_request")
                        self.assertNotIn("synthetic-private-marker", body)

    def test_http_checks_authentication_and_length_before_body_read(self):
        server = create_http_server(FakeRuntime(), "synthetic", port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            cases = (
                ("", "100", 403),
                ("Authorization: Bearer synthetic\r\n", "20971521", 413),
                ("Authorization: Bearer synthetic\r\n", "-1", 400),
            )
            for auth, length, want in cases:
                with self.subTest(want=want), socket.create_connection(server.server_address, timeout=1) as connection:
                    connection.sendall(("POST /api/agent10/drafts HTTP/1.1\r\nHost: localhost\r\n" + auth + "Content-Length: " + length + "\r\n\r\n").encode())
                    response = connection.recv(4096)
                    self.assertEqual(int(response.split(b" ")[1]), want)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_http_has_a_total_body_deadline_even_when_bytes_keep_arriving(self):
        with patch("asset_library.http_server.REQUEST_TIMEOUT_SECONDS", 0.2):
            server = create_http_server(FakeRuntime(), "synthetic", port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with socket.create_connection(server.server_address, timeout=0.8) as connection:
                    connection.sendall(b"POST /api/agent10/drafts HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer synthetic\r\nContent-Length: 100\r\n\r\n")
                    def drip():
                        for _ in range(15):
                            try:
                                connection.sendall(b"x")
                            except OSError:
                                return
                            time.sleep(0.03)
                    sender = threading.Thread(target=drip, daemon=True)
                    started = time.monotonic()
                    sender.start()
                    response = connection.recv(4096)
                    self.assertEqual(int(response.split(b" ")[1]), 408)
                    self.assertLess(time.monotonic() - started, 0.4)
                sender.join(timeout=1)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
