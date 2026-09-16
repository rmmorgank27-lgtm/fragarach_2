"""SPEC-009C read-only operational truth for the complete authority estate."""

from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from .freshness import authority_revision_for_lane, normalized_utc
from .lane_freshness_service import lane_freshness_report
from .storage import open_read_only
from .truth_engine import (
    TRUTH_COMPONENT_WEIGHTS,
    TRUTH_ENGINE_VERSION,
    TRUTH_STATE_CONTRACT,
    truth_state_from_persisted_facts,
)
from .validation.price_outliers import assess_lane_price_quality
from .lane_commissioning import commissioned_lane_keys,eligibility_reason,market_policy,resolved_calendar_authority
from .acquisition_orchestrator import cached_acquisition_capability_projection
from .commissioning_authority import ALL_TIMEFRAMES,displayed_timeframes,project_required_lanes
from .scheduler_integrity import active_universe
from .provider_facts import load_provider_facts
from .lane_update_register import register_path


ESTATE_TRUTH_CONTRACT = "fragarach_ii.estate_truth_state.v1"
AUTHORITY_VERSION = 2


def estate_truth_state(
    database_path: str | Path, *, clock: Callable[[], datetime] | None = None
) -> dict[str, object]:
    """Build one estate snapshot from persisted authority."""

    authority_generated = normalized_utc(clock() if clock else None)
    authority_generated_text = authority_generated.isoformat()
    connection = open_read_only(database_path)
    try:
        rows = connection.execute(
            """
            WITH lane_ranges AS (
                SELECT asset,timeframe,count(*) AS bar_count,min(open_time_utc) AS earliest_bar,
                       max(open_time_utc) AS latest_bar,max(close_time_utc) AS latest_close
                FROM bars GROUP BY asset,timeframe
            )
            SELECT r.asset,l.timeframe,r.display_name,r.aliases_json,r.asset_class,
                   r.exchange_name,r.provider_id,r.provider_contract,r.provider_symbol,r.registration_status,
                   s.validation_summary,
                   (SELECT max(p.recorded_at) FROM provenance p
                    WHERE p.symbol=l.asset AND p.timeframe=l.timeframe) AS provider_freshness,
                   ranges.bar_count,ranges.earliest_bar,ranges.latest_bar,ranges.latest_close,
                   EXISTS(SELECT 1 FROM authority_events e
                     WHERE e.entity_kind='EVIDENCE_LANE'
                       AND (json_extract(e.canonical_payload,'$.body.legacy_key.asset')=l.asset
                         OR json_extract(e.canonical_payload,'$.body.asset')=l.asset)
                       AND (json_extract(e.canonical_payload,'$.body.legacy_key.timeframe')=l.timeframe
                         OR json_extract(e.canonical_payload,'$.body.timeframe')=l.timeframe)) AS ledger_bound
            FROM evidence_lanes l
            JOIN instrument_registrations r
              ON r.asset=l.asset AND r.timeframe=l.registration_timeframe
            LEFT JOIN lane_state s ON s.asset=l.asset AND s.timeframe=l.timeframe
            JOIN lane_ranges ranges ON ranges.asset=l.asset AND ranges.timeframe=l.timeframe
              AND NOT EXISTS (SELECT 1 FROM authority_events e WHERE json_extract(e.canonical_payload,'$.body.asset')=l.asset AND json_extract(e.canonical_payload,'$.body.timeframe')=l.timeframe
                AND (json_extract(e.canonical_payload,'$.body.lifecycle_state') LIKE 'RETIRED%' OR json_extract(e.canonical_payload,'$.body.lifecycle_state') LIKE 'QUARANTINED%' OR json_extract(e.canonical_payload,'$.body.lifecycle_state')='PERMANENTLY_REMOVED')
                AND NOT EXISTS(SELECT 1 FROM authority_events successor WHERE successor.supersedes_event_id=e.authority_event_id))
            ORDER BY r.asset,l.timeframe
            """
        ).fetchall()
        registered_lane_rows = connection.execute(
            """
            SELECT r.asset,l.timeframe,r.display_name,r.aliases_json,r.asset_class,
                   r.exchange_name,r.provider_id,r.provider_contract,r.provider_symbol,
                   r.registration_status,r.registered_at_utc,r.identity_json,
                   (SELECT count(*) FROM bars b
                    WHERE b.asset=l.asset AND b.timeframe=l.timeframe) AS bar_count,
                   (SELECT min(open_time_utc) FROM bars b
                    WHERE b.asset=l.asset AND b.timeframe=l.timeframe) AS first_observation,
                   (SELECT max(open_time_utc) FROM bars b
                    WHERE b.asset=l.asset AND b.timeframe=l.timeframe) AS latest_observation,
                   (SELECT max(p.recorded_at) FROM provenance p
                    WHERE p.symbol=l.asset AND p.timeframe=l.timeframe) AS provider_freshness
            FROM evidence_lanes l
            JOIN instrument_registrations r
              ON r.asset=l.asset AND r.timeframe=l.registration_timeframe
            WHERE r.timeframe='D1' AND r.registration_status LIKE 'REGISTERED_%'
              AND NOT EXISTS (SELECT 1 FROM authority_events e WHERE json_extract(e.canonical_payload,'$.body.asset')=r.asset
                AND (json_extract(e.canonical_payload,'$.body.lifecycle_state') LIKE 'RETIRED%' OR json_extract(e.canonical_payload,'$.body.lifecycle_state') LIKE 'QUARANTINED%' OR json_extract(e.canonical_payload,'$.body.lifecycle_state')='PERMANENTLY_REMOVED')
                AND NOT EXISTS(SELECT 1 FROM authority_events successor WHERE successor.supersedes_event_id=e.authority_event_id))
            ORDER BY r.asset,l.timeframe
            """
        ).fetchall()
        last_persisted_authority_change = connection.execute(
            """
            SELECT max(value) FROM (
              SELECT max(updated_at_utc) AS value FROM lane_state
              UNION ALL SELECT max(recorded_at_utc) FROM authority_events
              UNION ALL SELECT max(registered_at_utc) FROM instrument_registrations
            )
            """
        ).fetchone()[0]
        registrations=connection.execute("""WITH latest_d1_source AS (
          SELECT registration.asset,
                 json_extract(run.detail,'$.provider') provider,
                 json_extract(run.detail,'$.provider_contract') provider_contract,
                 json_extract(run.detail,'$.provider_symbol') provider_symbol
          FROM instrument_registrations registration
          JOIN bars b ON b.asset=registration.asset AND b.timeframe='D1'
            AND b.open_time_utc=(SELECT max(latest.open_time_utc) FROM bars latest
              WHERE latest.asset=registration.asset AND latest.timeframe='D1')
          JOIN ingest_runs run ON run.ingest_run_id=b.updated_by_ingest_run_id
          WHERE registration.timeframe='D1'
        )
        SELECT r.asset,r.asset_class,
          coalesce(r.provider_id,source.provider),
          coalesce(r.provider_contract,source.provider_contract),
          coalesce(r.provider_symbol,source.provider_symbol),
          r.representation_type,r.calendar_id,r.exchange_name,r.identity_json,r.registration_status
          FROM instrument_registrations r
          LEFT JOIN latest_d1_source source ON source.asset=r.asset
          WHERE r.timeframe='D1' AND r.registration_status LIKE 'REGISTERED_%'
          ORDER BY r.asset""").fetchall()
        lane_facts={(r[0],r[1]):r[2] for r in connection.execute("SELECT l.asset,l.timeframe,(SELECT count(*) FROM bars b WHERE b.asset=l.asset AND b.timeframe=l.timeframe) FROM evidence_lanes l").fetchall()}
        commissioned_lanes=commissioned_lane_keys(connection)
        latest_lane_sources = {
            (str(row[0]), str(row[1])): (row[2], row[3], row[4])
            for row in connection.execute(
                """SELECT lane.asset,lane.timeframe,
                          json_extract(run.detail,'$.provider'),
                          json_extract(run.detail,'$.provider_contract'),
                          json_extract(run.detail,'$.provider_symbol')
                   FROM evidence_lanes lane
                   JOIN bars b ON b.asset=lane.asset AND b.timeframe=lane.timeframe
                     AND b.open_time_utc=(
                       SELECT max(latest.open_time_utc) FROM bars latest
                       WHERE latest.asset=lane.asset AND latest.timeframe=lane.timeframe
                     )
                   JOIN ingest_runs run ON run.ingest_run_id=b.updated_by_ingest_run_id
                   WHERE json_extract(run.detail,'$.provider') IS NOT NULL"""
            ).fetchall()
            if row[0] and row[1]
        }
        price_quality_by_lane = {
            (str(row[0]), str(row[1])): assess_lane_price_quality(
                connection,
                symbol=str(row[0]),
                timeframe=str(row[1]),
                asset_class=str(row[4]),
            )
            for row in rows
            if str(row[4]) == "FX" and str(row[1]) == "D1"
        }
    finally:
        connection.close()

    universe = active_universe(database_path)
    active_symbols={
        str(row["symbol"])
        for row in universe["active_lanes"].values()
        if row["timeframe"] == "D1"
    }
    active_lane_ids = set(universe["active_lanes"])
    registrations=[row for row in registrations if str(row[0]) in active_symbols]
    registered_lane_rows=[
        row for row in registered_lane_rows
        if f"{row[0]}:{row[1]}" in active_lane_ids
    ]
    scheduler_journal = _scheduler_journal(database_path)
    scheduler_register = _scheduler_register_states(database_path)
    capability_projection = cached_acquisition_capability_projection(
        database_path, now=authority_generated
    )
    # MT5 is an authenticated asynchronous broker bridge, rather than a
    # generic HTTP provider adapter.  Its approved terminal catalogue is
    # therefore not represented by acquisition_orchestrator's provider
    # profiles.  Add its live, audited routes here so the operator surface
    # cannot misdescribe a working broker route as "no provider capability".
    # This is a projection-only enrichment: catalogue presence never changes
    # evidence, registrations, or the generic-provider execution path.
    capability_rows = [
        *list(capability_projection["rows"]),
        *_mt5_bridge_capability_rows(database_path),
    ]
    capabilities=[_capability(row,lane_facts,capability_rows,scheduler_journal) for row in registrations]
    capability_by_lane={
        (str(row["symbol"]),str(item["timeframe"])):item
        for row in capabilities for item in row["timeframes"]
    }
    # Freshness also provides the exact per-lane authority revision.  Compute
    # it once, then reuse it while projecting each lane instead of repeating
    # the same canonical reads through truth_state_for_lane.
    freshness_report = lane_freshness_report(
        database_path, clock=lambda: authority_generated
    )
    freshness_by_lane = {
        (str(item["symbol"]), str(item["timeframe"])): item
        for item in freshness_report["lanes"]
    }
    lanes = []
    for row in rows:
        lane_key = (str(row[0]), str(row[1]))
        lane_provider, lane_contract, lane_provider_symbol = latest_lane_sources.get(
            lane_key, (row[6], row[7], row[8])
        )
        freshness_row = freshness_by_lane[lane_key]
        truth = truth_state_from_persisted_facts(
            symbol=str(row[0]), timeframe=str(row[1]),
            registration=(row[6], row[7], row[8], row[9]),
            range_row=(int(row[12]), int(row[13]), int(row[14]), row[15]),
            validation=json.loads(row[10]) if row[10] else None,
            ledger_bound=bool(row[16]), freshness=dict(freshness_row["freshness"]),
            authority_revision=str(freshness_row["authority_revision"]),
            authority_generated=authority_generated_text,
            price_quality=price_quality_by_lane.get((str(row[0]), str(row[1]))),
        )
        register_state = scheduler_register.get(lane_key)
        truth = _apply_scheduler_operational_state(truth, register_state)
        validation = json.loads(row[10]) if row[10] else None
        gap_counts = _gap_counts(validation)
        lane_capabilities = [
            item for item in capability_rows
            if item["canonical_symbol"] == row[0] and item["timeframe"] == row[1]
        ]
        eligible_providers = [
            str(item["provider"]) for item in lane_capabilities if item["eligibility"] == "ELIGIBLE"
        ]
        lanes.append(
            {
                "symbol": row[0],
                "timeframe": row[1],
                "latest_canonical_observation": truth["latest_canonical_observation"],
                "authority_generated": authority_generated_text,
                "authority_revision": truth["authority_revision"],
                "freshness": truth["freshness"],
                "validation": truth["validation"],
                "truth_state": truth,
                "evidence_integrity": truth["evidence_integrity"],
                "freshness_dimension": truth["freshness_dimension"],
                "acquisition_dimension": {
                    "state": (
                        "SCHEDULER_BLOCKED"
                        if register_state and register_state.get("state") == "BLOCKED"
                        else "AUTOMATED_UPDATE_AVAILABLE"
                        if eligible_providers else "AUTOMATION_UNAVAILABLE"
                    ),
                    "eligible_providers": eligible_providers,
                    "provider_capabilities": lane_capabilities,
                    "scheduler_state": register_state,
                },
                "overall_operational_state": truth["overall_operational_state"],
                "operational_state_label": truth["operational_state_label"],
                "search_metadata": {
                    "canonical_symbol": row[0],
                    "display_name": row[2],
                    "aliases": json.loads(row[3]),
                    "market": "NOT_RECORDED",
                    "asset_class": row[4],
                    "exchange": row[5],
                    "provider_family": row[6],
                },
                "provider_summary": {
                    "provider": lane_provider,
                    "provider_contract": lane_contract,
                    "provider_symbol": lane_provider_symbol,
                    "provider_freshness": row[11] or "NOT_MEASURED",
                    "provider_confidence": truth["provider_summary"]["confidence"],
                    "entitlement": "NOT_MEASURED",
                    "unknown_values": [
                        name
                        for name, value in (
                            ("provider_freshness", row[11]),
                            ("provider_confidence", truth["provider_score"]),
                            ("entitlement", None),
                        )
                        if value is None
                    ],
                },
                "gap_summary": {
                    **gap_counts,
                    "total_gap_count": validation.get("missing_expected_session_count") if validation else None,
                    "gap_classification": truth["gap_classification"],
                    "operational_impact": truth["gap_impact"],
                },
            }
        )
    published_lane_keys={(str(lane["symbol"]),str(lane["timeframe"])) for lane in lanes}
    for row in registered_lane_rows:
        key=(str(row[0]),str(row[1]))
        if key in published_lane_keys:
            continue
        lanes.append(
            _unpublished_truth_lane(
                row,
                generated_at=authority_generated_text,
                authority_revision=_authority_revision(database_path,key[0],key[1]),
                capability=capability_by_lane.get(key),
                journal=scheduler_journal,
            )
        )
    lanes=_overlay_published_synthetic_m15_lanes(lanes,database_path)
    lanes=sorted(lanes,key=lambda lane:(str(lane["symbol"]),str(lane["timeframe"])))
    freshness_states={}
    for row in freshness_report["lanes"]:
        key=(str(row["symbol"]),str(row["timeframe"]))
        freshness=dict(row["freshness"])
        state=str(freshness["state"])
        capability=capability_by_lane.get(key,{})
        provider_eligible=any(
            item.get("eligibility")=="ELIGIBLE"
            for item in capability.get("provider_capabilities",[]) or []
        )
        if (
            state=="Unavailable"
            and freshness.get("reason_code")=="NO_CANONICAL_OBSERVATION"
            and provider_eligible
        ):
            state="Behind"
        if scheduler_register.get(key, {}).get("state") == "BLOCKED":
            state="Unavailable"
        freshness_states[key]=state
    commissioning_matrix=_commissioning_matrix(
        registrations,lane_facts,commissioned_lanes,capabilities,freshness_states,
        blocked_lanes={key for key,value in scheduler_register.items() if value.get("state")=="BLOCKED"},
    )
    estate_summary = _estate_summary(
        lanes, authority_generated_text, last_persisted_authority_change,
        commissioning_matrix,
    )
    provider_fact_revision=int(load_provider_facts(database_path).get("revision",0) or 0)
    register_revision=hashlib.sha256(
        json.dumps(
            [
                {"symbol":key[0],"timeframe":key[1],**value}
                for key,value in sorted(scheduler_register.items())
            ],
            sort_keys=True,separators=(",",":"),
        ).encode()
    ).hexdigest()
    estate_revision="sha256:"+hashlib.sha256(
        f"{freshness_report['authority_revision']}|provider-facts:{provider_fact_revision}|scheduler-register:{register_revision}".encode()
    ).hexdigest()
    return {
        "contract": ESTATE_TRUTH_CONTRACT,
        "latest_canonical_observation": estate_summary["latest_canonical_observation"],
        "caodt": estate_summary["latest_canonical_observation"],
        "authority_generated": authority_generated_text,
        "authority_revision": freshness_report["authority_revision"],
        "provider_fact_revision":provider_fact_revision,
        "estate_revision":estate_revision,
        "estate_summary": estate_summary,
        "truth_matrix": lanes,
        "commissioning_matrix": commissioning_matrix,
        "missing_commissions": [
            row for row in commissioning_matrix if row["missing_commission"]
        ],
        "lane_freshness_report": freshness_report,
        "timeframe_capabilities":capabilities,
        "acquisition_capability_projection": capability_projection,
    }


