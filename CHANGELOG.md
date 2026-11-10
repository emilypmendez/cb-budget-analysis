# Changes from the 2022 notebook

The original team notebook is kept in `original_2022/data_explore_2022.ipynb` (credentials removed) so the two versions can be compared. The revised analysis is `cb_budget_analysis.ipynb`.

## Corrections

| Issue in the 2022 notebook | Effect | Fix |
|---|---|---|
| Expense budget totals summed every row for the fiscal year, across all budget publications (preliminary, executive, adopted, modifications) | Agency totals overstated several times over; the Department of Education showed about $81.7B for FY2021 | Totals now use one publication (the latest for the year). Section 3.2 shows every publication's total so the choice is visible |
| Requests were filtered with `boro = 3`. In the current dataset Brooklyn is `2` (the only code with 18 community boards); `3` is a 12-board borough, Manhattan if the codes are alphabetical as they appear to be | In the current data, the analysis would cover the wrong borough | Borough is set by name and mapped to the dataset's code; the notebook checks that the download has the expected number of boards |
| Each request appears in every publication of the register within a year (up to three) | Requests counted more than once | One row per tracking code per year, from the latest publication |
| Markdown said "CB4 in 2021" while the code filtered publication year 2022 and Boards 4, 14, 10, and 9 | Text and results disagreed | Years and boards are set once as parameters; all titles and summaries are built from them |
| A section described the Department of Parks and Recreation, but `agen_keywords(df)[0]` returned the Department of Education; the chart title also said 2021 | Wrong agency and year on the chart | Agency and year come from the data, not hardcoded text |
| Chart titled "Adopted Budget" plotted Current Modified Budget | Mislabeled measure | Axis label names the measure and the publication date |
| `type_e(df_exp)` cell raised `NameError` | Notebook could not run from top to bottom | Removed; the notebook now runs end to end (verified with `nbclient`) |
| Count column renamed with a key that did not exist, so the count column was labeled `responsible_agency` | Confusing table header | Counts come from SQL with explicit column names |
| API key, key secret, app token, and token secret written into a cell | Credentials exposed | Removed. An optional token is read from the `SOCRATA_APP_TOKEN` environment variable |
| Two datasets read from local Colab files (`/Expense_Budget.csv`, `/New_York_City_Council_Discretionary_Funding.csv`) | Not reproducible | All three datasets are downloaded through the Socrata API with server-side filters |
| `DtypeWarning` on CSV load was ignored | Mixed-type columns parsed inconsistently | Everything loads as text, then each column is parsed explicitly, and failures are counted |

## Additions

- **Data quality checks** for each dataset: missing keys, unparseable numbers and dates, negative amounts, future dates, inconsistent board numbering, repeated requests, and generic request labels, each with counts and shares.
- **SQL** (`sql/`): data is loaded into SQLite and aggregated with SQL, including window functions for shares and rankings.
- **Statistical test**: chi-square test of independence on the boards' agency mix. Publication years 2022 to 2024 are pooled, with each request counted once by tracking code, so the test has enough data. Sparse agencies are merged automatically until every expected count is at least 5. Cramér's V is interpreted only when the result is significant, and adjusted residuals show which agencies drive any difference.
- **Keyword extraction improvements**: phrases are lowercased, leading instruction words are removed, generic category labels are excluded, and each phrase counts once per request.
- **Schema checks**: column names are resolved from each dataset's metadata, so a renamed field stops the notebook with a clear error.
- **Unit tests** (`tests/`) for parsing, quality checks, keyword extraction, the chi-square helper, and the budget SQL.
- **Offline mode** with small synthetic fixtures, so the notebook and tests run without network access.
- **Limitations section** and a generated summary whose numbers always match the loaded data.
- The pie chart was replaced with sorted bar charts, which make it easier to compare similar-sized shares.

## Kept from the original

- The project question and the three datasets the team chose.
- The noun-phrase chunking approach to keyword extraction (now in `budget_utils.noun_phrases`).
- The organization into filter, rank, and summarize steps, now as SQL queries and tested helper functions.
