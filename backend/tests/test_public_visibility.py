from __future__ import annotations

import unittest

from backend.app import db


class PublicVisibilityTests(unittest.TestCase):
    def test_current_period_row_without_historical_votes_is_hidden(self) -> None:
        row = {"periodo": "2026-2030", "votes_expected_total": None}
        self.assertTrue(db._is_new_without_historical_baseline(row, reference_year=2026))

    def test_current_period_row_with_historical_votes_stays_visible(self) -> None:
        row = {"periodo": "2026-ACTUAL", "votes_expected_total": 144}
        self.assertFalse(db._is_new_without_historical_baseline(row, reference_year=2026))

    def test_previous_period_row_without_votes_is_not_hidden_by_newcomer_rule(self) -> None:
        row = {"periodo": "2022-2026", "votes_expected_total": None}
        self.assertFalse(db._is_new_without_historical_baseline(row, reference_year=2026))


if __name__ == "__main__":
    unittest.main()
