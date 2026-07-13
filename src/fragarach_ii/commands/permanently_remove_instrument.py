"""Plan or confirm permanent removal of an evidence-free retired instrument."""
import argparse,json,sys
from fragarach_ii.retirement import RetirementError,permanent_removal_impact,permanently_remove_instrument

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database",required=True);parser.add_argument("--asset",required=True);parser.add_argument("--confirmation",default="");parser.add_argument("--confirm",action="store_true");parser.add_argument("--json",action="store_true",required=True)
    args=parser.parse_args(argv)
    try:result=permanently_remove_instrument(args.database,args.asset,typed_confirmation=args.confirmation) if args.confirm else permanent_removal_impact(args.database,args.asset)
    except RetirementError as error:print(json.dumps({"code":error.code,"error":str(error)},sort_keys=True,separators=(",",":")));return 1
    print(json.dumps(result,sort_keys=True,separators=(",",":")));return 0

if __name__=="__main__":sys.exit(main())
