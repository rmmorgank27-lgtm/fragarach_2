from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from fragarach_ii.commands.operations import CLI_ID, main
from fragarach_ii.storage import initialize_database


class OperationsCliTests(unittest.TestCase):
    def invoke(self, arguments: list[str]) -> tuple[int, dict[str, object]]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(arguments)
        return code, json.loads(output.getvalue())

    def test_identity_is_stable_structured_json(self) -> None:
        code, payload = self.invoke(["identity", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(payload, {"cli_id": CLI_ID, "cli_version": 1})

    def test_verify_and_verified_backup_are_structured(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "authority.sqlite3"
            destination = Path(directory) / "backup.sqlite3"
            initialize_database(source)
            code, verification = self.invoke(["verify", "--database", str(source), "--json"])
            self.assertEqual(code, 0)
            self.assertTrue(verification["integrity_ok"])
            self.assertTrue(verification["foreign_keys_ok"])
            self.assertTrue(verification["migration_checksums_ok"])
            self.assertTrue(verification["exact_seven_tables"])
            self.assertTrue(verification["read_only_contract"])
            code, backup = self.invoke(["backup", "--database", str(source), "--destination", str(destination), "--json"])
            self.assertEqual(code, 0)
            self.assertEqual(backup["cli_id"], CLI_ID)
            self.assertEqual(len(backup["backup_sha256"]), 64)
            self.assertTrue(backup["verification"]["integrity_ok"])

    def test_missing_or_existing_destination_fails_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "missing.sqlite3"
            destination = Path(directory) / "backup.sqlite3"
            code, payload = self.invoke(["backup", "--database", str(source), "--destination", str(destination), "--json"])
            self.assertEqual(code, 1)
            self.assertIn("error", payload)


if __name__ == "__main__":
    unittest.main()