def _overlay_published_synthetic_m15_lanes(lanes,database_path):
    """Project governed M5-derived M15 products instead of retained raw M15.

    Raw broker M15 history stays preserved in canonical storage for audit. For
    an active synthetic registration, the published complete M5 triplets are
    the governed current M15 product. This is read-only presentation logic;
    it neither rewrites canonical evidence nor deletes the raw history.
    """
    from .synthetic_repository import SyntheticRepository,SyntheticRepositoryError
    try:
        products=SyntheticRepository(database_path).list_products(refresh_status=False)
    except (OSError,sqlite3.Error,SyntheticRepositoryError,ValueError):
        return lanes
    return _overlay_synthetic_m15_products(lanes,products)


def _overlay_synthetic_m15_products(lanes,products):
    """Pure projection helper for active, published M15 synthetic products."""
    by_key={(str(lane["symbol"]),str(lane["timeframe"])):lane for lane in lanes}
    replacements={}
    for product in products:
        if not isinstance(product,dict) or (
            product.get("target_timeframe")!="M15"
            or product.get("registration_status")!="ACTIVE"
            or product.get("immediate_source_evidence_class")!="REAL"
            or product.get("immediate_source_timeframe")!="M5"
        ):
            continue
        symbol=str(product.get("symbol") or "")
        source=by_key.get((str(product.get("immediate_source_symbol") or symbol),"M5"))
        target=by_key.get((symbol,"M15"))
        if source is None or target is None:
            continue
        replacements[(symbol,"M15")]=_synthetic_m15_lane(target,source,product)
    return [replacements.get((str(lane["symbol"]),str(lane["timeframe"])),lane) for lane in lanes]


