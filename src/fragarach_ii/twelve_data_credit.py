"""Cross-process Twelve Data credit-window and dispatch authority.

The authority is credential-scoped because every Twelve Data endpoint using the
same plan shares one cumulative allowance.  Only a SHA-256 credential
fingerprint is used in the local path; credentials and request targets are
never persisted.
"""

from __future__ import annotations

import email.utils
import fcntl
import hashlib
import json
import math
import os
import tempfile
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Callable


Clock = Callable[[], datetime]
Sleeper = Callable[[float], None]
_LOCAL_GUARDS: dict[str, threading.RLock] = {}
_LOCAL_GUARDS_LOCK = threading.Lock()


def credit_authority_values(config_path: str | Path | None = None) -> dict[str, object]:
    path = Path(config_path) if config_path else (
        Path(__file__).resolve().parents[2] / "config/providers/acquisition_orchestrator.v1.json"
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    row = next(
        item for item in payload.get("providers", [])
        if str(item.get("provider", "")).upper() == "TWELVE_DATA"
    )
    costs = {
        str(key): max(1, int(value))
        for key, value in dict(row.get("endpoint_credit_costs", {})).items()
    }
    return {
        "plan_limit": int(row["request_limit"]),
        "operational_limit": int(row["operational_limit"]),
        "window_seconds": int(row["request_window_seconds"]),
        "dispatch_interval_seconds": float(row["dispatch_interval_seconds"]),
        "endpoint_credit_costs": costs,
    }


def endpoint_credit_cost(endpoint: str, config_path: str | Path | None = None) -> int:
    values = credit_authority_values(config_path)
    costs = values["endpoint_credit_costs"]
    assert isinstance(costs, dict)
    return int(costs.get(endpoint, costs.get("default", 1)))


def authority_path_for_credential(
    credential: str,
    *,
    root: str | Path | None = None,
) -> Path:
    fingerprint = hashlib.sha256(credential.encode("utf-8")).hexdigest()
    configured = os.environ.get("FRAGARACH_TWELVE_DATA_CREDIT_ROOT")
    base = Path(root or configured or (
        Path.home() / "Library" / "Application Support" / "Fragarach II" / "Twelve Data Credit Authority"
    )).expanduser()
    return base / f"{fingerprint}.json"


class TwelveDataCreditAuthority:
    """Atomic fixed-window reservations with provider-wide dispatch pacing."""

    def __init__(
        self,
        *,
        credential: str,
        plan_limit: int,
        operational_limit: int,
        window_seconds: int,
        dispatch_interval_seconds: float,
        path: str | Path | None = None,
        clock: Clock | None = None,
        sleeper: Sleeper = time.sleep,
    ) -> None:
        if not credential:
            raise ValueError("Twelve Data credit authority requires a credential")
        if not 0 < operational_limit <= plan_limit:
            raise ValueError("operational limit must be positive and no greater than plan limit")
        if window_seconds <= 0 or dispatch_interval_seconds < 0:
            raise ValueError("credit window and dispatch cadence must be valid")
        self.plan_limit = int(plan_limit)
        self.operational_limit = int(operational_limit)
        self.limit = self.operational_limit
        self.window_seconds = float(window_seconds)
        self.dispatch_interval_seconds = float(dispatch_interval_seconds)
        self.path = Path(path or authority_path_for_credential(credential)).expanduser().resolve()
        self.lock_path = Path(f"{self.path}.lock")
        self._clock = clock or (lambda: datetime.now(UTC))
        self._sleeper = sleeper
        with _LOCAL_GUARDS_LOCK:
            self._guard = _LOCAL_GUARDS.setdefault(str(self.lock_path), threading.RLock())

    def inspect(self, request_count: int = 0, **_: object) -> dict[str, object]:
        with self._locked_state() as state:
            return self._projection(state, request_count=request_count)

    def reserve(
        self,
        request_count: int,
        *,
        endpoint: str = "time_series",
        **_: object,
    ) -> dict[str, object]:
        if request_count <= 0:
            raise ValueError("credit cost must be positive")
        with self._locked_state() as state:
            now = self._now()
            blocked_until = self._datetime(state.get("rate_limit_until"))
            if blocked_until and blocked_until > now:
                return self._projection(state, request_count=request_count) | {
                    "eligible": False,
                    "reason": "PROVIDER_429",
                    "next_available": blocked_until.isoformat(),
                }
            committed = int(state["credits_reserved"]) + int(state["credits_consumed"])
            operational_remaining = max(0, self.operational_limit - committed)
            hard_remaining = max(0, self.plan_limit - committed)
            if request_count > operational_remaining or request_count > hard_remaining:
                return self._projection(state, request_count=request_count) | {
                    "eligible": False,
                    "reason": "CREDIT_WINDOW",
                    "next_available": state["window_ends_at"],
                }
            next_dispatch = self._datetime(state.get("next_dispatch_at")) or now
            dispatch_at = max(now, next_dispatch)
            window_end = self._datetime(state["window_ends_at"])
            assert window_end is not None
            final_slot = dispatch_at + timedelta(
                seconds=self.dispatch_interval_seconds * max(0, request_count - 1)
            )
            if final_slot >= window_end:
                return self._projection(state, request_count=request_count) | {
                    "eligible": False,
                    "reason": "CREDIT_WINDOW",
                    "next_available": window_end.isoformat(),
                }
            identifier = f"reservation-{uuid.uuid4().hex}"
            reservation = {
                "id": identifier,
                "endpoint": endpoint,
                "cost": request_count,
                "remaining": request_count,
                "reserved_at": now.isoformat(),
                "dispatch_at": dispatch_at.isoformat(),
            }
            state["reservations"].append(reservation)
            state["credits_reserved"] = int(state["credits_reserved"]) + request_count
            state["next_dispatch_at"] = (
                dispatch_at + timedelta(seconds=self.dispatch_interval_seconds * request_count)
            ).isoformat()
            return self._projection(state) | {
                "eligible": True,
                "reserved": request_count,
                "reservation_id": identifier,
                "dispatch_at": reservation["dispatch_at"],
                "reason": None,
            }

    def dispatch(self, reservation_id: str, request_count: int = 1) -> dict[str, object]:
        if request_count <= 0:
            raise ValueError("dispatch credit cost must be positive")
        with self._locked_state() as state:
            reservation = self._reservation(state, reservation_id)
            dispatch_at = self._datetime(reservation["dispatch_at"]) or self._now()
        delay = max(0.0, (dispatch_at - self._now()).total_seconds())
        if delay:
            self._sleeper(delay)
        with self._locked_state() as state:
            reservation = self._reservation(state, reservation_id)
            remaining = int(reservation["remaining"])
            if request_count > remaining:
                raise ValueError("dispatch exceeds reserved Twelve Data credits")
            now = self._now()
            reservation["remaining"] = remaining - request_count
            reservation["dispatch_at"] = (
                dispatch_at + timedelta(seconds=self.dispatch_interval_seconds * request_count)
            ).isoformat()
            state["credits_reserved"] = int(state["credits_reserved"]) - request_count
            state["credits_consumed"] = int(state["credits_consumed"]) + request_count
            state["dispatches"].append({
                "at": now.isoformat(),
                "endpoint": reservation["endpoint"],
                "cost": request_count,
            })
            if int(reservation["remaining"]) == 0:
                state["reservations"].remove(reservation)
            return {
                "dispatched": request_count,
                "reservation_id": reservation_id,
                "credits_consumed": state["credits_consumed"],
            }

    def release(self, reservation_id: str, request_count: int | None = None) -> int:
        with self._locked_state() as state:
            try:
                reservation = self._reservation(state, reservation_id)
            except ValueError:
                return 0
            remaining = int(reservation["remaining"])
            released = remaining if request_count is None else min(remaining, max(0, request_count))
            reservation["remaining"] = remaining - released
            state["credits_reserved"] = int(state["credits_reserved"]) - released
            if int(reservation["remaining"]) == 0:
                state["reservations"].remove(reservation)
            return released

    def record_429(
        self,
        *,
        response_body: bytes,
        retry_after: str | None,
        endpoint: str,
    ) -> dict[str, object]:
        with self._locked_state() as state:
            now = self._now()
            resume = self._retry_after(retry_after, now)
            if resume is None:
                resume = self._datetime(state["window_ends_at"])
            assert resume is not None
            state["last_429_at"] = now.isoformat()
            state["rate_limit_until"] = resume.isoformat()
            state["last_429_evidence"] = {
                "http_status": 429,
                "response_body": response_body[:2048].decode("utf-8", errors="replace"),
                "retry_after": retry_after,
                "endpoint": endpoint,
                "observed_at": now.isoformat(),
                "credit_window": {
                    "window_started_at": state["window_started_at"],
                    "window_ends_at": state["window_ends_at"],
                    "credits_reserved": state["credits_reserved"],
                    "credits_consumed": state["credits_consumed"],
                },
            }
            return self._projection(state)

    def persisted_events(self) -> list[dict[str, object]]:
        return list(self.inspect().get("dispatches", []))

    def persisted_reservations(self) -> list[dict[str, object]]:
        return list(self.inspect().get("reservations", []))

    def _projection(self, state: dict[str, object], request_count: int = 0) -> dict[str, object]:
        committed = int(state["credits_reserved"]) + int(state["credits_consumed"])
        remaining = max(0, self.operational_limit - committed)
        now = self._now()
        started = self._datetime(state["window_started_at"]) or now
        elapsed = max(1.0, (now - started).total_seconds())
        dispatch_rate = min(
            float(self.operational_limit) * 60.0 / self.window_seconds,
            int(state["credits_consumed"]) * 60.0 / elapsed,
        )
        blocked_until = self._datetime(state.get("rate_limit_until"))
        eligible = request_count <= remaining and not (blocked_until and blocked_until > now)
        return {
            "eligible": eligible,
            "reason": None if eligible else ("PROVIDER_429" if blocked_until and blocked_until > now else "CREDIT_WINDOW"),
            "plan_limit": self.plan_limit,
            "operational_limit": self.operational_limit,
            "window_started_at": state["window_started_at"],
            "window_ends_at": state["window_ends_at"],
            "credits_reserved": int(state["credits_reserved"]),
            "credits_consumed": int(state["credits_consumed"]),
            "credits_remaining": remaining,
            "hard_credits_remaining": max(0, self.plan_limit - committed),
            "next_dispatch_at": state.get("next_dispatch_at"),
            "last_429_at": state.get("last_429_at"),
            "rate_limit_until": state.get("rate_limit_until"),
            "calls_used": int(state["credits_consumed"]),
            "calls_available": remaining,
            "active_reservations": len(state["reservations"]),
            "reserved_calls": int(state["credits_reserved"]),
            "queue_calls_used": int(state["credits_consumed"]),
            "queue_calls_reserved": int(state["credits_reserved"]),
            "queue_ceiling": self.operational_limit,
            "queue_available": remaining,
            "protected_capacity": self.plan_limit - self.operational_limit,
            "next_available": state["window_ends_at"] if not eligible else None,
            "requests_last_minute": sum(int(item["cost"]) for item in state["dispatches"]),
            "dispatch_rate_per_minute": round(dispatch_rate, 3),
            "dispatches": list(state["dispatches"]),
            "reservations": list(state["reservations"]),
        }

    def _initial_state(self, now: datetime) -> dict[str, object]:
        epoch = math.floor(now.timestamp() / self.window_seconds) * self.window_seconds
        started = datetime.fromtimestamp(epoch, UTC)
        return {
            "plan_limit": self.plan_limit,
            "operational_limit": self.operational_limit,
            "window_started_at": started.isoformat(),
            "window_ends_at": (started + timedelta(seconds=self.window_seconds)).isoformat(),
            "credits_reserved": 0,
            "credits_consumed": 0,
            "credits_remaining": self.operational_limit,
            "next_dispatch_at": now.isoformat(),
            "last_429_at": None,
            "rate_limit_until": None,
            "reservations": [],
            "dispatches": [],
        }

    def _normalize(self, state: object) -> dict[str, object]:
        now = self._now()
        if not isinstance(state, dict):
            return self._initial_state(now)
        window_end = self._datetime(state.get("window_ends_at"))
        if window_end is None or window_end <= now:
            fresh = self._initial_state(now)
            fresh["last_429_at"] = state.get("last_429_at")
            carried = []
            max_age = timedelta(seconds=max(300.0, self.window_seconds * 5.0))
            for item in state.get("reservations", []):
                if not isinstance(item, dict):
                    continue
                try:
                    remaining = max(0, int(item.get("remaining", 0)))
                except (TypeError, ValueError):
                    continue
                reserved_at = self._datetime(item.get("reserved_at"))
                if remaining <= 0 or reserved_at is None or now - reserved_at > max_age:
                    continue
                carried_item = dict(item)
                dispatch_at = self._datetime(carried_item.get("dispatch_at")) or now
                carried_item["dispatch_at"] = max(dispatch_at, now).isoformat()
                carried.append(carried_item)
            if carried:
                fresh["reservations"] = carried
                fresh["credits_reserved"] = sum(int(item["remaining"]) for item in carried)
                fresh["credits_remaining"] = max(
                    0, self.operational_limit - int(fresh["credits_reserved"])
                )
                fresh["next_dispatch_at"] = max(
                    (str(item.get("dispatch_at")) for item in carried),
                    default=now.isoformat(),
                )
            return fresh
        state["plan_limit"] = self.plan_limit
        state["operational_limit"] = self.operational_limit
        reservations = [item for item in state.get("reservations", []) if isinstance(item, dict)]
        state["reservations"] = reservations
        state["credits_reserved"] = sum(max(0, int(item.get("remaining", 0))) for item in reservations)
        state["credits_consumed"] = max(0, int(state.get("credits_consumed", 0)))
        state["credits_remaining"] = max(
            0,
            self.operational_limit
            - int(state["credits_reserved"])
            - int(state["credits_consumed"]),
        )
        cutoff = now - timedelta(seconds=self.window_seconds)
        state["dispatches"] = [
            item for item in state.get("dispatches", [])
            if isinstance(item, dict) and (self._datetime(item.get("at")) or now) > cutoff
        ]
        blocked = self._datetime(state.get("rate_limit_until"))
        if blocked and blocked <= now:
            state["rate_limit_until"] = None
        state.setdefault("next_dispatch_at", now.isoformat())
        state.setdefault("last_429_at", None)
        return state

    class _StateContext:
        def __init__(self, authority: "TwelveDataCreditAuthority") -> None:
            self.authority = authority
            self.handle = None
            self.state: dict[str, object] | None = None

        def __enter__(self) -> dict[str, object]:
            authority = self.authority
            authority.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            authority._guard.acquire()
            self.handle = authority.lock_path.open("a+", encoding="utf-8")
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX)
            try:
                value = json.loads(authority.path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                value = {}
            self.state = authority._normalize(value)
            return self.state

        def __exit__(self, exc_type, exc, traceback) -> None:
            authority = self.authority
            try:
                if exc_type is None and self.state is not None:
                    self.state["credits_remaining"] = max(
                        0,
                        authority.operational_limit
                        - int(self.state["credits_reserved"])
                        - int(self.state["credits_consumed"]),
                    )
                    descriptor, temporary = tempfile.mkstemp(
                        prefix=f".{authority.path.name}.", dir=authority.path.parent
                    )
                    try:
                        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                            json.dump(self.state, output, sort_keys=True, separators=(",", ":"))
                            output.write("\n")
                            output.flush()
                            os.fsync(output.fileno())
                        os.chmod(temporary, 0o600)
                        os.replace(temporary, authority.path)
                    except BaseException:
                        Path(temporary).unlink(missing_ok=True)
                        raise
            finally:
                assert self.handle is not None
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
                self.handle.close()
                authority._guard.release()

    def _locked_state(self) -> "TwelveDataCreditAuthority._StateContext":
        return self._StateContext(self)

    @staticmethod
    def _reservation(state: dict[str, object], identifier: str) -> dict[str, object]:
        reservations = state["reservations"]
        assert isinstance(reservations, list)
        match = next((item for item in reservations if item.get("id") == identifier), None)
        if match is None:
            raise ValueError(f"unknown Twelve Data reservation: {identifier}")
        return match

    def _now(self) -> datetime:
        value = self._clock()
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    @staticmethod
    def _datetime(value: object) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value))
        except ValueError:
            return None
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)

    @staticmethod
    def _retry_after(value: str | None, now: datetime) -> datetime | None:
        if not value:
            return None
        try:
            return now + timedelta(seconds=max(0.0, float(value)))
        except ValueError:
            try:
                parsed = email.utils.parsedate_to_datetime(value)
            except (TypeError, ValueError):
                return None
            return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def authority_for_credential(
    credential: str,
    *,
    clock: Clock | None = None,
    sleeper: Sleeper = time.sleep,
    path: str | Path | None = None,
) -> TwelveDataCreditAuthority:
    values = credit_authority_values()
    return TwelveDataCreditAuthority(
        credential=credential,
        plan_limit=int(values["plan_limit"]),
        operational_limit=int(values["operational_limit"]),
        window_seconds=int(values["window_seconds"]),
        dispatch_interval_seconds=float(values["dispatch_interval_seconds"]),
        path=path,
        clock=clock,
        sleeper=sleeper,
    )


def credited_send(
    credential: str,
    *,
    endpoint: str,
    send: Callable[[], object],
    clock: Clock | None = None,
    sleeper: Sleeper = time.sleep,
) -> object:
    """Reserve, pace, consume, and execute one endpoint request."""

    authority = authority_for_credential(credential, clock=clock, sleeper=sleeper)
    cost = endpoint_credit_cost(endpoint)
    reservation = authority.reserve(cost, endpoint=endpoint)
    if not reservation["eligible"]:
        raise RuntimeError(
            f"TWELVEDATA_CREDIT_WINDOW_EXHAUSTED:{reservation.get('next_available')}"
        )
    authority.dispatch(str(reservation["reservation_id"]), cost)
    response = send()
    if int(getattr(response, "status", 0) or 0) == 429:
        header = getattr(response, "header", None)
        retry_after = header("retry-after") if callable(header) else None
        authority.record_429(
            response_body=bytes(getattr(response, "body", b"")),
            retry_after=retry_after,
            endpoint=endpoint,
        )
    return response
