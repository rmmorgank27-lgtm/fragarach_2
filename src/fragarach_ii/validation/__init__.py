"""Deterministic factual validation; consumers interpret the result."""

from .d1_sessions import ValidationError, validate_lane as validate_d1_lane
from .intraday import validate_intraday_lane
from .result import ValidationResult

def validate_lane(database_path,*,symbol,timeframe,through_date,persist=False,config_root=None,clock=None):
    if timeframe.strip().upper()=="D1":return validate_d1_lane(database_path,symbol=symbol,timeframe=timeframe,through_date=through_date,persist=persist,config_root=config_root,clock=clock)
    return validate_intraday_lane(database_path,symbol=symbol,timeframe=timeframe,through_date=through_date,persist=persist,clock=clock)

__all__ = ["ValidationError", "ValidationResult", "validate_lane"]
