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
    def __init__(self, registry):
        self.registry = registry

    def check(self, draft, vault_path):
        existing_by_key = self.registry.get_by_idempotent_key(idempotent_key(draft))
        if existing_by_key:
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

        if self.registry.path_exists(vault_path):
            return {
                "action": "reject",
                "reason": "target path already exists",
            }

        return None
