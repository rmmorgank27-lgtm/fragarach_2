"""Immutable generic authority-event ledger for SPEC-008A1."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .database import open_read_only, registered_writer, transaction
from .migrations import apply_migrations

LEDGER_CONTRACT = "AUTHORITY_EVENT_LEDGER_V1"
PAYLOAD_FORMAT = "fragarach_ii.authority_event_payload.v1"
ENTITY_KINDS = {"INSTRUMENT_REGISTRATION", "PROVIDER_MAPPING", "EVIDENCE_LANE"}
COMPATIBILITY_STATES = {"COMPATIBLE", "INCOMPATIBLE_PROVIDER_MAPPING", "SOURCE_CONTRACT_PROBLEM",
    "INSUFFICIENT_EFFECTIVE_RANGE", "AUTHORITY_GAP", "ENTITLEMENT_BLOCKED", "UNRESOLVED_MATERIAL_FACT"}
EVENT_ENTITY = {
    "LEGACY_REGISTRATION_BOUND":"INSTRUMENT_REGISTRATION", "REGISTRATION_DECLARED":"INSTRUMENT_REGISTRATION",
    "REGISTRATION_REVISED":"INSTRUMENT_REGISTRATION", "REGISTRATION_REJECTED":"INSTRUMENT_REGISTRATION",
    "REGISTRATION_SUPERSEDED":"INSTRUMENT_REGISTRATION", "PROVIDER_MAPPING_DISCOVERED":"PROVIDER_MAPPING",
    "PROVIDER_MAPPING_REVIEWED":"PROVIDER_MAPPING", "PROVIDER_MAPPING_APPROVED":"PROVIDER_MAPPING",
    "PROVIDER_MAPPING_REJECTED":"PROVIDER_MAPPING", "PROVIDER_MAPPING_SUPERSEDED":"PROVIDER_MAPPING",
    "LEGACY_LANE_BOUND":"EVIDENCE_LANE", "LANE_CANDIDATE_RETAINED":"EVIDENCE_LANE",
    "LANE_DECLARED":"EVIDENCE_LANE", "LANE_REVISED":"EVIDENCE_LANE", "LANE_REJECTED":"EVIDENCE_LANE",
    "LANE_SUPERSEDED":"EVIDENCE_LANE",
}
CROSS_CUTTING = {"ENTITLEMENT_CHANGED", "EFFECTIVE_RANGE_CHANGED", "AUTHORITY_BINDING_CHANGED",
    "COMPATIBILITY_FINDING_RECORDED", "COMPATIBILITY_FINDING_SUPERSEDED"}
SUPERSEDING_KINDS = {"REGISTRATION_REVISED", "REGISTRATION_SUPERSEDED", "PROVIDER_MAPPING_REVIEWED",
    "PROVIDER_MAPPING_APPROVED", "PROVIDER_MAPPING_SUPERSEDED", "LANE_REVISED", "LANE_SUPERSEDED",
    "ENTITLEMENT_CHANGED", "EFFECTIVE_RANGE_CHANGED", "AUTHORITY_BINDING_CHANGED",
    "COMPATIBILITY_FINDING_SUPERSEDED"}


class AuthorityLedgerError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class AuthorityEventManifest:
    entity_kind: str
    entity_id: str
    event_kind: str
    effective_from_utc: str
    recorded_by: str
    authority_bindings: tuple[dict[str, Any], ...]
    compatibility_state: str
    compatibility_reasons: tuple[dict[str, Any], ...]
    body: dict[str, Any]
    supersedes_event_id: str | None = None
    effective_to_utc: str | None = None


@dataclass(frozen=True, slots=True)
class PreparedAuthorityEvent:
    authority_event_id: str
    ledger_contract: str
    ledger_contract_version: int
    entity_kind: str
    entity_id: str
    event_kind: str
    supersedes_event_id: str | None
    effective_from_utc: str
    effective_to_utc: str | None
    canonical_payload: str
    payload_checksum_sha256: str
    event_checksum_sha256: str
    recorded_by: str


@dataclass(frozen=True, slots=True)
class AuthorityEventResult:
    operation_contract: str
    outcome: str
    authority_event_id: str
    entity_kind: str
    entity_id: str
    event_kind: str
    payload_checksum_sha256: str
    event_checksum_sha256: str
    def as_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))


def canonical_json(value: Any) -> str:
    _validate_json_value(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def prepare_authority_event(manifest: AuthorityEventManifest) -> PreparedAuthorityEvent:
    _validate_manifest(manifest)
    bindings = tuple(sorted(manifest.authority_bindings, key=lambda b: (str(b.get("document_id")), str(b.get("version")), str(b.get("path")))))
    reasons = tuple(sorted(manifest.compatibility_reasons, key=canonical_json))
    payload = {"authority_bindings":bindings, "body":manifest.body,
        "compatibility_reasons":reasons, "compatibility_state":manifest.compatibility_state,
        "entity_id":manifest.entity_id, "entity_kind":manifest.entity_kind,
        "event_kind":manifest.event_kind, "format":PAYLOAD_FORMAT}
    canonical_payload = canonical_json(payload)
    payload_checksum = hashlib.sha256(canonical_payload.encode()).hexdigest()
    identity = {"effective_from_utc":manifest.effective_from_utc,"effective_to_utc":manifest.effective_to_utc,
        "entity_id":manifest.entity_id,"entity_kind":manifest.entity_kind,"event_kind":manifest.event_kind,
        "ledger_contract":LEDGER_CONTRACT,"ledger_contract_version":1,"payload_checksum_sha256":payload_checksum,
        "recorded_by":manifest.recorded_by,"supersedes_event_id":manifest.supersedes_event_id}
    event_checksum = hashlib.sha256(canonical_json(identity).encode()).hexdigest()
    return PreparedAuthorityEvent(event_checksum,LEDGER_CONTRACT,1,manifest.entity_kind,manifest.entity_id,
        manifest.event_kind,manifest.supersedes_event_id,manifest.effective_from_utc,manifest.effective_to_utc,
        canonical_payload,payload_checksum,event_checksum,manifest.recorded_by)


def append_authority_event(database_path: str | Path, manifest: AuthorityEventManifest, *,
        recorded_at_utc: str | None = None, dry_run: bool = False) -> AuthorityEventResult:
    prepared = prepare_authority_event(manifest)
    if dry_run:
        return _result("DRY_RUN", prepared)
    observed = recorded_at_utc or datetime.now(UTC).isoformat()
    _utc(observed, "recorded_at_utc")
    with registered_writer(database_path) as connection:
        apply_migrations(connection)
        with transaction(connection):
            existing = connection.execute("SELECT * FROM authority_events WHERE authority_event_id=?",(prepared.authority_event_id,)).fetchone()
            if existing is not None:
                expected=(prepared.authority_event_id,prepared.ledger_contract,prepared.ledger_contract_version,
                    prepared.entity_kind,prepared.entity_id,prepared.event_kind,prepared.supersedes_event_id,
                    prepared.effective_from_utc,prepared.effective_to_utc,prepared.canonical_payload,
                    prepared.payload_checksum_sha256,prepared.event_checksum_sha256,existing[12],prepared.recorded_by)
                if tuple(existing)!=expected: raise AuthorityLedgerError("CHECKSUM_INTEGRITY_FAILURE",prepared.authority_event_id)
                return _result("UNCHANGED",prepared)
            _validate_predecessor(connection, prepared)
            connection.execute("INSERT INTO authority_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(
                prepared.authority_event_id,prepared.ledger_contract,prepared.ledger_contract_version,
                prepared.entity_kind,prepared.entity_id,prepared.event_kind,prepared.supersedes_event_id,
                prepared.effective_from_utc,prepared.effective_to_utc,prepared.canonical_payload,
                prepared.payload_checksum_sha256,prepared.event_checksum_sha256,observed,prepared.recorded_by))
        row=connection.execute("SELECT canonical_payload,payload_checksum_sha256,event_checksum_sha256 FROM authority_events WHERE authority_event_id=?",(prepared.authority_event_id,)).fetchone()
        if row is None or hashlib.sha256(row[0].encode()).hexdigest()!=row[1] or row[2]!=prepared.event_checksum_sha256:
            raise AuthorityLedgerError("READBACK_FAILED",prepared.authority_event_id)
    return _result("INSERTED",prepared)


def inspect_authority(database_path: str | Path, *, entity_kind: str | None=None, entity_id: str | None=None) -> list[dict[str,Any]]:
    connection=open_read_only(database_path)
    try:
        sql="SELECT authority_event_id,entity_kind,entity_id,event_kind,supersedes_event_id,effective_from_utc,effective_to_utc,canonical_payload,payload_checksum_sha256,event_checksum_sha256,recorded_at_utc,recorded_by FROM authority_events"
        args:list[str]=[]; clauses=[]
        if entity_kind: clauses.append("entity_kind=?");args.append(entity_kind)
        if entity_id: clauses.append("entity_id=?");args.append(entity_id)
        if clauses: sql += " WHERE "+" AND ".join(clauses)
        sql += " ORDER BY entity_kind,entity_id,effective_from_utc,recorded_at_utc,authority_event_id"
        rows=connection.execute(sql,args).fetchall()
        keys=("authority_event_id","entity_kind","entity_id","event_kind","supersedes_event_id","effective_from_utc","effective_to_utc","payload","payload_checksum_sha256","event_checksum_sha256","recorded_at_utc","recorded_by")
        return [dict(zip(keys,(*row[:7],json.loads(row[7]),*row[8:]))) for row in rows]
    finally: connection.close()


def reconstruct_authority(database_path: str | Path, *, as_of_utc: str | None=None) -> list[dict[str,Any]]:
    events=inspect_authority(database_path); by_id={e["authority_event_id"]:e for e in events}
    superseded={e["supersedes_event_id"] for e in events if e["supersedes_event_id"]}
    result=[]
    for event in events:
        if event["authority_event_id"] in superseded: continue
        if event["event_kind"].endswith("REJECTED") or event["event_kind"]=="LANE_CANDIDATE_RETAINED": continue
        if as_of_utc and not _covers(event,as_of_utc): continue
        chain=[];current=event;seen=set()
        while current:
            if current["authority_event_id"] in seen: raise AuthorityLedgerError("SUPERSESSION_CYCLE",current["entity_id"])
            seen.add(current["authority_event_id"]);chain.append(current["authority_event_id"])
            current=by_id.get(current["supersedes_event_id"])
        item=dict(event);item["supersession_chain"]=tuple(reversed(chain));result.append(item)
    return result


def bootstrap_legacy_authority(database_path: str | Path, *, dry_run: bool=False) -> list[AuthorityEventResult]:
    connection=open_read_only(database_path)
    try:
        registrations=connection.execute("SELECT asset,timeframe,registered_at_utc,identity_json,identity_checksum_sha256,registration_status,asset_class FROM instrument_registrations ORDER BY asset,timeframe").fetchall()
        lanes=connection.execute("SELECT asset,timeframe,registration_timeframe,lane_contract,lane_contract_version,created_at_utc FROM evidence_lanes ORDER BY asset,timeframe").fetchall()
    finally: connection.close()
    root=Path(__file__).resolve().parents[3]
    def binding(path: str) -> dict[str,Any]:
        content=(root/path).read_bytes()
        return {"document_id":Path(path).stem,"path":path,"sha256":hashlib.sha256(content).hexdigest(),"version":1}
    common=(binding("constitution/CONSTITUTION.md"),binding("specs/foundation/SPEC-008A1_IMMUTABLE_AUTHORITY_LEDGER_AMENDMENT.md"))
    families={"FX":("FX","fx"),"CRYPTO":("CRYPTO","crypto"),"METALS":("METALS","metals"),"ENERGY":("ENERGY","energy"),"INDICES":("INDICES","indices"),
        "US_EQUITIES":("US_EQUITIES","equities_us"),"UK_EQUITIES":("UK_EQUITIES","equities_uk"),"GERMAN_EQUITIES":("GERMAN_EQUITIES","equities_de"),"AUSTRALIAN_EQUITIES":("AUSTRALIAN_EQUITIES","equities_au")}
    registration_bindings={}
    results=[]
    for asset,timeframe,created,identity,checksum,status,asset_class in registrations:
        family,directory=families[asset_class]
        bindings=common+(binding(f"constitution/doctrines/{family}_BASE_DOCTRINE_V1.md"),binding(f"constitution/authorities/{directory}/{family}_{timeframe}_AUTHORITY_V1.md"))
        registration_bindings[asset]=bindings
        body={"legacy_key":{"asset":asset,"registration_timeframe":timeframe},"legacy_identity":json.loads(identity),
            "legacy_identity_checksum_sha256":checksum,"legacy_registration_status":status,
            "metadata_completeness":"UNRESOLVED","unresolved_facts":["adjustment_basis","approved_effective_range","canonical_unit","session_profile_id"]}
        manifest=AuthorityEventManifest("INSTRUMENT_REGISTRATION",f"legacy-registration:{asset}:{timeframe}","LEGACY_REGISTRATION_BOUND",created,
            "SPEC-008A1_BOOTSTRAP",bindings,"UNRESOLVED_MATERIAL_FACT",({"code":"LEGACY_METADATA_INCOMPLETE"},),body)
        results.append(append_authority_event(database_path,manifest,recorded_at_utc=created,dry_run=dry_run))
    for asset,timeframe,registration_timeframe,contract,version,created in lanes:
        body={"activation_state":"ACTIVE" if timeframe=="D1" else "DECLARED","legacy_key":{"asset":asset,"timeframe":timeframe},
            "lane_contract":contract,"lane_contract_version":version,"registration_entity_id":f"legacy-registration:{asset}:{registration_timeframe}",
            "metadata_completeness":"UNRESOLVED","accepted_historical_evidence_readable":True}
        manifest=AuthorityEventManifest("EVIDENCE_LANE",f"legacy-lane:{asset}:{timeframe}","LEGACY_LANE_BOUND",created,
            "SPEC-008A1_BOOTSTRAP",registration_bindings[asset],"UNRESOLVED_MATERIAL_FACT",({"code":"LEGACY_METADATA_INCOMPLETE"},),body)
        results.append(append_authority_event(database_path,manifest,recorded_at_utc=created,dry_run=dry_run))
    return results


def _validate_manifest(m: AuthorityEventManifest) -> None:
    if m.entity_kind not in ENTITY_KINDS: raise AuthorityLedgerError("INVALID_ENTITY_KIND",m.entity_kind)
    expected=EVENT_ENTITY.get(m.event_kind)
    if expected and expected!=m.entity_kind: raise AuthorityLedgerError("INVALID_EVENT_ENTITY",m.event_kind)
    if not expected and m.event_kind not in CROSS_CUTTING: raise AuthorityLedgerError("INVALID_EVENT_KIND",m.event_kind)
    if not m.entity_id or m.entity_id!=m.entity_id.strip(): raise AuthorityLedgerError("INVALID_ENTITY_ID",m.entity_id)
    if not m.recorded_by or m.recorded_by!=m.recorded_by.strip(): raise AuthorityLedgerError("INVALID_ACTOR",m.recorded_by)
    _utc(m.effective_from_utc,"effective_from_utc")
    if m.effective_to_utc:
        start=_utc(m.effective_from_utc,"effective_from_utc");end=_utc(m.effective_to_utc,"effective_to_utc")
        if end<=start: raise AuthorityLedgerError("INVALID_EFFECTIVE_RANGE",m.entity_id)
    if m.compatibility_state not in COMPATIBILITY_STATES: raise AuthorityLedgerError("INVALID_COMPATIBILITY_STATE",m.compatibility_state)
    if m.compatibility_state=="COMPATIBLE" and m.compatibility_reasons: raise AuthorityLedgerError("INVALID_COMPATIBILITY_REASONS",m.entity_id)
    if m.compatibility_state!="COMPATIBLE" and not m.compatibility_reasons: raise AuthorityLedgerError("MISSING_COMPATIBILITY_REASON",m.entity_id)
    if m.event_kind in {"REGISTRATION_DECLARED","REGISTRATION_REVISED","PROVIDER_MAPPING_APPROVED","LANE_DECLARED","LANE_REVISED"} and m.compatibility_state!="COMPATIBLE":
        raise AuthorityLedgerError("UNRESOLVED_MATERIAL_FACT",m.entity_id)
    if m.event_kind=="LANE_DECLARED" and m.body.get("activation_state") not in {"DECLARED","ACTIVE_NO_EVIDENCE","ACTIVE","AMBER"}: raise AuthorityLedgerError("INVALID_ACTIVATION_STATE",m.entity_id)
    for binding in m.authority_bindings:
        if set(binding)!={"document_id","path","sha256","version"}: raise AuthorityLedgerError("INVALID_AUTHORITY_BINDING",m.entity_id)


def _validate_predecessor(connection, p: PreparedAuthorityEvent) -> None:
    if p.event_kind in SUPERSEDING_KINDS and not p.supersedes_event_id:
        raise AuthorityLedgerError("MISSING_SUPERSESSION",p.event_kind)
    if p.supersedes_event_id:
        row=connection.execute("SELECT entity_kind,entity_id,effective_from_utc FROM authority_events WHERE authority_event_id=?",(p.supersedes_event_id,)).fetchone()
        if row is None: raise AuthorityLedgerError("MISSING_PREDECESSOR",p.supersedes_event_id)
        if row[0:2]!=(p.entity_kind,p.entity_id): raise AuthorityLedgerError("SUPERSESSION_IDENTITY_MISMATCH",p.entity_id)
        if _utc(p.effective_from_utc,"effective_from_utc") < _utc(row[2],"predecessor_effective_from"): raise AuthorityLedgerError("INVALID_SUPERSESSION_RANGE",p.entity_id)


def _validate_json_value(value: Any) -> None:
    if isinstance(value,float): raise AuthorityLedgerError("FLOAT_FORBIDDEN","canonical JSON")
    if isinstance(value,dict):
        if any(not isinstance(k,str) for k in value): raise AuthorityLedgerError("INVALID_JSON_KEY","canonical JSON")
        for v in value.values(): _validate_json_value(v)
    elif isinstance(value,(list,tuple)):
        for v in value: _validate_json_value(v)
    elif value is not None and not isinstance(value,(str,int,bool)):
        raise AuthorityLedgerError("INVALID_JSON_VALUE",type(value).__name__)


def _utc(value: str, name: str) -> datetime:
    try: parsed=datetime.fromisoformat(value)
    except ValueError as error: raise AuthorityLedgerError("INVALID_TIMESTAMP",name) from error
    if parsed.utcoffset()!=UTC.utcoffset(parsed) or not value.endswith("+00:00"): raise AuthorityLedgerError("INVALID_TIMESTAMP",name)
    return parsed


def _covers(event: dict[str,Any], as_of: str) -> bool:
    instant=_utc(as_of,"as_of_utc");start=_utc(event["effective_from_utc"],"effective_from_utc")
    return start<=instant and (event["effective_to_utc"] is None or instant<_utc(event["effective_to_utc"],"effective_to_utc"))


def _result(outcome: str,p: PreparedAuthorityEvent) -> AuthorityEventResult:
    return AuthorityEventResult("fragarach_ii.authority_event_result.v1",outcome,p.authority_event_id,p.entity_kind,p.entity_id,p.event_kind,p.payload_checksum_sha256,p.event_checksum_sha256)
