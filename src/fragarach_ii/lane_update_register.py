"""Durable, indexed runtime register for time-triggered lane upkeep.

The register deliberately lives beside (rather than inside) the immutable
authority database.  It is scheduler runtime state: losing it is recoverable
by :func:`audit_estate`, while canonical bars, registrations, and provenance
are never changed by its migration or recovery path.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterator

from .freshness import assess_lane_freshness, authority_revision_for_lane, normalized_utc
from .operational_schedule import schedule_for_lane
from .scheduler_integrity import active_universe
from .storage import open_read_only


REGISTER_CONTRACT = "fragarach_ii.lane_update_register.v1"
REGISTER_PRIORITY_REVISION = "2"
REGISTER_STATES = frozenset({"READY", "RETRY", "BLOCKED", "PAUSED", "RUNNING"})
_NORMAL_STATES = ("READY", "RETRY")


def register_path(database_path: str | Path) -> Path:
    database = Path(database_path).expanduser().resolve()
    return Path(f"{database}.lane-update-register.sqlite3")


class LaneUpdateRegister:
    """Small SQLite work index with one row per active commissioned lane."""

    def __init__(self, database_path: str | Path, *, path: str | Path | None = None) -> None:
        self.database_path = Path(database_path).expanduser().resolve()
        self.path = Path(path).expanduser().resolve() if path else register_path(database_path)
        self._initialize()

    def is_seeded(self) -> bool:
        with self._connection() as connection:
            return self._meta(connection, "seeded_at_utc") is not None

    def initialize_if_needed(self, *, at: datetime | None = None) -> dict[str, object]:
        """Perform the one permitted startup migration, never a routine scan."""
        if self.is_seeded():
            return {"seeded": False, "reason": "ALREADY_INITIALIZED"}
        report = self.audit_estate(at=at, reason="INITIAL_MIGRATION")
        return {"seeded": True, **report}

    def audit_estate(self, *, at: datetime | None = None, reason: str = "OPERATOR_AUDIT") -> dict[str, object]:
        """Rebuild only the operational register from active commissioned lanes.

        This is intentionally the only method in this module that projects the
        estate.  Normal dispatch uses :meth:`claim_due` and has no authority
        estate scan.
        """
        observed = normalized_utc(at)
        universe = active_universe(self.database_path)
        active = universe["active_lanes"]
        rows: list[dict[str, object]] = []
        with open_read_only(self.database_path) as authority:
            for lane_id, lane in sorted(active.items()):
                symbol, timeframe = str(lane["symbol"]), str(lane["timeframe"])
                schedule = schedule_for_lane(
                    # Include a boundary that closes exactly at migration
                    # time.  It is a legitimate due check, not a reason to
                    # defer the lane by a complete cadence interval.
                    authority, symbol=symbol, timeframe=timeframe,
                    after=observed - timedelta(microseconds=1),
                )
                if schedule.get("available") and schedule.get("next_scheduled_acquisition"):
                    next_check = str(schedule["next_scheduled_acquisition"])
                    state, outcome = "READY", "MIGRATED"
                else:
                    next_check = None
                    state, outcome = "BLOCKED", str(schedule.get("reason_code") or "SCHEDULE_UNAVAILABLE")
                rows.append({
                    "asset": symbol,
                    "timeframe": timeframe,
                    "state": state,
                    "next_expected_boundary_utc": next_check,
                    "next_check_at_utc": next_check,
                    "last_successful_bar_utc": _latest_bar(authority, symbol, timeframe),
                    "last_outcome": outcome,
                    "provider_route_revision": authority_revision_for_lane(
                        authority, symbol=symbol, timeframe=timeframe
                    ),
                    "calendar_or_session_revision": _schedule_revision(schedule),
                    "priority": _priority_for(str(lane.get("asset_class") or ""), timeframe),
                })

        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                existing = {
                    (str(row[0]), str(row[1])): dict(row)
                    for row in connection.execute("SELECT * FROM lane_update_register")
                }
                active_keys = {(row["asset"], row["timeframe"]) for row in rows}
                connection.execute("DELETE FROM lane_update_register")
                for row in rows:
                    prior = existing.get((row["asset"], row["timeframe"]))
                    # Preserve a retry or an operator pause across an audit
                    # unless the lane's approved scheduling authority changed.
                    preserve = prior and prior["state"] in {"RETRY", "PAUSED", "BLOCKED"} and (
                        prior["calendar_or_session_revision"] == row["calendar_or_session_revision"]
                        and prior["provider_route_revision"] == row["provider_route_revision"]
                    )
                    self._insert(connection, {**row, **(_preserved_values(prior) if preserve else {})}, observed)
                self._set_meta(connection, "seeded_at_utc", observed.isoformat())
                self._set_meta(connection, "last_audit_at_utc", observed.isoformat())
                self._set_meta(connection, "last_audit_reason", reason)
                self._set_meta(connection, "active_universe_revision", str(universe["revision"]))
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
        return {
            "contract": REGISTER_CONTRACT,
            "audit_reason": reason,
            "active_lane_count": len(rows),
            "removed_lane_count": len(set(existing) - active_keys),
            "register_path": str(self.path),
        }

    def ensure_commissioned_lane(
        self, *, asset: str, timeframe: str, at: datetime | None = None,
    ) -> dict[str, object]:
        """Insert one newly commissioned lane without rebuilding the estate.

        Estate admission happens after the register's initial migration in a
        long-running service.  New lanes must therefore be registered here at
        admission time; waiting for the weekly audit leaves their normal
        schedule invisible to the time-triggered executor.
        """
        observed = normalized_utc(at)
        symbol, interval = asset.strip().upper(), timeframe.strip().upper()
        with open_read_only(self.database_path) as authority:
            registration = authority.execute(
                "SELECT asset_class FROM instrument_registrations WHERE asset=? AND timeframe='D1'",
                (symbol,),
            ).fetchone()
            lane = authority.execute(
                "SELECT 1 FROM evidence_lanes WHERE asset=? AND timeframe=?",
                (symbol, interval),
            ).fetchone()
            if registration is None or lane is None:
                raise KeyError(f"commissioned evidence lane is unavailable: {symbol}:{interval}")
            schedule = schedule_for_lane(authority, symbol=symbol, timeframe=interval, after=observed)
            latest = _latest_bar(authority, symbol, interval)
            route_revision = authority_revision_for_lane(
                authority, symbol=symbol, timeframe=interval,
            )

        next_check = schedule.get("next_scheduled_acquisition")
        state = "READY" if next_check else "BLOCKED"
        row = {
            "asset": symbol,
            "timeframe": interval,
            "state": state,
            "next_expected_boundary_utc": str(next_check) if next_check else None,
            # A new lane with no canonical evidence must be eligible now.  An
            # explicit initial-fetch request wins for the same lane when one
            # is present, so this cannot create duplicate provider work.
            "next_check_at_utc": (
                observed.isoformat() if next_check and latest is None else str(next_check) if next_check else None
            ),
            "last_successful_bar_utc": latest,
            "last_outcome": "COMMISSIONED" if next_check else str(schedule.get("reason_code") or "SCHEDULE_UNAVAILABLE"),
            "provider_route_revision": route_revision,
            "calendar_or_session_revision": _schedule_revision(schedule),
            "priority": _priority_for(str(registration[0]), interval),
        }
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                existing = connection.execute(
                    "SELECT state,next_check_at_utc FROM lane_update_register WHERE asset=? AND timeframe=?",
                    (symbol, interval),
                ).fetchone()
                if existing is None:
                    self._insert(connection, row, observed)
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
        return {
            "asset": symbol, "timeframe": interval,
            "state": str(existing[0]) if existing is not None else state,
            "created": existing is None,
        }

    def claim_due(self, *, at: datetime, limit: int) -> list[dict[str, object]]:
        """Atomically claim only indexed normal/retry rows due at ``at``."""
        observed = normalized_utc(at).isoformat()
        if limit <= 0:
            return []
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                rows = connection.execute(
                    """
                    SELECT asset,timeframe,state,next_expected_boundary_utc,next_check_at_utc,
                           last_checked_boundary_utc,last_attempted_at_utc,last_successful_bar_utc,
                           last_outcome,retry_count,retry_not_before_utc,
                           provider_route_revision,calendar_or_session_revision,lane_state_version,
                           updated_at_utc,priority
                    FROM lane_update_register
                    WHERE state IN ('READY','RETRY')
                      AND next_check_at_utc IS NOT NULL
                      AND next_check_at_utc <= ?
                      AND (retry_not_before_utc IS NULL OR retry_not_before_utc <= ?)
                    ORDER BY priority,next_check_at_utc,asset,timeframe
                    LIMIT ?
                    """,
                    (observed, observed, int(limit)),
                ).fetchall()
                for row in rows:
                    connection.execute(
                        """UPDATE lane_update_register
                           SET state='RUNNING',last_attempted_at_utc=?,updated_at_utc=?,
                               lane_state_version=lane_state_version+1
                           WHERE asset=? AND timeframe=?""",
                        (observed, observed, row[0], row[1]),
                    )
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
        return [_row_dict(row) for row in rows]

    def next_due_at(self) -> datetime | None:
        with self._connection() as connection:
            row = connection.execute(
                """SELECT min(next_check_at_utc) FROM lane_update_register
                   WHERE state IN ('READY','RETRY') AND next_check_at_utc IS NOT NULL"""
            ).fetchone()
        return _parse_utc(row[0] if row else None)

    def due_count(self, *, at: datetime | None = None) -> int:
        """Count dispatchable rows using the register's due-work index only."""
        observed = normalized_utc(at).isoformat()
        with self._connection() as connection:
            row = connection.execute(
                """SELECT count(*) FROM lane_update_register
                   WHERE state IN ('READY','RETRY')
                     AND next_check_at_utc IS NOT NULL
                     AND next_check_at_utc <= ?
                     AND (retry_not_before_utc IS NULL OR retry_not_before_utc <= ?)""",
                (observed, observed),
            ).fetchone()
        return int(row[0] if row else 0)

    def summary(self) -> dict[str, object]:
        with self._connection() as connection:
            states = dict(connection.execute(
                "SELECT state,count(*) FROM lane_update_register GROUP BY state"
            ).fetchall())
            next_due = connection.execute(
                """SELECT min(next_check_at_utc) FROM lane_update_register
                   WHERE state IN ('READY','RETRY') AND next_check_at_utc IS NOT NULL"""
            ).fetchone()[0]
        return {
            "contract": REGISTER_CONTRACT,
            "next_due_check": next_due,
            "ready_count": int(states.get("READY", 0)),
            "retrying_count": int(states.get("RETRY", 0)),
            "blocked_count": int(states.get("BLOCKED", 0)),
            "paused_count": int(states.get("PAUSED", 0)),
            "running_count": int(states.get("RUNNING", 0)),
        }

    def rows(self) -> list[dict[str, object]]:
        """Return bounded operational rows for the explicit audit workflow."""
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT asset,timeframe,state,next_expected_boundary_utc,next_check_at_utc,
                           last_checked_boundary_utc,last_attempted_at_utc,last_successful_bar_utc,
                           last_outcome,retry_count,retry_not_before_utc,provider_route_revision,
                           calendar_or_session_revision,lane_state_version,updated_at_utc,priority
                     FROM lane_update_register ORDER BY asset,timeframe"""
            ).fetchall()
        return [_row_dict(row) for row in rows]

    def dashboard_rows(self, *, limit: int = 24) -> list[dict[str, object]]:
        """Return the next small operational horizon for the live dashboard.

        This is an indexed read of the register only.  It deliberately does
        not rebuild lane freshness, decode the operational journal, or load
        the entire estate into the desktop app.
        """
        if limit <= 0:
            return []
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT asset,timeframe,state,next_expected_boundary_utc,next_check_at_utc,
                          last_checked_boundary_utc,last_attempted_at_utc,last_successful_bar_utc,
                          last_outcome,retry_count,retry_not_before_utc,updated_at_utc,priority
                   FROM lane_update_register
                   ORDER BY CASE state
                                WHEN 'RUNNING' THEN 0
                                WHEN 'RETRY' THEN 1
                                WHEN 'BLOCKED' THEN 2
                                WHEN 'READY' THEN 3
                                ELSE 4
                            END,
                            CASE WHEN next_check_at_utc IS NULL THEN 1 ELSE 0 END,
                            next_check_at_utc,priority,asset,timeframe
                   LIMIT ?""",
                (int(limit),),
            ).fetchall()
        return [_row_dict(row) for row in rows]

    def blocked_rows(self, *, limit: int = 100) -> list[dict[str, object]]:
        """Return bounded, actionable block findings from the runtime index."""
        if limit <= 0:
            return []
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT asset,timeframe,state,next_expected_boundary_utc,next_check_at_utc,
                          last_checked_boundary_utc,last_attempted_at_utc,last_successful_bar_utc,
                          last_outcome,retry_count,retry_not_before_utc,updated_at_utc,priority
                   FROM lane_update_register
                   WHERE state='BLOCKED'
                   ORDER BY priority,updated_at_utc DESC,asset,timeframe
                   LIMIT ?""",
                (int(limit),),
            ).fetchall()
        return [_row_dict(row) for row in rows]

    def audit_due(self, *, at: datetime | None = None) -> bool:
        """Whether the bounded weekly maintenance audit is due."""
        observed = normalized_utc(at)
        with self._connection() as connection:
            raw = self._meta(connection, "last_audit_at_utc")
        prior = _parse_utc(raw)
        return prior is None or observed - prior >= timedelta(days=7)

    def record_audit(self, *, at: datetime | None = None, reason: str) -> None:
        observed = normalized_utc(at)
        with self._connection() as connection:
            self._set_meta(connection, "last_audit_at_utc", observed.isoformat())
            self._set_meta(connection, "last_audit_reason", reason)

    def record_checked(self, *, asset: str, timeframe: str, checked_boundary: str, at: datetime | None = None, outcome: str = "NO_CHANGE") -> dict[str, object]:
        """Complete a normal boundary once and calculate its next approved check."""
        observed = normalized_utc(at)
        # Provider-route authority is fixed by the explicit register audit.
        # Re-scanning the authority-event JSON ledger on every completed
        # boundary turns ordinary M5 upkeep into a multi-gigabyte query.  A
        # route change is observed by the next weekly/operator audit, which
        # refreshes this stored revision before any later work is claimed.
        with self._connection() as runtime:
            prior = runtime.execute(
                """SELECT provider_route_revision FROM lane_update_register
                   WHERE asset=? AND timeframe=?""",
                (asset, timeframe),
            ).fetchone()
        if prior is None:
            raise KeyError(f"unknown lane update register row: {asset}:{timeframe}")
        with open_read_only(self.database_path) as authority:
            schedule = schedule_for_lane(
                authority, symbol=asset, timeframe=timeframe, after=observed
            )
            next_check = schedule.get("next_scheduled_acquisition")
            calendar_revision = _schedule_revision(schedule)
            successful_bar = _latest_bar(authority, asset, timeframe)
        if not next_check:
            return self.block(asset=asset, timeframe=timeframe, reason=str(schedule.get("reason_code") or "SCHEDULE_UNAVAILABLE"), at=observed)
        self._update(
            asset, timeframe,
            state="READY", next_expected_boundary_utc=str(next_check), next_check_at_utc=str(next_check),
            last_checked_boundary_utc=checked_boundary, last_successful_bar_utc=successful_bar,
            last_outcome=outcome, retry_count=0, retry_not_before_utc=None,
            provider_route_revision=prior[0], calendar_or_session_revision=calendar_revision,
            updated_at_utc=observed.isoformat(),
        )
        return {"state": "READY", "next_check_at_utc": str(next_check)}

    def retry(self, *, asset: str, timeframe: str, reason: str, at: datetime | None = None, not_before: datetime | None = None) -> dict[str, object]:
        observed = normalized_utc(at)
        with self._connection() as connection:
            row = connection.execute(
                "SELECT retry_count,next_expected_boundary_utc FROM lane_update_register WHERE asset=? AND timeframe=?",
                (asset, timeframe),
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown lane update register row: {asset}:{timeframe}")
        retries = int(row[0]) + 1
        retry_at = normalized_utc(not_before) if not_before else observed + timedelta(seconds=_retry_delay(asset, timeframe, retries))
        self._update(
            asset, timeframe, state="RETRY", next_check_at_utc=retry_at.isoformat(),
            last_outcome=reason, retry_count=retries, retry_not_before_utc=retry_at.isoformat(),
            updated_at_utc=observed.isoformat(),
        )
        return {"state": "RETRY", "retry_count": retries, "next_check_at_utc": retry_at.isoformat()}

    def block(self, *, asset: str, timeframe: str, reason: str, at: datetime | None = None) -> dict[str, object]:
        observed = normalized_utc(at)
        self._update(
            asset, timeframe, state="BLOCKED", next_check_at_utc=None,
            last_outcome=reason, retry_not_before_utc=None, updated_at_utc=observed.isoformat(),
        )
        return {"state": "BLOCKED", "reason": reason}

    def pause(self, *, asset: str, timeframe: str, at: datetime | None = None) -> None:
        self._update(asset, timeframe, state="PAUSED", updated_at_utc=normalized_utc(at).isoformat())

    def resume(self, *, asset: str, timeframe: str, at: datetime | None = None) -> dict[str, object]:
        """Clear an operator pause at the lane's next valid approved boundary."""
        observed = normalized_utc(at)
        with open_read_only(self.database_path) as authority:
            schedule = schedule_for_lane(authority, symbol=asset, timeframe=timeframe, after=observed)
            freshness = assess_lane_freshness(
                authority, symbol=asset, timeframe=timeframe, as_of=observed
            )
        next_check = schedule.get("next_scheduled_acquisition")
        if not next_check:
            return self.block(asset=asset, timeframe=timeframe, reason=str(schedule.get("reason_code") or "SCHEDULE_UNAVAILABLE"), at=observed)
        needs_catch_up = (
            freshness.get("state") == "Behind"
            or freshness.get("latest_canonical_observation") is None
        )
        self._update(
            asset, timeframe, state="READY", next_expected_boundary_utc=str(next_check),
            # Resume preserves the calendar boundary, but an overdue lane is
            # eligible immediately.  Waiting for its next future boundary
            # silently leaves a paused catch-up lane stale.
            next_check_at_utc=observed.isoformat() if needs_catch_up else str(next_check), retry_not_before_utc=None,
            last_outcome="PAUSE_CLEARED_CATCH_UP" if needs_catch_up else "PAUSE_CLEARED",
            updated_at_utc=observed.isoformat(),
        )
        return {
            "state": "READY",
            "next_check_at_utc": observed.isoformat() if needs_catch_up else str(next_check),
        }

    def recover_running(self, *, at: datetime | None = None) -> int:
        """Make interrupted work retryable without reconstructing the estate."""
        observed = normalized_utc(at)
        with self._connection() as connection:
            cursor = connection.execute(
                """UPDATE lane_update_register SET state='RETRY',next_check_at_utc=?,
                   retry_not_before_utc=?,last_outcome='RECOVERY_INTERRUPTED',
                   updated_at_utc=?,lane_state_version=lane_state_version+1 WHERE state='RUNNING'""",
                (observed.isoformat(), observed.isoformat(), observed.isoformat()),
            )
            return int(cursor.rowcount)

    def _initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA synchronous=FULL;
                CREATE TABLE IF NOT EXISTS register_meta (
                    key TEXT PRIMARY KEY, value TEXT NOT NULL
                ) STRICT;
                CREATE TABLE IF NOT EXISTS lane_update_register (
                    asset TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('READY','RETRY','BLOCKED','PAUSED','RUNNING')),
                    next_expected_boundary_utc TEXT,
                    next_check_at_utc TEXT,
                    last_checked_boundary_utc TEXT,
                    last_attempted_at_utc TEXT,
                    last_successful_bar_utc TEXT,
                    last_outcome TEXT,
                    retry_count INTEGER NOT NULL DEFAULT 0 CHECK(retry_count >= 0),
                    retry_not_before_utc TEXT,
                    provider_route_revision TEXT,
                    calendar_or_session_revision TEXT,
                    lane_state_version INTEGER NOT NULL DEFAULT 0 CHECK(lane_state_version >= 0),
                    updated_at_utc TEXT NOT NULL,
                    priority INTEGER NOT NULL DEFAULT 100,
                    PRIMARY KEY(asset,timeframe)
                ) STRICT, WITHOUT ROWID;
                CREATE INDEX IF NOT EXISTS lane_update_register_due
                    ON lane_update_register(state,next_check_at_utc,priority,asset,timeframe);
                """
            )
            # Correct registers created by the original v1 writer, which
            # accidentally treated the valid D1 priority (0) as false and
            # stored 100. This is scheduler-side metadata only and is
            # deliberately idempotent for a live service restart.
            if self._meta(connection, "priority_revision") != REGISTER_PRIORITY_REVISION:
                connection.execute(
                    """UPDATE lane_update_register
                       SET priority=CASE timeframe
                           WHEN 'D1' THEN 0
                           WHEN 'H1' THEN 10
                           WHEN 'M30' THEN 20
                           WHEN 'M5' THEN 30
                           ELSE 100
                       END"""
                )
                self._set_meta(connection, "priority_revision", REGISTER_PRIORITY_REVISION)
            self._set_meta(connection, "contract", REGISTER_CONTRACT)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=5000")
            yield connection
        finally:
            connection.close()

    @staticmethod
    def _meta(connection: sqlite3.Connection, key: str) -> str | None:
        row = connection.execute("SELECT value FROM register_meta WHERE key=?", (key,)).fetchone()
        return str(row[0]) if row else None

    @staticmethod
    def _set_meta(connection: sqlite3.Connection, key: str, value: str) -> None:
        connection.execute(
            "INSERT INTO register_meta(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

    @staticmethod
    def _insert(connection: sqlite3.Connection, row: dict[str, object], observed: datetime) -> None:
        connection.execute(
            """INSERT INTO lane_update_register(
                 asset,timeframe,state,next_expected_boundary_utc,next_check_at_utc,
                 last_checked_boundary_utc,last_attempted_at_utc,last_successful_bar_utc,
                 last_outcome,retry_count,retry_not_before_utc,provider_route_revision,
                 calendar_or_session_revision,lane_state_version,updated_at_utc,priority
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                row["asset"], row["timeframe"], row["state"], row.get("next_expected_boundary_utc"),
                row.get("next_check_at_utc"), row.get("last_checked_boundary_utc"),
                row.get("last_attempted_at_utc"), row.get("last_successful_bar_utc"),
                row.get("last_outcome"), int(row.get("retry_count", 0) or 0),
                row.get("retry_not_before_utc"), row.get("provider_route_revision"),
                row.get("calendar_or_session_revision"), int(row.get("lane_state_version", 0) or 0),
                str(row.get("updated_at_utc") or observed.isoformat()),
                # Priority zero is meaningful (D1), not an absent value.
                int(row["priority"]) if row.get("priority") is not None else 100,
            ),
        )

    def _update(self, asset: str, timeframe: str, **values: object) -> None:
        if not values:
            return
        assignments = ",".join(f"{key}=?" for key in values)
        with self._connection() as connection:
            cursor = connection.execute(
                f"UPDATE lane_update_register SET {assignments},lane_state_version=lane_state_version+1 WHERE asset=? AND timeframe=?",
                (*values.values(), asset, timeframe),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"unknown lane update register row: {asset}:{timeframe}")


