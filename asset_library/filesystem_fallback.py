import os
import secrets
import stat
from pathlib import Path

from .locking import VaultWriteLock


class DirectFilesystemFallbackWriter:
    def __init__(self, vault_path, lock_timeout_seconds=30, use_internal_lock=True):
        self.vault_path = Path(vault_path).resolve()
        self.lock_timeout_seconds = lock_timeout_seconds
        self.use_internal_lock = use_internal_lock

    def write_note(self, path, markdown):
        target = self._resolve_target(path)
        operation_id = f"write:{path}:{secrets.token_hex(4)}"
        lock_path = self.vault_path / "99_System" / "audit" / ".asset-writer.lock"
        lock = (
            VaultWriteLock(
                lock_path,
                operation_id=operation_id,
                timeout_seconds=self.lock_timeout_seconds,
            )
            if self.use_internal_lock
            else _NoopLock()
        )
        with lock:
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(f".{target.name}.{secrets.token_hex(4)}.tmp")
            data = markdown.encode("utf-8")

            mode = stat.S_IMODE(target.stat().st_mode) & 0o600 if target.exists() else 0o600
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
            try:
                with os.fdopen(fd, "wb") as handle:
                    os.fchmod(handle.fileno(), mode)
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(tmp, target)
                _fsync_directory(target.parent)
            finally:
                tmp.unlink(missing_ok=True)

    def _resolve_target(self, path):
        target = (self.vault_path / path).resolve()
        try:
            target.relative_to(self.vault_path)
        except ValueError as exc:
            raise ValueError(f"path escapes vault: {path}") from exc
        return target


class _NoopLock:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _fsync_directory(path):
    if not hasattr(os, "O_DIRECTORY"):
        return
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
