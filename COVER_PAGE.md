# Code Sample Cover Page

**Applicant:** Emily Portalatín-Méndez

**Position:** Data Scientist, Research and Analytics Department (Reference No. RAD_NYC_DAS_6463)

**Repository:** [ADD PUBLIC GITHUB LINK]

**Where to start:** `cb_budget_analysis.ipynb`; supporting code in `budget_utils.py` and `sql/`


## Background

In summer 2022, as a Public Interest Technology Data Science Fellow (Columbia University and Lehman College), I worked on a team that built data tools for Brooklyn Community Boards 4 and 14. This notebook explored three NYC Open Data datasets behind the project's budgeting dashboard: the Register of Community Board Budget Requests, the City's Expense Budget, and City Council Discretionary Funding.

**My role in 2022.** I helped decide which data mattered for the boards' questions and helped design the notebook's code structure. Teammates wrote most of the original analysis code. That version is included unchanged, except with credentials removed, in `original_2022/`.

**The 2026 revision.** I revised the notebook in November 2026 with the help of an AI coding assistant, then reviewed and ran every part myself. The revision corrects errors in the original, makes it reproducible, and adds data quality checks, SQL, and a statistical test. The `CHANGELOG.md` file is included, which lists each change.

## Question and approach

What do the two boards ask the City to fund, which agencies are those requests aimed at, and do the boards' priorities differ?

1. **Acquire:** download all three datasets through the Socrata API with server-side filters, resolving column names from each dataset's metadata so schema changes fail loudly.
2. **Check reliability:** parse every column explicitly and count missing keys, unparseable values, negatives, repeated rows, and generic request labels.
3. **Aggregate:** load into SQLite and summarize with SQL (CTEs and window functions).
4. **Test:** a chi-square test of independence on the boards' agency mix, reporting Cramér's V and adjusted residuals alongside the p-value.
5. **Text analysis:** noun-phrase keyword extraction from request text with NLTK.

## What I would point a reviewer to

- **Section 3.1.** The request register uses different borough codes from many City datasets (Brooklyn is 2, not 3), and it repeats each open request in every publication within a year. The notebook checks the borough by its number of community boards and counts each request once by its tracking code.
- **Section 3.2.** The expense budget restates each fiscal year in several publications. The original notebook summed all of them, which overstated agency totals several times over. The revision uses one publication and shows every publication's total so the choice is visible.
- **Section 5.** The chi-square result is read together with effect size, and the notebook explains why the independence assumption makes the p-value a guide, not a precise probability.
- **Section 10.** Limitations, including that requests measure priorities, not spending.

## Key findings

From NYC Open Data, downloaded November 2026:

- **Two data problems would have inflated the results about threefold.** The request register repeats each open request in every publication within a year: 27,754 Brooklyn rows held 10,083 distinct requests per year, about 2.8 rows per request. The expense budget restates FY2023 in three publications, so summing them gives $330.9B instead of $114.0B (2.9x). Both are corrected.
- **Boards 4 and 14 filed 115 and 128 distinct requests published from 2022 to 2024.** Board 4's most common agency was the Department of Transportation (16% of its requests). Board 14's were the Department of Transportation and the Department of Sanitation (10% each).
- **No clear evidence that the two boards' agency priorities differ** (chi-square = 8.2, df = 6, p = 0.23). With 243 requests the test can only detect large differences, so this is not evidence that their priorities are the same.

## Tools

Python (pandas, SciPy, NLTK, matplotlib, sodapy), SQL (SQLite), pytest, Jupyter.
