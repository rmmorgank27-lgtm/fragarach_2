"""Durable Fragarach-only dispatch budget shared by MT5 and HTTP acquisition.

This operational sidecar does not alter canonical evidence or the signed MT5
request/response contract. A reservation is conservatively counted until it
is proved undispatched; a crash therefore cannot grant an automatic attempt 4.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path


ATTEMPT_CAP = 3


def ledger_path(database_path: str | Path) -> Path:
    database = Path(database_path).expanduser().resolve()
    return Path(f"{database}.provider-attempts.sqlite3")


class ProviderAttemptLedger:
    def __init__(self, database_path: str | Path, *, path: str | Path | None = None) -> None:
        self.path = Path(path).expanduser().resolve() if path else ledger_path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS provider_attempts (
                       request_id TEXT PRIMARY KEY,
                       lane TEXT NOT NULL,
                       expected_boundary TEXT NOT NULL,
                       routing_revision TEXT NOT NULL,
                       ordinal INTEGER NOT NULL,
                       provider TEXT NOT NULL,
                       node_id TEXT,
                       status TEXT NOT NULL CHECK(status IN ('RESERVED','DISPATCHED','RELEASED')),
                       reserved_at_utc TEXT NOT NULL,
                       dispatched_at_utc TEXT,
                       outcome TEXT,
                       UNIQUE(lane,expected_boundary,routing_revision,ordinal)
                   )"""
            )
            connection.execute(
                """CREATE INDEX IF NOT EXISTS provider_attempts_boundary
                   ON provider_attempts(lane,expected_boundary,routing_revision,status,ordinal)"""
            )

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=15000")
        return connection

    def reserve(
        self, *, request_id: str, lane: str, expected_boundary: str,
        routing_revision: str, provider: str, node_id: str | None = None,
        at: datetime | None = None,
    ) -> dict[str, object] | None:
        if not all((request_id, lane, expected_boundary, routing_revision, provider)):
            raise ValueError("INCOMPLETE_PROVIDER_ATTEMPT_IDENTITY")
        observed = (at or datetime.now(UTC)).astimezone(UTC).isoformat()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM provider_attempts WHERE request_id=?", (request_id,),
            ).fetchone()
            if existing is not None:
                if tuple(existing[key] for key in (
                    "lane", "expected_boundary", "routing_revision", "provider",
                )) != (lane, expected_boundary, routing_revision, provider):
                    raise ValueError("PROVIDER_ATTEMPT_IDENTITY_COLLISION")
                return dict(existing) if existing["status"] != "RELEASED" else None
            active = connection.execute(
                """SELECT count(*) FROM provider_attempts
                   WHERE lane=? AND expected_boundary=? AND routing_revision=?
                     AND status IN ('RESERVED','DISPATCHED')""",
                (lane, expected_boundary, routing_revision),
            ).fetchone()
            if int(active[0]) >= ATTEMPT_CAP:
                return None
            prior = connection.execute(
                """SELECT coalesce(max(ordinal),0) FROM provider_attempts
                   WHERE lane=? AND expected_boundary=? AND routing_revision=?""",
                (lane, expected_boundary, routing_revision),
            ).fetchone()
            ordinal = int(prior[0]) + 1
            connection.execute(
                """INSERT INTO provider_attempts
                   (request_id,lane,expected_boundary,routing_revision,ordinal,
                    provider,node_id,status,reserved_at_utc)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (request_id, lane, expected_boundary, routing_revision, ordinal,
                 provider, node_id, "RESERVED", observed),
            )
            return {
                "request_id": request_id, "lane": lane,
                "expected_boundary": expected_boundary,
                "routing_revision": routing_revision, "ordinal": ordinal,
                "provider": provider, "node_id": node_id,
                "status": "RESERVED", "reserved_at_utc": observed,
            }

    def mark_dispatched(self, request_id: str, *, at: datetime | None = None) -> None:
        observed = (at or datetime.now(UTC)).astimezone(UTC).isoformat()
        with self._connection() as connection:
            updated = connection.execute(
                """UPDATE provider_attempts
                   SET status='DISPATCHED',dispatched_at_utc=coalesce(dispatched_at_utc,?)
                   WHERE request_id=? AND status IN ('RESERVED','DISPATCHED')""",
                (observed, request_id),
            )
            if updated.rowcount != 1:
                raise ValueError("PROVIDER_ATTEMPT_RESERVATION_NOT_FOUND")

    def release_undispatched(self, request_id: str, *, reason: str) -> None:
        if not reason:
            raise ValueError("RELEASE_REASON_REQUIRED")
        with self._connection() as connection:
            connection.execute(
                """UPDATE provider_attempts SET status='RELEASED',outcome=?
                   WHERE request_id=? AND status='RESERVED'""",
                (reason, request_id),
            )

    def mark_outcome(self, request_id: str, outcome: str) -> None:
        if not outcome:
            raise ValueError("ATTEMPT_OUTCOME_REQUIRED")
        with self._connection() as connection:
            connection.execute(
                """UPDATE provider_attempts SET outcome=?
                   WHERE request_id=? AND status='DISPATCHED'""",
                (outcome, request_id),
            )

    def attempts(
        self, *, lane: str, expected_boundary: str, routing_revision: str,
    ) -> list[dict[str, object]]:
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT * FROM provider_attempts
                   WHERE lane=? AND expected_boundary=? AND routing_revision=?
                     AND status IN ('RESERVED','DISPATCHED')
                   ORDER BY ordinal""",
                (lane, expected_boundary, routing_revision),
            ).fetchall()
        return [dict(row) for row in rows]


def latest_attempts_by_lane(
    database_path: str | Path, *, routing_revision: str,
) -> dict[str, list[dict[str, object]]]:
    """Read the newest boundary per lane without creating or changing state."""
    path = ledger_path(database_path)
    if not path.is_file():
        return {}
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """SELECT * FROM provider_attempts
               WHERE routing_revision=? AND status IN ('RESERVED','DISPATCHED')
               ORDER BY reserved_at_utc DESC,ordinal DESC""",
            (routing_revision,),
        ).fetchall()
    latest: dict[str, list[dict[str, object]]] = {}
    boundaries: dict[str, str] = {}
    for row in rows:
        lane, boundary = str(row["lane"]), str(row["expected_boundary"])
        if lane not in boundaries:
            boundaries[lane] = boundary
            latest[lane] = []
        if boundaries[lane] == boundary:
            latest[lane].append(dict(row))
    for attempts in latest.values():
        attempts.sort(key=lambda item: int(item["ordinal"]))
    return latest


__all__ = [
    "ATTEMPT_CAP", "ProviderAttemptLedger", "latest_attempts_by_lane", "ledger_path",
]
