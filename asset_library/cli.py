import json
from pathlib import Path

from .schema import validate_draft


def run_cli(argv, service):
    if not argv:
        return 1, _usage()
    command = argv[0]
    try:
        if command == "validate-draft":
            draft = _read_json_arg(argv, 1)
            errors = validate_draft(draft)
            if errors:
                return 1, "\n".join(errors)
            return 0, "OK"
        if command == "ingest-draft":
            result = service.ingest_draft(_read_json_arg(argv, 1))
            return 0, json.dumps(result, ensure_ascii=False, sort_keys=True)
        if command == "ingest-agent06":
            if len(argv) < 2:
                return 1, "source_asset_path is required"
            result = service.ingest_producer_asset("agent06", {"source_asset_path": argv[1]})
            return 0, json.dumps(result, ensure_ascii=False, sort_keys=True)
    except Exception as exc:
        return 1, str(exc)
    return 1, _usage()


def _read_json_arg(argv, index):
    if len(argv) <= index:
        raise ValueError("json path is required")
    return json.loads(Path(argv[index]).read_text(encoding="utf-8"))


def _usage():
    return "usage: validate-draft <draft.json> | ingest-draft <draft.json> | ingest-agent06 <source_asset_path>"
