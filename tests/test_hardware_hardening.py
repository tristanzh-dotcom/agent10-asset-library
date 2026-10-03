import collections
import tempfile
import threading
import unittest
import io
from unittest.mock import patch
from urllib.error import HTTPError
from pathlib import Path

from asset_library.hardware_indexes import HardwareIndexPublisher, INDEX_PATHS
from asset_library.hardware_notes import HardwareNotePublisher, hardware_note_path
from asset_library.hardware_service import HardwareService
from asset_library.hardware_store import HardwareStore
from asset_library.locking import VaultWriteLock
from asset_library.filesystem_fallback import DirectFilesystemFallbackWriter
from asset_library.obsidian_rest import ObsidianRestClient
from tests.test_hardware_schema import valid_model


class MemoryNotes:
    def __init__(self):
        self.notes = {}
        self.writes = collections.Counter()
        self.fail_path = None

    def write_note(self, path, markdown):
        if path == self.fail_path:
            raise ConnectionError("synthetic unavailable")
        self.notes[path] = markdown
        self.writes[path] += 1

    def read_note(self, path):
        return self.notes.get(path)


class HardwareHardeningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = HardwareStore(self.root / "hardware.sqlite3")
        self.rest = MemoryNotes()
        self.lock_factory = lambda operation: VaultWriteLock(self.root / "writer.lock", operation_id=operation, timeout_seconds=3)
        self.service = self.build_service()

    def build_service(self):
        indexes = HardwareIndexPublisher(self.rest, None, self.lock_factory)
        publisher = HardwareNotePublisher(self.rest, None, self.store, self.lock_factory, indexes)
        return HardwareService(self.store, publisher, clock=lambda: "2026-10-03T01:00:00+00:00")

    def submit(self, operation="one", record=None):
        return self.service.submit({"channel": "web", "submitted_by": "TZ", "operation_key": operation, "draft": record or valid_model()})

    def accept(self, submitted):
        return self.service.accept(submitted["intake_id"], "TZ", submitted["snapshot_hash"])

    def _assert_stale_same_record_retry_is_rejected(self, changed_path=False, newer_mirror_failure=False, older_index_failure=False):
        old_record = dict(valid_model(), manufacturer="Synthetic Old")
        old = self.submit("old-operation", old_record)
        if older_index_failure:
            self.rest.fail_path = INDEX_PATHS[0]
            self.assertEqual(self.accept(old)["status"], "partial")
            self.rest.fail_path = None
        else:
            with patch.object(self.store, "upsert_record", side_effect=OSError("synthetic old mirror failure")):
                self.assertEqual(self.accept(old)["status"], "partial")
        newer_record = dict(valid_model(), manufacturer="Synthetic New", display_name="Synthetic New board")
        if changed_path:
            newer_record["canonical_name"] = "Synthetic New canonical name"
            self.assertNotEqual(hardware_note_path(old_record), hardware_note_path(newer_record))
        newer = self.submit("newer-operation", newer_record)
        if newer_mirror_failure:
            with patch.object(self.store, "upsert_record", side_effect=OSError("synthetic newer mirror failure")):
                self.assertEqual(self.accept(newer)["status"], "partial")
        else:
            self.assertEqual(self.accept(newer)["status"], "published")
        before_notes = dict(self.rest.notes)
        before_writes = self.rest.writes.copy()
        before_mirror = self.store.get_record(old_record["hardware_model_id"])
        self.assertIn("Synthetic New", before_notes[hardware_note_path(newer_record)])
        if not newer_mirror_failure:
            self.assertEqual(before_mirror["acceptance"]["snapshot_hash"], newer["snapshot_hash"])
            self.assertIn("Synthetic New board", before_notes[INDEX_PATHS[0]])
        with self.assertRaises(ValueError):
            self.accept(old)
        self.assertEqual(self.rest.notes, before_notes)
        self.assertEqual(self.rest.writes, before_writes)
        self.assertEqual(self.store.get_record(old_record["hardware_model_id"]), before_mirror)
        self.assertNotEqual(self.store.get_intake(old["intake_id"])["intake_status"], "published")

    def test_older_same_path_retry_cannot_downgrade_newer_publication(self):
        self._assert_stale_same_record_retry_is_rejected()

    def test_older_changed_path_retry_cannot_downgrade_newer_publication(self):
        self._assert_stale_same_record_retry_is_rejected(changed_path=True)

    def test_older_retry_cannot_downgrade_newer_primary_with_failed_mirror(self):
        self._assert_stale_same_record_retry_is_rejected(newer_mirror_failure=True)

    def test_older_retry_cannot_downgrade_changed_path_primary_with_failed_mirror(self):
        self._assert_stale_same_record_retry_is_rejected(changed_path=True, newer_mirror_failure=True)

    def test_older_partial_projection_cannot_claim_success_after_same_record_replacement(self):
        self._assert_stale_same_record_retry_is_rejected(changed_path=True, older_index_failure=True)

    def test_legitimate_update_can_resume_mirror_failure_after_prior_record(self):
        prior_record = dict(valid_model(), manufacturer="Synthetic Prior")
        self.assertEqual(self.accept(self.submit("prior-operation", prior_record))["status"], "published")
        update_record = dict(valid_model(), manufacturer="Synthetic Update", display_name="Synthetic Update board")
        update = self.submit("update-operation", update_record)
        with patch.object(self.store, "upsert_record", side_effect=OSError("synthetic update mirror failure")):
            self.assertEqual(self.accept(update)["status"], "partial")
        note_path = hardware_note_path(update_record)
        successful_primary = self.rest.notes[note_path]
        write_count = self.rest.writes[note_path]
        self.assertEqual(self.accept(update)["status"], "published")
        self.assertEqual(self.rest.notes[note_path], successful_primary)
        self.assertEqual(self.rest.writes[note_path], write_count)
        self.assertEqual(self.store.get_record(update_record["hardware_model_id"])["acceptance"]["snapshot_hash"], update["snapshot_hash"])
        self.assertIn("Synthetic Update board", self.rest.notes[INDEX_PATHS[0]])

    def test_mirror_checkpoint_retry_still_resolves_exact_hardware_gap(self):
        submitted = self.submit()
        with patch.object(self.store, "upsert_record", side_effect=OSError("synthetic mirror failure")):
            self.assertEqual(self.accept(submitted)["status"], "partial")
        path = hardware_note_path(valid_model())
        original_note = self.rest.notes[path]
        self.store.record_gap("unrelated", "unrelated.md", "synthetic unrelated gap")
        with patch.object(self.store, "resolve_gaps", side_effect=OSError("synthetic resolution failure")):
            with self.assertRaises(OSError):
                self.accept(submitted)
        self.assertEqual(self.accept(submitted)["status"], "published")
        self.assertEqual(self.rest.notes[path], original_note)
        self.assertEqual(self.rest.writes[path], 1)
        self.assertEqual(self.store.open_gap_count(), 1)

    def test_distinct_stock_drafts_preserve_both_batches_and_total(self):
        for name, quantity, action in (("first", 2, "new"), ("second", 3, "merge")):
            draft = self.service.create_draft(draft_id_factory=lambda: "hwd_" + name)
            patched = self.service.patch_draft(draft["draft_id"], 1, {"display_name": "Demo board", "quantity": quantity, "inventory_action": action, "merge_target_id": "hwm_demo-board"})
            bundle = self.service.prepare_draft(draft["draft_id"], patched["revision"])
            self.assertEqual(self.service.accept_draft(draft["draft_id"], bundle["bundle_hash"])["status"], "published")
            self.assertEqual(self.service.accept_draft(draft["draft_id"], bundle["bundle_hash"])["status"], "published")
        units = self.store.list_records(record_type="hardware_unit")
        self.assertEqual(len(units), 2)
        self.assertEqual(sum(unit["quantity_total"] for unit in units), 5)

    def test_primary_failure_retry_reuses_acceptance_and_published_receipt(self):
        submitted = self.submit()
        path = hardware_note_path(valid_model())
        self.rest.fail_path = path
        with self.assertRaises(ConnectionError):
            self.accept(submitted)
        accepted_at = self.store.get_intake(submitted["intake_id"])["acceptance"]["accepted_at"]
        self.rest.fail_path = None
        self.service = self.build_service()
        result = self.accept(submitted)
        self.assertEqual(self.accept(submitted), result)
        self.assertEqual(self.rest.writes[path], 1)
        self.assertEqual(self.store.get_intake(submitted["intake_id"])["acceptance"]["accepted_at"], accepted_at)
        with self.assertRaises(ValueError):
            self.service.accept(submitted["intake_id"], "TZ", "sha256:wrong")

    def test_real_rest_http_404_proves_pending_primary_is_missing(self):
        submitted = self.submit()
        path = hardware_note_path(valid_model())
        self.rest.fail_path = path
        with self.assertRaises(ConnectionError):
            self.accept(submitted)
        self.rest.fail_path = None
        real_reader = ObsidianRestClient("https://127.0.0.1:27124", "synthetic-token")
        real_reader.write_note = self.rest.write_note
        self.service.publisher.rest_client = real_reader
        missing = HTTPError("https://127.0.0.1:27124", 404, "Not Found", {}, io.BytesIO(b""))
        with patch("asset_library.obsidian_rest.urlopen", side_effect=missing):
            self.assertEqual(self.accept(submitted)["status"], "published")
        self.assertEqual(self.rest.writes[path], 1)

    def test_internal_publication_stages_do_not_become_public_note_or_record(self):
        submitted = self.submit()
        self.accept(submitted)
        self.assertNotIn("publication:", self.rest.notes[hardware_note_path(valid_model())])
        self.assertNotIn("publication", self.store.get_record(valid_model()["hardware_model_id"]))

    def test_crash_after_primary_before_stage_save_reconciles_readback(self):
        submitted = self.submit()
        original = self.store.update_intake
        def crash_after_primary(intake):
            if ((intake.get("publication") or {}).get("stages", {}).get("primary") or {}).get("status") == "done":
                raise OSError("synthetic crash before stage save")
            return original(intake)
        self.store.update_intake = crash_after_primary
        with self.assertRaises(OSError):
            self.accept(submitted)
        self.store.update_intake = original
        self.service = self.build_service()
        self.assertEqual(self.accept(submitted)["status"], "published")
        self.assertEqual(self.rest.writes[hardware_note_path(valid_model())], 1)

    def test_crash_after_fallback_primary_reads_local_note_before_retry(self):
        class Fallback(DirectFilesystemFallbackWriter):
            writes = 0
            def write_note(self, path, markdown):
                self.writes += 1
                return super().write_note(path, markdown)
        fallback = Fallback(self.root / "vault", use_internal_lock=False)
        self.service.publisher.fallback_writer = fallback
        record = valid_model()
        record.update(summary="line one\r\nline two", body_markdown="body one\r\nbody two")
        submitted = self.submit(record=record)
        self.rest.fail_path = hardware_note_path(valid_model())
        original = self.store.update_intake
        def crash_after_primary(intake):
            if ((intake.get("publication") or {}).get("stages", {}).get("primary") or {}).get("status") == "done":
                raise OSError("synthetic crash before fallback stage save")
            return original(intake)
        self.store.update_intake = crash_after_primary
        with self.assertRaises(OSError):
            self.accept(submitted)
        self.store.update_intake = original
        target = fallback._resolve_target(hardware_note_path(record))
        written_bytes = target.read_bytes()
        self.assertIn(b"line one\r\nline two", written_bytes)
        self.assertEqual(self.accept(submitted)["status"], "published")
        self.assertEqual(fallback.writes, 1)
        self.assertEqual(target.read_bytes(), written_bytes)

    def test_ambiguous_primary_identity_fails_closed_without_rewrite(self):
        submitted = self.submit()
        self.rest.fail_path = hardware_note_path(valid_model())
        with self.assertRaises(ConnectionError):
            self.accept(submitted)
        self.rest.fail_path = None
        self.rest.notes[hardware_note_path(valid_model())] = "unrelated content"
        with self.assertRaises(ValueError):
            self.accept(submitted)
        self.assertEqual(self.rest.writes[hardware_note_path(valid_model())], 0)

    def test_existing_accepted_record_without_stages_reconciles_instead_of_rewriting(self):
        submitted = self.submit()
        self.accept(submitted)
        legacy = self.store.get_intake(submitted["intake_id"])
        legacy["intake_status"] = "accepted"
        legacy.pop("publication")
        self.store.update_intake(legacy)
        self.assertEqual(self.accept(submitted)["status"], "published")
        self.assertEqual(self.rest.writes[hardware_note_path(valid_model())], 1)

    def test_partial_indexes_resume_only_unfinished_paths(self):
        submitted = self.submit()
        self.rest.fail_path = INDEX_PATHS[2]
        self.assertEqual(self.accept(submitted)["status"], "partial")
        self.rest.fail_path = None
        self.assertEqual(self.accept(submitted)["status"], "published")
        self.assertEqual([self.rest.writes[path] for path in INDEX_PATHS], [1, 1, 1, 1, 1, 1])

    def test_interleaved_partial_publication_refreshes_previously_completed_indexes(self):
        first = self.submit("first")
        self.rest.fail_path = INDEX_PATHS[2]
        self.assertEqual(self.accept(first)["status"], "partial")
        second_record = valid_model()
        second_record.update(hardware_model_id="hwm_second", canonical_name="Second board", display_name="Second board")
        second = self.submit("second", second_record)
        self.rest.fail_path = INDEX_PATHS[0]
        self.assertEqual(self.accept(second)["status"], "partial")
        self.rest.fail_path = None
        self.assertEqual(self.accept(first)["status"], "published")
        self.assertIn("Second board", self.rest.notes[INDEX_PATHS[0]])
        self.assertIn("Second board", self.rest.notes[INDEX_PATHS[1]])

    def test_mirror_and_index_failures_resume_without_rewriting_primary(self):
        for failure in ("mirror", "index"):
            with self.subTest(stage=failure):
                self.setUp()
                submitted = self.submit()
                path = hardware_note_path(valid_model())
                original = self.store.upsert_record
                if failure == "mirror":
                    self.store.upsert_record = lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("synthetic mirror failure"))
                else:
                    self.rest.fail_path = INDEX_PATHS[0]
                self.assertEqual(self.accept(submitted)["status"], "partial")
                self.store.upsert_record = original
                self.rest.fail_path = None
                self.service = self.build_service()
                result = self.accept(submitted)
                self.assertEqual(result["status"], "published")
                self.assertEqual(self.accept(submitted), result)
                self.assertEqual(self.rest.writes[path], 1)
                self.assertEqual(self.store.open_gap_count(), 0)

    def test_partial_bundle_resumes_failed_intake_and_rejects_wrong_hash(self):
        draft = self.service.create_draft(draft_id_factory=lambda: "hwd_bundle")
        patched = self.service.patch_draft(draft["draft_id"], 1, {"display_name": "Demo board", "quantity": 2, "inventory_action": "new"})
        bundle = self.service.prepare_draft(draft["draft_id"], patched["revision"])
        self.rest.fail_path = INDEX_PATHS[0]
        self.assertEqual(self.service.accept_draft(draft["draft_id"], bundle["bundle_hash"])["status"], "partial")
        self.rest.fail_path = None
        self.assertEqual(self.service.accept_draft(draft["draft_id"], bundle["bundle_hash"])["status"], "published")
        with self.assertRaises(ValueError):
            self.service.accept_draft(draft["draft_id"], "wrong")

    def test_concurrent_acceptance_writes_same_primary_once(self):
        submitted = self.submit()
        results = []
        errors = []
        barrier = threading.Barrier(2)
        def run():
            try:
                barrier.wait()
                results.append(self.accept(submitted))
            except Exception as exc:
                errors.append(exc)
        threads = [threading.Thread(target=run) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(5)
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)
        self.assertEqual(self.rest.writes[hardware_note_path(valid_model())], 1)

    def test_delayed_snapshot_cannot_overwrite_newer_index(self):
        first = self.submit("first")
        second_record = valid_model()
        second_record.update(hardware_model_id="hwm_second", canonical_name="Second board", display_name="Second board")
        second = self.submit("second", second_record)
        original_list = self.store.list_records
        started = threading.Event()
        completed = threading.Event()
        errors = []
        old_calls = 0
        def delayed_list(*args, **kwargs):
            nonlocal old_calls
            records = original_list(*args, **kwargs)
            if threading.current_thread().name == "old-publication":
                old_calls += 1
                if old_calls == 2:
                    started.set()
                    completed.wait(0.3)
            return records
        self.store.list_records = delayed_list
        def run(submitted, wait=False):
            try:
                if wait:
                    started.wait(2)
                self.accept(submitted)
            except Exception as exc:
                errors.append(exc)
            finally:
                if wait:
                    completed.set()
        threads = [threading.Thread(target=run, args=(first,), name="old-publication"), threading.Thread(target=run, args=(second, True), name="new-publication")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(5)
        self.assertEqual(errors, [])
        self.assertIn("Second board", self.rest.notes[INDEX_PATHS[0]])
        self.assertIn("ESP32-S3", self.rest.notes[INDEX_PATHS[0]])
