"""Discover a market and its onboarding options without authority mutation."""
import argparse,json,sqlite3,sys
from pathlib import Path
from fragarach_ii.market_discovery import discover_market
def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--database",required=True);p.add_argument("--query",required=True);p.add_argument("--json",action="store_true",required=True);a=p.parse_args(argv)
    try:result=discover_market(
        Path(a.database).expanduser().resolve(),a.query,resolve_crypto_catalogue=True
    )
    except (ValueError,FileNotFoundError,RuntimeError,sqlite3.Error) as e:print(json.dumps({"code":"MARKET_DISCOVERY_FAILED","error":str(e)},sort_keys=True,separators=(",",":")));return 1
    print(json.dumps(result,sort_keys=True,separators=(",",":")));return 0
if __name__=="__main__":sys.exit(main())
