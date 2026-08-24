"""Minimal SQLite storage for the work tracker."""
from __future__ import annotations
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

SERIES = {
    "CCPI": ("CCPI headline index", "index", "monthly"),
    "NCPI": ("NCPI headline index", "index", "monthly"),
    "PPI": ("PPI aggregate index", "index", "monthly"),
}

def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute("pragma foreign_keys=on")
    db.executescript("""
    create table if not exists series (id integer primary key, code text not null unique, name text not null, unit text not null, frequency text not null, source text not null);
    create table if not exists observations (series_id integer not null references series(id), period text not null, metric text not null, value real not null, source_url text not null, retrieved_at text not null, primary key(series_id, period, metric));
    """)
    for code, (name, unit, frequency) in SERIES.items():
        db.execute("insert or ignore into series(code,name,unit,frequency,source) values(?,?,?,?,?)", (code, name, unit, frequency, "DCS Sri Lanka"))
    db.commit(); return db

def _write_index_rows(db: sqlite3.Connection, code: str, rows: list[dict], source_url: str) -> int:
    series_id = db.execute("select id from series where code=?", (code,)).fetchone()[0]
    retrieved_at = datetime.now(UTC).isoformat(); inserted = 0
    for row in rows:
        metrics = {"index": row["index"]}
        metrics.update({"mom": row.get("mom"), "yoy": row.get("yoy"), "ma12": row.get("ma12")})
        for metric, value in metrics.items():
            if value is None: continue
            before = db.total_changes
            db.execute("insert into observations(series_id,period,metric,value,source_url,retrieved_at) values(?,?,?,?,?,?) on conflict(series_id,period,metric) do update set value=excluded.value,source_url=excluded.source_url,retrieved_at=excluded.retrieved_at", (series_id, row["period"], metric, value, source_url, retrieved_at))
            inserted += db.total_changes - before
    return inserted

def upsert_index_rows(db: sqlite3.Connection, code: str, rows: list[dict], source_url: str) -> int:
    with db:
        return _write_index_rows(db, code, rows, source_url)

def replace_index_rows(db: sqlite3.Connection, code: str, rows: list[dict], source_url: str) -> int:
    """Atomically replace one complete published series after successful parsing."""
    with db:
        series_id = db.execute("select id from series where code=?", (code,)).fetchone()[0]
        db.execute("delete from observations where series_id=?", (series_id,))
        return _write_index_rows(db, code, rows, source_url)

def history(db: sqlite3.Connection, code: str, metric: str):
    return db.execute("select o.period,o.value from observations o join series s on s.id=o.series_id where s.code=? and o.metric=? order by o.period", (code, metric)).fetchall()
