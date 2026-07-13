# Agent10 Production Activation and Shared Web Contract Design

Date: 2026-07-12
Status: Approved by TZ for direct execution

## Goal

Activate the Production Obsidian Vault, run Agent10 as a localhost-only service, and replace the shared Web Agent10 placeholder with a governance-only published surface.

## Architecture

```text
Browser
  -> Web :3000 /api/agent10/*
  -> inject local control Bearer token
  -> Agent10 :8010 (127.0.0.1 only)
  -> Obsidian Local REST :27124 (127.0.0.1 HTTPS only)
  -> Production AgentAssetVault
```

The browser never receives the Obsidian REST key or the Agent10 control token. Agent10 reads the Obsidian runtime key from the ignored Local REST plugin configuration. The Web server reads the same local control-token file and injects the token while proxying; direct Agent10 requests without that token receive `403`.

## API Contract

- `GET /api/agent10/governance`: Web proxy requires a valid local control token and returns the side-effect-free governance snapshot.
- `POST /api/agent10/governance/actions/{recover-writer|compact-mirror-gaps}`: Web proxy injects the local control token. Agent10 applies its existing explicit mutation authorization gate.
- `POST /api/agent10/drafts` and `POST /api/agent10/producers/agent06/assets`: Agent10-only producer routes. Normal drafts cannot carry final `asset_id`; Agent06 remains the only enabled producer.
- `POST /api/agent10/migrations/drafts`: default-denied controlled migration route. The Web route does not expose it in this release.
- No Web endpoint exposes raw Vault notes, Obsidian credentials, control-token bytes, or asset body content.

## Local Authentication

- `99_System/audit/.agent10-control.token` is a generated 32-byte random token encoded as hexadecimal, mode `0600`, and excluded by the Vault `.gitignore`.
- The Agent10 service reads its token from `AGENT10_CONTROL_TOKEN_FILE` and verifies `Authorization: Bearer <token>` with constant-time comparison.
- The shared Web process reads only `AGENT10_CONTROL_TOKEN_FILE`; it injects the header server-side and never serializes it into HTML, JavaScript, logs, or platform status APIs.
- Agent10 and Obsidian bind only to loopback addresses. The Agent10 service rejects any non-loopback client address.

## Production Activation

1. Open the existing Production Vault in the pre-installed Obsidian app.
2. Enable the already copied Local REST API plugin and generate its runtime configuration/key through Obsidian's trust flow.
3. Generate the separate Agent10 local control token in the Vault audit directory.
4. Start Agent10 through the shared backend supervisor on `127.0.0.1:8010`.
5. Verify authenticated Local REST status, Agent10 governance, the Web proxy, and the published Agent10 page.

## Boundaries

- Agent05 remains retired and excluded.
- Knowledge Bridge promotion, mirror-gap retry, and reconciliation stay unavailable; this release does not add an external model route or send project data outside the machine.
- Obsidian UI remains the asset reading/editing surface. Web renders governance health only.
- The actual Obsidian plugin key and Agent10 control token are never printed, committed, or copied into Web configuration.
