from __future__ import annotations

import sqlite3
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).parent / "data" / "inflation.sqlite3"

st.set_page_config(page_title="Sri Lanka Inflation Tracker", layout="wide")
st.title("Sri Lanka Inflation Tracker")
st.caption("Official DCS headline CCPI, headline NCPI, and aggregate PPI.")

if not DB_PATH.exists():
    st.error("The bundled inflation data file is unavailable. Please contact the application owner.")
    st.stop()

try:
    with sqlite3.connect(DB_PATH) as db:
        data = pd.read_sql_query(
            """select s.code, o.period, o.metric, o.value, o.source_url, o.retrieved_at
               from observations o join series s on s.id = o.series_id""",
            db,
        )
except (OSError, sqlite3.Error, pd.errors.DatabaseError):
    st.error("The bundled inflation data could not be loaded. Please contact the application owner.")
    st.stop()

if data.empty:
    st.info("No data yet. Run `python update_data.py` first.")
    st.stop()

data["period"] = pd.to_datetime(data["period"])


def latest(code: str, metric: str) -> pd.Series | None:
    result = data[(data.code == code) & (data.metric == metric)].sort_values("period").tail(1)
    return None if result.empty else result.iloc[0]


def indicator_card(column, code: str) -> None:
    index = latest(code, "index")
    yoy = latest(code, "yoy")
    if index is None:
        column.metric(f"{code} Index", "—")
        return
    yoy_text = "YoY unavailable" if yoy is None else f"YoY {yoy.value:.1f}%"
    level = f"{index.value:.2f}" if code == "PPI" else f"{index.value:.1f}"
    column.metric(f"{code} Index", level, yoy_text)
    column.caption(f"Latest period: {index.period:%b %Y}")


def trend_chart(frame: pd.DataFrame, title: str, y_title: str, decimals: int) -> None:
    st.subheader(title)
    if frame.empty:
        st.info("No observations are available for the selected date range.")
        return
    chart = (
        alt.Chart(frame)
        .mark_line(point=alt.OverlayMarkDef(size=24))
        .encode(
            x=alt.X("period:T", title="Period", axis=alt.Axis(format="%b %Y", labelAngle=-35)),
            y=alt.Y("value:Q", title=y_title),
            color=alt.Color("code:N", title="Series"),
            tooltip=[
                alt.Tooltip("code:N", title="Series"),
                alt.Tooltip("period:T", title="Period", format="%b %Y"),
                alt.Tooltip("value:Q", title=y_title, format=f".{decimals}f"),
            ],
        )
        .properties(height=280)
        .interactive()
    )
    st.altair_chart(chart, use_container_width=True)


st.subheader("Latest indicators")
cards = st.columns(3)
for column, code in zip(cards, ("CCPI", "NCPI", "PPI")):
    indicator_card(column, code)

st.subheader("Inflation trends")
minimum, maximum = data.period.min().date(), data.period.max().date()
selected = st.date_input("Date range", (minimum, maximum), min_value=minimum, max_value=maximum)
start, end = pd.Timestamp(selected[0]), pd.Timestamp(selected[1])
shown = data[(data.period >= start) & (data.period <= end)]

trend_chart(shown[(shown.code == "CCPI") & (shown.metric == "yoy")], "CCPI YoY", "YoY change (%)", 1)
trend_chart(shown[(shown.code == "NCPI") & (shown.metric == "yoy")], "NCPI YoY", "YoY change (%)", 1)
trend_chart(shown[(shown.code.isin(["CCPI", "NCPI"])) & (shown.metric == "yoy")], "CCPI vs NCPI YoY", "YoY change (%)", 1)

st.subheader("Producer prices")
trend_chart(shown[(shown.code == "PPI") & (shown.metric == "index")], "PPI Index", "Index level", 2)
trend_chart(shown[(shown.code == "PPI") & (shown.metric == "yoy")], "PPI YoY", "YoY change (%)", 1)

st.subheader("Data")
recent = shown.sort_values(["period", "code", "metric"], ascending=[False, True, True]).head(60).copy()
display = recent.rename(columns={"code": "Series", "period": "Period", "metric": "Metric", "value": "Value"})
display["Period"] = display["Period"].dt.strftime("%b %Y")
display["Value"] = display.apply(lambda row: f"{row.Value:.1f}%" if row.Metric in ("mom", "yoy", "ma12") else f"{row.Value:.2f}", axis=1)
st.dataframe(display[["Series", "Period", "Metric", "Value"]], use_container_width=True, hide_index=True)
st.download_button("Download displayed data (CSV)", recent.to_csv(index=False).encode(), "sri_lanka_inflation.csv", "text/csv")
st.caption("Source: Department of Census and Statistics, Sri Lanka")
