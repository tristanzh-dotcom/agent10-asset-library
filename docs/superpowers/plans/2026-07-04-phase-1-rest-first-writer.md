# Phase 1 REST-first Writer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Agent10's Phase 1 core around the validated Obsidian Local REST API with MCP, while preserving direct filesystem writing as an offline fallback.

**Architecture:** Agent10 validates agent asset drafts, renders Obsidian-compatible Markdown/frontmatter, writes through Local REST API when available, and falls back to the design contract's direct file writer only when REST is unavailable. Obsidian remains the product surface; Agent10 code fills schema/idempotency/safety gaps only.

**Tech Stack:** Python 3 standard library, `unittest`, `urllib.request`, `ssl`, `hashlib`, `secrets`, `pathlib`.

## Global Constraints

- Primary interface: Obsidian Local REST API with MCP on localhost HTTPS with Bearer auth.
- Fallback interface: direct filesystem writer governed by 11.6 write safety strategy.
- Do not store API keys in source-controlled files.
- Do not require network access beyond localhost for tests.
- Preserve flat YAML frontmatter and Obsidian nested tags.
- No Git write operations from this repo.

---

### Task 1: Draft Contract and Rendering

**Files:**
- Create: `asset_library/__init__.py`
- Create: `asset_library/schema.py`
- Create: `asset_library/naming.py`
- Create: `asset_library/hashing.py`
- Create: `asset_library/frontmatter.py`
- Test: `tests/test_contract_rendering.py`

**Interfaces:**
- Produces: `validate_draft(draft: dict) -> list[str]`
- Produces: `generate_asset_id(now=None, token_hex=None) -> str`
- Produces: `sanitize_short_title(title: str, asset_id: str) -> str`
- Produces: `compute_body_hash(body_markdown: str) -> str`
- Produces: `render_note(draft: dict) -> str`

- [x] Write failing tests for enum validation, asset ID format, title sanitization, body hash normalization, and rendered note frontmatter.
- [x] Run tests and confirm failure because modules are missing.
- [x] Implement the minimum code needed.
- [x] Run tests and confirm pass.

### Task 2: Obsidian REST Client

**Files:**
- Create: `asset_library/obsidian_rest.py`
- Test: `tests/test_obsidian_rest.py`

**Interfaces:**
- Produces: `ObsidianRestClient(base_url: str, api_key: str, verify_tls: bool = False)`
- Produces: `status() -> dict`
- Produces: `read_note(path: str) -> str`
- Produces: `write_note(path: str, markdown: str) -> None`
- Produces: `list_tags() -> dict`
- Produces: `mcp_initialize() -> dict`

- [x] Write failing tests against an injected fake transport.
- [x] Run tests and confirm failure.
- [x] Implement client methods with Bearer auth and URL encoding compatible with Obsidian paths.
- [x] Run tests and confirm pass.

### Task 3: REST-first Writer with Fallback Boundary

**Files:**
- Create: `asset_library/writer.py`
- Test: `tests/test_writer.py`

**Interfaces:**
- Consumes: Task 1 rendering and Task 2 client.
- Produces: `AssetWriteResult`
- Produces: `RestFirstAssetWriter.write(draft: dict) -> AssetWriteResult`

- [x] Write failing tests for REST success and fallback invocation when REST is unavailable.
- [x] Run tests and confirm failure.
- [x] Implement writer orchestration without full SQLite Mirror.
- [x] Run tests and confirm pass.

### Task 4: Phase 1 Follow-up Plan

**Files:**
- Modify: `docs/OBSIDIAN_PHASE1_LAYER1_VALIDATION_20260704.md`
- Create: `docs/OBSIDIAN_PHASE1_IMPLEMENTATION_STATUS_20260704.md`

**Interfaces:**
- Consumes: test results from Tasks 1-3.
- Produces: implementation status and remaining risk list.

- [x] Record what is implemented.
- [x] Record what remains deferred: SQLite Mirror, full 11.6 fallback locking, Dataview/UI validation, Agent06 adapter.

### Task 5: SQLite Mirror and Mirror Gap Journal

**Files:**
- Create: `asset_library/sqlite_mirror.py`
- Modify: `asset_library/writer.py`
- Test: `tests/test_sqlite_mirror.py`
- Test: `tests/test_writer.py`

**Interfaces:**
- Produces: `SQLiteAssetMirror(db_path).upsert_asset(draft, vault_path)`
- Produces: `SQLiteAssetMirror(db_path).get_asset(asset_id)`
- Produces: `MirrorGapJournal(journal_path).append_gap(asset_id, vault_path, fail_reason)`
- Produces: `MirrorGapScanner(journal, mirror, draft_resolver).retry_gaps()`

- [x] Write failing tests for mirror upsert, idempotent replacement, gap journal append, and gap scanner retry.
- [x] Run tests and confirm failure because mirror/scanner are missing.
- [x] Implement the minimum SQLite mirror and journal code.
- [x] Connect `RestFirstAssetWriter` to mirror after successful note writes.
- [x] Ensure mirror failure after REST success does not trigger fallback rewrite.
- [x] Run target tests and full test suite.

### Task 6: Spec Closure for Writer Safety, Hashing, Migration, and Promotion Contracts

