from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from generate_dashboard import DATABASE, DEFAULT_RANGE_MONTHS, generate, load_data


class StaticDashboardTests(unittest.TestCase):
    def test_generator_writes_dashboard_with_known_latest_values(self):
        with tempfile.TemporaryDirectory() as directory:
            output = generate(DATABASE, Path(directory) / "index.html")
            page = output.read_text(encoding="utf-8")
        self.assertTrue(page.startswith("<!doctype html>"))
        self.assertGreater(len(page), 20_000)
        self.assertIn('"index":208.2', page)
        self.assertIn('"index":223.4', page)
        self.assertIn('"index":241.97845167559007', page)

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

    def test_embedded_history_is_complete_and_has_no_prohibited_wording(self):
        rows = load_data(DATABASE)
        self.assertEqual({row["series"] for row in rows}, {"CCPI", "NCPI", "PPI"})
        self.assertGreaterEqual(len(rows), 800)
        with tempfile.TemporaryDirectory() as directory:
            page = generate(DATABASE, Path(directory) / "index.html").read_text(encoding="utf-8").lower()
        for prohibited in ("bonus", "employee", "compensation"):
            self.assertNotIn(prohibited, page)


if __name__ == "__main__":
    unittest.main()
