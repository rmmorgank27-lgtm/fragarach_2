"""Commit one reviewed instrument through the registered Python writer."""
import argparse,base64,json,sys,time
from dataclasses import asdict
from datetime import UTC,datetime
from fragarach_ii.providers.instrument_search import candidate_from_dict
from fragarach_ii.storage import RegistrationError,WriterLockError,initialize_database,register_instrument
from fragarach_ii.onboarding import register_provider_aware_instrument
from fragarach_ii.scheduler_daemon import ServicePaths, make_command, send_service_request
def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--database",required=True);p.add_argument("--candidate",required=True);p.add_argument("--manual-only",action="store_true");p.add_argument("--json",action="store_true");a=p.parse_args(argv)
    try:
        value=json.loads(base64.urlsafe_b64decode(a.candidate.encode()).decode());candidate=candidate_from_dict(value)
        result=_retry_when_writer_busy(lambda: _register_once(a.database,candidate,a.manual_only))
    except (ValueError,TypeError,json.JSONDecodeError,RegistrationError) as e:print(json.dumps({"code":getattr(e,"code","REGISTRATION_REJECTED"),"error":str(e)},sort_keys=True,separators=(",",":")));return 1
    _notify_scheduler(a.database)
    print(json.dumps(result,sort_keys=True,separators=(",",":")));return 0


def _register_once(database,candidate,manual_only):
    initialize_database(database)
    observed=datetime.now(UTC).isoformat()
    return (
        asdict(register_instrument(database,candidate,registered_at_utc=observed))
        if manual_only else
        register_provider_aware_instrument(database,candidate,registered_at_utc=observed)
    )


def _retry_when_writer_busy(operation,*,attempts=8,sleeper=time.sleep):
    """Absorb short Scheduler write sections before declining registration.

    The Scheduler and a user registration legitimately share one registered
    SQLite writer. Its provider commits are short, so a bounded retry keeps a
    normal Add to Estate action from failing merely because it arrived between
    a commit and its lock release. The last failure is deliberately surfaced
    as a stable operator message rather than a Python traceback.
    """
    for attempt in range(max(1,int(attempts))):
        try:
            return operation()
        except WriterLockError as error:
            if attempt + 1 >= max(1,int(attempts)):
                raise RegistrationError(
                    "WRITER_BUSY",
                    "The Scheduler is briefly committing authority data. No registration was made; try again in a few seconds.",
                ) from error
            sleeper(min(0.75,0.05 * (2 ** attempt)))


def _notify_scheduler(database):
    paths=ServicePaths.create(database)
    if not paths.socket.exists():return
    # Admission has already made the initial-history work durable. Ask the
    # live owner to refresh its routing facts and drain that work now rather
    # than leaving a newly-added instrument invisible until its next cadence.
    # Both requests are idempotent and the daemon journals their command IDs.
    for command in ("PROVIDER_FACT_REFRESH","RUN_QUEUE_NOW"):
        try:send_service_request(paths,make_command(command),timeout=2.0)
        except (OSError,ValueError,TimeoutError):pass
if __name__=="__main__":sys.exit(main())