def _synthetic_m15_lane(target,source,product):
    """Build an explicitly synthetic M15 operational projection from M5."""
    try:
        latest_text=datetime.fromtimestamp(int(product.get("latest_synthetic_observation")),UTC).isoformat()
    except (TypeError,ValueError,OSError,OverflowError):
        return target
    source_freshness=dict(source.get("freshness") or {})
    current=(
        # ``Incomplete`` can mean only the presently open triplet is
        # unpublished (or a closed-market interval has no M5 components).
        # When the product was generated from the exact current M5 revision,
        # its latest complete M15 edge remains current.
        product.get("status") in {"Available","Incomplete"}
        and product.get("source_revision")==source.get("authority_revision")
        and source_freshness.get("state")=="Current"
    )
    freshness=dict(source_freshness)
    freshness.update({
        "symbol":target["symbol"],"timeframe":"M15",
        "latest_canonical_observation":latest_text,
        "expected_latest":latest_text if current else source_freshness.get("expected_latest"),
        "state":"Current" if current else "Behind",
        "lane_status":"GOLD" if current else "RED",
        "severity":"HEALTHY" if current else "ATTENTION",
        "operational_state":"Current" if current else "Behind",
        "lag":{"count":0,"unit":"closed_interval"} if current else source_freshness.get("lag"),
        "lag_seconds":0 if current else source_freshness.get("lag_seconds"),
        "reason_code":"SYNTHETIC_M15_COMPLETE_FROM_CURRENT_M5" if current else "SYNTHETIC_M15_BEHIND_M5_SOURCE",
        "calendar_id":product.get("calendar_authority"),"evidence_class":"SYNTHETIC",
        "immediate_source":f"{product.get('immediate_source_symbol')}:{product.get('immediate_source_timeframe')}",
    })
    truth=copy.deepcopy(source["truth_state"])
    revision="sha256:"+hashlib.sha256(
        f"{product.get('source_revision')}|{product.get('synthetic_revision')}|{product.get('content_checksum')}".encode()
    ).hexdigest()
    truth.update({
        "symbol":target["symbol"],"timeframe":"M15","authority_revision":revision,
        "latest_canonical_observation":latest_text,"freshness":freshness,
        "freshness_dimension":{"state":"HEALTHY" if current else "CRITICAL","label":"Derived M15 current" if current else "Derived M15 behind M5 source","lag":freshness["lag"]},
        "validation_state":"DERIVED_FROM_CURRENT_M5" if current else "SYNTHETIC_SOURCE_STALE",
        "operational_state_label":"Complete M15 derived from current M5 · Current" if current else "Derived M15 is behind its M5 source",
        "authority_state":"GOLD" if current else "RED",
        "overall_operational_state":"Healthy" if current else "Critical",
    })
    result=copy.deepcopy(target)
    result.update({
        "timeframe":"M15","latest_canonical_observation":latest_text,"authority_revision":revision,
        "freshness":freshness,
        "validation":{"state":truth["validation_state"],"source_revision":product.get("source_revision"),"synthetic_revision":product.get("synthetic_revision"),"aggregation_rule":product.get("aggregation_rule")},
        "truth_state":truth,
        "evidence_integrity":{**dict(source.get("evidence_integrity") or {}),"evidence_class":"SYNTHETIC"},
        "freshness_dimension":truth["freshness_dimension"],
        "acquisition_dimension":{**dict(source.get("acquisition_dimension") or {}),"state":"SYNTHETIC_CURRENT" if current else "SYNTHETIC_REGENERATION_REQUIRED"},
        "overall_operational_state":truth["overall_operational_state"],"operational_state_label":truth["operational_state_label"],
        "provider_summary":{**dict(source.get("provider_summary") or {}),"provider_contract":product.get("aggregation_rule"),"provider_freshness":product.get("generated_at"),"evidence_class":"SYNTHETIC","immediate_source":f"{product.get('immediate_source_symbol')}:{product.get('immediate_source_timeframe')}"},
        "gap_summary":{**dict(source.get("gap_summary") or {}),"gap_classification":"SYNTHETIC_M15_COMPLETE" if current else "SYNTHETIC_M15_SOURCE_STALE","operational_impact":"NONE" if current else "HIGH"},
        "synthetic_product":{"id":product.get("id"),"status":product.get("status"),"synthetic_revision":product.get("synthetic_revision"),"aggregation_rule":product.get("aggregation_rule"),"source_revision":product.get("source_revision")},
    })
    return result

