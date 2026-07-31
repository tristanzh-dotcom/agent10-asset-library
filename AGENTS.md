# Agent10 Asset Library Governance

Scope: this repository.

Agent10 is the approved consumer and publication boundary for structured assets
stored in Obsidian-first form with a local mirror. Its README, draft schemas,
migration contract, operation-key rules, and tests define local behavior.

## Data and write boundaries

- `AgentAssetVault` is a shared data root, not a project. Access it only through
  Agent10's approved paths and operations; do not add `AgentAssetVault/AGENTS.md`.
- Treat drafts, source references, generated assets, Obsidian notes, mirror
  records, and migration artifacts as distinct states. Generated content is not
  evidence for its own claims.
- Validation is read-only. Ingest, migration, repair, compaction, and mirror or
  Obsidian writes require their approved command/confirmation and idempotency
  contract.
- Preserve operation keys, atomic write behavior, file permissions, rollback,
  and Obsidian-primary/mirror-secondary semantics. A partial write is not
  success.
- Keep tokens and private asset content out of repos, logs, URLs, tests, and
  browser output.

## Verification and acceptance

The README's draft-validation command is the stable read-only check for one
draft. For implementation work, select the affected schema, writer, idempotency,
migration, mirror, or API test module from current tests. Use package-wide
compile coverage only when the changed surface or release gate warrants it.

Complete unittest discovery is Level 4 or an approved release/migration gate.
Completion requires schema/provenance evidence and idempotent/partial-failure
checks for the affected write path, without an unapproved Vault or Obsidian
write.
