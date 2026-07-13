import os
import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .collision import CollisionChecker, VaultFilesystemCollisionProbe
from .config import resolve_vault_path
from .filesystem_fallback import DirectFilesystemFallbackWriter
from .governance import GovernanceService
from .locking import VaultWriteLock
from .obsidian_rest import ObsidianRestClient
from .producer_api import ProducerApiService
from .sqlite_mirror import MirrorGapJournal, SQLiteAssetMirror
from .writer import RestFirstAssetWriter


DEFAULT_REST_BASE_URL = "https://127.0.0.1:27124"


@dataclass(frozen=True)
class AssetLibraryRuntime:
    vault_path: Path
    rest_client: ObsidianRestClient
    fallback_writer: DirectFilesystemFallbackWriter
    mirror: SQLiteAssetMirror
    mirror_gap_journal: MirrorGapJournal
    writer: RestFirstAssetWriter
    producer_service: ProducerApiService
    governance_service: GovernanceService


def build_runtime(env=None, config_path=None):
    env = os.environ if env is None else env
    resolved = resolve_vault_path(env=env) if config_path is None else resolve_vault_path(config_path, env=env)
    vault_path = resolved.path.resolve()
    base_url = str(env.get("OBSIDIAN_REST_BASE_URL", DEFAULT_REST_BASE_URL)).strip()
    _validate_local_rest_url(base_url)
    api_key = resolve_obsidian_rest_api_key(env=env, vault_path=vault_path)
    if not api_key:
        raise ValueError("OBSIDIAN_REST_API_KEY is required")

    audit_dir = vault_path / "99_System" / "audit"
    indexes_dir = vault_path / "99_System" / "indexes"
    lock_path = audit_dir / ".asset-writer.lock"
    mirror = SQLiteAssetMirror(indexes_dir / "assets.sqlite3")
    gap_journal = MirrorGapJournal(audit_dir / ".mirror-gap.jsonl")
    fallback = DirectFilesystemFallbackWriter(vault_path, use_internal_lock=False)
    rest_client = ObsidianRestClient(base_url=base_url, api_key=api_key, verify_tls=False)

    def operation_lock(operation_id):
        return VaultWriteLock(lock_path, operation_id=operation_id)

    def locked_mutation(action, callback):
        def run():
            with operation_lock(f"governance:{action}"):
                return callback()

        return run

    writer = RestFirstAssetWriter(
        rest_client=rest_client,
        fallback_writer=fallback,
        mirror=mirror,
        mirror_gap_journal=gap_journal,
        collision_checker=CollisionChecker(
            mirror,
            vault_probe=VaultFilesystemCollisionProbe(vault_path),
        ),
        operation_lock_factory=operation_lock,
    )
    producer_service = ProducerApiService(writer=writer)
    governance_service = GovernanceService(
        vault_path=vault_path,
        mirror=mirror,
        mirror_gap_journal=gap_journal,
        promotion_journal_path=audit_dir / ".promotion-journal.jsonl",
        mutation_handlers={
            "compact-mirror-gaps": locked_mutation(
                "compact-mirror-gaps",
                gap_journal.compact_resolved,
            )
        },
    )
    return AssetLibraryRuntime(
        vault_path=vault_path,
        rest_client=rest_client,
        fallback_writer=fallback,
        mirror=mirror,
        mirror_gap_journal=gap_journal,
        writer=writer,
        producer_service=producer_service,
        governance_service=governance_service,
    )


def _validate_local_rest_url(base_url):
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Obsidian REST base URL must use localhost HTTPS")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Obsidian REST base URL must use localhost HTTPS")


def resolve_obsidian_rest_api_key(env, vault_path):
    direct = str(env.get("OBSIDIAN_REST_API_KEY", "")).strip()
    if direct:
        return direct
    config_path = Path(
        env.get(
            "OBSIDIAN_REST_CONFIG_PATH",
            vault_path / ".obsidian" / "plugins" / "obsidian-local-rest-api" / "data.json",
        )
    )
    if not config_path.exists():
        return ""
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    return str(config.get("apiKey", "")).strip()
