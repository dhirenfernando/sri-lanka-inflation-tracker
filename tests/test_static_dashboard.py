from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from generate_dashboard import DATABASE, DEFAULT_RANGE_MONTHS, OUTPUT, card_summary, dashboard_payload, generate, load_data
from src.storage import connect, upsert_index_rows


class StaticDashboardTests(unittest.TestCase):
    def _seed_dashboard_database(self, database: Path, missing_latest_ppi_rates: bool = False) -> None:
        db = connect(database)
        try:
            for position, code in enumerate(("CCPI", "NCPI", "PPI"), start=1):
                rows = [
                    {"period": "2026-01-01", "index": 100.0 + position, "mom": 1.0, "yoy": 2.0, "ma12": 3.0},
                    {
                        "period": "2026-02-01",
                        "index": 110.0 + position,
                        "mom": None if code == "PPI" and missing_latest_ppi_rates else 1.5,
                        "yoy": None if code == "PPI" and missing_latest_ppi_rates else 2.5,
                        "ma12": 3.5,
                    },
                ]
                upsert_index_rows(db, code, rows, "https://example.test/source")
        finally:
            db.close()

    def test_generator_writes_dashboard_with_deterministic_data(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "inflation.sqlite3"
            self._seed_dashboard_database(database)
            rows = load_data(database)
            output = generate(database, Path(directory) / "index.html")
            page = output.read_text(encoding="utf-8")
        self.assertTrue(page.startswith("<!doctype html>"))
        self.assertGreater(len(page), 5_000)
        self.assertIn("const CARDS=" + json.dumps(dashboard_payload(rows)["cards"], separators=(",", ":"), sort_keys=True), page)
        self.assertEqual({card["series"]: card["index"] for card in dashboard_payload(rows)["cards"]}, {"CCPI": 111.0, "NCPI": 112.0, "PPI": 113.0})

    def test_card_does_not_mix_latest_index_with_older_rates(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "inflation.sqlite3"
            self._seed_dashboard_database(database, missing_latest_ppi_rates=True)
            rows = load_data(database)
            page = generate(database, Path(directory) / "index.html").read_text(encoding="utf-8")
        ppi = card_summary(rows, "PPI")
        self.assertEqual(ppi["period"], "2026-02-01")
        self.assertIsNone(ppi["mom"])
        self.assertIsNone(ppi["yoy"])
        self.assertIn('"mom":null', page)
        self.assertIn("unavailable(card.yoy)", page)

    def test_generated_dashboard_has_bounded_presets_and_export(self):
        with tempfile.TemporaryDirectory() as directory:
            page = generate(DATABASE, Path(directory) / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-range="12"', page)
        self.assertIn('data-range="24" class="active"', page)
        self.assertIn('data-range="36"', page)
        self.assertNotIn('data-range="all"', page)
        self.assertEqual(page.count('data-range="'), 3)
        self.assertIn('const MAX_RANGE_MONTHS=36', page)
        self.assertIn('monthShift(maxPeriod,rangeMonths)', page)
        self.assertIn('earliestAllowed=clampMonth(monthShift(to,MAX_RANGE_MONTHS)', page)
        self.assertIn('Custom range limited to ${MAX_RANGE_MONTHS} months.', page)
        self.assertIn('id="download"', page)
        self.assertIn('series,period,metric,value', page)
        self.assertIn("].join('\\n');", page)
        self.assertIn(f"const DEFAULT_RANGE_MONTHS={DEFAULT_RANGE_MONTHS}", page)
        self.assertIn('pointRadius:(ctx)=>ctx.dataIndex===labels.length-1?3:0', page)
        self.assertIn('maxTicksLimit:7', page)
        self.assertIn('Current index:', page)
        self.assertIn('MoM:', page)
        self.assertIn('YoY:', page)

    def test_one_resolved_range_is_shared_by_charts_table_and_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            page = generate(DATABASE, Path(directory) / "index.html").read_text(encoding="utf-8")
        self.assertIn('currentVisible=filtered(range)', page)
        self.assertIn('renderCharts(currentVisible); renderTable(currentVisible);', page)
        self.assertIn("...currentVisible.map(row=>", page)
        self.assertIn("fromControl.value=range.from; toControl.value=range.to", page)
        self.assertIn("fromControl.min=minPeriod; fromControl.max=maxPeriod", page)
        self.assertIn("toControl.min=minPeriod; toControl.max=maxPeriod", page)

    def test_live_database_has_required_series_and_clean_wording(self):
        rows = load_data(DATABASE)
        self.assertEqual({row["series"] for row in rows}, {"CCPI", "NCPI", "PPI"})
        self.assertEqual({row["series"] for row in rows if row["metric"] == "index"}, {"CCPI", "NCPI", "PPI"})
        with tempfile.TemporaryDirectory() as directory:
            page = generate(DATABASE, Path(directory) / "index.html").read_text(encoding="utf-8").lower()
        for prohibited in ("bonus", "employee", "compensation"):
            self.assertNotIn(prohibited, page)

    def test_generated_artifact_matches_database_when_requested(self):
        if os.environ.get("CHECK_GENERATED_ARTIFACT") != "1":
            self.skipTest("artifact check runs after dashboard generation in CI")
        rows = load_data(DATABASE)
        page = OUTPUT.read_text(encoding="utf-8")
        cards = json.dumps(dashboard_payload(rows)["cards"], separators=(",", ":"), sort_keys=True)
        self.assertIn("const CARDS=" + cards, page)
        for card in dashboard_payload(rows)["cards"]:
            self.assertIn(json.dumps(card["period"]), page)


if __name__ == "__main__":
    unittest.main()
