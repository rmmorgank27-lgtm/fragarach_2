"""Emit the registry-derived SPEC-025 target-market timeframe audit."""
from __future__ import annotations
import argparse,json,sys
from collections.abc import Sequence
from fragarach_ii.estate_timeframe_audit import audit_target_timeframes

def main(argv:Sequence[str]|None=None)->int:
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--database",required=True);parser.add_argument("--output");parser.add_argument("--json",action="store_true")
    arguments=parser.parse_args(argv);payload=audit_target_timeframes(arguments.database);text=json.dumps(payload,indent=2,sort_keys=True)
    if arguments.output:
        with open(arguments.output,"w",encoding="utf-8") as handle:handle.write(text+"\n")
    if arguments.json or not arguments.output:print(text)
    return 0

if __name__=="__main__":sys.exit(main())
