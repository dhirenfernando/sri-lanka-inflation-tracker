"""Fetch the three DCS series and update the local work-tracker database."""
from __future__ import annotations
from pathlib import Path
from src.calculations import percent_change
from src.dcs import DcsError, fetch_ccpi, fetch_ncpi, fetch_ppi
from src.storage import connect, replace_index_rows, upsert_index_rows

DB_PATH = Path(__file__).parent / "data" / "inflation.sqlite3"

def _derive_ppi(rows: list[dict]) -> list[dict]:
    index = {row["period"]: row["index"] for row in rows}
    periods = list(index)
    for position, row in enumerate(rows):
        row["mom"] = percent_change(row["index"], index.get(periods[position - 1]) if position else None)
        row["yoy"] = percent_change(row["index"], index.get(periods[position - 12]) if position >= 12 else None)
    return rows

def main() -> int:
    db = connect(DB_PATH)
    sources = (("CCPI", fetch_ccpi), ("NCPI", fetch_ncpi), ("PPI", fetch_ppi))
    try:
        results = []
        for code, fetch in sources:
            rows, url = fetch()
            if code == "PPI":
                rows = _derive_ppi(rows)
                replace_index_rows(db, code, rows, url)
            else:
                upsert_index_rows(db, code, rows, url)
            latest = rows[-1]
            results.append((code, latest, len(rows)))
    except DcsError as error:
        print(f"Data update failed: {error}")
        return 1
    finally:
        db.close()
    print("Data update successful")
    for code, latest, count in results:
        suffix = f" | YoY: {latest['yoy']:.1f}%" if latest.get("yoy") is not None else ""
        print(f"{code} latest: {latest['period'][:7]} | Index: {latest['index']:.2f}{suffix} | rows: {count}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
