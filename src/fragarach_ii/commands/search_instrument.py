"""Search and review exactly one provider instrument without writing authority."""
import argparse,json,sys
from fragarach_ii.credentials import CredentialAuthority
from fragarach_ii.providers.instrument_search import InstrumentSearchError,search_instrument
def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--database",required=True);p.add_argument("--query",required=True);p.add_argument("--json",action="store_true");a=p.parse_args(argv)
    try:result=search_instrument(a.database,a.query,credential=CredentialAuthority().credential_for("TWELVE_DATA"))
    except InstrumentSearchError as e:print(json.dumps({"code":e.code,"error":str(e)},sort_keys=True,separators=(",",":")));return 1
    print(result.as_json());return 0
if __name__=="__main__":sys.exit(main())
