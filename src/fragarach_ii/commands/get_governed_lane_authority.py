"""Return one published Estate lane authority projection for downstream governed consumers."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections.abc import Sequence
from pathlib import Path

from fragarach_ii.publication_service import lane_publication_detail
from fragarach_ii.lane_commissioning import (
    lane_eligibility,
    resolved_provider_mapping_for_lane,
)
from fragarach_ii.market_history_service import (
    SBV2_REQUIRED_CLOSED_BARS,
    MarketHistoryService,
)
from fragarach_ii.provider_facts import representation_mapping
from fragarach_ii.storage import open_read_only
from fragarach_ii.truth_engine import TruthEngineError, truth_state_for_lane


CONTRACT = "fragarach_ii.governed_lane_authority.v1"


def _sbv2_chartability(
    database: Path,
    symbol: str,
    timeframe: str,
    lane: dict[str, object] | None,
    publication_state: str,
) -> dict[str, object]:
    """Project the exact, bounded proof SBv2 needs before chart construction.

    A published lane is not automatically chartable: the configured mapping,
    calendar, CAODT and at least thirty closed bars must all be present.  This
    is read-only and deliberately does not attempt recovery or acquisition.
    """

    result: dict[str, object] = {
        "required_closed_bars": SBV2_REQUIRED_CLOSED_BARS,
        "returned_closed_bars": 0,
        "caodt": None,
    }
    if lane is None:
        return {
            **result,
            "state": "LANE_NOT_VISIBLE",
            "reason": "No governed evidence lane is visible.",
        }
    acquisition = lane.get("acquisition_dimension")
    acquisition = acquisition if isinstance(acquisition, dict) else {}
    mapping_state = str(acquisition.get("state") or "AUTOMATION_UNAVAILABLE")
    if mapping_state in {"MAPPING_DISCOVERY", "MAPPING_REQUIRED"}:
        return {
            **result,
            "state": "MAPPING_DISCOVERY",
            "reason": str(acquisition.get("reason") or "Approved provider mapping is required."),
        }
    if mapping_state != "AUTOMATED_UPDATE_AVAILABLE":
        return {
            **result,
            "state": "MAPPING_UNAVAILABLE",
            "reason": str(acquisition.get("reason") or mapping_state),
        }
    if publication_state != "PUBLISHED":
        return {
            **result,
            "state": "PUBLICATION_UNUSABLE",
            "reason": f"Lane publication is {publication_state.lower()}.",
        }
    return MarketHistoryService(database).assess_sbv2_chartability(symbol, timeframe)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--timeframe", required=True)
    parser.add_argument("--json", action="store_true", required=True)
    arguments = parser.parse_args(argv)
    symbol, timeframe = arguments.symbol.strip().upper(), arguments.timeframe.strip().upper()
    try:
        database = Path(arguments.database).expanduser().resolve()
        connection = open_read_only(database)
        try:
            row = connection.execute(
                """
                SELECT r.display_name,r.asset_class,r.exchange_name,r.provider_id,
                       r.provider_contract,r.provider_symbol,r.representation_type,r.registration_status,
                       EXISTS(SELECT 1 FROM bars b WHERE b.asset=l.asset AND b.timeframe=l.timeframe)
                FROM evidence_lanes l JOIN instrument_registrations r
                  ON r.asset=l.asset AND r.timeframe=l.registration_timeframe
                WHERE l.asset=? AND l.timeframe=?
                """, (symbol, timeframe),
            ).fetchone()
        finally:
            connection.close()
        lane = None
        if row and row[8]:
            try:
                truth = truth_state_for_lane(database, symbol=symbol, timeframe=timeframe)
            except TruthEngineError:
                truth = None
            if truth is not None:
                # Registration history deliberately remains immutable. A
                # REGISTERED_UNMAPPED marker therefore cannot itself decide
                # whether a lane is currently automatable: exact provider
                # facts may have resolved the representation later. Reuse the
                # same read-only eligibility seam used by commissioning and
                # Estate Truth so downstream consumers see one authority.
                eligible, eligibility_reason = lane_eligibility(
                    database, symbol, timeframe
                )
                provider_id = str(row[3]).upper() if row[3] else None
                provider_contract = str(row[4]) if row[4] else None
                provider_symbol = str(row[5]) if row[5] else None
                recovered = None
                if not provider_id or not provider_symbol:
                    recovered = resolved_provider_mapping_for_lane(database, symbol, timeframe)
                    if recovered:
                        provider_id = recovered["provider"]
                        provider_contract = recovered["provider_contract"]
                        provider_symbol = recovered["provider_symbol"]
                mapping = (
                    representation_mapping(database, provider_id, symbol)
                    if provider_id else None
                )
                mapping_class = str(mapping.get("mapping_class")) if mapping else (
                    str(recovered["mapping_class"]) if recovered else "EXACT_REPRESENTATION" if provider_symbol else None
                )
                mapping_status = str(mapping.get("status")) if mapping else (
                    str(recovered["authority_source"]) if recovered else "CANONICAL_INSTRUMENT_REGISTRATION" if provider_symbol else None
                )
                capabilities = mapping.get("timeframe_capabilities") if mapping else None
                timeframe_capability = (
                    capabilities.get(timeframe, {}) if isinstance(capabilities, dict) else {}
                )
                discovery = row[7] == "REGISTERED_UNMAPPED" and not eligible
                lane = {
                    "symbol": symbol, "timeframe": timeframe,
                    "commissioning_state": "COMMISSIONED",
                    "latest_canonical_observation": truth["latest_canonical_observation"],
                    "authority_revision": truth["authority_revision"],
                    "freshness": truth["freshness"], "validation": truth["validation"],
                    "truth_state": truth,
                    "acquisition_dimension": {
                        "state": "AUTOMATED_UPDATE_AVAILABLE" if eligible else "MAPPING_DISCOVERY" if discovery else "AUTOMATION_UNAVAILABLE",
                        "eligible_providers": [provider_id] if eligible and provider_id and provider_symbol else [],
                        "provider_capabilities": [{
                            "provider": provider_id,
                            "provider_symbol": provider_symbol,
                            "mapping_class": mapping_class,
                            "mapping_status": mapping_status,
                            "provider_contract": provider_contract,
                            "timeframe": timeframe,
                            "supported": timeframe_capability.get("supported"),
                            "reason": timeframe_capability.get("reason") or eligibility_reason,
                        }] if mapping else [],
                        "reason": eligibility_reason,
                    },
                    "search_metadata": {
                        "canonical_symbol": symbol, "display_name": row[0], "market": "NOT_RECORDED",
                        "asset_class": row[1], "exchange": row[2], "provider_family": row[3],
                        "canonical_representation": row[6],
                    },
                }
        publication = lane_publication_detail(arguments.database, symbol, timeframe)
    except (FileNotFoundError, RuntimeError, sqlite3.Error, ValueError, OSError) as error:
        print(json.dumps({"contract": CONTRACT, "status": "AUTHORITY_UNAVAILABLE", "error": str(error)}, sort_keys=True, separators=(",", ":")))
        return 1
    publication_revision = publication.get("revision")
    transaction_id = publication.get("job_id") or f"publication-revision-{publication_revision}"
    publication_state = str(publication.get("state") or "PUBLISHED")
    payload = {
        "contract": CONTRACT,
        "status": publication_state,
        "symbol": symbol,
        "timeframe": timeframe,
        "estate_revision": lane.get("authority_revision") if lane else None,
        "lane": lane,
        "publication": {
            **publication,
            "transaction_id": transaction_id,
        },
        "chartability": _sbv2_chartability(
            database, symbol, timeframe, lane, publication_state
        ),
    }
    if lane is None:
        payload["status"] = "NOT_VISIBLE"
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
