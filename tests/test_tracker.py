from __future__ import annotations
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.calculations import percent_change
from src.dcs import _movement_rows, parse_ppi_workbook
from src.storage import connect, upsert_index_rows

FIXTURES = ROOT / "tests" / "fixtures"

class TrackerTests(unittest.TestCase):
    def test_ccpi_fixture_latest_value(self):
        rows = _movement_rows((FIXTURES / "ccpi/headline.pdf").read_bytes(), "MOVEMENTS OF THE CCPI")
        self.assertEqual(rows[-1]["period"], "2026-07-01")
        self.assertEqual(rows[-1]["index"], 208.2)
        self.assertEqual(rows[-1]["yoy"], 7.3)

    def test_ncpi_fixture_latest_value(self):
        rows = _movement_rows((FIXTURES / "ncpi_july_2026.pdf").read_bytes(), "MOVEMENTS OF THE NCPI")
        self.assertEqual((rows[-1]["period"], rows[-1]["index"], rows[-1]["yoy"]), ("2026-07-01", 223.4, 7.2))

    def test_ppi_fixture_latest_value(self):
        rows = parse_ppi_workbook((FIXTURES / "ppi/ppi_june_2026.xlsx").read_bytes())
        self.assertEqual(rows[-1]["period"], "2026-06-01")
        self.assertAlmostEqual(rows[-1]["index"], 241.97845167559007)
        self.assertEqual(max(row["period"] for row in rows), "2026-06-01")

    def test_percent_change(self):
        self.assertAlmostEqual(percent_change(110, 100), 10.0)
        self.assertIsNone(percent_change(110, None))

    def test_duplicate_safe_insert_and_smoke_query(self):
        with tempfile.TemporaryDirectory() as directory:
            db = connect(Path(directory) / "inflation.sqlite3")
            rows = [{"period": "2026-07-01", "index": 208.2, "mom": 0.2, "yoy": 7.3, "ma12": 3.3}]
            upsert_index_rows(db, "CCPI", rows, "https://example.test/ccpi.pdf")
            upsert_index_rows(db, "CCPI", rows, "https://example.test/ccpi.pdf")
            self.assertEqual(db.execute("select count(*) from observations").fetchone()[0], 4)
            self.assertEqual(db.execute("select value from observations where metric='yoy'").fetchone()[0], 7.3)
            db.close()

if __name__ == "__main__":
    unittest.main()
