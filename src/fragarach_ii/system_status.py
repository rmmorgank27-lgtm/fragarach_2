"""Truth Authority-owned ``bruce.system-status.v1`` publication.

This projection reads only Fragarach_2's governed catalogue, provider-route,
lane-state, and scheduler-monitor facts. It never inspects consumer processes,
recalculates Truth scores, or promotes a provider fallback into authority.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Any, Mapping


SCHEMA = "bruce.system-status.v1"
HEARTBEAT_BUDGET_SECONDS = 15
TRUTH_FRESHNESS_SECONDS = 36 * 3_600
TRUTH_FAILURE_SECONDS = 72 * 3_600
AFFECTED_CONSUMERS = ["Gator", "Morphix", "Kevin", "Bruce", "Fidel"]
_FACT_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_FACT_LOCK = threading.Lock()


def _stamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _parse(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    except ValueError:
        return None


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def _authority_facts(database: Path, monitor: Mapping[str, Any], *, force: bool = False) -> dict[str, Any]:
    key = str(database.resolve())
    with _FACT_LOCK:
        cached = _FACT_CACHE.get(key)
        if cached and cached[1].get("registration_count") and not force and time.monotonic() - cached[0] < 60:
            return dict(cached[1])
    provider_facts_path = Path(f"{database}.provider-facts.json")
    provider_facts = json.loads(provider_facts_path.read_text(encoding="utf-8"))
    mappings = provider_facts.get("mappings") if isinstance(provider_facts, dict) else {}
    mappings = mappings if isinstance(mappings, dict) else {}
    providers: dict[str, dict[str, Any]] = {}
    symbols: set[str] = set()
    for raw in mappings.values():
        if not isinstance(raw, dict):
            continue
        provider = str(raw.get("provider") or "").upper()
        symbol = str(raw.get("provider_symbol") or "")
        canonical = str(raw.get("canonical_symbol") or "")
        mapping_state = str(raw.get("mapping_classification") or raw.get("mapping_class") or "").upper()
        reviewed = bool((raw.get("operator_decision") or {}).get("decision")) or mapping_state in {"REVIEWED_AUTHORITY", "EXACT_REPRESENTATION", "APPROVED_PROVIDER_ALIAS"}
        if not provider or not symbol or not reviewed:
            continue
        symbols.add(canonical)
        route = providers.setdefault(provider, {"lanes": 0, "contracts": set(), "last_refresh": None, "authoritative_mapping": True})
        route["lanes"] += 1
        route["contracts"].update(str(key) for key in (raw.get("timeframe_capabilities") or {}).keys())
        verified = raw.get("last_verified") or raw.get("effective_time")
        route["last_refresh"] = max(filter(None, [route["last_refresh"], verified]), default=None)
    register = monitor.get("register") if isinstance(monitor.get("register"), dict) else {}
    registration_count = sum(int(register.get(key, 0) or 0) for key in ("ready_count", "retrying_count", "blocked_count", "paused_count", "running_count"))
    execution = monitor.get("execution") if isinstance(monitor.get("execution"), dict) else {}
    latest = execution.get("completed_at") if int(execution.get("canonical_advanced_count", 0) or 0) > 0 else None
    lookup_failures = provider_facts.get("lookup_failures") if isinstance(provider_facts, dict) else {}
    facts = {
        "registration_count": registration_count,
        "symbol_count": len(symbols),
        "registered_count": registration_count,
        "missing_routes": len(lookup_failures) if isinstance(lookup_failures, dict) else 0,
        "providers": {
            provider: {**value, "contracts": sorted(value["contracts"])}
            for provider, value in providers.items()
        },
        "latest_truth_refresh": latest,
    }
    if registration_count:
        with _FACT_LOCK:
            _FACT_CACHE[key] = (time.monotonic(), dict(facts))
    return facts


def _capability(
    capability_id: str, state: str, reason: str, *, last_good: str | None = None,
    next_expected: str | None = None, affected: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": capability_id,
        "state": state,
        "reason": reason,
        "lastGoodAt": last_good,
        "nextExpectedAt": next_expected,
        "affectedConsumers": affected or [],
    }


def _freshness_state(value: datetime | None, now: datetime) -> str:
    if value is None:
        return "ATTENTION"
    age = (now - value).total_seconds()
    return "FAILURE" if age > TRUTH_FAILURE_SECONDS else "ATTENTION" if age > TRUTH_FRESHNESS_SECONDS else "OPERATIONAL"


def build_truth_authority_status(
    database: Path,
    monitor: Mapping[str, Any],
    *, now: datetime | None = None,
    facts: Mapping[str, Any] | None = None,
    previous: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    observed = (now or datetime.now(UTC)).astimezone(UTC)
    capabilities: list[dict[str, Any]] = []
    heartbeat = _parse(monitor.get("heartbeat_time"))
    heartbeat_age = (observed - heartbeat).total_seconds() if heartbeat else float("inf")
    service_state = str(monitor.get("service_state") or "UNKNOWN")
    operational_health = str((monitor.get("operational_health") or {}).get("overall_operational_health") or "UNKNOWN")
    if service_state in {"STOPPED", "UNREACHABLE", "REPAIR_REQUIRED", "CRASH_LOOP_PROTECTED"}:
        lifecycle_state = "FAILURE"
    elif service_state != "RUNNING" or heartbeat_age > HEARTBEAT_BUDGET_SECONDS or operational_health == "STALLED":
        lifecycle_state = "ATTENTION"
    else:
        lifecycle_state = "OPERATIONAL"
    capabilities.append(_capability(
        "truth-service-lifecycle", lifecycle_state,
        f"Scheduler service is {service_state}; monitor health is {operational_health}; heartbeat budget is 15 seconds.",
        last_good=_stamp(heartbeat) if heartbeat else None,
        next_expected=str(monitor.get("next_run") or "") or None,
        affected=AFFECTED_CONSUMERS if lifecycle_state != "OPERATIONAL" else [],
    ))

    try:
        authority = dict(facts) if facts is not None else _authority_facts(database, monitor)
        authority_error = ""
    except (OSError, ValueError, json.JSONDecodeError) as error:
        authority = {}
        authority_error = str(error)

    registration_count = int(authority.get("registration_count", 0) or 0)
    registered_count = int(authority.get("registered_count", 0) or 0)
    missing_routes = int(authority.get("missing_routes", 0) or 0)
    if authority_error or (facts is None and not database.exists()):
        catalogue_state = "FAILURE"
        catalogue_reason = f"Governed catalogue/symbol truth is unavailable: {authority_error or 'authority database missing'}."
    elif registration_count == 0 or registered_count == 0:
        catalogue_state = "ATTENTION"
        catalogue_reason = "Owner lane register is recovering after service start; catalogue failure is not inferred."
    else:
        catalogue_state = "OPERATIONAL"
        catalogue_reason = f"Catalogue exposes {authority.get('symbol_count', 0)} governed symbols and {registered_count} registered lanes."
        if missing_routes:
            catalogue_reason += f" {missing_routes} unresolved reference lookups are retained for review and are not missing registered lanes."
    capabilities.append(_capability(
        "catalogue-symbol-truth", catalogue_state, catalogue_reason,
        last_good=str(authority.get("latest_truth_refresh") or "") or None,
        affected=AFFECTED_CONSUMERS if catalogue_state != "OPERATIONAL" else [],
    ))

    providers = authority.get("providers") if isinstance(authority.get("providers"), dict) else {}
    if not providers:
        capabilities.append(_capability(
            "provider-route-unavailable", "FAILURE",
            "No complete provider route is present in the governed catalogue; provider process presence is not accepted as Truth.",
            affected=AFFECTED_CONSUMERS,
        ))
    for provider, raw in sorted(providers.items()):
        route = raw if isinstance(raw, dict) else {}
        refreshed = _parse(route.get("last_refresh"))
        route_state = "OPERATIONAL" if route.get("authoritative_mapping") else _freshness_state(refreshed, observed)
        if refreshed is None:
            route_reason = f"{provider} has {route.get('lanes', 0)} reviewed routes but no route-verification timestamp; current bar provenance is reported separately."
        elif provider == "YAHOO_FINANCE":
            route_reason = f"Yahoo fallback has {route.get('lanes', 0)} reviewed route mappings, last verified at {_stamp(refreshed)}; fallback/process availability alone is never authoritative, and current bar provenance is reported separately."
        else:
            route_reason = f"{provider} has {route.get('lanes', 0)} reviewed route mappings, last verified at {_stamp(refreshed)}; current bar provenance is reported separately."
        capabilities.append(_capability(
            f"provider-route-{provider.lower().replace('_', '-')}", route_state, route_reason,
            last_good=_stamp(refreshed) if refreshed else None,
            affected=AFFECTED_CONSUMERS if route_state != "OPERATIONAL" else [],
        ))
    if missing_routes:
        capabilities.append(_capability(
            "provider-route-unresolved-lookups", "OPERATIONAL",
            f"{missing_routes} unresolved provider reference lookups are retained for review; they do not represent missing registered lanes and no substitute route is inferred.",
        ))

    truth_refresh = _parse(authority.get("latest_truth_refresh"))
    if truth_refresh is None and previous:
        prior_capabilities = previous.get("capabilities") if isinstance(previous.get("capabilities"), list) else []
        prior_refresh = next((item.get("lastGoodAt") for item in prior_capabilities if isinstance(item, dict) and item.get("id") == "latest-provenance-backed-truth-refresh"), None)
        truth_refresh = _parse(prior_refresh)
    truth_state = _freshness_state(truth_refresh, observed)
    capabilities.append(_capability(
        "latest-provenance-backed-truth-refresh", truth_state,
        "Latest committed lane-state refresh is backed by a committed ingest run and provenance event within 36 hours."
        if truth_state == "OPERATIONAL" else
        "No current provenance-backed truth refresh exists within the 36-hour owner budget.",
        last_good=_stamp(truth_refresh) if truth_refresh else None,
        next_expected=str(monitor.get("next_run") or "") or None,
        affected=AFFECTED_CONSUMERS if truth_state != "OPERATIONAL" else [],
    ))

    blocked = int((monitor.get("operational_health") or {}).get("blocked_queue_depth", 0) or 0)
    if blocked:
        capabilities.append(_capability(
            "affected-consumers", "ATTENTION",
            f"{blocked} owner lanes are blocked; affected consumers are {', '.join(AFFECTED_CONSUMERS)}.",
            last_good=_stamp(truth_refresh) if truth_refresh else None,
            next_expected=str(monitor.get("next_run") or "") or None,
            affected=AFFECTED_CONSUMERS,
        ))

    state = _worst([item["state"] for item in capabilities])
    reason = (
        "Truth service, catalogue, provider routes, and provenance-backed refresh are within owner limits."
        if state == "OPERATIONAL" else
        next(item["reason"] for item in capabilities if item["state"] == state)
    )
    repository = Path(__file__).resolve().parents[2]
    revision, branch = _git_identity(repository)
    built_at = _stamp(datetime.fromtimestamp(Path(__file__).stat().st_mtime, UTC))
    current_good = max((item["lastGoodAt"] for item in capabilities if item.get("lastGoodAt")), default=None)
    retained_good = current_good or str((previous or {}).get("lastGoodAt") or "") or _stamp(observed)
    return {
        "schema": SCHEMA,
        "systemID": "fragarach_2",
        "displayName": "Fragarach_2 — Truth Authority",
        "lifecycle": "OPERATIONAL",
        "state": state,
        "reason": reason,
        "observedAt": _stamp(observed),
        "lastGoodAt": retained_good,
        "version": {
            "display": str(monitor.get("service_build") or "0.1.0"),
            "revision": revision, "branch": branch, "builtAt": built_at,
        },
        "capabilities": capabilities,
        "detailURL": "fragarach2://truth-authority",
        "remoteVisibility": "SUMMARY",
        "evidenceReferences": [
            "Fragarach_2 governed catalogue and symbol-truth registration",
            "Fragarach_2 provider route identity and committed ingest provenance",
            "Fragarach_2 scheduler operational monitor",
        ],
        "validation": {
            "state": "FAILED" if state == "FAILURE" else "OWNER_ASSESSED",
            "validatedAt": _stamp(observed),
            "detail": "Owner budgets: scheduler heartbeat 15 seconds; provenance-backed truth refresh and provider-route evidence Attention after 36 hours and Failure after 72 hours. No market score is produced.",
        },
    }


def publish_truth_authority_status(
    database: Path,
    monitor: Mapping[str, Any],
    *, now: datetime | None = None,
    destination: Path | None = None,
    facts: Mapping[str, Any] | None = None,
) -> Path:
    output = destination or database.parent / "fragarach-system-status.json"
    try:
        previous = json.loads(output.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        previous = {}
    payload = build_truth_authority_status(database, monitor, now=now, facts=facts, previous=previous)
    _atomic_json(output, payload)
    return output


def _git_identity(repository: Path) -> tuple[str, str]:
    try:
        head = (repository / ".git/HEAD").read_text(encoding="utf-8").strip()
    except OSError:
        return "", ""
    prefix = "ref: refs/heads/"
    if not head.startswith(prefix):
        return head[:12], ""
    branch = head[len(prefix):]
    try:
        revision = (repository / f".git/refs/heads/{branch}").read_text(encoding="utf-8").strip()[:12]
    except OSError:
        revision = ""
    return revision, branch


def _worst(states: list[str]) -> str:
    for state in ("FAILURE", "ATTENTION", "UNAVAILABLE"):
        if state in states:
            return state
    return "OPERATIONAL"
