# Agent10 V1 Hardening Design

Date: 2026-07-11
Status: Approved by TZ

## Goal

Turn the existing Phase 1 component prototype into a safe, runnable Agent10 V1 foundation, with Agent06 as the only producer in scope.

## Approved Product Decisions

1. Repeated submissions with the same idempotent key reuse the existing asset without updating its note or creating a version.
2. Normal producers cannot submit a final `asset_id`. Historical migration uses a separate controlled interface.
3. Governance GET operations are strictly read-only. Recovery, retry, and journal compaction are explicit mutation operations.
4. V1 integrates only Agent06. Agent05 is retired and is excluded from all future Agent10 implementation scope.

## Architecture

The existing schema, writer, Obsidian REST client, fallback writer, SQLite mirror, journals, and Agent06 adapter remain separate components. A new runtime composition layer constructs them with one validated configuration and exposes normal producer ingestion separately from controlled migration ingestion.

The Vault remains the human-facing asset record. SQLite is a rebuildable mirror. Obsidian REST remains the primary write transport, but Agent10 owns path validation, collision policy, process-level serialization, and recovery evidence.

## Write Contract

- Normal drafts must omit `asset_id`; the writer generates it.
- Controlled migrations may preserve an existing valid `asset_id` only through a separate method.
- `agent_id`, generated paths, timestamps, hashes, references, and schema version are validated before IO.
- Repeated idempotent keys return `idempotent_reuse` and perform no note or mirror update.
- A generated ID collision triggers a new ID, up to five attempts.
- A path or ID conflict that is not idempotent reuse fails before writing.
- YAML scalar values are emitted through a standards-compliant safe serializer.

## Concurrency and Recovery

Both REST and filesystem fallback writes are serialized by the same Vault lock. Journal rewrites use the same lock plus same-directory temporary files and atomic replace. Read-only governance snapshots inspect state without creating directories, clearing lock metadata, or writing audit events. Explicit recovery performs mutations and records evidence.

## API Boundaries

- Normal producer ingestion accepts Agent06 source paths but no final asset ID.
- Controlled migration is a separate service method and route contract.
- Governance GET only reports state.
- Recovery, mirror retry, promotion reconciliation, and compaction are explicit mutation endpoints or CLI commands.
- No Agent05 adapter, route, or documentation remains in active V1 scope.

## Verification

Every behavior change follows red-green TDD. Acceptance requires the full unit suite, compile check, clean diff check, malicious-path probes, YAML round-trip tests, concurrency/journal tests, runtime construction tests, and confirmation that the shared Web still exposes only the approved Agent10 surface.