**Files:**
- Create: `asset_library/config.py`
- Create: `asset_library/collision.py`
- Create: `asset_library/locking.py`
- Create: `asset_library/schema_migration.py`
- Create: `asset_library/knowledge_bridge.py`
- Modify: `asset_library/hashing.py`
- Modify: `asset_library/frontmatter.py`
- Modify: `asset_library/schema.py`
- Modify: `asset_library/writer.py`
- Modify: `asset_library/filesystem_fallback.py`
- Modify: `asset_library/sqlite_mirror.py`
- Test: `tests/test_config.py`
- Test: `tests/test_collision.py`
- Test: `tests/test_locking.py`
- Test: `tests/test_schema_migration.py`
- Test: `tests/test_knowledge_bridge.py`

**Interfaces:**
- Produces: `resolve_vault_path(...)`
- Produces: `compute_non_body_hash(draft)`
- Produces: `CollisionChecker(registry).check(draft, vault_path)`
- Produces: `VaultWriteLock(lock_path, operation_id, timeout_seconds=30)`
- Produces: `recover_writer_state(vault_path, ...)`
- Produces: `normalize_asset_frontmatter(frontmatter)`
- Produces: `KnowledgeBridge(note_store, ingest_adapter, promotion_journal).promote(vault_path, confirmed=True)`
- Produces: `PromotionJournal(path)` and `ReconciliationJob(...)`

- [x] Write failing tests for Vault path resolution priority.
- [x] Write failing tests for canonical non-body asset hashing.
- [x] Write failing tests for writer-generated `asset_id`, pre-write hash preparation, idempotent reuse, and collision rejection.
- [x] Write failing tests for SQLite-backed collision registry queries.
- [x] Write failing tests for lock metadata, timeout behavior, stale-lock recovery, and tmp-file reporting.
- [x] Write failing tests for mirror-gap resolved marking and explicit compaction.
- [x] Write failing tests for schema normalization without in-place note mutation.
- [x] Write failing tests for Knowledge Bridge confirmation, two-phase status updates, promotion journal, and retry-limit escalation.
- [x] Implement minimum production code for all above.
- [x] Run full test suite.

### Task 7: Agent06 Adapter, Obsidian UI Validation, and Governance API Contract

**Files:**
- Create: `asset_library/adapters/__init__.py`
- Create: `asset_library/adapters/agent06.py`
- Create: `asset_library/governance.py`
- Create: `asset_library/governance_api.py`
- Create: `docs/OBSIDIAN_AGENT06_UI_GOVERNANCE_VALIDATION_20260704.md`
- Modify: `asset_library/frontmatter.py`
- Test: `tests/test_agent06_adapter.py`
- Test: `tests/test_governance.py`
- Test: `tests/test_governance_api.py`
- Test: `tests/test_contract_rendering.py`

**Interfaces:**
- Produces: `discover_agent06_answers(pka_data_root)`
- Produces: `agent06_answer_to_draft(asset_dir)`
- Produces: `GovernanceService(...).snapshot()`
- Produces: `governance_response(path, service)`

- [x] Write failing tests for Agent06 V0 manifest/answer conversion.
- [x] Implement Agent06 adapter without modifying Agent06 source directories.
- [x] Live smoke real Agent06 asset through Obsidian REST and SQLite Mirror.
- [x] Write failing tests for governance snapshot excluding note body.
- [x] Implement governance service for writer health, mirror gaps, promotion journal, and schema drift.
- [x] Write failing tests for `GET /api/asset-library/governance` route contract.
- [x] Fix frontmatter rendering to emit YAML nested mappings instead of Python dict strings.
- [x] Validate Obsidian tag index for Agent06 note.
- [x] Record UI/governance validation evidence.
- [x] Run full test suite.

### Task 8: Production Vault Bootstrap

**Files:**
- Create: `asset_library/vault_bootstrap.py`
- Test: `tests/test_vault_bootstrap.py`
- Modify: `docs/OBSIDIAN_PHASE1_IMPLEMENTATION_STATUS_20260704.md`

**Interfaces:**
- Produces: `bootstrap_vault(vault_path, plugin_source=None)`

- [x] Write failing tests for production Vault directory creation.
- [x] Write failing tests for schema/template/index note creation.
- [x] Write failing tests for copying Local REST API plugin without `data.json`.
- [x] Write failing tests for idempotency and no overwrite of existing system notes.
- [x] Implement production Vault bootstrap.
- [x] Execute bootstrap for `/Users/tristanzh/agent/AgentAssetVault/`.
- [x] Verify production Vault `.gitignore` and folder layout.
- [x] Verify direct fallback writer can write a production smoke note.

### Task 9: Producer API and CLI Contract

**Files:**
- Create: `asset_library/producer_api.py`
- Create: `asset_library/cli.py`
- Test: `tests/test_producer_api.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: `ProducerApiService(writer).ingest_draft(draft)`
- Produces: `ProducerApiService(writer).ingest_producer_asset(producer_id, payload)`
- Produces: `producer_response(method, path, body, service)`
- Produces: `run_cli(argv, service)`

- [x] Write failing tests for `POST /api/asset-library/drafts`.
- [x] Write failing tests for `POST /api/asset-library/producers/agent06/assets`.
- [x] Write failing tests for unknown producer rejection.
- [x] Write failing tests for CLI `validate-draft`, `ingest-draft`, and `ingest-agent06`.
- [x] Implement Producer API and CLI contract.
- [x] Confirm Producer API does not modify child Agent code.
- [x] Run full test suite.
