from __future__ import annotations

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from unittest import mock
from datetime import UTC, datetime
from pathlib import Path

from fragarach_ii.commands.acquire import main as command_main
from fragarach_ii.providers import AcquisitionError, acquire_twelve_data
from fragarach_ii.providers.config import load_provider_config
from fragarach_ii.providers.http import HttpRequest, HttpResponse, ResponseTooLarge
from fragarach_ii.storage import open_read_only, verify_integrity
from fragarach_ii.storage.schema import APPLICATION_TABLES


NOW = datetime(2026, 7, 11, 0, 0, tzinfo=UTC)
FIXTURES = Path("tests/fixtures/twelve_data")


class FakeTransport:
    def __init__(self, *outcomes: object) -> None:
        self.outcomes = list(outcomes)
        self.requests: list[HttpRequest] = []
        self.credentials: list[str] = []

    def send(self, request, credential, config):
        self.requests.append(request)
        self.credentials.append(credential)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _response(body: bytes, **values: object) -> HttpResponse:
    return HttpResponse(
        status=values.get("status", 200),
        content_type=values.get("content_type", "application/json; charset=utf-8"),
        body=body,
        host=values.get("host", "api.twelvedata.com"),
    )


def _counts(path: Path) -> tuple[int, int, int, int, tuple[object, ...] | None]:
    if not path.exists():
        return (0, 0, 0, 0, None)
    connection = open_read_only(path)
    try:
        return (
            connection.execute("SELECT count(*) FROM bars").fetchone()[0],
            connection.execute("SELECT count(*) FROM raw_blocks").fetchone()[0],
            connection.execute("SELECT count(*) FROM provenance").fetchone()[0],
            connection.execute("SELECT count(*) FROM ingest_runs").fetchone()[0],
            connection.execute("SELECT high_watermark_open_time_utc,validation_summary FROM lane_state").fetchone(),
        )
    finally:
        connection.close()


class TwelveDataAcquisitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.database = self.root / "authority.sqlite3"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def acquire(self, body: bytes, asset: str = "AUDUSD", **overrides: object):
        transport = overrides.pop("transport", FakeTransport(_response(body)))
        arguments = {
            "asset": asset,
            "timeframe": "D1",
            "from_date": "2026-07-09",
            "through_date": "2026-07-10",
            "merge_mode": "preserve",
            "credential": "test-secret-value",
            "transport": transport,
            "clock": lambda: NOW,
            "sleeper": lambda _seconds: None,
        }
        arguments.update(overrides)
        result = acquire_twelve_data(self.database, **arguments)
        return result, transport

    def test_explicit_mapping_and_unauthorized_inputs(self) -> None:
        config = load_provider_config()
        self.assertEqual(
            {asset: config.provider_symbol(asset) for asset in ("AUDUSD", "XAUUSD", "BTCUSD")},
            {"AUDUSD": "AUD/USD", "XAUUSD": "XAU/USD", "BTCUSD": "BTC/USD"},
        )
        body = _fixture("audusd_d1_2026-07-09_2026-07-10.json")
        cases = (
            ({"asset": "EURUSD"}, "PROVIDER_CONFIGURATION_ERROR"),
            ({"timeframe": "H1"}, "UNSUPPORTED_TIMEFRAME"),
            ({"from_date": "2026-07-11"}, "INVALID_BOUNDARY"),
            ({"from_date": "07/09/2026"}, "INVALID_FROM_DATE"),
            ({"from_date": "2000-01-01"}, "RANGE_TOO_LARGE"),
        )
        for values, code in cases:
            with self.assertRaises(AcquisitionError) as raised:
                self.acquire(body, **values)
            self.assertEqual(raised.exception.code, code)
        self.assertFalse(self.database.exists())

    def test_provider_configuration_checksum_drift_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "providers").mkdir()
            path = root / "providers/twelve_data_time_series_d1.v1.json"
            shutil.copy2("config/providers/twelve_data_time_series_d1.v1.json", path)
            data = json.loads(path.read_text())
            data["max_attempts"] = 99
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "checksum drift"):
                load_provider_config(root)

    def test_request_is_deterministic_and_secret_free(self) -> None:
        body = _fixture("audusd_d1_2026-07-09_2026-07-10.json")
        result, transport = self.acquire(body)
        target = transport.requests[0].target
        self.assertEqual(
            target,
            "/time_series?end_date=2026-07-10&format=JSON&interval=1day&order=ASC&outputsize=2&start_date=2026-07-09&symbol=AUD%2FUSD&timezone=UTC",
        )
        self.assertNotIn("test-secret-value", target)
        self.assertNotIn("test-secret-value", result.as_json())
        self.assertEqual(result.provider_symbol, "AUD/USD")

    def test_exact_bytes_staging_order_volume_and_read_only_verification(self) -> None:
        body = _fixture("btcusd_d1_2026-07-09_2026-07-10.json")
        result, _ = self.acquire(body, asset="BTCUSD")
        self.assertEqual((result.received, result.staged, result.inserted), (2, 2, 2))
        self.assertTrue(result.read_only_verification)
        connection = open_read_only(self.database)
        try:
            raw = connection.execute("SELECT payload,byte_length,media_type FROM raw_blocks").fetchone()
            self.assertEqual(raw, (body, len(body), "application/json"))
            bars = connection.execute("SELECT close,volume FROM bars ORDER BY open_time_utc").fetchall()
            self.assertEqual(bars, [("63191.29", "500"), ("64655.87", "520")])
            details = json.loads(connection.execute("SELECT detail FROM ingest_runs").fetchone()[0])
            self.assertEqual(details["provider_contract"], "TWELVE_DATA_TIME_SERIES_D1_V1")
            self.assertNotIn("test-secret-value", json.dumps(details))
        finally:
            connection.close()

    def test_missing_volume_remains_null_and_identical_repeat_reuses_raw(self) -> None:
        body = _fixture("audusd_d1_2026-07-09_2026-07-10.json")
        first, _ = self.acquire(body)
        second, _ = self.acquire(body)
        self.assertEqual((first.inserted, first.unchanged), (2, 0))
        self.assertEqual((second.inserted, second.unchanged), (0, 2))
        self.assertEqual(first.raw_block_id, second.raw_block_id)
        self.assertTrue(second.raw_block_reused)
        connection = open_read_only(self.database)
        try:
            self.assertEqual(connection.execute("SELECT count(*) FROM raw_blocks").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT count(*) FROM bars WHERE volume IS NULL").fetchone()[0], 2)
            self.assertEqual(connection.execute("SELECT count(*) FROM provenance").fetchone()[0], 4)
        finally:
            connection.close()

    def test_invalid_payload_contracts_leave_no_authority(self) -> None:
        base = json.loads(_fixture("audusd_d1_2026-07-09_2026-07-10.json"))
        mutations = []
        value = json.loads(json.dumps(base)); value["meta"]["symbol"] = "EUR/USD"; mutations.append((value, "SYMBOL_MISMATCH"))
        value = json.loads(json.dumps(base)); value["meta"]["interval"] = "1h"; mutations.append((value, "INTERVAL_MISMATCH"))
        value = json.loads(json.dumps(base)); value["values"][0]["datetime"] = "2026-07-11"; mutations.append((value, "OUT_OF_RANGE_OBSERVATION"))
        value = json.loads(json.dumps(base)); value["values"][0]["high"] = "NaN"; mutations.append((value, "NON_FINITE_NUMERIC"))
        value = json.loads(json.dumps(base)); del value["values"][0]["open"]; mutations.append((value, "MISSING_OHLC"))
        for payload, code in mutations:
            database = self.root / f"{code}.sqlite3"
            with self.assertRaises(AcquisitionError) as raised:
                acquire_twelve_data(
                    database, asset="AUDUSD", timeframe="D1",
                    from_date="2026-07-09", through_date="2026-07-10",
                    credential="secret", transport=FakeTransport(_response(json.dumps(payload).encode())),
                    sleeper=lambda _: None,
                )
            self.assertEqual(raised.exception.code, code)
            self.assertFalse(database.exists())

        for body, code in (
            (b"not-json", "MALFORMED_PAYLOAD"),
            (b'{"status":"error","code":400,"message":"bad"}', "PROVIDER_DECLARED_ERROR"),
        ):
            database = self.root / f"{code}.sqlite3"
            with self.assertRaises(AcquisitionError) as raised:
                acquire_twelve_data(
                    database, asset="AUDUSD", timeframe="D1",
                    from_date="2026-07-09", through_date="2026-07-10",
                    credential="secret", transport=FakeTransport(_response(body)),
                    sleeper=lambda _: None,
                )
            self.assertEqual(raised.exception.code, code)
            self.assertFalse(database.exists())

    def test_retryable_failure_can_recover_without_duplicate_attempt_state(self) -> None:
        body = _fixture("audusd_d1_2026-07-09_2026-07-10.json")
        transport = FakeTransport(TimeoutError(), _response(body))
        result, _ = self.acquire(body, transport=transport)
        self.assertEqual(result.inserted, 2)
        self.assertEqual(len(transport.requests), 2)
        connection = open_read_only(self.database)
        try:
            self.assertEqual(connection.execute("SELECT count(*) FROM ingest_runs").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT count(*) FROM raw_blocks").fetchone()[0], 1)
        finally:
            connection.close()

    def test_exact_duplicate_is_delegated_and_conflicting_duplicate_rejects(self) -> None:
        base = json.loads(_fixture("audusd_d1_2026-07-09_2026-07-10.json"))
        base["values"].append(dict(base["values"][0]))
        result, _ = self.acquire(json.dumps(base, separators=(",", ":")).encode())
        self.assertEqual((result.received, result.staged), (3, 2))
        conflict = json.loads(json.dumps(base)); conflict["values"][-1]["close"] = "0.69400"
        other = self.root / "conflict.sqlite3"
        with self.assertRaises(AcquisitionError) as raised:
            acquire_twelve_data(
                other, asset="AUDUSD", timeframe="D1", from_date="2026-07-09",
                through_date="2026-07-10", credential="secret",
                transport=FakeTransport(_response(json.dumps(conflict).encode())), sleeper=lambda _: None,
            )
        self.assertEqual(raised.exception.code, "CONFLICTING_DUPLICATE")
        self.assertFalse(other.exists())

    def test_existing_preserve_and_correct_modes_are_reused(self) -> None:
        original = _fixture("audusd_d1_2026-07-09_2026-07-10.json")
        self.acquire(original)
        changed = json.loads(original); changed["values"][0]["close"] = "0.69505"
        changed_body = json.dumps(changed, separators=(",", ":")).encode()
        preserved, _ = self.acquire(changed_body)
        self.assertEqual(preserved.conflicts_preserved, 1)
        corrected, _ = self.acquire(changed_body, merge_mode="correct")
        self.assertEqual(corrected.corrected, 1)
        connection = open_read_only(self.database)
        try:
            actions = connection.execute("SELECT merge_action,count(*) FROM provenance GROUP BY merge_action").fetchall()
            self.assertEqual(dict(actions)["CONFLICT_PRESERVED"], 1)
            self.assertEqual(dict(actions)["CORRECTED"], 1)
        finally:
            connection.close()

    def test_transport_failures_retries_and_protections_leave_invariants(self) -> None:
        body = _fixture("audusd_d1_2026-07-09_2026-07-10.json")
        self.acquire(body)
        before = _counts(self.database)
        cases = (
            (FakeTransport(TimeoutError(), TimeoutError(), TimeoutError()), "RETRY_EXHAUSTED"),
            (FakeTransport(_response(b"{}", status=500), _response(b"{}", status=500), _response(b"{}", status=500)), "RETRY_EXHAUSTED"),
            (FakeTransport(_response(b"{}", status=429), _response(b"{}", status=429), _response(b"{}", status=429)), "RATE_LIMIT"),
            (FakeTransport(_response(b"{}", status=400)), "HTTP_ERROR"),
            (FakeTransport(_response(b"{}", status=302)), "UNEXPECTED_REDIRECT"),
            (FakeTransport(_response(body, content_type="text/html")), "UNSUPPORTED_MEDIA_TYPE"),
            (FakeTransport(_response(body, host="other.example")), "UNEXPECTED_HOST"),
            (FakeTransport(ResponseTooLarge("too large")), "RESPONSE_TOO_LARGE"),
        )
        for transport, code in cases:
            with self.assertRaises(AcquisitionError) as raised:
                self.acquire(body, transport=transport)
            self.assertEqual(raised.exception.code, code)
            self.assertEqual(_counts(self.database), before)

    def test_interruption_before_ingest_leaves_no_state_and_rerun_succeeds(self) -> None:
        body = _fixture("audusd_d1_2026-07-09_2026-07-10.json")
        def interrupt() -> None:
            raise RuntimeError("simulated interruption")
        with self.assertRaisesRegex(RuntimeError, "simulated"):
            self.acquire(body, before_ingest=interrupt)
        self.assertFalse(self.database.exists())
        result, _ = self.acquire(body)
        self.assertEqual(result.inserted, 2)

    def test_post_ingest_validation_failure_clears_summary_but_keeps_evidence(self) -> None:
        body = _fixture("audusd_d1_2026-07-09_2026-07-10.json")
        def fail_validation(*_args, **_kwargs):
            raise RuntimeError("validation unavailable")
        with self.assertRaises(AcquisitionError) as raised:
            self.acquire(body, validator=fail_validation)
        self.assertEqual(raised.exception.code, "POST_INGEST_VALIDATION_FAILED")
        self.assertTrue(raised.exception.evidence_committed)
        connection = open_read_only(self.database)
        try:
            self.assertEqual(connection.execute("SELECT count(*) FROM bars").fetchone()[0], 2)
            self.assertIsNone(connection.execute("SELECT validation_summary FROM lane_state").fetchone()[0])
        finally:
            connection.close()

    def test_missing_credential_command_redacts_and_does_not_create_database(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            with mock.patch.dict("os.environ", {}, clear=True):
                status = command_main(
                    ["--database", str(self.database), "--provider", "TWELVE_DATA",
                     "--asset", "AUDUSD", "--timeframe", "D1",
                     "--from-date", "2026-07-09", "--through-date", "2026-07-10", "--json"]
                )
        self.assertEqual(status, 1)
        self.assertEqual(json.loads(output.getvalue())["code"], "MISSING_CREDENTIAL")
        self.assertFalse(self.database.exists())

    def test_integrity_migrations_and_exact_seven_tables(self) -> None:
        body = _fixture("xauusd_d1_2026-07-09_2026-07-10.json")
        self.acquire(body, asset="XAUUSD")
        report = verify_integrity(self.database)
        self.assertTrue(report.ok)
        self.assertEqual(report.application_tables, APPLICATION_TABLES)


if __name__ == "__main__":
    unittest.main()