def _capability(row,lane_facts,capability_rows,journal=None):
    asset,asset_class,provider,contract,symbol,representation,calendar,exchange,identity,registration_status=row;items=[]
    for timeframe in displayed_timeframes(asset_class):
        policy=market_policy(asset_class,timeframe);count=lane_facts.get((asset,timeframe));deferred=policy=="INTENTIONALLY_DEFERRED"
        provider_facts=[item for item in capability_rows if item["canonical_symbol"]==asset and item["timeframe"]==timeframe]
        eligible=sorted((item for item in provider_facts if item["eligibility"]=="ELIGIBLE"),key=lambda item:(item["priority"],item["provider"]))
        supported=[item for item in provider_facts if item["capability_state"] in {"SUPPORTED","SUPPORTED_WITH_APPROVED_MAPPING","CREDENTIAL_REQUIRED","ENTITLEMENT_REQUIRED","RATE_POLICY_UNVERIFIED"}]
        primary=[item for item in supported if item["provider"]==provider]
        bridge_routes=sorted(
            (item for item in supported if item["provider"]=="MT5_BRIDGE"),
            key=lambda item:(item["priority"],item["provider"]),
        )
        # Broker routes are primary only where the manifest's market/timeframe
        # policy explicitly says so. Terminal availability alone is not route
        # authority.
        reviewed_bridge_routes = [
            item for item in bridge_routes
            if _is_manifest_primary_bridge_route(asset, asset_class, timeframe, item)
        ]
        selected=(
            (reviewed_bridge_routes or primary or eligible or bridge_routes or supported or provider_facts or [None])[0]
            if reviewed_bridge_routes or timeframe in {"H1","M30","M5"}
            else (primary or eligible or bridge_routes or supported or provider_facts or [None])[0]
        )
        reason=None if deferred or supported else eligibility_reason(asset_class=asset_class,representation_type=representation,provider_id=provider,provider_contract=contract,provider_symbol=symbol,calendar_id=calendar,exchange_name=exchange,identity_json=identity,registration_status=registration_status,timeframe=timeframe,canonical_symbol=asset) or "NO_APPROVED_PROVIDER_CAPABILITY"
        # An absent provider mapping is an automation stop, never an evidence
        # failure.  Legacy lanes can therefore remain selectable and servable
        # while an operator reviews an exact discovered representation.
        reviewable_mapping_rows=[
            item for item in provider_facts
            if item.get("provider") in {"TWELVE_DATA", "YAHOO_FINANCE"}
        ]
        unresolved_exact_mapping_rows=[
            item for item in provider_facts
            if item.get("rejection_reason") == "NO_APPROVED_MAPPING"
        ]
        # FX may be canonically registered before a provider representation is
        # verified.  That is an explicit mapping-discovery state, not an
        # evidence or registration failure.  Keep it distinct from the
        # stricter provider-setup path used by evidence-bearing lanes.
        mapping_discovery_pending=(
            asset_class == "FX"
            and registration_status == "REGISTERED_UNMAPPED"
            and not deferred
            # A dynamically verified exact representation supersedes the
            # registration's original unmapped marker immediately.  The
            # marker remains audit history; it must not keep a newly resolved
            # lane in mapping discovery.
            and not supported
            # Mapping is representation-scoped.  For an intraday lane, other
            # providers may correctly be timeframe-unsupported; that must not
            # hide the unresolved exact Twelve Data representation shared by
            # the symbol's lanes.
            and bool(unresolved_exact_mapping_rows)
        )
        provider_setup_required=(
            not mapping_discovery_pending
            and not deferred and bool(count) and registration_status == "REGISTERED_UNMAPPED"
            and bool(reviewable_mapping_rows)
            and all(item.get("rejection_reason") == "NO_APPROVED_MAPPING" for item in reviewable_mapping_rows)
        )
        # Capability absence is a routing condition, never authority to stop
        # a normal lane.  The Scheduler keeps provider cycling on the normal
        # cadence; only an explicit operator decision can create a runtime
        # BLOCKED row.
        route_pending=not deferred and not supported and not provider_setup_required and not mapping_discovery_pending
        blocked=False
        state=_registration_transaction_state(
            registration_status=registration_status,
            bar_count=int(count or 0),
            deferred=deferred,
            blocked=blocked,
            # A legacy failed journal entry records the old interpretation of
            # an unmapped FX representation.  It must not turn the current,
            # explicit mapping-discovery state back into a failed acquisition.
            journal_state=(
                {"state":"IDLE","reason":None}
                if mapping_discovery_pending
                else _lane_journal_state(journal,asset,timeframe)
            ),
        )
        reasons=["POLICY_INTENTIONALLY_DEFERRED"] if deferred else ["MAPPING_DISCOVERY_PENDING"] if mapping_discovery_pending else ["PROVIDER_SETUP_REQUIRED"] if provider_setup_required else ["PROVIDER_ROUTE_PENDING",reason] if route_pending else []
        consumption_available=bool(count) and not blocked
        automation_eligible=bool(eligible)
        # A bridge-scheduled provider is intentionally excluded from the HTTP
        # worker's ELIGIBLE set, but its catalogue-confirmed primary route is
        # still a valid operator acquisition path.  Publish that distinction
        # explicitly so management clients do not mistake transport ownership
        # for an unavailable lane.
        operator_fetch_eligible=automation_eligible or bool(reviewed_bridge_routes)
        # This predates the explicit automation field and is also consumed as a
        # lane-selectability flag by the native client.  Keep it true whenever
        # canonical evidence is available, even when provider setup is pending.
        initial_fetch_eligible=automation_eligible or provider_setup_required
        action=_required_operator_action(
            state,
            provider_setup_required=provider_setup_required,
            mapping_discovery_pending=mapping_discovery_pending,
            automation_eligible=automation_eligible,
            blocked=blocked,
            has_evidence=bool(count),
        )
        display_provider=selected if selected and selected.get("provider_symbol") else None
        items.append({"timeframe":timeframe,"policy_state":policy,"authority_state":state,"publication_state":state,"provider_mapping_state":selected["mapping_status"] if selected else "MAPPING_REQUIRED","provider":display_provider["provider"] if display_provider else None,"provider_symbol":display_provider["provider_symbol"] if display_provider else None,"provider_contract":_provider_contract(display_provider["provider"],timeframe) if display_provider else None,"calendar_authority":resolved_calendar_authority(asset_class=asset_class,calendar_id=calendar,exchange_name=exchange,canonical_symbol=asset),"session_authority":"REGULAR_SESSION_ONLY" if "EQUIT" in asset_class else "CONTINUOUS" if asset_class=="CRYPTO" else calendar,"entitlement_state":selected["entitlement_status"] if selected else "NOT_MEASURED","evidence_state":"PRESENT" if count else "NO_EVIDENCE","validation_state":"AVAILABLE" if count and not blocked else "NOT_APPLICABLE" if deferred else "BLOCKED" if blocked else "NOT_MEASURED","truth_state":"AVAILABLE" if count and not blocked else "NOT_APPLICABLE" if deferred else "BLOCKED" if blocked else "NOT_MEASURED","servable":consumption_available,"consumption_available":consumption_available,"automation_eligible":automation_eligible,"operator_fetch_eligible":operator_fetch_eligible,"required_operator_action":action,"initial_fetch_eligible":initial_fetch_eligible,"initial_fetch_blockers":reasons,"reason_codes":reasons,"provider_capabilities":provider_facts,"last_successful_provider":next((item["last_successful_provider"] for item in provider_facts if item.get("last_successful_provider")),None)})
    active_states={"ACTIVE_PUBLISHED","REGISTERED_WITH_EVIDENCE","REGISTERED_NO_EVIDENCE","REGISTERED_ACQUIRING_HISTORY","REGISTERED_FAILED_RECOVERABLE"}
    return {"symbol":asset,"asset_class":asset_class,"authorised_timeframes":[x["timeframe"] for x in items if x["policy_state"]=="REQUIRED"],"declared_timeframes":[x["timeframe"] for x in items if (asset,x["timeframe"]) in lane_facts],"active_timeframes":[x["timeframe"] for x in items if x["authority_state"] in active_states],"servable_timeframes":[x["timeframe"] for x in items if x["servable"]],"intentionally_deferred_timeframes":[x["timeframe"] for x in items if x["policy_state"]=="INTENTIONALLY_DEFERRED"],"blocked_timeframes":[x["timeframe"] for x in items if x["authority_state"] in {"BLOCKED","REGISTERED_FAILED_RECOVERABLE"}],"timeframes":items}


