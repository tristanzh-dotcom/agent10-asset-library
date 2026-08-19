# Plan: Agent14 → Agent10 最小归档垂直切片

> **Execution note:** execute this plan inline in the two existing dirty checkouts; do not create a worktree or commit. Preserve unrelated user changes. Use the canonical design spec at `docs/superpowers/specs/2026-08-19-agent14-agent10-archive-integration-design.md` as the contract authority.

## Goal

Implement the smallest useful, production-safe slice of the approved design:

1. Agent14 can explicitly create a deterministic, immutable local archive snapshot and durable Outbox record without waiting for Agent10.
2. Agent10 can validate an Agent14 `agent14-archive:v1` snapshot and map it to a normal producer draft without accepting a caller-supplied final `asset_id`.
3. Tests prove the snapshot contract, path/hash rejection, and existing Agent14 upload/edit/export isolation.

This slice does not enable Production Vault writes, direct Agent14→Agent10 network delivery, the Web button, attachment copying into `03_Assets`, or legacy Obsidian mode switching. Those are later gates requiring their own implementation and acceptance evidence.

## Constraints and invariants

- Work in place because both repositories are already dirty and the user explicitly authorized automatic implementation in the current workspace; do not create a worktree.
- Do not modify or delete unrelated dirty files.
- Snapshot source is `work/`, never `exports/` or `outbox/`.
- Snapshot publication is staging + atomic rename; a failed build leaves no visible snapshot or Outbox record.
- `archive-manifest.json` is excluded from its own `files` list and bundle hash.
- Agent14 creates the operation key; Agent10 verifies it and allocates any final asset ID only through its normal writer later.
- No absolute path, credential, Vault configuration, or raw exception enters snapshot/Outbox/adapter output.
- Normal Agent10 drafts must remain `asset_id`-free and default to `sensitivity: restricted`, `knowledge_status: not_indexed`.

## Task 1 — Add failing Agent14 snapshot contract tests

**Files:** `agent14-ppt2html/test/archive-snapshot.test.mjs`, optionally the existing server test for endpoint isolation.

1. Add a fixture that creates a project through the existing conversion endpoint, exports revision 1, and calls `POST /api/agent14/projects/doc-demo/archive-snapshots` with `{ expectedRevision: 1, includeOriginal: false }`.
2. Assert HTTP `202`, `snapshotStatus: ready`, `deliveryStatus: queued`, `archiveStatus: pending`, a generated snapshot/operation identity, and no wait on a fake downstream service.
3. Inspect the temporary runtime to assert the required payload files and Outbox JSON; assert no `source/` exists when `includeOriginal` is false.
4. Call the same request again and assert the same snapshot identity is reused rather than a second snapshot.
5. Add negative cases for revision conflict, missing export, invalid request shape, and an attempt to read/modify a published snapshot through the API.
6. Run the new test before implementation and confirm it fails for the missing route/contract.

## Task 2 — Implement Agent14 deterministic snapshots and local state

**Files:** `agent14-ppt2html/src/archive-snapshot.mjs`, `src/project-store.mjs`, `src/server.mjs`, and `package.json` check coverage if needed.

1. Add small pure helpers for POSIX relative paths, safe copy enumeration, UTF-8/LF/one-final-newline Markdown normalization, SHA-256, canonical JSON, warning-code collection, and media-type mapping.
2. Add a per-document async mutex used by `updateBlock`, `writeExport`, and snapshot creation. Keep the lock local to the process and release it before any future transport.
3. Implement `createArchiveSnapshot(documentId, expectedRevision, includeOriginal)`:
   - read the current project/manifest and require exact revision;
   - require the matching revision export ZIP to exist;
   - stage `work/index.html`, normalized `work/content.md`, `work/manifest.json`, optional `work/assets/**`, and optional safe original input under `payload/`;
   - reject links/special files and unexpected payload paths;
   - compute per-file hashes, canonical manifest core, bundle hash, snapshot ID (`snap-r<revision>-<hash12>`), and operation key;
   - write final manifest, atomically rename the snapshot directory, then atomically write the Outbox record;
   - reuse an existing matching snapshot/Outbox for the same revision and bundle.
4. Implement read-only snapshot listing/projection from snapshots + Outbox + receipts. Missing/corrupt state must project `unknown` and never block normal project reads.
5. Add the same-origin routes:
   - `POST /api/agent14/projects/:documentId/archive-snapshots` → `202` after local persistence;
   - `GET /api/agent14/projects/:documentId/archive-snapshots`;
   - no downstream call in this slice; leave delivery `queued`.
6. Add stable error mapping for `INVALID_ARCHIVE_REQUEST`, `EXPORT_NOT_READY`, `REVISION_CONFLICT`, `SNAPSHOT_NOT_FOUND`, and local build failure. Preserve all existing routes and Obsidian behavior.

## Task 3 — Add failing Agent10 Agent14 adapter tests

**Files:** `agent10-asset-library/tests/test_agent14_adapter.py`, `tests/fixtures/agent14-archive-v1/` (test-only temporary fixture builder preferred).

1. Build a temporary valid `agent14-archive:v1` snapshot with payload files and a manifest generated by the same public contract rules.
2. Assert the adapter returns a normal draft with `agent_id=agent14`, `asset_type=agent14_document_snapshot`, restricted/not-indexed defaults, canonical source path, stable metadata, HTML/Markdown/manifest `file_refs`, and no final `asset_id`.
3. Assert independent hash/bundle verification rejects tampered content, manifest file-list mismatches, path traversal, symlinks, unsupported contract versions, and an `outbox` path passed as the source.
4. Assert missing optional original input is represented as metadata only, never a fabricated file path.
5. Run the new tests before implementation and confirm they fail for the absent adapter.

## Task 4 — Implement Agent10 validation adapter and minimal producer registration

**Files:** `agent10-asset-library/asset_library/adapters/agent14.py`, `asset_library/producer_api.py`, targeted tests.

1. Implement strict realpath containment against an explicitly supplied Agent14 snapshot root; reject symlinks, non-regular files, absolute/traversal paths, outbox paths, and extra payload files.
2. Independently read payload bytes, normalize/verify Markdown bytes, verify every declared file hash/size/media type, warning-code ordering, content hash, canonical manifest core, bundle hash, snapshot ID, and operation key.
3. Map the verified snapshot into a normal draft without `asset_id`; use the manifest source file name and bundle hash as metadata, logical `source_asset_path`, and non-absolute snapshot-relative file references for this draft-only slice. Keep original file refs absent when not included; physical Agent10 attachment staging remains a later task.
4. Register `agent14` only in explicit adapter injection or the controlled default producer map; do not widen unrelated producer behavior or write the live Vault.
5. Keep the external route prefix unchanged for now; route/service tests only prove the adapter contract and normal draft handoff. Do not invent a persistent operation store in this slice.

## Task 5 — Minimal verification and handoff

1. Run Agent14 `npm test` and `npm run check`.
2. Run Agent10 focused tests for the new adapter plus `tests.test_producer_api`, `tests.test_http_server`, and `tests.test_writer`.
3. Run a read-only diff/status audit in both repositories; ensure only intended new/modified files are present and the duplicate Agent14 design file remains absent.
4. Report exact commands, pass/fail counts, skipped production integration gates, and the next approval boundary (real Agent10 HTTP delivery/temporary Vault, then Web entry point).
