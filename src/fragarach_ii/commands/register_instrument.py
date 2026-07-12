"""Commit one reviewed instrument through the registered Python writer."""
import argparse,base64,json,sys
from datetime import UTC,datetime
from fragarach_ii.providers.instrument_search import candidate_from_dict
from fragarach_ii.storage import RegistrationError,register_instrument
from fragarach_ii.fx_orientation import validate_direct_mapping
def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--database",required=True);p.add_argument("--candidate",required=True);p.add_argument("--json",action="store_true");a=p.parse_args(argv)
    try:
        value=json.loads(base64.urlsafe_b64decode(a.candidate.encode()).decode());candidate=candidate_from_dict(value)
        if candidate.asset_class=="FX":validate_direct_mapping(candidate.asset,candidate.provider_id,candidate.provider_symbol)
        result=register_instrument(a.database,candidate,registered_at_utc=datetime.now(UTC).isoformat())
    except (ValueError,TypeError,json.JSONDecodeError,RegistrationError) as e:print(json.dumps({"code":getattr(e,"code","REGISTRATION_REJECTED"),"error":str(e)},sort_keys=True,separators=(",",":")));return 1
    print(result.as_json());return 0
if __name__=="__main__":sys.exit(main())
