from __future__ import annotations

import math
import os
import sqlite3
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from generate_dashboard import DATABASE, dashboard_payload, load_data
from src.calculations import percent_change
from update_data import _shift_calendar_month


class RefreshContractTests(unittest.TestCase):
    expected_series = {"CCPI", "NCPI", "PPI"}

    @staticmethod
    def index_rows(database: Path) -> dict[str, list[tuple[str, float]]]:
        with sqlite3.connect(database) as db:
            rows = db.execute(
                """select s.code, o.period, o.value from observations o
                   join series s on s.id=o.series_id where o.metric='index'
                   order by s.code, o.period"""
            ).fetchall()
        result: dict[str, list[tuple[str, float]]] = {}
        for code, period, value in rows:
            result.setdefault(code, []).append((period, value))
        return result

    def test_live_index_rows_are_valid_monthly_series(self):
        by_series = self.index_rows(DATABASE)
        self.assertEqual(set(by_series), self.expected_series)
        for code, rows in by_series.items():
            with self.subTest(series=code):
                self.assertTrue(rows)
                periods = [period for period, _ in rows]
                self.assertEqual(periods, sorted(periods))
                self.assertEqual(len(periods), len(set(periods)))
                for period, value in rows:
                    self.assertEqual(date.fromisoformat(period).day, 1)
                    self.assertTrue(math.isfinite(value) and value > 0)

    def test_ppi_derived_rates_use_only_exact_calendar_comparators(self):
        with sqlite3.connect(DATABASE) as db:
            rows = db.execute(
                """select o.period, o.metric, o.value from observations o
                   join series s on s.id=o.series_id where s.code='PPI'
                   order by o.period, o.metric"""
            ).fetchall()
        metrics: dict[str, dict[str, float]] = {}
        for period, metric, value in rows:
            metrics.setdefault(period, {})[metric] = value
        indexes = {period: values["index"] for period, values in metrics.items() if "index" in values}
        for period, values in metrics.items():
            if "index" not in values:
                continue
            for metric, offset in (("mom", -1), ("yoy", -12)):
                expected = percent_change(values["index"], indexes.get(_shift_calendar_month(period, offset)))
                if expected is None:
                    self.assertNotIn(metric, values, f"{period} {metric} must be absent without its exact comparator")
                else:
                    self.assertIn(metric, values)
                    self.assertAlmostEqual(values[metric], expected, places=9)

    def test_dashboard_cards_match_their_index_period(self):
        rows = load_data(DATABASE)
        for card in dashboard_payload(rows)["cards"]:
            with self.subTest(series=card["series"]):
                same_period = {
                    row["metric"]: row["value"]
                    for row in rows
                    if row["series"] == card["series"] and row["period"] == card["period"]
                }
                self.assertEqual(card["index"], same_period["index"])
                self.assertEqual(card["mom"], same_period.get("mom"))
                self.assertEqual(card["yoy"], same_period.get("yoy"))

    def test_refresh_does_not_remove_existing_index_history(self):
        snapshot = os.environ.get("PRE_REFRESH_DATABASE")
        if not snapshot:
            self.skipTest("continuity check runs with the workflow pre-refresh snapshot")
        previous = self.index_rows(Path(snapshot))
        current = self.index_rows(DATABASE)
        self.assertEqual(set(previous), self.expected_series)
        for code, prior_rows in previous.items():
            with self.subTest(series=code):
                prior_periods = {period for period, _ in prior_rows}
                current_periods = {period for period, _ in current[code]}
                self.assertTrue(prior_periods <= current_periods, f"{code}: refresh removed index history")
                self.assertGreaterEqual(current[code][-1][0], prior_rows[-1][0], f"{code}: latest period regressed")


if __name__ == "__main__":
    unittest.main()
