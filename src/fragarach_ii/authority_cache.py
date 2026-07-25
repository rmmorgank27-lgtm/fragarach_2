"""Revision-bound cache for read-only authority planning projections."""

from __future__ import annotations

import copy
import hashlib
import json
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any


class AuthorityPreflightCache:
    """Small process-local cache whose entries are valid only for one revision."""

    def __init__(self) -> None:
        self._values: dict[str, object] = {}
        self._lock = threading.RLock()
        self.hits = 0
        self.misses = 0

    def get_or_compute(self, key: object, compute: Callable[[], Any]) -> Any:
        encoded = _key(key)
        with self._lock:
            if encoded in self._values:
                self.hits += 1
                return copy.deepcopy(self._values[encoded])
        value = compute()
        with self._lock:
            self.misses += 1
            self._values[encoded] = copy.deepcopy(value)
        return value

    def invalidate(self) -> None:
        with self._lock:
            self._values.clear()

    def metrics(self) -> dict[str, int]:
        with self._lock:
            return {"hits": self.hits, "misses": self.misses, "entries": len(self._values)}


AUTHORITY_PREFLIGHT_CACHE = AuthorityPreflightCache()


def revision_key(
    database_path: str | Path,
    *,
    provider_facts_revision: object,
    credential_revision: object,
    profile_revision: object,
    provider_state_revision: object,
    request: object,
) -> dict[str, object]:
    """Return a key that cannot survive an authority/configuration mutation."""
    path = Path(database_path).expanduser().resolve()
    # SQLite normally commits operational changes to ``<database>-wal`` rather
    # than the main database file.  Keying only on the latter therefore let a
    # process reuse a capability projection made before a subsequent symbol
    # registration.  Include each SQLite authority file's timestamp and size;
    # this is inexpensive and invalidates the cache for every committed WAL
    # mutation without reading or retaining any authority content.
    def file_revision(candidate: Path) -> tuple[int, int] | None:
        try:
            stat = candidate.stat()
            return stat.st_mtime_ns, stat.st_size
        except OSError:
            return None

    database_revision = {
        "database": file_revision(path),
        "wal": file_revision(Path(f"{path}-wal")),
        "shm": file_revision(Path(f"{path}-shm")),
    }
    return {
        "database": str(path),
        "database_revision": database_revision,
        "provider_facts_revision": provider_facts_revision,
        "credential_revision": credential_revision,
        "profile_revision": profile_revision,
        "provider_state_revision": provider_state_revision,
        "request": request,
    }


def redacted_revision(value: object) -> str:
    """Fingerprint an authority input without retaining credential material."""
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def _key(value: object) -> str:
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
