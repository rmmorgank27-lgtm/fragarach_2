"""Timeframe-aware closed-interval validation for commissioned intraday lanes."""
from __future__ import annotations
import hashlib,json
from datetime import UTC,date,datetime,time
from pathlib import Path
from fragarach_ii.storage import open_read_only,registered_writer,transaction
from fragarach_ii.storage.migrations import apply_migrations
from .d1_sessions import ValidationError
from .intraday_profiles import expected_opens,iso,profile_for,is_aligned_open
from .result import ValidationResult

FORMAT="fragarach_ii.intraday_validation.v1";VERSION="SPEC-025_INTRADAY_VALIDATOR_V1"

def validate_intraday_lane(database_path:str|Path,*,symbol:str,timeframe:str,through_date:str,persist:bool=False,clock=None)->ValidationResult:
    symbol=symbol.strip().upper();timeframe=timeframe.strip().upper()
    try:through=date.fromisoformat(through_date)
    except ValueError as error:raise ValidationError("INVALID_THROUGH_DATE",through_date) from error
    now=(clock or (lambda:datetime.now(UTC)))().astimezone(UTC)
    boundary=min(now,datetime.combine(through,time.max,UTC));db=Path(database_path)
    c=open_read_only(db)
    try:
        row=c.execute("""SELECT r.asset_class,r.gap_doctrine_id,r.gap_doctrine_version
          FROM evidence_lanes l JOIN instrument_registrations r ON r.asset=l.asset AND r.timeframe=l.registration_timeframe
          WHERE l.asset=? AND l.timeframe=?""",(symbol,timeframe)).fetchone()
        if not row:raise ValidationError("UNDECLARED_LANE",f"{symbol}:{timeframe}")
        profile=profile_for(row[0],timeframe)
        bars=c.execute("SELECT open_time_utc,close_time_utc FROM bars WHERE asset=? AND timeframe=? ORDER BY open_time_utc",(symbol,timeframe)).fetchall()
    finally:c.close()
    if not bars:raise ValidationError("LANE_NOT_FOUND",f"{symbol}:{timeframe}")
    invalid=[o for o,e in bars if e!=o+profile.seconds or not is_aligned_open(o,profile) or e>int(now.timestamp())]
    if invalid:raise ValidationError("INVALID_INTRADAY_CANONICAL_BAR",str(invalid[0]))
    present={o for o,_ in bars if o+profile.seconds<=int(boundary.timestamp())}
    expected=expected_opens(min(o for o,_ in bars),int(boundary.timestamp()),profile);expected_set=set(expected)
    missing=expected_set-present;outside=present-expected_set;latest=expected[-1] if expected else max(present)
    gap_path=Path(__file__).resolve().parents[3]/"config/gap_doctrine.v1.json";gap_checksum=hashlib.sha256(gap_path.read_bytes()).hexdigest()
    factual={"format":FORMAT,"symbol":symbol,"timeframe":timeframe,"calendar_id":profile.calendar_id,"calendar_version":1,"calendar_checksum":profile.checksum,
      "session_profile_id":profile.session_profile_id,"session_profile_version":1,"session_profile_checksum":profile.checksum,
      "gap_doctrine_id":row[1],"gap_doctrine_version":row[2],"gap_doctrine_checksum":gap_checksum,"validator_version":VERSION,
      "boundary_utc":boundary.isoformat(),"expected_interval_count":len(expected),"present_expected_interval_count":len(present&expected_set),
      "missing_expected_interval_count":len(missing),"outside_expected_interval_count":len(outside),
      "latest_expected_closed_interval_open_utc":iso(latest),"latest_expected_closed_interval_end_utc":iso(latest+profile.seconds),
      "latest_expected_closed_interval_present":latest in present,"material_gap_count":sum(x>=latest-30*profile.seconds for x in missing),
      "non_material_gap_count":sum(x<latest-30*profile.seconds for x in missing)}
    result=ValidationResult(factual,now.isoformat())
    if persist:
        with registered_writer(db) as connection:
            apply_migrations(connection)
            with transaction(connection):
                cursor=connection.execute("UPDATE lane_state SET validation_summary=? WHERE asset=? AND timeframe=?",(result.lane_summary().as_json(),symbol,timeframe))
                if cursor.rowcount!=1:raise ValidationError("LANE_STATE_NOT_FOUND",f"{symbol}:{timeframe}")
    return result
