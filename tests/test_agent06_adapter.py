import json
import tempfile
import unittest
from pathlib import Path

from asset_library.adapters.agent06 import agent06_answer_to_draft, discover_agent06_answers


class Agent06AdapterTests(unittest.TestCase):
    def test_agent06_answer_to_draft_maps_v0_manifest_to_unified_draft(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            asset_dir = Path(tmpdir) / "ans_20260703204333_87b29e"
            asset_dir.mkdir()
            (asset_dir / "answer.md").write_text("# marcus\n\nbody", encoding="utf-8")
            (asset_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "asset_id": "ans_20260703204333_87b29e",
                        "asset_type": "answer_result",
                        "title": "marcus",
                        "question": "marcus",
                        "source_status": "grounded",
                        "rag_status": "not_indexed",
                        "model_route": "deepseek",
                        "created_at": "2026-07-03T20:43:33.561774",
                        "updated_at": "2026-07-03T20:43:33.561774",
                        "tags": ["strategy"],
                        "sources": [
                            {
                                "chunk_id": "Offer.md#13",
                                "source_name": "Offer.md",
                                "raw_file_path": "raw/Offer.md",
                            }
                        ],
                        "exports": [{"path": "exports/answer.docx"}],
                    }
                ),
                encoding="utf-8",
            )

            draft = agent06_answer_to_draft(asset_dir)

            self.assertNotIn("asset_id", draft)
            self.assertEqual(draft["agent_id"], "agent06")
            self.assertEqual(draft["workflow_id"], "ask")
            self.assertEqual(draft["asset_type"], "agent06_pka_answer")
            self.assertEqual(draft["title"], "marcus")
            self.assertEqual(draft["body_markdown"], "# marcus\n\nbody")
            self.assertEqual(draft["knowledge_status"], "not_indexed")
            self.assertEqual(draft["source_status"], "grounded")
            self.assertEqual(draft["model_route"], "deepseek")
            self.assertEqual(draft["source_asset_path"], str(asset_dir))
            self.assertEqual(draft["source_refs"][0]["chunk_id"], "Offer.md#13")
            self.assertEqual(draft["file_refs"][0]["path"], str(asset_dir / "answer.md"))
            self.assertEqual(draft["export_refs"][0]["path"], "exports/answer.docx")
            self.assertIn("agent/agent06", draft["tags"])
            self.assertIn("workflow/ask", draft["tags"])
            self.assertIn("type/pka-answer", draft["tags"])
            self.assertIn("strategy", draft["tags"])

    def test_discover_agent06_answers_finds_answer_asset_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            asset_dir = root / "assets" / "answers" / "2026-07-03" / "ans_a"
            asset_dir.mkdir(parents=True)
            (asset_dir / "answer.md").write_text("body", encoding="utf-8")
            (asset_dir / "manifest.json").write_text("{}", encoding="utf-8")
            incomplete = root / "assets" / "answers" / "2026-07-03" / "ans_b"
            incomplete.mkdir()
            (incomplete / "answer.md").write_text("body", encoding="utf-8")

            self.assertEqual(discover_agent06_answers(root), [asset_dir])


if __name__ == "__main__":
    unittest.main()
