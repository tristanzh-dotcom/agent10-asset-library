# Phase 1 Asset Library Core Implementation Plan

> **Status:** Superseded before execution on 2026-07-04. TZ clarified that Phase 1 must start from Obsidian's native capabilities, plugin ecosystem, interfaces, and product boundaries before writing internal asset-library code. Do not execute this plan until it is rewritten from the Obsidian-first capability audit.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first local, deterministic core of Agent10 Asset Library: config resolution, schema validation, ID/naming/hash utilities, Vault bootstrap, SQLite mirror, and atomic note writing.

**Architecture:** Implement a small Python standard-library package under `asset_library/`. Agents submit draft dictionaries to a validator/writer; the writer resolves the Vault path, creates Obsidian-compatible Markdown notes, writes them atomically, and mirrors metadata into SQLite. Obsidian App installation and RAG ingestion remain outside this phase.

**Tech Stack:** Python 3 standard library, `unittest`/`pytest` test runner compatibility, SQLite via `sqlite3`, file locking via `fcntl` on macOS/Linux.

## Global Constraints

- No external model provider is used; this project is unregistered in `/Users/tristanzh/agent/GLOBAL_MODEL_ROUTING_RECORD.md`.
- No Obsidian download, app installation, sync setup, or real user Vault mutation in Phase 1 core tests.
- Vault default path is `/Users/tristanzh/agent/AgentAssetVault/`, overridden by `AGENT_ASSET_VAULT_PATH`, then `config.json` `vault_path`.
- Frontmatter enums must follow the frozen design document: `sensitivity`, `knowledge_status`, `source_status`, and `status`.
- Note writes must use same-directory temp files and atomic rename.
- SQLite Mirror failure must not roll back a successfully written note.
- Git write operations are not part of this plan; use Agent08 for commits if needed.

---

### Task 1: Core Schema, Config, and Naming Utilities

**Files:**
- Create: `asset_library/__init__.py`
- Create: `asset_library/config.py`
- Create: `asset_library/schema.py`
- Create: `asset_library/naming.py`
- Test: `tests/test_config_schema_naming.py`

**Interfaces:**
- Produces: `resolve_vault_path(config_path=None, env=None) -> tuple[Path, str]`
- Produces: `validate_draft(draft: dict, *, for_update=False) -> list[str]`
- Produces: `generate_asset_id(now=None, token_hex=None) -> str`
- Produces: `sanitize_short_title(title: str, asset_id: str) -> str`

- [ ] Write failing tests for config priority, enum validation, asset ID format, and filename sanitization.
- [ ] Run tests and confirm imports fail because modules do not exist.
- [ ] Implement the minimal modules with only the tested behavior.
- [ ] Run tests and confirm they pass.

### Task 2: Content Hashing and Frontmatter Rendering

**Files:**
- Create: `asset_library/hashing.py`
- Create: `asset_library/frontmatter.py`
- Test: `tests/test_hashing_frontmatter.py`

**Interfaces:**
- Consumes: enum/schema constants from Task 1.
- Produces: `compute_body_hash(body_markdown: str) -> str`
- Produces: `compute_non_body_hash(metadata: dict, file_refs: list[dict]) -> tuple[str, str]`
- Produces: `render_note(draft: dict, body_markdown: str) -> str`

- [ ] Write failing tests for normalized body SHA-256, deterministic non-body hash, `hash_source`, and YAML-like frontmatter output.
- [ ] Run tests and confirm failure.
- [ ] Implement minimal deterministic hashing and frontmatter rendering.
- [ ] Run tests and confirm they pass.

### Task 3: Vault Bootstrap and SQLite Mirror

**Files:**
- Create: `asset_library/bootstrap.py`
- Create: `asset_library/mirror.py`
- Test: `tests/test_bootstrap_mirror.py`

**Interfaces:**
- Consumes: resolved Vault path from Task 1.
- Produces: `bootstrap_vault(vault_path: Path) -> list[Path]`
- Produces: `SQLiteMirror(db_path: Path)` with `initialize()`, `upsert_asset(asset: dict)`, `get_asset(asset_id: str)`.

- [ ] Write failing tests for directory creation and mirror upsert/read behavior.
- [ ] Run tests and confirm failure.
- [ ] Implement bootstrap directories and minimal mirror schema.
- [ ] Run tests and confirm they pass.

### Task 4: Atomic Writer V1

**Files:**
- Create: `asset_library/writer.py`
- Test: `tests/test_writer.py`

**Interfaces:**
- Consumes: config, schema, naming, hashing, frontmatter, bootstrap, mirror.
- Produces: `UnifiedAssetWriter(vault_path: Path, mirror_db_path: Path | None = None)`
- Produces: `UnifiedAssetWriter.write_draft(draft: dict) -> dict`

- [ ] Write failing tests for successful note write, duplicate idempotent update, mirror-gap journal on mirror failure, and sanitized path output.
- [ ] Run tests and confirm failure.
- [ ] Implement writer with lock, tmp file, atomic replace, collision check, and mirror gap journal.
- [ ] Run targeted writer tests and then the full test suite.
