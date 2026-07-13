"""Reactivate a retired instrument while preserving its authority history."""
import argparse,json,sys
from fragarach_ii.retirement import RetirementError,reactivate_instrument

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database",required=True);parser.add_argument("--asset",required=True);parser.add_argument("--confirm",action="store_true");parser.add_argument("--json",action="store_true",required=True)
    args=parser.parse_args(argv)
    if not args.confirm:
        print(json.dumps({"code":"EXPLICIT_CONFIRMATION_REQUIRED","error":f"Confirm reactivation of {args.asset.strip().upper()}"},sort_keys=True,separators=(",",":")));return 1
    try:result=reactivate_instrument(args.database,args.asset)
    except RetirementError as error:print(json.dumps({"code":error.code,"error":str(error)},sort_keys=True,separators=(",",":")));return 1
    print(json.dumps(result,sort_keys=True,separators=(",",":")));return 0

if __name__=="__main__":sys.exit(main())
