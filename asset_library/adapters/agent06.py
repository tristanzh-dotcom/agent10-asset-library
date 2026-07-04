import json
from pathlib import Path


def discover_agent06_answers(pka_data_root):
    root = Path(pka_data_root)
    answers_root = root / "assets" / "answers"
    if not answers_root.exists():
        return []
    return sorted(
        path.parent
        for path in answers_root.rglob("manifest.json")
        if (path.parent / "answer.md").exists()
    )


def agent06_answer_to_draft(asset_dir):
    asset_dir = Path(asset_dir)
    manifest = json.loads((asset_dir / "manifest.json").read_text(encoding="utf-8"))
    body = (asset_dir / "answer.md").read_text(encoding="utf-8")
    source_refs = _source_refs(manifest.get("sources", []))
    tags = _tags(manifest.get("tags", []))
    return {
        "agent_id": "agent06",
        "workflow_id": "ask",
        "asset_type": "agent06_pka_answer",
        "title": manifest.get("title") or manifest.get("question") or asset_dir.name,
        "status": "active",
        "knowledge_status": _knowledge_status(manifest.get("rag_status")),
        "source_status": manifest.get("source_status", "unverified"),
        "sensitivity": "normal",
        "created_at": manifest.get("created_at", ""),
        "updated_at": manifest.get("updated_at", manifest.get("created_at", "")),
        "source_asset_path": str(asset_dir),
        "source_refs": source_refs,
        "input_refs": [{"type": "question", "text": manifest.get("question", "")}]
        if manifest.get("question")
        else [],
        "file_refs": [
            {
                "role": "primary_markdown",
                "path": str(asset_dir / "answer.md"),
                "media_type": "text/markdown",
            },
            {
                "role": "agent06_manifest",
                "path": str(asset_dir / "manifest.json"),
                "media_type": "application/json",
            },
        ],
        "export_refs": manifest.get("exports", []),
        "model_route": manifest.get("model_route", ""),
        "subject_refs": [],
        "collection_refs": [],
        "tags": tags,
        "body_markdown": body,
    }


def _knowledge_status(rag_status):
    if rag_status == "indexed":
        return "indexed"
    if rag_status == "promotion_failed":
        return "promotion_failed"
    return "not_indexed"


def _source_refs(sources):
    refs = []
    for source in sources:
        refs.append(
            {
                "chunk_id": source.get("chunk_id", ""),
                "source_name": source.get("source_name", ""),
                "source_type": source.get("source_type", ""),
                "raw_file_path": source.get("raw_file_path", ""),
                "relevance": source.get("relevance"),
            }
        )
    return refs


def _tags(existing):
    tags = ["agent/agent06", "workflow/ask", "type/pka-answer", "knowledge/not-indexed"]
    for tag in existing:
        if tag not in tags:
            tags.append(tag)
    return tags