def _is_manifest_primary_bridge_route(asset, asset_class, timeframe, item):
    if item.get("provider") != "MT5_BRIDGE":
        return False
    from .mt5_route_manifest import is_mt5_primary_lane
    return is_mt5_primary_lane(
        str(asset), str(timeframe), provider_symbol=str(item.get("provider_symbol") or ""),
        asset_class=str(asset_class),
    )


def _mt5_bridge_capability_rows(database_path: str | Path) -> list[dict[str, object]]:
    """Project only catalogue-confirmed MT5 bridge routes for operator truth.

    The manifest supplies the approved canonical alias and the Windows
    catalogue proves that exact alias is available now.  A bridge route is
    deliberately marked ``BRIDGE_SCHEDULED`` rather than ``ELIGIBLE`` because
    the normal HTTP acquisition worker must not attempt to execute it.
    """

    from .mt5_bridge_queue import MT5BridgeQueueError
    from .mt5_catalogue import authorised_lanes

    database = Path(database_path).expanduser().resolve()
    try:
        routes = authorised_lanes(
            Path(f"{database}.read-only-clients"), database=database,
        )
    except (OSError, ValueError, sqlite3.Error, MT5BridgeQueueError):
        return []
    rows: list[dict[str, object]] = []
    for (symbol, timeframe), provider_symbol in sorted(routes.items()):
        rows.append({
            "canonical_symbol": symbol,
            "canonical_representation": "BROKER_MT5_ROUTE",
            "timeframe": timeframe,
            "provider": "MT5_BRIDGE",
            "provider_symbol": provider_symbol,
            "provider_representation": provider_symbol,
            "mapping_status": "APPROVED_PROVIDER_ALIAS",
            "mapping_class": "APPROVED_PROVIDER_ALIAS",
            "capability_state": "SUPPORTED_WITH_APPROVED_MAPPING",
            "eligibility": "BRIDGE_SCHEDULED",
            "credential_status": "AVAILABLE",
            "entitlement_status": "AVAILABLE",
            "rate_policy_status": "NOT_CREDIT_LIMITED",
            "history_range_support": "TERMINAL_LOCAL_HISTORY",
            "priority": 0,
            "routing_policy": "MT5_BRIDGE_MANIFEST_V3",
            "routing_rank": 0,
            "quote_equivalence": None,
            "quote_equivalence_reason": None,
            "rejection_reason": None,
            "authority_source": "MT5_ROUTE_MANIFEST_V3_OPERATOR_APPROVED",
            "resolution_method": "LIVE_TERMINAL_CATALOGUE",
            "resolution_evidence": "CATALOGUE_AND_MANIFEST_INTERSECTION",
            "timeframe_capability": {"timeframe": timeframe, "supported": True},
            "registration_status": "ROUTE_CONFIRMED",
            "existing_commissioned_lane": False,
            "last_successful_provider": None,
        })
    return rows


