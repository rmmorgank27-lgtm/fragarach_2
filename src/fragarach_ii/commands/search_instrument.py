"""Search and review exactly one provider instrument without writing authority."""
import argparse,json,os,sys
from fragarach_ii.providers.instrument_search import InstrumentSearchError,search_instrument
def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--database",required=True);p.add_argument("--query",required=True);p.add_argument("--json",action="store_true");a=p.parse_args(argv)
    try:result=search_instrument(a.database,a.query,credential=os.environ.get("TWELVE_DATA_API_KEY"))
    except InstrumentSearchError as e:print(json.dumps({"code":e.code,"error":str(e)},sort_keys=True,separators=(",",":")));return 1
    print(result.as_json());return 0
if __name__=="__main__":sys.exit(main())
