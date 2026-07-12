from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from fragarach_ii.commands.ingest_file import main


class IngestCommandTests(unittest.TestCase):
    def test_json_command_surface_reports_factual_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "AUDUSD_D1.csv"
            source.write_text(
                "timestamp,open,high,low,close\n2026-07-09,1,2,0,1\n",
                encoding="utf-8",
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                status = main(
                    [
                        "--database",
                        str(root / "authority.sqlite3"),
                        "--file",
                        str(source),
                        "--symbol",
                        "AUDUSD",
                        "--timeframe",
                        "D1",
                        "--json",
                    ]
                )
            self.assertEqual(status, 0)
            result = json.loads(output.getvalue())
            required = {
                "ingest_run_id",
                "raw_block_id",
                "checksum",
                "source_rows",
                "staged",
                "inserted",
                "corrected",
                "unchanged",
                "conflicts_preserved",
                "rejected",
                "earliest",
                "latest",
                "canonical_count",
                "transaction_state",
            }
            self.assertTrue(required <= result.keys())
            self.assertEqual(result["transaction_state"], "committed")

    def test_partial_import_is_success_with_warning_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/"partial.csv"
            source.write_text("timestamp,open,high,low,close\n2026-07-08,1,2,0,1\n2026-07-09,2,3,1.6,1.5\n",encoding="utf-8")
            output=io.StringIO()
            with contextlib.redirect_stdout(output):status=main(["--database",str(root/"authority.sqlite3"),"--file",str(source),"--symbol","AUDUSD","--timeframe","D1","--json"])
            result=json.loads(output.getvalue())
            self.assertEqual(status,0)
            self.assertEqual((result["transaction_state"],result["accepted"],result["rejected"]),("COMPLETED_WITH_WARNINGS",1,1))


if __name__ == "__main__":
    unittest.main()
