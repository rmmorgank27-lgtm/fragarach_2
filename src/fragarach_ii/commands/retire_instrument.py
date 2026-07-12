"""Plan or confirm immutable instrument retirement."""
import argparse,json,sys
from fragarach_ii.retirement import RetirementError,retire_instrument,retirement_impact
def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--database",required=True);p.add_argument("--asset",required=True);p.add_argument("--scope",choices=("WHOLE_INSTRUMENT","SELECTED_LANES"),default="WHOLE_INSTRUMENT");p.add_argument("--lanes",default="D1");p.add_argument("--reason");p.add_argument("--note",default="");p.add_argument("--confirmation",default="");p.add_argument("--confirm",action="store_true");p.add_argument("--json",action="store_true",required=True);a=p.parse_args(argv)
    try:
        lanes=tuple(x.strip().upper() for x in a.lanes.split(",") if x.strip())
        result=retire_instrument(a.database,a.asset,scope=a.scope,selected_lanes=lanes,reason=a.reason or "",operator_note=a.note,typed_confirmation=a.confirmation) if a.confirm else retirement_impact(a.database,a.asset,a.scope,lanes)
    except RetirementError as e:print(json.dumps({"code":e.code,"error":str(e)},sort_keys=True,separators=(",",":")));return 1
    print(json.dumps(result,sort_keys=True,separators=(",",":")));return 0
if __name__=="__main__":sys.exit(main())
