"""Inspect and append immutable registration, provider-mapping, and lane authority."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from fragarach_ii.providers.contracts import list_provider_contracts,load_provider_contract
from fragarach_ii.storage import (AuthorityEventManifest,AuthorityLedgerError,append_authority_event,
    bootstrap_legacy_authority,inspect_authority,prepare_authority_event,reconstruct_authority)

def _manifest(path: str) -> AuthorityEventManifest:
    value=json.loads(Path(path).read_text())
    value["authority_bindings"]=tuple(value.get("authority_bindings",[]));value["compatibility_reasons"]=tuple(value.get("compatibility_reasons",[]))
    return AuthorityEventManifest(**value)

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--database",required=True)
    sub=parser.add_subparsers(dest="domain",required=True)
    for domain in ("registration","lane"):
        d=sub.add_parser(domain); ops=d.add_subparsers(dest="operation",required=True)
        inspect=ops.add_parser("inspect");inspect.add_argument("--entity-id")
        for op in (("validate-manifest",) if domain=="lane" else ("validate-manifest","apply-reviewed-mapping","declare","revise")):
            q=ops.add_parser(op);q.add_argument("--manifest",required=True);q.add_argument("--dry-run",action="store_true")
        if domain=="lane":
            for op in ("declare","replay","supersede"):
                q=ops.add_parser(op);q.add_argument("--manifest",required=True);q.add_argument("--dry-run",action="store_true")
            ops.add_parser("matrix-stage-a")
    bootstrap=sub.add_parser("bootstrap");bootstrap.add_argument("--dry-run",action="store_true")
    contracts=sub.add_parser("provider-contract");cops=contracts.add_subparsers(dest="operation",required=True);cops.add_parser("list");ci=cops.add_parser("inspect");ci.add_argument("--id",required=True)
    args=parser.parse_args(argv)
    try:
        if args.domain=="provider-contract": result=list_provider_contracts() if args.operation=="list" else load_provider_contract(args.id)
        elif args.domain=="bootstrap": result=[json.loads(r.as_json()) for r in bootstrap_legacy_authority(args.database,dry_run=args.dry_run)]
        elif args.operation=="inspect": result=inspect_authority(args.database,entity_kind="INSTRUMENT_REGISTRATION" if args.domain=="registration" else "EVIDENCE_LANE",entity_id=args.entity_id)
        elif args.operation=="matrix-stage-a": result=_stage_a(args.database)
        else:
            manifest=_manifest(args.manifest)
            if args.operation=="validate-manifest":
                p=prepare_authority_event(manifest);result={"outcome":"VALID","authority_event_id":p.authority_event_id,"payload_checksum_sha256":p.payload_checksum_sha256}
            else: result=json.loads(append_authority_event(args.database,manifest,dry_run=args.dry_run).as_json())
        print(json.dumps(result,sort_keys=True,separators=(",",":"),ensure_ascii=False));return 0
    except (AuthorityLedgerError,ValueError,TypeError,OSError,json.JSONDecodeError) as error:
        print(json.dumps({"code":getattr(error,"code","AUTHORITY_OPERATION_FAILED"),"error":str(error)},sort_keys=True,separators=(",",":")));return 1

def _stage_a(database):
    candidates=("AUDUSD","BTCUSD_AGGREGATE","XAUUSD","USOIL","SP500_PRICE_RETURN_USD","AAPL_XNGS","SHEL_XLON","SAP_XETR","BHP_XASX")
    current=reconstruct_authority(database);lanes={(e["entity_id"],e["payload"].get("body",{}).get("timeframe")):e for e in current if e["entity_kind"]=="EVIDENCE_LANE"}
    return [{"candidate":c,"timeframe":tf,"lane_state":(lanes.get((c,tf),{}).get("event_kind") or "NOT_DECLARED"),"accepted_historical_evidence_readable":c in {"AUDUSD","XAUUSD"} and tf=="D1"} for c in candidates for tf in ("D1","H1","M30","M5")]

if __name__=="__main__":sys.exit(main())