def _latest_bar(connection: sqlite3.Connection, asset: str, timeframe: str) -> str | None:
    row = connection.execute(
        "SELECT max(CASE WHEN ?='D1' THEN open_time_utc ELSE close_time_utc END) FROM bars WHERE asset=? AND timeframe=?",
        (timeframe, asset, timeframe),
    ).fetchone()
    return datetime.fromtimestamp(int(row[0]), UTC).isoformat() if row and row[0] is not None else None


def _schedule_revision(schedule: dict[str, object]) -> str:
    source = json.dumps({
        key: schedule.get(key) for key in ("calendar_id", "timezone", "session_close_rule", "calendar_status")
    }, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(source.encode()).hexdigest()


def _priority_for(asset_class: str, timeframe: str) -> int:
    # Larger cadence leads inside a normal due set; market class is an
    # ordering tie-breaker only and never widens selection beyond due rows.
    return {"D1": 0, "H1": 10, "M30": 20, "M5": 30}.get(timeframe.upper(), 100)


def _retry_delay(asset: str, timeframe: str, retry_count: int) -> int:
    base = min(15 * 60, 5 * (2 ** min(retry_count - 1, 8)))
    digest = hashlib.sha256(f"{asset}:{timeframe}:{retry_count}".encode()).digest()
    return base + int(digest[0] % max(1, base // 5 + 1))


def _parse_utc(value: object) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _row_dict(row: sqlite3.Row) -> dict[str, object]:
    return {str(key): row[key] for key in row.keys()}


def _preserved_values(prior: dict[str, object] | None) -> dict[str, object]:
    if not prior:
        return {}
    return {
        "state": prior["state"],
        "next_expected_boundary_utc": prior["next_expected_boundary_utc"],
        "next_check_at_utc": prior["next_check_at_utc"],
        "last_checked_boundary_utc": prior["last_checked_boundary_utc"],
        "last_attempted_at_utc": prior["last_attempted_at_utc"],
        "last_successful_bar_utc": prior["last_successful_bar_utc"],
        "last_outcome": prior["last_outcome"],
        "retry_count": prior["retry_count"],
        "retry_not_before_utc": prior["retry_not_before_utc"],
        "lane_state_version": prior["lane_state_version"],
    }
