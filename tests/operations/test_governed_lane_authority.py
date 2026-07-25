from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fragarach_ii.commands.get_governed_lane_authority import _sbv2_chartability


class GovernedLaneAuthorityChartabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary.name) / "authority.sqlite3"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_mapping_discovery_is_never_reported_chartable(self) -> None:
        result = _sbv2_chartability(
            self.database,
            "CAT",
            "D1",
            {"acquisition_dimension": {"state": "MAPPING_DISCOVERY", "reason": "PROVIDER_SYMBOL_MAPPING_REQUIRED"}},
            "PUBLISHED",
        )

        self.assertEqual(result["state"], "MAPPING_DISCOVERY")
        self.assertEqual(result["returned_closed_bars"], 0)

    def test_pending_publication_is_never_reported_chartable(self) -> None:
        result = _sbv2_chartability(
            self.database,
            "GOOGL",
            "D1",
            {"acquisition_dimension": {"state": "AUTOMATED_UPDATE_AVAILABLE"}},
            "PUBLISHING",
        )

        self.assertEqual(result["state"], "PUBLICATION_UNUSABLE")
        self.assertEqual(result["returned_closed_bars"], 0)


if __name__ == "__main__":
    unittest.main()
