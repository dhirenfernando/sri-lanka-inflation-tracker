"""Generate the primary static dashboard from the local SQLite history."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).parent
DATABASE = ROOT / "data" / "inflation.sqlite3"
OUTPUT = ROOT / "docs" / "index.html"
DEFAULT_RANGE_MONTHS = 24
SERIES_NAMES = {"CCPI": "CCPI", "NCPI": "NCPI", "PPI": "PPI"}


def load_data(database: Path = DATABASE) -> list[dict[str, object]]:
    """Return the small, ordered public dataset required by the static page."""
    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            """select s.code, o.period, o.metric, o.value
               from observations o join series s on s.id = o.series_id
               where s.code in ('CCPI', 'NCPI', 'PPI')
               order by s.code, o.period, o.metric"""
        ).fetchall()
    if not rows:
        raise RuntimeError(f"No observations found in {database}")
    return [{"series": series, "period": period, "metric": metric, "value": value} for series, period, metric, value in rows]


def latest(rows: list[dict[str, object]], series: str, metric: str) -> dict[str, object]:
    matches = [row for row in rows if row["series"] == series and row["metric"] == metric]
    if not matches:
        raise RuntimeError(f"No {metric} observations for {series}")
    return matches[-1]


def value_for_period(rows: list[dict[str, object]], series: str, period: object, metric: str) -> object | None:
    return next((row["value"] for row in rows if row["series"] == series and row["period"] == period and row["metric"] == metric), None)


def card_summary(rows: list[dict[str, object]], series: str) -> dict[str, object]:
    index = latest(rows, series, "index")
    return {
        "series": series,
        "period": index["period"],
        "index": index["value"],
        "yoy": value_for_period(rows, series, index["period"], "yoy"),
        "mom": value_for_period(rows, series, index["period"], "mom"),
    }


def change_summary(rows: list[dict[str, object]], series: str, metric: str) -> dict[str, object]:
    values = [row for row in rows if row["series"] == series and row["metric"] == metric]
    if len(values) < 2:
        raise RuntimeError(f"Need two {metric} observations for {series} callout")
    current, previous = values[-1], values[-2]
    return {"current": current["value"], "previous": previous["value"], "change": float(current["value"]) - float(previous["value"])}


def dashboard_payload(rows: list[dict[str, object]]) -> dict[str, object]:
    cards = [card_summary(rows, series) for series in ("CCPI", "NCPI", "PPI")]
    return {
        "cards": cards,
        "changes": {
            "ccpi": change_summary(rows, "CCPI", "yoy"),
            "ncpi": change_summary(rows, "NCPI", "yoy"),
            "ppi": cards[2],
        },
    }


def _page(rows: list[dict[str, object]]) -> str:
    payload = dashboard_payload(rows)
    embedded_rows = json.dumps(rows, separators=(",", ":"), sort_keys=True)
    embedded_cards = json.dumps(payload["cards"], separators=(",", ":"), sort_keys=True)
    embedded_changes = json.dumps(payload["changes"], separators=(",", ":"), sort_keys=True)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sri Lanka Inflation Tracker</title>
  <script src="chart.umd.min.js"></script>
  <style>
    :root {{ --ink:#17324d; --muted:#5d6b78; --page:#f4f7fa; --card:#fff; --line:#dbe3ea; --ccpi:#1666a8; --ncpi:#d95732; --ppi:#27835c; }}
    * {{ box-sizing:border-box; }} body {{ margin:0; color:var(--ink); background:var(--page); font:15px/1.45 Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    main {{ max-width:1180px; margin:auto; padding:34px 22px 48px; }}
    header {{ display:flex; justify-content:space-between; align-items:end; gap:18px; border-bottom:1px solid var(--line); padding-bottom:20px; }}
    h1 {{ margin:0; font-size:30px; letter-spacing:-.02em; }} h2 {{ margin:34px 0 14px; font-size:19px; }} h3 {{ margin:0 0 8px; font-size:16px; }} p {{ margin:0; }} .source {{ color:var(--muted); font-size:13px; }}
    .cards {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; margin-top:20px; }} .card,.panel {{ background:var(--card); border:1px solid var(--line); border-radius:10px; }}
    .card {{ padding:18px; }} .metric {{ font-size:28px; font-weight:700; letter-spacing:-.03em; margin:7px 0; }} .meta {{ color:var(--muted); font-size:13px; }} .positive {{ color:#16704a; }} .negative {{ color:#b33b27; }}
    .controls {{ display:flex; flex-wrap:wrap; gap:9px; align-items:center; margin:0 0 15px; }} button {{ border:1px solid #b9c8d4; border-radius:6px; background:#fff; color:var(--ink); padding:7px 11px; cursor:pointer; font:inherit; }} button.active {{ background:var(--ink); color:#fff; border-color:var(--ink); }} button:hover {{ border-color:var(--ink); }} label {{ color:var(--muted); font-size:13px; }} input {{ border:1px solid #b9c8d4; border-radius:6px; padding:6px; color:var(--ink); background:#fff; }}
    .chart-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; }} .panel {{ padding:16px; min-width:0; }} .callout {{ color:var(--muted); font-size:13px; min-height:20px; margin-bottom:8px; }} .chart-wrap {{ height:265px; position:relative; }}
    .data-actions {{ display:flex; justify-content:space-between; gap:12px; align-items:center; margin:0 0 10px; }} .table-wrap {{ overflow:auto; background:#fff; border:1px solid var(--line); border-radius:10px; }} table {{ width:100%; border-collapse:collapse; font-size:14px; }} th,td {{ padding:10px 12px; border-bottom:1px solid var(--line); text-align:left; white-space:nowrap; }} th {{ background:#f8fafc; color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.04em; }} tr:last-child td {{ border-bottom:0; }} footer {{ color:var(--muted); font-size:13px; margin-top:28px; }}
    @media (max-width:760px) {{ main {{ padding:24px 14px 36px; }} header {{ align-items:start; flex-direction:column; }} .cards,.chart-grid {{ grid-template-columns:1fr; }} .chart-wrap {{ height:240px; }} }}
  </style>
</head>
<body>
<main>
  <header><div><h1>Sri Lanka Inflation Tracker</h1><p class="source">Official DCS headline CCPI, headline NCPI, and aggregate PPI.</p></div><p class="source">Static dashboard · public data</p></header>
  <section><h2>Latest indicators</h2><div class="cards" id="cards"></div></section>
  <section><h2>Inflation trends</h2><div class="controls" aria-label="Chart date range"><strong>View:</strong><button data-range="12">1Y</button><button data-range="24" class="active">2Y</button><button data-range="36">3Y</button><label>From <input id="from" type="month"></label><label>To <input id="to" type="month"></label><span class="source" id="range-note" role="status"></span></div>
    <div class="chart-grid">
      <article class="panel"><h3>CCPI YoY</h3><p class="callout" id="ccpi-callout"></p><div class="chart-wrap"><canvas id="ccpi-chart"></canvas></div></article>
      <article class="panel"><h3>NCPI YoY</h3><p class="callout" id="ncpi-callout"></p><div class="chart-wrap"><canvas id="ncpi-chart"></canvas></div></article>
      <article class="panel"><h3>CCPI vs NCPI YoY</h3><p class="callout">Comparison of published year-on-year inflation.</p><div class="chart-wrap"><canvas id="comparison-chart"></canvas></div></article>
      <article class="panel"><h3>PPI index</h3><p class="callout" id="ppi-callout"></p><div class="chart-wrap"><canvas id="ppi-index-chart"></canvas></div></article>
      <article class="panel"><h3>PPI YoY</h3><p class="callout">Calculated from the aggregate PPI index.</p><div class="chart-wrap"><canvas id="ppi-yoy-chart"></canvas></div></article>
    </div>
  </section>
  <section><h2>Data</h2><div class="data-actions"><p class="source" id="table-summary"></p><button id="download">Download filtered data (CSV)</button></div><div class="table-wrap"><table><thead><tr><th>Series</th><th>Period</th><th>Metric</th><th>Value</th></tr></thead><tbody id="recent"></tbody></table></div></section>
  <footer>Source: Department of Census and Statistics, Sri Lanka</footer>
</main>
<script>
const DATA={embedded_rows}; const CARDS={embedded_cards}; const CHANGES={embedded_changes}; const DEFAULT_RANGE_MONTHS={DEFAULT_RANGE_MONTHS};
const MAX_RANGE_MONTHS=36; const charts={{}}; const color={{CCPI:'#1666a8',NCPI:'#d95732',PPI:'#27835c'}}; let rangeMonths=DEFAULT_RANGE_MONTHS; let currentVisible=[];
const fmtPeriod=(period)=>new Date(period+'T00:00:00Z').toLocaleDateString(undefined,{{month:'short',year:'numeric',timeZone:'UTC'}});
const unavailable=(value)=>value===null||value===undefined; const fmtPct=(value)=>unavailable(value)?'N/A':`${{Number(value).toFixed(1)}}%`; const fmtIndex=(value,series)=>unavailable(value)?'N/A':Number(value).toFixed(series==='PPI'?2:1);
const maxPeriod=DATA.reduce((latest,row)=>row.period>latest?row.period:latest,DATA[0].period).slice(0,7); const minPeriod=DATA.reduce((earliest,row)=>row.period<earliest?row.period:earliest,DATA[0].period).slice(0,7);
function monthShift(period, months) {{ const d=new Date(period+'T00:00:00Z'); d.setUTCMonth(d.getUTCMonth()-months+1); return d.toISOString().slice(0,7); }}
function clampMonth(period,lower,upper) {{ return period<lower?lower:(period>upper?upper:period); }}
function resolveRange() {{ if(rangeMonths!==null) return {{from:monthShift(maxPeriod,rangeMonths),to:maxPeriod,note:''}}; const requestedFrom=document.querySelector('#from').value; const requestedTo=document.querySelector('#to').value; const to=clampMonth(requestedTo||maxPeriod,minPeriod,maxPeriod); let from=clampMonth(requestedFrom||monthShift(to,DEFAULT_RANGE_MONTHS),minPeriod,to); let note=''; if(requestedFrom&&requestedFrom>to) {{ from=clampMonth(monthShift(to,DEFAULT_RANGE_MONTHS),minPeriod,to); note='Start date reset because it was after the end date.'; }} const earliestAllowed=clampMonth(monthShift(to,MAX_RANGE_MONTHS),minPeriod,to); if(from<earliestAllowed) {{ from=earliestAllowed; note=`Custom range limited to ${{MAX_RANGE_MONTHS}} months.`; }} return {{from,to,note}}; }}
function filtered(range) {{ return DATA.filter(row=>row.period.slice(0,7)>=range.from&&row.period.slice(0,7)<=range.to); }}
function renderCards() {{ document.querySelector('#cards').innerHTML=CARDS.map(card=>`<article class="card"><h3>${{card.series}} Index</h3><div class="metric">${{fmtIndex(card.index,card.series)}}</div><p class="${{unavailable(card.yoy)&&unavailable(card.mom)?'meta':'positive'}}">YoY ${{fmtPct(card.yoy)}} · MoM ${{fmtPct(card.mom)}}</p><p class="meta">Latest period: ${{fmtPeriod(card.period)}}</p></article>`).join(''); }}
function direction(value) {{ return unavailable(value)?'':(value>=0?'positive':'negative'); }}
function renderCallouts() {{ for(const [id,change] of Object.entries(CHANGES)) {{ if(id==='ppi') {{ document.querySelector('#ppi-callout').innerHTML=`Current index: <strong>${{fmtIndex(change.index,'PPI')}}</strong> · MoM: <span class="${{direction(change.mom)}}">${{fmtPct(change.mom)}}</span> · YoY: ${{fmtPct(change.yoy)}}`; continue; }} const delta=(change.change>=0?'+':'')+change.change.toFixed(1); document.querySelector('#'+id+'-callout').innerHTML=`Current: <strong>${{fmtPct(change.current)}}</strong> · Previous month: ${{fmtPct(change.previous)}} · <span class="${{direction(change.change)}}">Change: ${{delta}} percentage points</span>`; }} }}
function rows(series,metric,visible) {{ return visible.filter(row=>row.series===series&&row.metric===metric); }}
function line(canvasId,datasets,yTitle) {{ if(charts[canvasId]) charts[canvasId].destroy(); const labels=[...new Set(datasets.flatMap(set=>set.rows.map(row=>row.period)))].sort(); charts[canvasId]=new Chart(document.querySelector('#'+canvasId),{{type:'line',data:{{labels,datasets:datasets.map(set=>({{label:set.label,data:labels.map(label=>{{const found=set.rows.find(row=>row.period===label);return found?found.value:null;}}),borderColor:set.color,backgroundColor:set.color,borderWidth:2.25,pointRadius:(ctx)=>ctx.dataIndex===labels.length-1?3:0,pointHoverRadius:5,spanGaps:false,tension:.18}}))}},options:{{responsive:true,maintainAspectRatio:false,interaction:{{mode:'index',intersect:false}},plugins:{{legend:{{display:datasets.length>1,position:'top',align:'end',labels:{{boxWidth:12,usePointStyle:true}}}},tooltip:{{callbacks:{{title:(items)=>fmtPeriod(items[0].label),label:(item)=>`${{item.dataset.label}}: ${{yTitle.includes('%')?fmtPct(item.raw):Number(item.raw).toFixed(yTitle==='Index level'?2:1)}}`}}}}}},scales:{{x:{{grid:{{display:false}},ticks:{{autoSkip:true,maxTicksLimit:7,maxRotation:0,minRotation:0,callback:(value,index)=>fmtPeriod(labels[index])}}}},y:{{title:{{display:true,text:yTitle}},ticks:{{callback:(value)=>yTitle.includes('%')?value+'%':value}}}}}}}}}}); }}
function renderCharts(visible) {{ line('ccpi-chart',[{{label:'CCPI',color:color.CCPI,rows:rows('CCPI','yoy',visible)}}],'YoY (%)'); line('ncpi-chart',[{{label:'NCPI',color:color.NCPI,rows:rows('NCPI','yoy',visible)}}],'YoY (%)'); line('comparison-chart',[{{label:'CCPI',color:color.CCPI,rows:rows('CCPI','yoy',visible)}},{{label:'NCPI',color:color.NCPI,rows:rows('NCPI','yoy',visible)}}],'YoY (%)'); line('ppi-index-chart',[{{label:'PPI',color:color.PPI,rows:rows('PPI','index',visible)}}],'Index level'); line('ppi-yoy-chart',[{{label:'PPI',color:color.PPI,rows:rows('PPI','yoy',visible)}}],'YoY (%)'); }}
function renderTable(visible) {{ const recent=visible.slice().sort((a,b)=>b.period.localeCompare(a.period)||a.series.localeCompare(b.series)||a.metric.localeCompare(b.metric)); document.querySelector('#table-summary').textContent=`${{recent.length}} observations in selected range`; document.querySelector('#recent').innerHTML=recent.slice(0,60).map(row=>`<tr><td>${{row.series}}</td><td>${{fmtPeriod(row.period)}}</td><td>${{row.metric.toUpperCase()}}</td><td>${{row.metric==='index'?fmtIndex(row.value,row.series):fmtPct(row.value)}}</td></tr>`).join(''); }}
function render() {{ const range=resolveRange(); currentVisible=filtered(range); const fromControl=document.querySelector('#from'); const toControl=document.querySelector('#to'); fromControl.min=minPeriod; fromControl.max=maxPeriod; toControl.min=minPeriod; toControl.max=maxPeriod; fromControl.value=range.from; toControl.value=range.to; document.querySelector('#range-note').textContent=range.note; document.querySelectorAll('[data-range]').forEach(button=>button.classList.toggle('active',String(rangeMonths)===button.dataset.range)); renderCharts(currentVisible); renderTable(currentVisible); }}
document.querySelectorAll('[data-range]').forEach(button=>button.addEventListener('click',()=>{{rangeMonths=Number(button.dataset.range); document.querySelector('#from').value=''; document.querySelector('#to').value=''; render();}})); document.querySelector('#from').addEventListener('change',()=>{{rangeMonths=null;render();}}); document.querySelector('#to').addEventListener('change',()=>{{rangeMonths=null;render();}});
document.querySelector('#download').addEventListener('click',()=>{{ const csv=['series,period,metric,value',...currentVisible.map(row=>`${{row.series}},${{row.period}},${{row.metric}},${{row.value}}`)].join('\\n'); const link=document.createElement('a'); link.href=URL.createObjectURL(new Blob([csv],{{type:'text/csv'}})); link.download='sri_lanka_inflation.csv'; link.click(); setTimeout(()=>URL.revokeObjectURL(link.href),0); }});
renderCards(); renderCallouts(); render();
</script>
</body>
</html>"""


def generate(database: Path = DATABASE, output: Path = OUTPUT) -> Path:
    rows = load_data(database)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_page(rows), encoding="utf-8")
    return output


if __name__ == "__main__":
    path = generate()
    print(f"Static dashboard generated: {path}")