def _commissioning_matrix(registrations,lane_facts,commissioned_lanes,capabilities,freshness_states,blocked_lanes=None):
    """Project every required lane without changing evidence or Truth scoring."""

    capability_by_symbol={row["symbol"]:row for row in capabilities}
    operational=set(); blocked_lanes=blocked_lanes or set()
    for registration in registrations:
        symbol,asset_class=registration[0],registration[1]
        timeframes={
            row["timeframe"]:row
            for row in capability_by_symbol.get(symbol,{}).get("timeframes",[])
        }
        for timeframe,capability in timeframes.items():
            key=(symbol,timeframe)
            evidence_count=int(lane_facts.get(key) or 0)
            if (
                key in lane_facts and key not in blocked_lanes and evidence_count > 0
                and capability.get("consumption_available",False)
            ):
                operational.add(key)
    return project_required_lanes(
        ((row[0],row[1]) for row in registrations),set(commissioned_lanes),
        evidence_counts=lane_facts,operational_states=freshness_states,
        operational_lanes=operational,
        enabled_lanes=set(commissioned_lanes),
    )


def _provider_contract(provider,timeframe):
    return {"TWELVE_DATA":f"TWELVE_DATA_TIME_SERIES_{timeframe}_V1","YAHOO_FINANCE":"YAHOO_FINANCE_CHART_D1_V1","BINANCE":"BINANCE_KLINES_V1","COINGECKO":"COINGECKO_OHLC_V1"}.get(provider)


def _authority_revision(database_path,symbol,timeframe):
    with open_read_only(database_path) as connection:
        return authority_revision_for_lane(connection,symbol=symbol,timeframe=timeframe)


def _scheduler_register_states(database_path):
    """Read lane operations without creating or repairing scheduler state."""

    path=register_path(database_path)
    if not path.exists():
        return {}
    try:
        connection=sqlite3.connect(f"file:{path}?mode=ro",uri=True)
        connection.row_factory=sqlite3.Row
        try:
            rows=connection.execute(
                """SELECT asset,timeframe,state,next_expected_boundary_utc,
                          next_check_at_utc,last_outcome,retry_count,updated_at_utc
                     FROM lane_update_register WHERE state='BLOCKED'"""
            ).fetchall()
        finally:
            connection.close()
    except sqlite3.Error:
        return {}
    return {
        (str(row["asset"]),str(row["timeframe"])):{
            "state":str(row["state"]),
            "next_expected_boundary_utc":row["next_expected_boundary_utc"],
            "next_check_at_utc":row["next_check_at_utc"],
            "last_outcome":row["last_outcome"],
            "retry_count":int(row["retry_count"] or 0),
            "updated_at_utc":row["updated_at_utc"],
        }
        for row in rows
    }


def _apply_scheduler_operational_state(truth,register_state):
    """Prevent a blocked update path from being presented as healthy Truth."""

    if not register_state or register_state.get("state") != "BLOCKED":
        return truth
    result=copy.deepcopy(truth)
    reason=str(register_state.get("last_outcome") or "SCHEDULER_LANE_BLOCKED")
    result["truth_score"]=min(int(result.get("truth_score") or 0),70)
    result["authority_state"]="RED"
    result["overall_operational_state"]="Critical"
    result["operational_state_label"]=(
        f"Scheduler blocked · {result.get('freshness',{}).get('operational_state') or result.get('freshness',{}).get('state') or 'Unknown'}"
    )
    explanation=result.setdefault("explanation",{})
    limitations=explanation.setdefault("limitations",[])
    if "SCHEDULER_LANE_BLOCKED" not in limitations:
        limitations.append("SCHEDULER_LANE_BLOCKED")
    components=explanation.setdefault("components",{})
    components["acquisition"]={"score":0,"basis":reason}
    explanation["operational_cap"]="SCHEDULER_BLOCKED_CAP_70"
    result["scheduler_state"]=dict(register_state)
    return result


def _scheduler_journal(database_path):
    path=Path(f"{Path(database_path).expanduser().resolve()}.scheduler.json")
    from .scheduler_state_store import SchedulerStateStore
    state=SchedulerStateStore(database_path,path).load()
    if isinstance(state,dict):
        return state
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError,ValueError,TypeError):
        return {}


def _lane_journal_state(journal,symbol,timeframe):
    if not isinstance(journal,dict):
        return {"state":"IDLE","reason":None}
    lane_id=f"{symbol}:{timeframe}"
    lane=journal.get("lanes",{}).get(lane_id,{})
    lane=lane if isinstance(lane,dict) else {}
    queue=[
        item for item in journal.get("acquisition_queue",[])
        if isinstance(item,dict) and item.get("lane")==lane_id
    ]
    manual=next((
        item for item in journal.get("manual_requests",[])
        if isinstance(item,dict) and item.get("symbol")==symbol and item.get("timeframe")==timeframe
        and item.get("status") in {"Required","Acknowledged","Waiting"}
    ),None)
    last=lane.get("last_operator_fetch_result")
    last=last if isinstance(last,dict) else {}
    if lane.get("operator_fetch_pending") or queue:
        return {"state":"ACQUIRING","reason":lane.get("reason") or (queue[0].get("waiting_reason") if queue else None)}
    if manual or lane.get("manual_request") or last.get("outcome") in {"FAILED","MANUAL_REQUIRED"} or lane.get("result")=="FAILED":
        return {"state":"FAILED","reason":lane.get("reason") or last.get("reason") or (manual or {}).get("reason")}
    if lane.get("result")=="WAITING" or last.get("outcome") in {"WAITING","DEDUPLICATED_ACTIVE_WORK"}:
        return {"state":"ACQUIRING","reason":lane.get("reason") or last.get("reason")}
    return {"state":"IDLE","reason":lane.get("reason") or last.get("reason")}


