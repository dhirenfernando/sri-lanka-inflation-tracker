# Sri Lanka Inflation Tracker

Tracks DCS headline CCPI, headline NCPI, and aggregate PPI. It includes historical charts, date filtering, recent observations, and CSV export.

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## Update data

```bash
.venv/bin/python update_data.py
```

## Run dashboard

```bash
.venv/bin/streamlit run app.py
```

The local SQLite database is `data/inflation.sqlite3`.

## Deployment

The repository includes a public DCS SQLite data snapshot so the dashboard displays data immediately after deployment. To refresh it, run the update command locally, then commit and push the updated database before redeploying.

For Streamlit Community Cloud: create a GitHub repository, push this project, then create a new app with `app.py` as the entry point. No credentials are required.
