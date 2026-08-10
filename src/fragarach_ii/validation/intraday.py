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


def validate_intraday_lane_incremental(
    database_path: str | Path,
    *,
    symbol: str,
    timeframe: str,
    through_date: str,
    canonical_inserts: int,
    canonical_corrections: int = 0,
    persist: bool = True,
    clock=None,
) -> ValidationResult:
    """Extend a trusted intraday summary when admission only moved its edge.

    The persisted v2 summary is a validation checkpoint.  We use it only when
    every newly inserted canonical row is strictly beyond the prior checked
    edge and no correction occurred.  Gap fills, backfills, stale summaries,
    authority changes, and corrections deliberately fall back to the complete
    validator.  Explicit operator validation always uses the complete path.
    """

    normalized_symbol = symbol.strip().upper()
    normalized_timeframe = timeframe.strip().upper()
    if canonical_inserts < 1 or canonical_corrections:
        return validate_intraday_lane(
            database_path, symbol=normalized_symbol, timeframe=normalized_timeframe,
            through_date=through_date, persist=persist, clock=clock,
        )
    now = (clock or (lambda: datetime.now(UTC)))().astimezone(UTC)
    try:
        through = date.fromisoformat(through_date)
    except ValueError as error:
        raise ValidationError("INVALID_THROUGH_DATE", through_date) from error
    boundary = min(now, datetime.combine(through, time.max, UTC))
    boundary_epoch = int(boundary.timestamp())
    db = Path(database_path)
    connection = open_read_only(db)
    try:
        row = connection.execute(
            """SELECT r.asset_class,r.gap_doctrine_id,r.gap_doctrine_version,
                      s.validation_summary
                 FROM evidence_lanes l
                 JOIN instrument_registrations r
                   ON r.asset=l.asset AND r.timeframe=l.registration_timeframe
                 JOIN lane_state s ON s.asset=l.asset AND s.timeframe=l.timeframe
                WHERE l.asset=? AND l.timeframe=?""",
            (normalized_symbol, normalized_timeframe),
        ).fetchone()
        if not row:
            raise ValidationError("UNDECLARED_LANE", f"{normalized_symbol}:{normalized_timeframe}")
        profile = profile_for(row[0], normalized_timeframe)
        try:
            prior = json.loads(row[3]) if row[3] else None
        except (json.JSONDecodeError, TypeError):
            prior = None
        if not _incremental_summary_matches(
            prior, symbol=normalized_symbol, timeframe=normalized_timeframe,
            profile=profile, gap_doctrine_id=row[1], gap_doctrine_version=row[2],
            boundary=boundary,
        ):
            return validate_intraday_lane(
                db, symbol=normalized_symbol, timeframe=normalized_timeframe,
                through_date=through_date, persist=persist, clock=clock,
            )
        previous_latest = int(datetime.fromisoformat(
            str(prior["latest_expected_closed_interval_open_utc"])
        ).timestamp())
        earliest_open = int(connection.execute(
            "SELECT min(open_time_utc) FROM bars WHERE asset=? AND timeframe=?",
            (normalized_symbol, normalized_timeframe),
        ).fetchone()[0])
        tail_count = int(connection.execute(
            """SELECT count(*) FROM bars
                WHERE asset=? AND timeframe=? AND open_time_utc>?""",
            (normalized_symbol, normalized_timeframe, previous_latest),
        ).fetchone()[0])
        if tail_count != canonical_inserts:
            return validate_intraday_lane(
                db, symbol=normalized_symbol, timeframe=normalized_timeframe,
                through_date=through_date, persist=persist, clock=clock,
            )
        tail = connection.execute(
            """SELECT open_time_utc,close_time_utc FROM bars
                WHERE asset=? AND timeframe=? AND open_time_utc>?
                ORDER BY open_time_utc""",
            (normalized_symbol, normalized_timeframe, previous_latest),
        ).fetchall()
        invalid = next((opened for opened, closed in tail if (
            closed != opened + profile.seconds
            or not is_aligned_open(opened, profile)
            or closed > int(now.timestamp())
        )), None)
        if invalid is not None:
            raise ValidationError("INVALID_INTRADAY_CANONICAL_BAR", str(invalid))

        expected = expected_opens(
            previous_latest + profile.seconds, boundary_epoch, profile
        )
        expected_set = set(expected)
        present = {opened for opened, closed in tail if closed <= boundary_epoch}
        new_present_expected = len(present & expected_set)
        missing_count = int(prior["missing_expected_interval_count"]) + (
            len(expected) - new_present_expected
        )
        latest = expected[-1] if expected else previous_latest
        recent_candidates = expected_opens(
            max(earliest_open, latest - 30 * profile.seconds),
            latest + profile.seconds,
            profile,
        )
        recent_present: set[int] = set()
        if recent_candidates:
            recent_present = {
                int(value[0]) for value in connection.execute(
                    """SELECT open_time_utc FROM bars
                        WHERE asset=? AND timeframe=?
                          AND open_time_utc BETWEEN ? AND ?""",
                    (
                        normalized_symbol, normalized_timeframe,
                        recent_candidates[0], recent_candidates[-1],
                    ),
                ).fetchall()
            }
    finally:
        connection.close()

    gap_path = Path(__file__).resolve().parents[3] / "config/gap_doctrine.v1.json"
    gap_checksum = hashlib.sha256(gap_path.read_bytes()).hexdigest()
    material = sum(value not in recent_present for value in recent_candidates)
    factual = {
        "format": FORMAT,
        "symbol": normalized_symbol,
        "timeframe": normalized_timeframe,
        "calendar_id": profile.calendar_id,
        "calendar_version": 1,
        "calendar_checksum": profile.checksum,
        "session_profile_id": profile.session_profile_id,
        "session_profile_version": 1,
        "session_profile_checksum": profile.checksum,
        "gap_doctrine_id": row[1],
        "gap_doctrine_version": row[2],
        "gap_doctrine_checksum": gap_checksum,
        "validator_version": VERSION,
        "boundary_utc": boundary.isoformat(),
        "expected_interval_count": int(prior["expected_interval_count"]) + len(expected),
        "present_expected_interval_count": int(prior["present_expected_interval_count"]) + new_present_expected,
        "missing_expected_interval_count": missing_count,
        "outside_expected_interval_count": int(prior["outside_expected_interval_count"]) + len(present - expected_set),
        "latest_expected_closed_interval_open_utc": iso(latest),
        "latest_expected_closed_interval_end_utc": iso(latest + profile.seconds),
        "latest_expected_closed_interval_present": latest in (
            present if expected else recent_present
        ),
        "material_gap_count": material,
        "non_material_gap_count": max(0, missing_count - material),
    }
    result = ValidationResult(factual, now.isoformat())
    if persist:
        with registered_writer(db) as writer:
            apply_migrations(writer)
            with transaction(writer):
                cursor = writer.execute(
                    "UPDATE lane_state SET validation_summary=? WHERE asset=? AND timeframe=?",
                    (result.lane_summary().as_json(), normalized_symbol, normalized_timeframe),
                )
                if cursor.rowcount != 1:
                    raise ValidationError(
                        "LANE_STATE_NOT_FOUND", f"{normalized_symbol}:{normalized_timeframe}"
                    )
    return result


