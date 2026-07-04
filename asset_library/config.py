import json
import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_VAULT_PATH = Path("/Users/tristanzh/agent/AgentAssetVault")
DEFAULT_CONFIG_PATH = Path("/Users/tristanzh/agent/agent10-asset-library/config.json")


@dataclass(frozen=True)
class ResolvedVaultPath:
    path: Path
    source: str


def resolve_vault_path(config_path=DEFAULT_CONFIG_PATH, env=None):
    env = os.environ if env is None else env
    env_value = _non_empty(env.get("AGENT_ASSET_VAULT_PATH"))
    if env_value:
        return ResolvedVaultPath(Path(env_value).expanduser(), "env:AGENT_ASSET_VAULT_PATH")

    config_path = Path(config_path)
    if config_path.exists():
        data = json.loads(config_path.read_text(encoding="utf-8"))
        config_value = _non_empty(data.get("vault_path"))
        if config_value:
            return ResolvedVaultPath(Path(config_value).expanduser(), f"config:{config_path}")

    return ResolvedVaultPath(DEFAULT_VAULT_PATH, "default")


def _non_empty(value):
    if value is None:
        return ""
    value = str(value).strip()
    return value