def _registration_transaction_state(*,registration_status,bar_count,deferred,blocked,journal_state):
    if deferred:
        return "INTENTIONALLY_DEFERRED"
    if blocked:
        return "REGISTERED_FAILED_RECOVERABLE"
    if bar_count:
        return "ACTIVE_PUBLISHED"
    if journal_state.get("state")=="ACQUIRING":
        return "REGISTERED_ACQUIRING_HISTORY"
    if journal_state.get("state")=="FAILED":
        return "REGISTERED_FAILED_RECOVERABLE"
    if registration_status=="REGISTERED_WITH_EVIDENCE":
        return "REGISTERED_WITH_EVIDENCE"
    return "REGISTERED_NO_EVIDENCE"


def _required_operator_action(state,*,provider_setup_required,mapping_discovery_pending,automation_eligible,blocked,has_evidence):
    if mapping_discovery_pending:
        return "WAIT_FOR_PROVIDER_MAPPING_DISCOVERY"
    if provider_setup_required:
        return "COMPLETE_PROVIDER_SETUP"
    if state=="REGISTERED_WITH_EVIDENCE" and has_evidence:
        return "REPAIR_PUBLICATION"
    if state=="REGISTERED_FAILED_RECOVERABLE":
        return "RESUME_INITIAL_HISTORY" if automation_eligible and not blocked else "CLEAR_FAILED_REGISTRATION"
    if state=="REGISTERED_NO_EVIDENCE" and automation_eligible:
        return "RESUME_INITIAL_HISTORY"
    return None


def _unpublished_truth_lane(row,*,generated_at,authority_revision,capability,journal):
    symbol,timeframe=str(row[0]),str(row[1])
    bar_count=int(row[12] or 0)
    state=(capability or {}).get("authority_state") or _registration_transaction_state(
        registration_status=str(row[9]),
        bar_count=bar_count,
        deferred=False,
        blocked=False,
        journal_state=_lane_journal_state(journal,symbol,timeframe),
    )
    authority_state="RED" if state=="REGISTERED_FAILED_RECOVERABLE" else "AMBER"
    operational_label={
        "REGISTERED_ACQUIRING_HISTORY":"Initial history acquisition is in progress.",
        "REGISTERED_FAILED_RECOVERABLE":"Initial history or publication failed; recovery is available.",
        "REGISTERED_WITH_EVIDENCE":"Evidence exists but Estate Truth publication needs repair.",
    }.get(state,"Registered without published canonical evidence.")
    provider_capabilities=(capability or {}).get("provider_capabilities") or []
    eligible=[str(item["provider"]) for item in provider_capabilities if item.get("eligibility")=="ELIGIBLE"]
    action=(capability or {}).get("required_operator_action")
    truth=_unpublished_truth_state(
        symbol=symbol,timeframe=timeframe,registration_status=str(row[9]),
        provider=row[6],provider_contract=row[7],provider_symbol=row[8],
        authority_state=authority_state,publication_state=state,
        authority_revision=authority_revision,generated_at=generated_at,
        reason=operational_label,
    )
    return {
        "symbol":symbol,
        "timeframe":timeframe,
        "latest_canonical_observation":"",
        "authority_generated":generated_at,
        "authority_revision":authority_revision,
        "freshness":truth["freshness"],
        "validation":truth["validation"],
        "truth_state":truth,
        "evidence_integrity":truth["evidence_integrity"],
        "freshness_dimension":truth["freshness_dimension"],
        "acquisition_dimension":{
            "state":"RECOVERY_AVAILABLE" if action else "INITIAL_HISTORY_REQUIRED",
            "eligible_providers":eligible,
            "provider_capabilities":provider_capabilities,
        },
        "overall_operational_state":"Critical" if authority_state=="RED" else "Attention",
        "operational_state_label":operational_label,
        "publication_state":state,
        "required_operator_action":action,
        "exclusion_explanation":None,
        "search_metadata":{
            "canonical_symbol":symbol,
            "display_name":row[2],
            "aliases":json.loads(row[3]) if row[3] else [],
            "market":"NOT_RECORDED",
            "asset_class":row[4],
            "exchange":row[5],
            "provider_family":row[6],
        },
        "provider_summary":{
            "provider":row[6],
            "provider_contract":row[7],
            "provider_symbol":row[8],
            "provider_freshness":row[15] or "NOT_MEASURED",
            "provider_confidence":"NOT_MEASURED",
            "entitlement":"NOT_MEASURED",
            "unknown_values":["provider_freshness","provider_confidence","entitlement"],
        },
        "gap_summary":{
            "current_gap_count":None,
            "recent_gap_count":None,
            "historical_gap_count":None,
            "total_gap_count":None,
            "gap_classification":"NO_CANONICAL_EVIDENCE",
            "operational_impact":"HIGH",
        },
    }


