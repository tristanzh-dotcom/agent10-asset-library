import fcntl
import json
import os
import socket
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path


class VaultWriteLock:
    def __init__(
        self,
        lock_path,
        operation_id,
        timeout_seconds=30,
        pid=None,
        hostname=None,
        clock=None,
        sleep=time.sleep,
    ):
        self.lock_path = Path(lock_path)
        self.operation_id = operation_id
        self.timeout_seconds = timeout_seconds
        self.pid = os.getpid() if pid is None else pid
        self.hostname = socket.gethostname() if hostname is None else hostname
        self.clock = clock or _now_utc8_iso
        self.sleep = sleep
        self._handle = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()

    def acquire(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.lock_path.open("a+", encoding="utf-8")
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            try:
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    self._handle.close()
                    self._handle = None
                    raise TimeoutError(f"timed out acquiring vault writer lock: {self.lock_path}")
                self.sleep(0.05)
        self._write_metadata()

    def release(self):
        if self._handle is None:
            return
        self._handle.seek(0)
        self._handle.truncate()
        self._handle.flush()
        os.fsync(self._handle.fileno())
        fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        self._handle.close()
        self._handle = None

    def _write_metadata(self):
        metadata = {
            "pid": self.pid,
            "hostname": self.hostname,
            "started_at": self.clock(),
            "operation_id": self.operation_id,
        }
        self._handle.seek(0)
        self._handle.truncate()
        json.dump(metadata, self._handle, ensure_ascii=False, sort_keys=True)
        self._handle.flush()
        os.fsync(self._handle.fileno())


def inspect_writer_state(vault_path, pid_exists=None):
    vault_path = Path(vault_path)
    pid_exists = _pid_exists if pid_exists is None else pid_exists
    audit_dir = vault_path / "99_System" / "audit"
    report = {
        "tmp_files": _relative_tmp_files(vault_path),
        "stale_locks": [],
        "active_locks": [],
    }
    lock_path = audit_dir / ".asset-writer.lock"
    metadata = _read_lock_metadata(lock_path)
    if metadata:
        try:
            holder_pid = int(metadata.get("pid", -1))
        except (TypeError, ValueError):
            holder_pid = -1
        if pid_exists(holder_pid):
            report["active_locks"].append(metadata)
        else:
            report["stale_locks"].append(metadata)
    return report


def recover_writer_state(vault_path, pid_exists=None, clock=None):
    vault_path = Path(vault_path)
    clock = clock or _now_utc8_iso
    report = inspect_writer_state(vault_path, pid_exists=pid_exists)
    audit_dir = vault_path / "99_System" / "audit"
    if report["stale_locks"]:
        audit_dir.mkdir(parents=True, exist_ok=True)
        lock_path = audit_dir / ".asset-writer.lock"
        for metadata in report["stale_locks"]:
            event = dict(metadata)
            event["recovered_at"] = clock()
            event_path = audit_dir / f"stale-lock-{event.get('operation_id', 'unknown')}.json"
            event_path.write_text(
                json.dumps(event, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        lock_path.write_text("", encoding="utf-8")
    return report


def _relative_tmp_files(vault_path):
    if not vault_path.exists():
        return []
    files = []
    for path in vault_path.rglob("*.tmp"):
        if path.is_file():
            files.append(path.relative_to(vault_path).as_posix())
    return sorted(files)


def _read_lock_metadata(lock_path):
    if not lock_path.exists():
        return None
    content = lock_path.read_text(encoding="utf-8").strip()
    if not content:
        return None
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"unreadable": True, "path": str(lock_path)}


def _pid_exists(pid):
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _now_utc8_iso():
    return datetime.now(timezone(timedelta(hours=8))).replace(microsecond=0).isoformat()
