# Brooklyn Community Board Budget Requests

What do Brooklyn Community Boards 4 and 14 ask the City to fund, which agencies do those requests go to, and do the two boards' priorities differ? The notebook answers this with three NYC Open Data datasets, and adds citywide agency budgets and City Council discretionary funding for context.

This is a 2026 revision of a 2022 team notebook from the Public Interest Technology Data Science Fellowship (Columbia University and Lehman College). See `CHANGELOG.md` for what changed.

## Start here

Open **`cb_budget_analysis.ipynb`**. It runs top to bottom and is organized as:

1. Setup and parameters
2. Acquire the data (Socrata API)
3. Clean the data and check its reliability
4. Which agencies receive each board's requests
5. Do the boards differ? (chi-square test with effect size)
6. Keywords from request text (NLTK noun-phrase chunking)
7. Citywide agency budgets
8. Council discretionary funding
9. Summary (generated from results)
10. Limitations

## Repository layout

```
cb_budget_analysis.ipynb   the analysis
budget_utils.py            acquisition, cleaning, quality checks, keywords, statistics
sql/                       SQL queries run against an in-memory SQLite database
tests/                     unit tests and small synthetic fixtures
scripts/make_fixtures.py   rebuilds the synthetic fixtures
figures/                   charts saved by the notebook
original_2022/             the 2022 team notebook, credentials removed
```

## Running it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# optional: raises NYC Open Data rate limits; never commit it
export SOCRATA_APP_TOKEN=your_token

jupyter nbconvert --to notebook --execute --inplace cb_budget_analysis.ipynb
```

To run offline on the synthetic fixtures instead of live data:

```bash
DATA_MODE=fixtures jupyter nbconvert --to notebook --execute --inplace cb_budget_analysis.ipynb
```

Tests:

```bash
python -m pytest -q
```

## Data sources

| Dataset | NYC Open Data ID |
|---|---|
| Register of Community Board Budget Requests | [vn4m-mk4t](https://data.cityofnewyork.us/d/vn4m-mk4t) |
| Expense Budget | [mwzb-yiwb](https://data.cityofnewyork.us/d/mwzb-yiwb) |
| New York City Council Discretionary Funding | [4d7f-74pe](https://data.cityofnewyork.us/d/4d7f-74pe) |