def _unpublished_truth_state(*,symbol,timeframe,registration_status,provider,provider_contract,provider_symbol,authority_state,publication_state,authority_revision,generated_at,reason):
    score=25 if authority_state=="RED" else 50
    return {
        "contract":TRUTH_STATE_CONTRACT,
        "engine_version":TRUTH_ENGINE_VERSION,
        "symbol":symbol,
        "timeframe":timeframe,
        "truth_score":score,
        "authority_score":score,
        "integrity_score":None,
        "freshness_score":None,
        "historical_depth_score":0,
        "coverage_score":0,
        "continuity_score":0,
        "validation_score":None,
        "provider_score":None,
        "authority_state":authority_state,
        "evidence_integrity":{"state":"Unavailable","score":None},
        "freshness_dimension":{"state":"CRITICAL" if authority_state=="RED" else "WARNING","label":"No canonical observation","lag":None},
        "overall_operational_state":"Critical" if authority_state=="RED" else "Attention",
        "operational_state_label":reason,
        "validation_state":"NOT_MEASURED",
        "caodt":"",
        "latest_canonical_observation":"",
        "authority_revision":authority_revision,
        "authority_generated":generated_at,
        "freshness":{
            "state":"Unavailable",
            "latest_canonical_observation":None,
            "expected_latest":None,
            "reason_code":"NO_CANONICAL_OBSERVATION",
            "severity":"CRITICAL" if authority_state=="RED" else "WARNING",
            "operational_state":publication_state,
        },
        "validation":{"state":"NOT_MEASURED","summary":None},
        "gap_classification":"NO_CANONICAL_EVIDENCE",
        "gap_impact":"HIGH",
        "coverage":{
            "earliest_bar":"",
            "latest_bar":"",
            "row_count":0,
            "expected_range":{"start":None,"end":None},
            "available_range":{"start":None,"end":None},
            "expected_session_count":None,
            "available_expected_session_count":0,
        },
        "gap_summary":{
            "classification":"NO_CANONICAL_EVIDENCE",
            "operational_impact":"HIGH",
            "total_known_gaps":None,
        },
        "provider_summary":{
            "provider":provider,
            "provider_contract":provider_contract,
            "provider_symbol":provider_symbol,
            "confidence":"NOT_MEASURED",
            "score":None,
            "basis":"NO_PUBLISHED_CANONICAL_EVIDENCE",
        },
        "epoch":"UNKNOWN",
        "explanation":{
            "method":"REGISTERED_BUT_UNPUBLISHED_RECOVERY_PROJECTION_V1",
            "weights":TRUTH_COMPONENT_WEIGHTS,
            "components":{
                "authority":{"score":score,"basis":f"{registration_status};{publication_state}"},
                "freshness":{"score":None,"basis":"NO_CANONICAL_OBSERVATION"},
                "integrity":{"score":None,"basis":"NO_CANONICAL_EVIDENCE"},
                "historical_depth":{"score":0,"basis":"0 canonical rows"},
                "continuity":{"score":0,"basis":"0 canonical rows"},
                "provider":{"score":None,"basis":"NO_PERSISTED_PROVIDER_CONFIDENCE_FACT"},
            },
            "limitations":["NO_CANONICAL_EVIDENCE","PROVIDER_NOT_MEASURED"],
        },
    }


class EstateTruthCache:
    """Explicit in-memory cache replaced only by load or manual refresh."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.database_path = Path(database_path)
        self.clock = clock
        self._value: dict[str, object] | None = None

    def load(self) -> dict[str, object]:
        if self._value is None:
            self._value = estate_truth_state(self.database_path, clock=self.clock)
        return copy.deepcopy(self._value)

    def refresh(self) -> dict[str, object]:
        self._value = estate_truth_state(self.database_path, clock=self.clock)
        return copy.deepcopy(self._value)


def _gap_counts(validation):
    if validation is None:
        return {"current_gap_count": None, "recent_gap_count": None, "historical_gap_count": None}
    missing = validation.get("missing_expected_interval_count",validation.get("missing_expected_session_count", 0))
    present=validation.get("latest_expected_closed_interval_present",validation.get("latest_expected_session_present"))
    current = 0 if present else min(1, missing)
    material = validation.get("material_gap_count", 0)
    recent = min(max(0, missing - current), material)
    historical = max(0, missing - current - recent)
    return {"current_gap_count": current, "recent_gap_count": recent, "historical_gap_count": historical}


def _estate_summary(lanes, generated_at, last_persisted_authority_change, commissioning=None):
    scores = [lane["truth_state"]["truth_score"] for lane in lanes]
    overall = round(sum(scores) / len(scores)) if scores else None
    counts = {state: sum(lane["truth_state"]["authority_state"] == state for lane in lanes) for state in ("GOLD", "GREEN", "AMBER", "RED")}
    # Gold means every lane has the expected closed edge. Green means one or
    # more lanes are within the three-boundary usable tolerance. Amber and Red
    # retain their established degraded and unsafe meanings.
    overall_state = (
        "NOT_MEASURED" if overall is None else
        "GOLD" if not counts["GREEN"] and not counts["AMBER"] and not counts["RED"] else
        "GREEN" if not counts["AMBER"] and not counts["RED"] else
        "GREEN" if overall is not None and overall >= 90 else
        "AMBER" if overall is not None and overall >= 50 else
        "RED" if overall is not None else "NOT_MEASURED"
    )
    latest_canonical_observation = max(
        (
            lane["latest_canonical_observation"]
            for lane in lanes
            if lane.get("latest_canonical_observation")
        ),
        default=None,
    )
    required_rows=[row for row in commissioning if row.get("required")] if commissioning is not None else []
    not_enabled_lanes=(
        sum(not bool(row.get("enabled")) for row in commissioning)
        if commissioning is not None else 0
    )
    required_lanes=len(required_rows) if commissioning is not None else len(lanes)
    commissioned_lanes=(
        sum(bool(row["commissioned"]) for row in required_rows)
        if commissioning is not None else len(lanes)
    )
    operational_lanes=(
        sum(bool(row["operational"]) for row in required_rows)
        if commissioning is not None else len(lanes)
    )
    missing_commissions=required_lanes-commissioned_lanes
    operational_coverage=(
        round(100 * commissioned_lanes / required_lanes)
        if required_lanes else None
    )
    return {
        "overall_truth_score": overall,
        "overall_authority_state": overall_state,
        "latest_canonical_observation": latest_canonical_observation,
        "caodt": latest_canonical_observation,
        "overall_caodt": latest_canonical_observation,
        "total_symbols": len({lane["symbol"] for lane in lanes}),
        "total_lanes": len(lanes),
        "required_lanes":required_lanes,
        "commissioned_lanes":commissioned_lanes,
        "operational_lanes":operational_lanes,
        "missing_commissions":missing_commissions,
        "not_enabled_lanes":not_enabled_lanes,
        "operational_coverage_percent":operational_coverage,
        "gold_count": counts["GOLD"],
        "green_count": counts["GREEN"],
        "amber_count": counts["AMBER"],
        "red_count": counts["RED"],
        "authority_version": AUTHORITY_VERSION,
        "generated_at": generated_at,
        "last_persisted_authority_change": last_persisted_authority_change,
        "aggregation": {
            "truth_score": "EQUAL_WEIGHT_MEAN_OF_LANE_TRUTH_SCORES",
            "authority_state": "NO_OPERATIONAL_FINDINGS_THEN_EQUAL_WEIGHT_MEAN_OF_LANE_TRUTH_SCORES",
            "caodt": "ALIAS_OF_LATEST_CANONICAL_OBSERVATION",
            "generated_at": "SNAPSHOT_CONSTRUCTION_TIMESTAMP",
            "operational_coverage": "COMMISSIONED_REQUIRED_LANES_DIVIDED_BY_REQUIRED_LANES",
        },
    }
