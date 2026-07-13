import json
import shutil
from dataclasses import dataclass
from pathlib import Path


BOOTSTRAP_DIRECTORIES = (
    "00_Inbox",
    "01_Agents/Agent01",
    "01_Agents/Agent02",
    "01_Agents/Agent03",
    "01_Agents/Agent04",
    "01_Agents/Agent06",
    "01_Agents/Agent07",
    "01_Agents/Agent08",
    "01_Agents/Agent09",
    "01_Agents/Agent10",
    "02_Workflows",
    "03_Subjects",
    "04_Collections",
    "05_Exports",
    "90_Attachments",
    "95_Ledgers",
    "99_System/audit",
    "99_System/indexes",
    "99_System/schemas",
    "99_System/templates",
)


@dataclass(frozen=True)
class BootstrapResult:
    vault_path: Path
    actions: tuple


def bootstrap_vault(vault_path, plugin_source=None):
    vault_path = Path(vault_path)
    actions = []
    vault_path.mkdir(parents=True, exist_ok=True)
    actions.append("created")
    for directory in BOOTSTRAP_DIRECTORIES:
        (vault_path / directory).mkdir(parents=True, exist_ok=True)
    _write_once(vault_path / ".gitignore", _gitignore_text())
    _write_once(vault_path / "99_System" / "schemas" / "asset_schema_v1.md", _schema_text())
    _write_once(vault_path / "99_System" / "templates" / "asset_note_template.md", _template_text())
    _write_once(vault_path / "99_System" / "indexes" / "asset_library_home.md", _home_text())
    _write_obsidian_config(vault_path)
    if plugin_source is not None:
        _copy_local_rest_plugin(Path(plugin_source), vault_path)
        actions.append("plugin_copied")
    return BootstrapResult(vault_path=vault_path, actions=tuple(actions))


def _write_once(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def _write_obsidian_config(vault_path):
    obsidian = vault_path / ".obsidian"
    obsidian.mkdir(parents=True, exist_ok=True)
    _write_once(obsidian / "app.json", "{\n  \"newFileLocation\": \"folder\",\n  \"newFileFolderPath\": \"00_Inbox\"\n}\n")
    _write_once(obsidian / "core-plugins.json", json.dumps(["file-explorer", "global-search", "backlink", "tag-pane", "properties", "templates"], indent=2) + "\n")


def _copy_local_rest_plugin(plugin_source, vault_path):
    target = vault_path / ".obsidian" / "plugins" / "obsidian-local-rest-api"
    target.mkdir(parents=True, exist_ok=True)
    for filename in ("main.js", "manifest.json", "styles.css"):
        source = plugin_source / filename
        if source.exists():
            shutil.copy2(source, target / filename)
    (vault_path / ".obsidian" / "community-plugins.json").write_text(
        '[\n  "obsidian-local-rest-api"\n]\n',
        encoding="utf-8",
    )


def _gitignore_text():
    return """\
.DS_Store
.obsidian/workspace.json
.obsidian/workspace-mobile.json
.obsidian/plugins/obsidian-local-rest-api/data.json
99_System/audit/.agent10-control.token
90_Attachments/**
*.tmp
*.log
"""


def _schema_text():
    return """\
# Asset Schema v1

Required fields:

- asset_id
- asset_schema_version
- title
- agent_id
- workflow_id
- asset_type
- status
- knowledge_status
- source_status
- sensitivity
- source_content_hash
- created_at
- updated_at
- source_asset_path

This file is the human-readable schema reference. The executable validator lives in Agent10.
"""


def _template_text():
    return """\
---
asset_id: ""
asset_schema_version: 1
title: ""
agent_id: ""
workflow_id: ""
asset_type: ""
status: active
knowledge_status: not_indexed
source_status: unverified
sensitivity: normal
source_content_hash: ""
hash_source: ""
created_at: ""
updated_at: ""
source_asset_path: ""
source_refs: []
input_refs: []
file_refs: []
export_refs: []
model_route: ""
subject_refs: []
collection_refs: []
tags: []
---

# {{title}}
"""


def _home_text():
    return """\
# Agent Asset Library

This Vault is managed by Agent10.

Use Obsidian for reading, editing, links, tags, search, templates, migration, and manual organization.

Use Agent10 governance UI/API for producer status, writer health, mirror gaps, promotion journal, schema drift, and retries.
"""
