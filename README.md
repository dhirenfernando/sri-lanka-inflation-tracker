# Sri Lanka Inflation Tracker

## Primary: static GitHub Pages dashboard

The primary dashboard is `docs/index.html`. It tracks DCS headline CCPI, headline NCPI, and aggregate PPI with latest indicators, recent-history charts, range controls, filtered observations, and CSV export.

Live static dashboard: set this URL after GitHub Pages is enabled.

## Generate locally

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python update_data.py
.venv/bin/python generate_dashboard.py
```

Open `docs/index.html` directly in a browser, or serve the `docs/` directory with any static web server.

## Deployment and automatic refresh

GitHub Actions checks DCS daily, refreshes `data/inflation.sqlite3`, regenerates `docs/index.html`, commits changed public data, and publishes `docs/` to GitHub Pages. In GitHub **Settings → Pages**, select **GitHub Actions** as the deployment source.

## Optional local backup

The original Streamlit application remains available locally:

```bash
.venv/bin/streamlit run app.py
```

GitHub Pages visitors do not need Streamlit or Python at runtime.
