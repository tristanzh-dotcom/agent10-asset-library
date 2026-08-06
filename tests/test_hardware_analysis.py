import tempfile
import unittest
from pathlib import Path

from asset_library.hardware_analysis import (
    MAX_REFERENCE_CHARS,
    AnalysisEngine,
    HardwareCandidateAnalyzer,
    compare_candidates,
    unavailable_analysis,
)


class _Store:
    def __init__(self, draft):
        self.draft = draft
        self.jobs = {}

    def get_draft(self, draft_id):
        return dict(self.draft) if draft_id == self.draft["draft_id"] else None

    def get_analysis_job_by_operation(self, operation_key):
        return next((dict(job) for job in self.jobs.values() if job["operation_key"] == operation_key), None)

    def save_analysis_job(self, job):
        self.jobs[job["job_id"]] = dict(job)
        return dict(job)

    def get_analysis_job(self, job_id):
        job = self.jobs.get(job_id)
        return dict(job) if job else None


class _Analyzer:
    def __init__(self):
        self.calls = []

    def analyze(self, images, reference_text, receipt_context):
        self.calls.append((images, reference_text, receipt_context))
        return {
            "candidates": [
                {"field": "length_mm", "value": 90, "origin": "reference"},
                {"field": "length_mm", "value": 100, "origin": "image"},
            ],
            "receipt": {"route_key": "hardware_reference_analysis", "status": "completed"},
        }


class _Transport:
    def __init__(self):
        self.payload = None

    def call(self, payload):
        self.payload = payload
        return {"candidates": [{"field": "display_name", "value": "Demo board", "origin": "reference"}]}


class HardwareAnalysisTests(unittest.TestCase):
    def test_image_dimension_is_not_measured_fact(self):
        rows = compare_candidates({}, None, [{"field": "length_mm", "value": 200, "origin": "image"}])
        self.assertEqual(rows[0]["evidence_level"], "label_or_photo")

    def test_conflicting_sources_are_explicit_and_remain_candidates(self):
        rows = compare_candidates(
            {},
            {"status": "fetched", "body": "90 mm"},
            [
                {"field": "length_mm", "value": 90, "origin": "reference"},
                {"field": "length_mm", "value": 100, "origin": "image"},
            ],
        )
        self.assertEqual({row["comparison"] for row in rows}, {"conflict"})
        self.assertTrue(all(row["authority"] == "candidate" for row in rows))

    def test_engine_marks_unconfigured_route_unavailable_and_is_idempotent(self):
        store = _Store({"draft_id": "hwd_demo", "revision": 3, "reference": {"status": "fetched"}})
        engine = AnalysisEngine(store, attachment_root=tempfile.mkdtemp())

        first = engine.start("hwd_demo", "op-demo")
        second = engine.start("hwd_demo", "op-demo")

        self.assertEqual(first["status"], "unavailable")
        self.assertEqual(first["job_id"], second["job_id"])
        self.assertEqual(first["reference_status"], "analysis_unavailable")

    def test_engine_uses_registered_analyzer_and_retains_structured_receipt(self):
        analyzer = _Analyzer()
        store = _Store({
            "draft_id": "hwd_demo",
            "revision": 3,
            "reference": {"status": "fetched", "body": "bounded reference"},
            "attachments": [],
        })
        engine = AnalysisEngine(store, analyzer=analyzer, attachment_root=Path(tempfile.mkdtemp()))

        job = engine.start("hwd_demo", "op-registered")

        self.assertEqual(job["status"], "completed")
        self.assertEqual(job["candidates"][0]["comparison"], "conflict")
        self.assertEqual(job["receipt"]["route_key"], "hardware_reference_analysis")
        self.assertEqual(len(analyzer.calls), 1)

    def test_registered_adapter_bounds_inputs_and_records_route_receipt(self):
        transport = _Transport()
        analyzer = HardwareCandidateAnalyzer(transport)

        result = analyzer.analyze(
            [{"content_type": "image/jpeg", "bytes": b"jpeg-bytes", "sha256": "sha256:" + "a" * 64}],
            "x" * (MAX_REFERENCE_CHARS + 100),
            {"draft_id": "hwd_demo", "draft_revision": 2, "operation_key": "op-route"},
        )

        self.assertEqual(transport.payload["metadata"]["route_key"], "hardware_reference_analysis")
        self.assertLessEqual(len(transport.payload["input"][0]["content"][1]["text"]), MAX_REFERENCE_CHARS + 20)
        self.assertEqual(result["receipt"]["status"], "completed")

    def test_unconfigured_analysis_fails_closed(self):
        self.assertEqual(unavailable_analysis("hwd_demo")["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
