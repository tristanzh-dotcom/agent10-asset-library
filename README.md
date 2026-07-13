# Agent10 Asset Library

Agent10 is the Obsidian-first asset publishing and governance layer for high-value Agent outputs. V1 supports Agent06 only. Obsidian is the human-facing asset UI; Agent10 owns schema validation, safe writing, idempotency, the SQLite mirror, and operational governance.

## Validate a Draft

Validation is local and does not require Obsidian credentials:

```bash
python3 -m asset_library validate-draft /absolute/path/to/draft.json
```

## Runtime Configuration

Commands that write assets require these environment variables:

```text
AGENT_ASSET_VAULT_PATH=/absolute/path/to/approved/vault
OBSIDIAN_REST_BASE_URL=https://127.0.0.1:27124
OBSIDIAN_REST_API_KEY=<runtime secret>
```

The REST URL must use HTTPS and a localhost host. Do not store the API key in source-controlled files.

For the Production Obsidian plugin, Agent10 reads the ignored runtime configuration by default from:

```text
AgentAssetVault/.obsidian/plugins/obsidian-local-rest-api/data.json
```

Agent10's separate Web control token is created at:

```text
AgentAssetVault/99_System/audit/.agent10-control.token
```

Both files must remain mode `0600` and must never be copied into Web HTML, JavaScript, logs, or Git.

## Ingestion

Normal drafts must not contain a final `asset_id`:

```bash
python3 -m asset_library ingest-draft /absolute/path/to/draft.json
```

Agent06 V0 assets use the Agent10-owned adapter:

```bash
python3 -m asset_library ingest-agent06 /absolute/path/to/agent06/answer-asset
```

Historical migrations that preserve an existing valid `asset_id` use the separate local command:

```bash
python3 -m asset_library ingest-migration /absolute/path/to/migration-draft.json
```

The HTTP migration contract denies access by default. A host must explicitly authorize a request after applying its local authentication policy.

## Governance Boundary

`GET /api/asset-library/governance` is read-only. Writer recovery and mirror-gap compaction are explicit, default-denied mutation actions. Mirror retry and promotion reconciliation remain unavailable until their production resolvers are wired. Shared Web wiring and production Obsidian trust activation remain separate publication and operations steps.

## Verification

```bash
python3 -m unittest discover -s tests -v
PYTHONPYCACHEPREFIX=/tmp/agent10-asset-library-pycache python3 -m compileall -q asset_library tests
```
