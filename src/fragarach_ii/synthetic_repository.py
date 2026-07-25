"""Explicit, rebuildable synthetic-timeframe repository and generator.

This module never writes to the canonical authority database.  Its governing
lineage rule is REAL -> SYNTHETIC, SYNTHETIC -> SYNTHETIC, and never the reverse.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from .freshness import authority_revision_for_lane
from .storage import open_read_only
from .validation.intraday_profiles import profile_for


REGISTRY_CONTRACT = "fragarach_ii.synthetic_registry.v1"
CONSUMER_CONTRACT = "fragarach_ii.synthetic_consumer.v1"
CONFIG_PATH = Path(__file__).resolve().parents[2] / "config/synthetic/synthetic_registry.v1.json"
EVIDENCE_CLASSES = {"REAL", "SYNTHETIC"}
SYNTHETIC_STATUSES = {"Available", "Stale", "Incomplete", "Unavailable"}
TIMEFRAME_SECONDS = {"M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H2": 7200, "H4": 14400}


class SyntheticRepositoryError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class AggregationRule:
    rule_id: str
    version: int
    source_timeframe: str
    target_timeframe: str
    calendar: str
    session_anchor: str
    interval_closure: str
    timezone: str
    required_component_count: int
    ohlc_calculation: str
    volume_handling: str
    missing_component_behaviour: str
    partial_current_period_behaviour: str

    @property
    def checksum(self) -> str:
        payload = json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()

    def as_dict(self) -> dict[str, object]:
        return {
            "rule_id": self.rule_id, "version": self.version,
            "source_timeframe": self.source_timeframe, "target_timeframe": self.target_timeframe,
            "calendar": self.calendar, "session_anchor": self.session_anchor,
            "interval_closure": self.interval_closure, "timezone": self.timezone,
            "required_component_count": self.required_component_count,
            "ohlc_calculation": self.ohlc_calculation, "volume_handling": self.volume_handling,
            "missing_component_behaviour": self.missing_component_behaviour,
            "partial_current_period_behaviour": self.partial_current_period_behaviour,
        }


def default_repository_path(authority_database: str | Path) -> Path:
    database = Path(authority_database).expanduser().resolve()
    configured = os.environ.get("FRAGARACH_SYNTHETIC_REPOSITORY")
    return Path(configured).expanduser().resolve() if configured else Path(f"{database}.synthetic.sqlite3")


def load_registry(path: str | Path | None = None) -> dict[str, object]:
    payload = json.loads(Path(path or CONFIG_PATH).read_text(encoding="utf-8"))
    if payload.get("contract") != REGISTRY_CONTRACT:
        raise SyntheticRepositoryError("INVALID_REGISTRY", "unsupported synthetic registry contract")
    rules: dict[tuple[str, int], AggregationRule] = {}
    for raw in payload.get("rules", []):
        rule = AggregationRule(**raw)
        _validate_rule(rule)
        key = (rule.rule_id, rule.version)
        if key in rules:
            raise SyntheticRepositoryError("DUPLICATE_RULE", f"{rule.rule_id}:v{rule.version}")
        rules[key] = rule
    registrations = []
    seen = set()
    for raw in payload.get("registrations", []):
        registration = _validate_registration(dict(raw), rules)
        key = (registration["symbol"], registration["target_timeframe"])
        if key in seen:
            raise SyntheticRepositoryError("DUPLICATE_REGISTRATION", ":".join(key))
        seen.add(key)
        registrations.append(registration)
    _validate_lineage_graph(registrations)
    return {"contract": REGISTRY_CONTRACT, "rules": rules, "registrations": registrations}


class SyntheticRepository:
    def __init__(
        self,
        authority_database: str | Path,
        repository_path: str | Path | None = None,
        registry_path: str | Path | None = None,
    ) -> None:
        self.authority_database = Path(authority_database).expanduser().resolve()
        self.path = Path(repository_path).expanduser().resolve() if repository_path else default_repository_path(self.authority_database)
        self.registry_path = Path(registry_path).expanduser().resolve() if registry_path else CONFIG_PATH

    def initialise(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(_SCHEMA)

    def activate_registry(self, *, generate_on_activation: bool = True) -> list[dict[str, object]]:
        registry = load_registry(self.registry_path)
        self.initialise()
        new_ids: list[str] = []
        with self._connect() as connection:
            for rule in registry["rules"].values():
                connection.execute(
                    """INSERT INTO aggregation_rules(rule_id,version,rule_json,checksum)
                       VALUES(?,?,?,?) ON CONFLICT(rule_id,version) DO UPDATE SET
                       rule_json=excluded.rule_json,checksum=excluded.checksum""",
                    (rule.rule_id, rule.version, _json(rule.as_dict()), rule.checksum),
                )
            for item in registry["registrations"]:
                self._verify_source_authority(connection, item)
                registration_id = f"{item['symbol']}:{item['target_timeframe']}"
                if connection.execute("SELECT 1 FROM synthetic_registrations WHERE registration_id=?", (registration_id,)).fetchone() is None:
                    new_ids.append(registration_id)
                connection.execute(
                    """INSERT INTO synthetic_registrations(
                       registration_id,symbol,target_timeframe,evidence_class,
                       immediate_source_symbol,immediate_source_timeframe,immediate_source_evidence_class,
                       originating_real_symbol,originating_real_timeframe,aggregation_rule_id,
                       aggregation_rule_version,calendar_authority,session_alignment,
                       authorised_consumers_json,registration_status,generation_status)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'Unavailable')
                       ON CONFLICT(registration_id) DO UPDATE SET
                       immediate_source_symbol=excluded.immediate_source_symbol,
                       immediate_source_timeframe=excluded.immediate_source_timeframe,
                       immediate_source_evidence_class=excluded.immediate_source_evidence_class,
                       originating_real_symbol=excluded.originating_real_symbol,
                       originating_real_timeframe=excluded.originating_real_timeframe,
                       aggregation_rule_id=excluded.aggregation_rule_id,
                       aggregation_rule_version=excluded.aggregation_rule_version,
                       calendar_authority=excluded.calendar_authority,
                       session_alignment=excluded.session_alignment,
                       authorised_consumers_json=excluded.authorised_consumers_json,
                       registration_status=excluded.registration_status""",
                    (
                        registration_id, item["symbol"], item["target_timeframe"], "SYNTHETIC",
                        item["immediate_source_symbol"], item["immediate_source_timeframe"],
                        item["immediate_source_evidence_class"], item["originating_real_symbol"],
                        item["originating_real_timeframe"], item["aggregation_rule"],
                        item["aggregation_rule_version"], item["calendar_authority"],
                        item["session_alignment"], _json(item["authorised_consumers"]), item["status"],
                    ),
                )
        if generate_on_activation and new_ids:
            self.generate_all()
        return self.list_products(refresh_status=False)

    def generate_all(self, *, generated_at: datetime | None = None) -> list[dict[str, object]]:
        self.activate_registry(generate_on_activation=False)
        results = []
        pending = {item["id"] for item in self.list_products(refresh_status=False) if item["registration_status"] == "ACTIVE"}
        while pending:
            progressed = False
            for registration_id in sorted(pending):
                try:
                    result = self.generate(registration_id, generated_at=generated_at)
                except SyntheticRepositoryError as error:
                    if error.code == "SOURCE_SYNTHETIC_UNAVAILABLE":
                        continue
                    result = {"id": registration_id, "status": "Unavailable", "reason": error.code}
                results.append(result)
                pending.remove(registration_id)
                progressed = True
                break
            if not progressed:
                for registration_id in sorted(pending):
                    self._set_failure(registration_id, "SOURCE_SYNTHETIC_UNAVAILABLE", "source synthetic product is unavailable", generated_at)
                    results.append({"id": registration_id, "status": "Unavailable", "reason": "SOURCE_SYNTHETIC_UNAVAILABLE"})
                break
        return results

    def generate(self, registration_id: str, *, generated_at: datetime | None = None) -> dict[str, object]:
        self.initialise()
        generated = _utc(generated_at)
        with self._connect() as connection:
            registration = connection.execute(
                "SELECT * FROM synthetic_registrations WHERE registration_id=?", (registration_id,)
            ).fetchone()
            if registration is None:
                raise SyntheticRepositoryError("UNREGISTERED_SYNTHETIC_PRODUCT", registration_id)
            if registration["evidence_class"] != "SYNTHETIC":
                raise SyntheticRepositoryError("SYNTHETIC_TO_REAL_FORBIDDEN", registration_id)
            rule = self._rule(connection, registration)
            source = self._source(connection, registration, generated)
            previous_source_revision = registration["source_revision"]
            previous_source_end = registration["source_observation_end"]
            full_rebuild = (
                previous_source_revision is None
                or source["revision"] == previous_source_revision
                or previous_source_end is None
                or int(source["latest_open"]) <= int(previous_source_end)
                or registration["rule_checksum"] != rule.checksum
            )
            affected_start = None if full_rebuild else _target_start(int(previous_source_end), rule)
            groups, incomplete = _aggregate(source["observations"], rule, generated, affected_start)
            if affected_start is None:
                connection.execute("DELETE FROM synthetic_observations WHERE registration_id=?", (registration_id,))
                connection.execute("DELETE FROM synthetic_provenance WHERE registration_id=?", (registration_id,))
            else:
                connection.execute("DELETE FROM synthetic_observations WHERE registration_id=? AND open_time_utc>=?", (registration_id, affected_start))
                connection.execute("DELETE FROM synthetic_provenance WHERE registration_id=? AND target_open_time_utc>=?", (registration_id, affected_start))
            lineage = list(source["lineage"]) + [{
                "symbol": registration["symbol"], "timeframe": registration["target_timeframe"],
                "evidence_class": "SYNTHETIC", "aggregation_rule": rule.rule_id,
                "aggregation_rule_version": rule.version,
            }]
            current_revision = int(registration["synthetic_revision"] or 0) + 1
            for target in groups:
                connection.execute(
                    """INSERT INTO synthetic_observations(
                       registration_id,open_time_utc,close_time_utc,open,high,low,close,volume,synthetic_revision)
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                    (registration_id, target["open_time"], target["close_time"], target["open"], target["high"], target["low"], target["close"], target["volume"], current_revision),
                )
                connection.execute(
                    """INSERT INTO synthetic_provenance(
                       registration_id,target_open_time_utc,source_observation_start,source_observation_end,
                       source_authority_revision,source_synthetic_revision,originating_real_authority_revision,
                       aggregation_rule_version,generated_time,complete_lineage_json)
                       VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (
                        registration_id, target["open_time"], target["source_start"], target["source_end"],
                        source["authority_revision"], source["synthetic_revision"], source["originating_real_revision"],
                        rule.version, generated.isoformat(), _json(lineage),
                    ),
                )
            aggregate = connection.execute(
                "SELECT count(*),min(open_time_utc),max(open_time_utc) FROM synthetic_observations WHERE registration_id=?",
                (registration_id,),
            ).fetchone()
            content_checksum = self._content_checksum(connection, registration_id)
            status = "Incomplete" if incomplete else ("Available" if aggregate[0] else "Unavailable")
            connection.execute(
                """UPDATE synthetic_registrations SET generation_status=?,source_revision=?,
                   originating_real_authority_revision=?,synthetic_revision=?,rule_checksum=?,
                   generated_at=?,source_observation_start=?,source_observation_end=?,
                   first_synthetic_observation=?,latest_synthetic_observation=?,observation_count=?,
                   complete_lineage_json=?,content_checksum=? WHERE registration_id=?""",
                (
                    status, source["revision"], source["originating_real_revision"], current_revision,
                    rule.checksum, generated.isoformat(), source["earliest_open"], source["latest_open"],
                    aggregate[1], aggregate[2], aggregate[0], _json(lineage), content_checksum, registration_id,
                ),
            )
            connection.execute("DELETE FROM generation_failures WHERE registration_id=?", (registration_id,))
            for failure in incomplete:
                connection.execute(
                    "INSERT INTO generation_failures(registration_id,target_open_time_utc,code,detail,recorded_at) VALUES(?,?,?,?,?)",
                    (registration_id, failure["target_open"], "MISSING_COMPONENTS", failure["detail"], generated.isoformat()),
                )
        return self.product(registration_id, refresh_status=False)

    def rebuild(self, *, generated_at: datetime | None = None) -> list[dict[str, object]]:
        self.path.unlink(missing_ok=True)
        self.initialise()
        self.activate_registry(generate_on_activation=False)
        return self.generate_all(generated_at=generated_at)

    def product(self, registration_id: str, *, refresh_status: bool = True) -> dict[str, object]:
        products = self.list_products(refresh_status=refresh_status)
        product = next((item for item in products if item["id"] == registration_id), None)
        if product is None:
            raise SyntheticRepositoryError("UNREGISTERED_SYNTHETIC_PRODUCT", registration_id)
        return product

    def list_products(self, *, refresh_status: bool = True) -> list[dict[str, object]]:
        if not self.path.exists():
            return []
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM synthetic_registrations ORDER BY symbol,target_timeframe").fetchall()
            products = []
            for row in rows:
                product = self._product_row(connection, row, refresh_status)
                products.append(product)
                if refresh_status:
                    connection.execute(
                        "UPDATE synthetic_registrations SET generation_status=? WHERE registration_id=?",
                        (product["status"], product["id"]),
                    )
            return products

    def observations(self, registration_id: str) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM synthetic_observations WHERE registration_id=? ORDER BY open_time_utc",
                (registration_id,),
            ).fetchall()
            provenance = {
                row["target_open_time_utc"]: row for row in connection.execute(
                    "SELECT * FROM synthetic_provenance WHERE registration_id=?", (registration_id,)
                ).fetchall()
            }
        return [{
            "timestamp": row["open_time_utc"], "close_time_utc": row["close_time_utc"],
            "open": row["open"], "high": row["high"], "low": row["low"], "close": row["close"],
            "volume": row["volume"], "synthetic_revision": row["synthetic_revision"],
            "provenance": {
                "source_observation_start": provenance[row["open_time_utc"]]["source_observation_start"],
                "source_observation_end": provenance[row["open_time_utc"]]["source_observation_end"],
                "source_authority_revision": provenance[row["open_time_utc"]]["source_authority_revision"],
                "source_synthetic_revision": provenance[row["open_time_utc"]]["source_synthetic_revision"],
                "originating_real_authority_revision": provenance[row["open_time_utc"]]["originating_real_authority_revision"],
                "aggregation_rule_version": provenance[row["open_time_utc"]]["aggregation_rule_version"],
                "generated_time": provenance[row["open_time_utc"]]["generated_time"],
                "complete_lineage": json.loads(provenance[row["open_time_utc"]]["complete_lineage_json"]),
            },
        } for row in rows]

    def _source(self, connection, registration, generated):
        symbol = registration["immediate_source_symbol"]
        timeframe = registration["immediate_source_timeframe"]
        source_class = registration["immediate_source_evidence_class"]
        if source_class == "REAL":
            with open_read_only(self.authority_database) as authority:
                lane = authority.execute("SELECT 1 FROM evidence_lanes WHERE asset=? AND timeframe=?", (symbol, timeframe)).fetchone()
                if lane is None:
                    raise SyntheticRepositoryError("SOURCE_REAL_LANE_UNAVAILABLE", f"{symbol}:{timeframe}")
                revision = authority_revision_for_lane(authority, symbol=symbol, timeframe=timeframe)
                rows = authority.execute(
                    """SELECT open_time_utc,coalesce(close_time_utc,open_time_utc+?),open,high,low,close,volume
                       FROM bars WHERE asset=? AND timeframe=? ORDER BY open_time_utc""",
                    (TIMEFRAME_SECONDS[timeframe], symbol, timeframe),
                ).fetchall()
            observations = [_source_observation(row) for row in rows if int(row[1]) <= int(generated.timestamp())]
            if not observations:
                raise SyntheticRepositoryError("SOURCE_REAL_HISTORY_UNAVAILABLE", f"{symbol}:{timeframe}")
            lineage = [{"symbol": symbol, "timeframe": timeframe, "evidence_class": "REAL", "authority_revision": revision}]
            return {
                "observations": observations, "revision": revision,
                "authority_revision": revision, "synthetic_revision": None,
                "originating_real_revision": revision, "lineage": lineage,
                "earliest_open": observations[0]["open_time"], "latest_open": observations[-1]["open_time"],
            }
        if source_class != "SYNTHETIC":
            raise SyntheticRepositoryError("INVALID_EVIDENCE_CLASS", source_class)
        source_id = f"{symbol}:{timeframe}"
        parent = connection.execute("SELECT * FROM synthetic_registrations WHERE registration_id=?", (source_id,)).fetchone()
        if parent is None or parent["generation_status"] not in {"Available", "Incomplete"}:
            raise SyntheticRepositoryError("SOURCE_SYNTHETIC_UNAVAILABLE", source_id)
        rows = connection.execute(
            "SELECT open_time_utc,close_time_utc,open,high,low,close,volume FROM synthetic_observations WHERE registration_id=? ORDER BY open_time_utc",
            (source_id,),
        ).fetchall()
        observations = [_source_observation(row) for row in rows if int(row[1]) <= int(generated.timestamp())]
        if not observations:
            raise SyntheticRepositoryError("SOURCE_SYNTHETIC_UNAVAILABLE", source_id)
        revision = f"synthetic:{parent['synthetic_revision']}:{parent['content_checksum']}"
        return {
            "observations": observations, "revision": revision,
            "authority_revision": parent["source_revision"],
            "synthetic_revision": parent["synthetic_revision"],
            "originating_real_revision": parent["originating_real_authority_revision"],
            "lineage": json.loads(parent["complete_lineage_json"]),
            "earliest_open": observations[0]["open_time"], "latest_open": observations[-1]["open_time"],
        }

    def _product_row(self, connection, row, refresh_status):
        status = row["generation_status"]
        if refresh_status and row["source_revision"]:
            if row["immediate_source_evidence_class"] == "SYNTHETIC":
                parent = connection.execute(
                    "SELECT * FROM synthetic_registrations WHERE registration_id=?",
                    (f"{row['immediate_source_symbol']}:{row['immediate_source_timeframe']}",),
                ).fetchone()
                if parent is None:
                    status = "Unavailable"
                else:
                    parent_status = self._product_row(connection, parent, True)["status"]
                    connection.execute(
                        "UPDATE synthetic_registrations SET generation_status=? WHERE registration_id=?",
                        (parent_status, parent["registration_id"]),
                    )
                if parent is not None and parent_status == "Stale":
                    status = "Stale"
                elif parent is not None and parent_status in {"Incomplete", "Unavailable"}:
                    status = parent_status
            try:
                if status not in {"Stale", "Unavailable"}:
                    current = self._source(connection, row, datetime.now(UTC))["revision"]
                    if current != row["source_revision"]:
                        status = "Stale"
            except SyntheticRepositoryError:
                status = "Unavailable"
        return {
            "id": row["registration_id"], "symbol": row["symbol"],
            "target_timeframe": row["target_timeframe"], "evidence_class": "SYNTHETIC",
            "immediate_source_symbol": row["immediate_source_symbol"],
            "immediate_source_timeframe": row["immediate_source_timeframe"],
            "immediate_source_evidence_class": row["immediate_source_evidence_class"],
            "originating_real_symbol": row["originating_real_symbol"],
            "originating_real_timeframe": row["originating_real_timeframe"],
            "aggregation_rule": row["aggregation_rule_id"],
            "aggregation_rule_version": row["aggregation_rule_version"],
            "calendar_authority": row["calendar_authority"], "session_alignment": row["session_alignment"],
            "authorised_consumers": json.loads(row["authorised_consumers_json"]),
            "registration_status": row["registration_status"], "status": status,
            "source_revision": row["source_revision"], "synthetic_revision": row["synthetic_revision"],
            "generated_at": row["generated_at"], "first_synthetic_observation": row["first_synthetic_observation"],
            "latest_synthetic_observation": row["latest_synthetic_observation"],
            "observation_count": row["observation_count"],
            "complete_lineage": json.loads(row["complete_lineage_json"] or "[]"),
        }

    def _verify_source_authority(self, connection, item):
        if item["immediate_source_evidence_class"] == "REAL":
            with open_read_only(self.authority_database) as authority:
                registration = authority.execute(
                    "SELECT asset_class FROM instrument_registrations WHERE asset=? AND timeframe='D1'",
                    (item["immediate_source_symbol"],),
                ).fetchone()
                lane = authority.execute(
                    "SELECT 1 FROM evidence_lanes WHERE asset=? AND timeframe=?",
                    (item["immediate_source_symbol"], item["immediate_source_timeframe"]),
                ).fetchone()
            if registration is None or lane is None:
                raise SyntheticRepositoryError("SOURCE_REAL_LANE_UNAVAILABLE", f"{item['immediate_source_symbol']}:{item['immediate_source_timeframe']}")
            profile = profile_for(str(registration[0]), item["immediate_source_timeframe"])
            if profile.calendar_id != item["calendar_authority"]:
                raise SyntheticRepositoryError("CALENDAR_AUTHORITY_MISMATCH", f"{item['immediate_source_symbol']}:{item['immediate_source_timeframe']}")
        else:
            parent = connection.execute(
                "SELECT evidence_class FROM synthetic_registrations WHERE registration_id=?",
                (f"{item['immediate_source_symbol']}:{item['immediate_source_timeframe']}",),
            ).fetchone()
            if parent is None or parent[0] != "SYNTHETIC":
                raise SyntheticRepositoryError("SOURCE_SYNTHETIC_UNAVAILABLE", f"{item['immediate_source_symbol']}:{item['immediate_source_timeframe']}")

    def _rule(self, connection, registration):
        row = connection.execute(
            "SELECT rule_json,checksum FROM aggregation_rules WHERE rule_id=? AND version=?",
            (registration["aggregation_rule_id"], registration["aggregation_rule_version"]),
        ).fetchone()
        if row is None:
            raise SyntheticRepositoryError("AGGREGATION_RULE_UNAVAILABLE", registration["registration_id"])
        rule = AggregationRule(**json.loads(row[0]))
        if rule.checksum != row[1]:
            raise SyntheticRepositoryError("AGGREGATION_RULE_CHECKSUM_MISMATCH", rule.rule_id)
        return rule

    def _content_checksum(self, connection, registration_id):
        rows = connection.execute(
            "SELECT open_time_utc,close_time_utc,open,high,low,close,volume FROM synthetic_observations WHERE registration_id=? ORDER BY open_time_utc",
            (registration_id,),
        ).fetchall()
        return "sha256:" + hashlib.sha256(_json([list(row) for row in rows]).encode()).hexdigest()

    def _set_failure(self, registration_id, code, detail, generated_at):
        generated = _utc(generated_at)
        with self._connect() as connection:
            connection.execute("UPDATE synthetic_registrations SET generation_status='Unavailable' WHERE registration_id=?", (registration_id,))
            connection.execute(
                "INSERT INTO generation_failures(registration_id,target_open_time_utc,code,detail,recorded_at) VALUES(?,NULL,?,?,?)",
                (registration_id, code, detail, generated.isoformat()),
            )

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection


class SyntheticConsumerService:
    def __init__(self, repository: SyntheticRepository) -> None:
        self.repository = repository

    def get_product(
        self, *, symbol: str, timeframe: str, consumer: str,
        evidence_requirement: str = "REAL_ONLY", regenerate_if_stale: bool = True,
    ) -> dict[str, object]:
        symbol, timeframe = symbol.strip().upper(), timeframe.strip().upper()
        requirement = evidence_requirement.strip().upper()
        registration_id = f"{symbol}:{timeframe}"
        try:
            product = self.repository.product(registration_id)
        except SyntheticRepositoryError:
            return self._real_product(symbol, timeframe, requirement)
        if consumer not in product["authorised_consumers"]:
            raise SyntheticRepositoryError("CONSUMER_NOT_AUTHORISED", f"{consumer}:{registration_id}")
        if requirement == "REAL_ONLY":
            return {
                "contract": CONSUMER_CONTRACT, "status": "SYNTHETIC_NOT_PERMITTED",
                "symbol": symbol, "timeframe": timeframe, "evidence_class": "SYNTHETIC",
                "source_lineage": product["complete_lineage"], "synthetic_revision": product["synthetic_revision"],
                "observations": [],
            }
        if requirement != "SYNTHETIC_PERMITTED":
            raise SyntheticRepositoryError("INVALID_EVIDENCE_REQUIREMENT", requirement)
        if product["status"] == "Stale" and regenerate_if_stale:
            self.repository.generate_all()
            product = self.repository.product(registration_id)
        return {
            "contract": CONSUMER_CONTRACT, "status": product["status"],
            "symbol": symbol, "timeframe": timeframe, "evidence_class": "SYNTHETIC",
            "source_lineage": product["complete_lineage"], "synthetic_revision": product["synthetic_revision"],
            "observations": self.repository.observations(registration_id),
        }

    def _real_product(self, symbol, timeframe, requirement):
        if requirement not in {"REAL_ONLY", "SYNTHETIC_PERMITTED"}:
            raise SyntheticRepositoryError("INVALID_EVIDENCE_REQUIREMENT", requirement)
        with open_read_only(self.repository.authority_database) as authority:
            lane = authority.execute("SELECT 1 FROM evidence_lanes WHERE asset=? AND timeframe=?", (symbol, timeframe)).fetchone()
            if lane is None:
                return {"contract": CONSUMER_CONTRACT, "status": "Unavailable", "symbol": symbol, "timeframe": timeframe, "evidence_class": None, "source_lineage": [], "synthetic_revision": None, "observations": []}
            revision = authority_revision_for_lane(authority, symbol=symbol, timeframe=timeframe)
            rows = authority.execute(
                "SELECT open_time_utc,close_time_utc,open,high,low,close,volume FROM bars WHERE asset=? AND timeframe=? ORDER BY open_time_utc",
                (symbol, timeframe),
            ).fetchall()
        return {
            "contract": CONSUMER_CONTRACT, "status": "Available" if rows else "Unavailable",
            "symbol": symbol, "timeframe": timeframe, "evidence_class": "REAL",
            "source_lineage": [{"symbol": symbol, "timeframe": timeframe, "evidence_class": "REAL", "authority_revision": revision}],
            "synthetic_revision": None,
            "observations": [{"timestamp": row[0], "close_time_utc": row[1], "open": row[2], "high": row[3], "low": row[4], "close": row[5], "volume": row[6]} for row in rows],
        }


def notify_source_revision_advanced(authority_database, symbol, timeframe, *, repository_path=None, registry_path=None):
    repository = SyntheticRepository(authority_database, repository_path, registry_path)
    if not repository.path.exists():
        return []
    dependents = [
        item for item in repository.list_products(refresh_status=False)
        if item["immediate_source_symbol"] == symbol and item["immediate_source_timeframe"] == timeframe
    ]
    results = []
    for item in dependents:
        try:
            results.append(repository.generate(item["id"]))
        except Exception as error:
            code = error.code if isinstance(error, SyntheticRepositoryError) else "GENERATION_FAILURE"
            repository._set_failure(item["id"], code, str(error), None)
            results.append({"id": item["id"], "status": "Unavailable", "reason": code})
            continue
        results.extend(notify_source_revision_advanced(
            authority_database, item["symbol"], item["target_timeframe"],
            repository_path=repository.path, registry_path=repository.registry_path,
        ))
    return results


def _validate_rule(rule):
    if rule.source_timeframe not in TIMEFRAME_SECONDS or rule.target_timeframe not in TIMEFRAME_SECONDS:
        raise SyntheticRepositoryError("UNSUPPORTED_TIMEFRAME", f"{rule.source_timeframe}->{rule.target_timeframe}")
    ratio = TIMEFRAME_SECONDS[rule.target_timeframe] / TIMEFRAME_SECONDS[rule.source_timeframe]
    if not ratio.is_integer() or int(ratio) != rule.required_component_count:
        raise SyntheticRepositoryError("INVALID_COMPONENT_COUNT", rule.rule_id)
    if rule.ohlc_calculation != "FIRST_OPEN_MAX_HIGH_MIN_LOW_LAST_CLOSE":
        raise SyntheticRepositoryError("UNAPPROVED_OHLC_RULE", rule.rule_id)
    if rule.missing_component_behaviour != "INCOMPLETE_NO_PUBLICATION" or rule.partial_current_period_behaviour != "UNPUBLISHED":
        raise SyntheticRepositoryError("UNSAFE_MISSING_COMPONENT_RULE", rule.rule_id)
    ZoneInfo(rule.timezone)


def _validate_registration(item, rules):
    required = {
        "symbol", "target_timeframe", "evidence_class", "immediate_source_symbol",
        "immediate_source_timeframe", "immediate_source_evidence_class",
        "originating_real_symbol", "originating_real_timeframe", "aggregation_rule",
        "aggregation_rule_version", "calendar_authority", "session_alignment",
        "authorised_consumers", "status",
    }
    missing = required - set(item)
    if missing:
        raise SyntheticRepositoryError("INCOMPLETE_REGISTRATION", ",".join(sorted(missing)))
    for key in ("symbol", "immediate_source_symbol", "originating_real_symbol"):
        item[key] = str(item[key]).upper()
    for key in ("target_timeframe", "immediate_source_timeframe", "originating_real_timeframe"):
        item[key] = str(item[key]).upper()
    item["evidence_class"] = str(item["evidence_class"]).upper()
    item["immediate_source_evidence_class"] = str(item["immediate_source_evidence_class"]).upper()
    if item["evidence_class"] != "SYNTHETIC":
        raise SyntheticRepositoryError("SYNTHETIC_TO_REAL_FORBIDDEN", f"{item['symbol']}:{item['target_timeframe']}")
    if item["immediate_source_evidence_class"] not in EVIDENCE_CLASSES:
        raise SyntheticRepositoryError("INVALID_EVIDENCE_CLASS", str(item["immediate_source_evidence_class"]))
    rule = rules.get((item["aggregation_rule"], int(item["aggregation_rule_version"])))
    if rule is None:
        raise SyntheticRepositoryError("AGGREGATION_RULE_UNAVAILABLE", str(item["aggregation_rule"]))
    if rule.source_timeframe != item["immediate_source_timeframe"] or rule.target_timeframe != item["target_timeframe"]:
        raise SyntheticRepositoryError("RULE_RELATIONSHIP_MISMATCH", f"{item['symbol']}:{item['target_timeframe']}")
    if rule.calendar != item["calendar_authority"]:
        raise SyntheticRepositoryError("CALENDAR_AUTHORITY_MISMATCH", f"{item['symbol']}:{item['target_timeframe']}")
    if not item["authorised_consumers"]:
        raise SyntheticRepositoryError("NO_AUTHORISED_CONSUMER", f"{item['symbol']}:{item['target_timeframe']}")
    return item


def _validate_lineage_graph(registrations):
    by_target = {(item["symbol"], item["target_timeframe"]): item for item in registrations}
    for item in registrations:
        if item["immediate_source_evidence_class"] == "SYNTHETIC":
            parent = by_target.get((item["immediate_source_symbol"], item["immediate_source_timeframe"]))
            if parent is None:
                raise SyntheticRepositoryError("UNAPPROVED_SYNTHETIC_SOURCE", f"{item['immediate_source_symbol']}:{item['immediate_source_timeframe']}")
            if (parent["originating_real_symbol"], parent["originating_real_timeframe"]) != (item["originating_real_symbol"], item["originating_real_timeframe"]):
                raise SyntheticRepositoryError("ORIGINATING_REAL_LINEAGE_MISMATCH", f"{item['symbol']}:{item['target_timeframe']}")
    for start in by_target:
        seen, current = set(), start
        while current in by_target and by_target[current]["immediate_source_evidence_class"] == "SYNTHETIC":
            if current in seen:
                raise SyntheticRepositoryError("SYNTHETIC_LINEAGE_CYCLE", ":".join(start))
            seen.add(current)
            parent = by_target[current]
            current = (parent["immediate_source_symbol"], parent["immediate_source_timeframe"])


def _source_observation(row):
    return {"open_time": int(row[0]), "close_time": int(row[1]), "open": str(row[2]), "high": str(row[3]), "low": str(row[4]), "close": str(row[5]), "volume": row[6]}


def _aggregate(observations, rule, generated, affected_start):
    by_open = {item["open_time"]: item for item in observations}
    groups, incomplete = [], []
    source_seconds = TIMEFRAME_SECONDS[rule.source_timeframe]
    target_seconds = TIMEFRAME_SECONDS[rule.target_timeframe]
    first_target = _target_start(observations[0]["open_time"], rule)
    last_target = _target_start(observations[-1]["open_time"], rule)
    targets = range(first_target, last_target + target_seconds, target_seconds)
    generated_epoch = int(generated.timestamp())
    for target in targets:
        if affected_start is not None and target < affected_start:
            continue
        if target + target_seconds > generated_epoch:
            continue
        expected = tuple(target + source_seconds * index for index in range(rule.required_component_count))
        components = [by_open[value] for value in expected if value in by_open and by_open[value]["close_time"] <= generated_epoch]
        if len(components) != rule.required_component_count:
            missing = [value for value in expected if value not in by_open]
            incomplete.append({"target_open": target, "detail": f"missing source opens: {missing}"})
            continue
        values = [[Decimal(item[key]) for key in ("open", "high", "low", "close")] for item in components]
        volumes = [item["volume"] for item in components]
        volume = str(sum(Decimal(str(value)) for value in volumes)) if all(value is not None for value in volumes) else None
        groups.append({
            "open_time": target, "close_time": target + target_seconds,
            "open": str(values[0][0]), "high": str(max(value[1] for value in values)),
            "low": str(min(value[2] for value in values)), "close": str(values[-1][3]),
            "volume": volume, "source_start": expected[0], "source_end": expected[-1],
        })
    return groups, incomplete


def _target_start(epoch, rule):
    zone = ZoneInfo(rule.timezone)
    local = datetime.fromtimestamp(epoch, UTC).astimezone(zone)
    hour, minute = (int(value) for value in rule.session_anchor.split(":"))
    anchor_date = local.date() if local.timetz().replace(tzinfo=None) >= time(hour, minute) else local.date() - timedelta(days=1)
    anchor_local = datetime.combine(anchor_date, time(hour, minute), zone)
    anchor_epoch = int(anchor_local.astimezone(UTC).timestamp())
    target_seconds = TIMEFRAME_SECONDS[rule.target_timeframe]
    return anchor_epoch + math.floor((epoch - anchor_epoch) / target_seconds) * target_seconds


def _utc(value):
    if value is None:
        return datetime.now(UTC)
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


_SCHEMA = """
CREATE TABLE IF NOT EXISTS aggregation_rules(
  rule_id TEXT NOT NULL,version INTEGER NOT NULL,rule_json TEXT NOT NULL,checksum TEXT NOT NULL,
  PRIMARY KEY(rule_id,version));
CREATE TABLE IF NOT EXISTS synthetic_registrations(
  registration_id TEXT PRIMARY KEY,symbol TEXT NOT NULL,target_timeframe TEXT NOT NULL,
  evidence_class TEXT NOT NULL CHECK(evidence_class='SYNTHETIC'),
  immediate_source_symbol TEXT NOT NULL,immediate_source_timeframe TEXT NOT NULL,
  immediate_source_evidence_class TEXT NOT NULL CHECK(immediate_source_evidence_class IN('REAL','SYNTHETIC')),
  originating_real_symbol TEXT NOT NULL,originating_real_timeframe TEXT NOT NULL,
  aggregation_rule_id TEXT NOT NULL,aggregation_rule_version INTEGER NOT NULL,
  calendar_authority TEXT NOT NULL,session_alignment TEXT NOT NULL,
  authorised_consumers_json TEXT NOT NULL,registration_status TEXT NOT NULL,
  generation_status TEXT NOT NULL CHECK(generation_status IN('Available','Stale','Incomplete','Unavailable')),
  source_revision TEXT,originating_real_authority_revision TEXT,synthetic_revision INTEGER NOT NULL DEFAULT 0,
  rule_checksum TEXT,generated_at TEXT,source_observation_start INTEGER,source_observation_end INTEGER,
  first_synthetic_observation INTEGER,latest_synthetic_observation INTEGER,observation_count INTEGER NOT NULL DEFAULT 0,
  complete_lineage_json TEXT,content_checksum TEXT,
  FOREIGN KEY(aggregation_rule_id,aggregation_rule_version) REFERENCES aggregation_rules(rule_id,version));
CREATE UNIQUE INDEX IF NOT EXISTS synthetic_symbol_timeframe ON synthetic_registrations(symbol,target_timeframe);
CREATE TABLE IF NOT EXISTS synthetic_observations(
  registration_id TEXT NOT NULL,open_time_utc INTEGER NOT NULL,close_time_utc INTEGER NOT NULL,
  open TEXT NOT NULL,high TEXT NOT NULL,low TEXT NOT NULL,close TEXT NOT NULL,volume TEXT,
  synthetic_revision INTEGER NOT NULL,PRIMARY KEY(registration_id,open_time_utc),
  FOREIGN KEY(registration_id) REFERENCES synthetic_registrations(registration_id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS synthetic_provenance(
  registration_id TEXT NOT NULL,target_open_time_utc INTEGER NOT NULL,
  source_observation_start INTEGER NOT NULL,source_observation_end INTEGER NOT NULL,
  source_authority_revision TEXT,source_synthetic_revision INTEGER,
  originating_real_authority_revision TEXT NOT NULL,aggregation_rule_version INTEGER NOT NULL,
  generated_time TEXT NOT NULL,complete_lineage_json TEXT NOT NULL,
  PRIMARY KEY(registration_id,target_open_time_utc),
  FOREIGN KEY(registration_id) REFERENCES synthetic_registrations(registration_id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS generation_failures(
  failure_id INTEGER PRIMARY KEY AUTOINCREMENT,registration_id TEXT NOT NULL,target_open_time_utc INTEGER,
  code TEXT NOT NULL,detail TEXT NOT NULL,recorded_at TEXT NOT NULL,
  FOREIGN KEY(registration_id) REFERENCES synthetic_registrations(registration_id) ON DELETE CASCADE);
"""
