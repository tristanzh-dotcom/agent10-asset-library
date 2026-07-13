from pathlib import Path


IDEMPOTENT_SEPARATOR = "\x1f"


def idempotent_key(draft):
    parts = (
        draft.get("agent_id", ""),
        draft.get("workflow_id", ""),
        draft.get("source_asset_path", ""),
        draft.get("source_content_hash", ""),
    )
    return IDEMPOTENT_SEPARATOR.join(str(part) for part in parts)


class CollisionChecker:
    def __init__(self, registry, vault_probe=None):
        self.registry = registry
        self.vault_probe = vault_probe

    def check(self, draft, vault_path):
        existing_by_key = self.registry.get_by_idempotent_key(idempotent_key(draft))
        if existing_by_key:
            if self.vault_probe is not None and not self.vault_probe.path_exists(
                existing_by_key["vault_path"]
            ):
                return {
                    "action": "reject",
                    "reason": "stale idempotent mirror entry: Vault note is missing",
                }
            return {
                "action": "reuse_existing",
                "asset_id": existing_by_key["asset_id"],
                "vault_path": existing_by_key["vault_path"],
            }

        existing_by_id = self.registry.get_by_asset_id(draft["asset_id"])
        if existing_by_id and existing_by_id.get("source_content_hash") != draft.get("source_content_hash"):
            return {
                "action": "reject",
                "reason": "asset_id collision with different source_content_hash",
            }

        if self.vault_probe is not None and self.vault_probe.asset_id_exists(draft["asset_id"]):
            return {
                "action": "reject",
                "reason": "asset_id exists in real Vault",
            }

        if self.registry.path_exists(vault_path):
            return {
                "action": "reject",
                "reason": "target path already exists",
            }

        if self.vault_probe is not None and self.vault_probe.path_exists(vault_path):
            return {
                "action": "reject",
                "reason": "target path already exists in real Vault",
            }

        return None


class VaultFilesystemCollisionProbe:
    def __init__(self, vault_path):
        self.vault_path = Path(vault_path).resolve()

    def path_exists(self, vault_path):
        target = (self.vault_path / vault_path).resolve()
        try:
            target.relative_to(self.vault_path)
        except ValueError:
            return True
        return target.exists()

    def asset_id_exists(self, asset_id):
        agents_root = self.vault_path / "01_Agents"
        if not agents_root.exists():
            return False
        suffix = f" - {asset_id}.md"
        return any(path.is_file() and path.name.endswith(suffix) for path in agents_root.rglob("*.md"))