def _incremental_summary_matches(
    value,
    *,
    symbol: str,
    timeframe: str,
    profile,
    gap_doctrine_id: str,
    gap_doctrine_version: int,
    boundary: datetime,
) -> bool:
    if not isinstance(value, dict):
        return False
    required = {
        "format": "fragarach_ii.lane_validation_summary.v2",
        "symbol": symbol,
        "timeframe": timeframe,
        "calendar_id": profile.calendar_id,
        "calendar_checksum": profile.checksum,
        "session_profile_id": profile.session_profile_id,
        "session_profile_checksum": profile.checksum,
        "gap_doctrine_id": gap_doctrine_id,
        "gap_doctrine_version": gap_doctrine_version,
        "validator_version": VERSION,
    }
    if any(value.get(key) != expected for key, expected in required.items()):
        return False
    try:
        prior_boundary = datetime.fromisoformat(str(value["boundary_utc"]))
        latest = datetime.fromisoformat(
            str(value["latest_expected_closed_interval_open_utc"])
        )
        for key in (
            "expected_interval_count", "present_expected_interval_count",
            "missing_expected_interval_count", "outside_expected_interval_count",
        ):
            if int(value[key]) < 0:
                return False
    except (KeyError, TypeError, ValueError):
        return False
    return (
        prior_boundary.tzinfo is not None
        and latest.tzinfo is not None
        and prior_boundary <= boundary
    )
