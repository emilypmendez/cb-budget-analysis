"""Helpers for the Brooklyn Community Board budget analysis notebook.

The notebook (cb_budget_analysis.ipynb) tells the story; this module holds the
reusable pieces so they can be tested on their own (see tests/).

Sections:
    1. Data acquisition from NYC Open Data (Socrata), with schema checks
    2. Cleaning helpers
    3. Data quality checks
    4. Keyword extraction from free-text requests (NLTK noun-phrase chunking)
    5. Statistics: chi-square test of independence with effect size
"""
from __future__ import annotations

import os
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

# ---------------------------------------------------------------------------
# 1. Data acquisition
# ---------------------------------------------------------------------------

DOMAIN = "data.cityofnewyork.us"
PAGE_SIZE = 50_000


@dataclass(frozen=True)
class DatasetSpec:
    """One NYC Open Data dataset and the columns we need from it.

    `columns` maps the name we use in the analysis to the dataset's display
    name (the column header on the NYC Open Data website). Display names are
    resolved to API field names at run time from the dataset's metadata, so a
    renamed field fails loudly instead of silently returning nothing.
    """
    key: str
    dataset_id: str
    title: str
    columns: dict[str, str]


REQUESTS = DatasetSpec(
    key="requests",
    dataset_id="vn4m-mk4t",
    title="Register of Community Board Budget Requests",
    columns={
        "boro": "Borough",
        "board": "Community Board",
        "publication": "Publication",
        "tracking_code": "Tracking Code",
        "responsible_agency": "Responsible Agency",
        "request": "Request",
    },
)

EXPENSE = DatasetSpec(
    key="expense",
    dataset_id="mwzb-yiwb",
    title="Expense Budget",
    columns={
        "publication_date": "Publication Date",
        "fiscal_year": "Fiscal Year",
        "agency_name": "Agency Name",
        "object_class_name": "Object Class Name",
        "adopted_budget_amount": "Adopted Budget Amount",
        "current_modified_budget_amount": "Current Modified Budget Amount",
        "financial_plan_amount": "Financial Plan Amount",
    },
)

DISCRETIONARY = DatasetSpec(
    key="discretionary",
    dataset_id="4d7f-74pe",
    title="New York City Council Discretionary Funding",
    columns={
        "fiscal_year": "Fiscal Year",
        "organization": "Legal Name of Organization",
        "source": "Source",
        "amount": "Amount ($)",
    },
)


# Borough codes in the Register of Community Board Budget Requests appear to be
# alphabetical (1 Bronx, 2 Brooklyn, 3 Manhattan, 4 Queens, 5 Staten Island),
# not the 1 Manhattan / 3 Brooklyn order used by many other City datasets.
# Checked against the data (November 2026): code 2 is the only one with 18
# community boards, 4 has 14, and 5 has 3. Codes 1 and 3 both have 12.
REQUESTS_BOROUGH_CODES = {"Bronx": 1, "Brooklyn": 2, "Manhattan": 3, "Queens": 4, "Staten Island": 5}
BOARDS_PER_BOROUGH = {"Bronx": 12, "Brooklyn": 18, "Manhattan": 12, "Queens": 14, "Staten Island": 3}


def _normalize_label(label: str) -> str:
    """'Amount ($)' -> 'amount'; used to match display names loosely."""
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def resolve_fields(spec: DatasetSpec, metadata_columns: list[dict]) -> dict[str, dict]:
    """Map each analysis column to its Socrata field name and data type.

    `metadata_columns` is the "columns" list from the dataset's metadata
    (each item has "name", "fieldName", "dataTypeName").
    """
    by_label = {_normalize_label(c["name"]): c for c in metadata_columns}
    by_field = {c["fieldName"]: c for c in metadata_columns}
    resolved, missing = {}, []
    for ours, display in spec.columns.items():
        col = (by_label.get(_normalize_label(display))
               or by_field.get(_normalize_label(display))
               or by_field.get(ours))
        if col is None:
            missing.append(display)
        else:
            resolved[ours] = {"field": col["fieldName"], "type": col.get("dataTypeName", "text")}
    if missing:
        available = sorted(c["name"] for c in metadata_columns)
        raise KeyError(
            f"{spec.title} ({spec.dataset_id}) has no column(s) {missing}. "
            f"Available columns: {available}"
        )
    return resolved


def soql_literal(value, data_type: str) -> str:
    """Quote a filter value the way SoQL expects for the column's type."""
    if data_type == "number":
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def fetch(spec: DatasetSpec, filters: dict | None = None, client=None) -> pd.DataFrame:
    """Download a dataset from NYC Open Data, paging through all rows.

    filters: {analysis_column: value} combined with AND, e.g. {"boro": 3}.
    The app token is read from the SOCRATA_APP_TOKEN environment variable;
    it is optional but raises the API's rate limits. Never hardcode it.
    """
    from sodapy import Socrata  # imported here so tests don't need network libraries

    client = client or Socrata(DOMAIN, os.environ.get("SOCRATA_APP_TOKEN"), timeout=120)
    fields = resolve_fields(spec, client.get_metadata(spec.dataset_id)["columns"])

    select = ", ".join(f"{f['field']} AS {ours}" for ours, f in fields.items())
    where = " AND ".join(
        f"{fields[col]['field']} = {soql_literal(val, fields[col]['type'])}"
        for col, val in (filters or {}).items()
    ) or None

    pages, offset = [], 0
    while True:
        rows = client.get(spec.dataset_id, select=select, where=where,
                          order=":id", limit=PAGE_SIZE, offset=offset)
        pages.append(pd.DataFrame.from_records(rows))
        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    df = pd.concat(pages, ignore_index=True)
    # Socrata omits null fields from JSON rows, so make sure every column exists.
    return df.reindex(columns=list(spec.columns)).astype("string")


def load_fixture(spec: DatasetSpec, fixtures_dir: Path) -> pd.DataFrame:
    """Load the small offline test extract for a dataset (same columns as fetch)."""
    df = pd.read_csv(fixtures_dir / f"{spec.key}.csv", dtype="string", keep_default_na=False)
    return df.reindex(columns=list(spec.columns)).replace("", pd.NA)


# ---------------------------------------------------------------------------
# 2. Cleaning helpers
# ---------------------------------------------------------------------------

def to_number(s: pd.Series) -> pd.Series:
    """Parse numbers that may contain $ or commas; unparseable values become NaN."""
    cleaned = s.astype("string").str.replace(r"[$,\s]", "", regex=True)
    return pd.to_numeric(cleaned, errors="coerce")


def to_date(s: pd.Series) -> pd.Series:
    """Parse dates in the formats NYC Open Data uses (ISO timestamps or YYYYMMDD)."""
    s = s.astype("string").str.strip()
    compact = s.str.fullmatch(r"\d{8}", na=False)
    out = pd.to_datetime(s.where(~compact), errors="coerce", format="ISO8601")
    out[compact] = pd.to_datetime(s[compact], format="%Y%m%d", errors="coerce")
    return out


SMALL_WORDS = {"of", "and", "for", "the", "&", "to", "in", "on", "at"}


def agency_title(name: str) -> str:
    """'DEPARTMENT OF PARKS AND RECREATION' -> 'Department of Parks and Recreation'."""
    words = str(name).lower().split()
    return " ".join(w if (i and w in SMALL_WORDS) else w.capitalize() for i, w in enumerate(words))


def clean_text(s: pd.Series) -> pd.Series:
    """Trim and collapse whitespace; blank strings become missing."""
    return s.astype("string").str.strip().str.replace(r"\s+", " ", regex=True).replace("", pd.NA)


def latest_per_request(df: pd.DataFrame, id_col: str = "tracking_code",
                       date_col: str = "publication", period_col: str = "publication_year") -> pd.DataFrame:
    """Keep one row per request ID per period: the one from the latest publication.

    The request register is republished several times a year, and each
    publication repeats the requests still open. Without this step a request
    is counted once per publication. Rows with no ID cannot be matched, so
    they are kept as they are.
    """
    has_id = df[id_col].notna()
    latest = (df[has_id].sort_values(date_col)
              .drop_duplicates(subset=[id_col, period_col], keep="last"))
    return pd.concat([latest, df[~has_id]]).sort_index()


# ---------------------------------------------------------------------------
# 3. Data quality checks
# ---------------------------------------------------------------------------

def quality_report(raw: pd.DataFrame, clean: pd.DataFrame, key_cols: list[str],
                   numeric_cols: list[str] = (), date_cols: list[str] = (),
                   duplicate_subset: list[str] | None = None) -> pd.DataFrame:
    """Summarize reliability problems found while cleaning one dataset.

    `raw` is the data as downloaded (strings); `clean` is after type parsing.
    Each row is one check with the number and share of affected rows.
    """
    n = len(raw)
    checks = [("Rows downloaded", n)]
    for c in key_cols:
        checks.append((f"Missing {c}", int(clean[c].isna().sum())))
    for c in numeric_cols:
        bad = clean[c].isna() & raw[c].notna()
        checks.append((f"Unparseable number in {c}", int(bad.sum())))
        checks.append((f"Negative {c}", int((clean[c] < 0).sum())))
    for c in date_cols:
        bad = clean[c].isna() & raw[c].notna()
        checks.append((f"Unparseable date in {c}", int(bad.sum())))
    if duplicate_subset:
        checks.append((f"Rows with identical {', '.join(duplicate_subset)}",
                       int(clean.duplicated(subset=duplicate_subset).sum())))
    out = pd.DataFrame(checks, columns=["check", "rows"])
    out["share"] = (out["rows"] / n).map("{:.1%}".format) if n else "n/a"
    out.loc[0, "share"] = ""
    return out


# ---------------------------------------------------------------------------
# 4. Keyword extraction
# ---------------------------------------------------------------------------

# Phrases that describe the form, not the need. "Other capital budget request"
# is a category label boards pick when no specific option fits, so counting it
# as a keyword would crowd out the real topics.
GENERIC_PHRASES = {
    "other capital budget request",
    "other expense budget request",
    "other request",
}
# Leading words that are instructions ("Provide ...", "Repair ...") rather than topics.
LEADING_VERBS = {
    "provide", "reconstruct", "renovate", "repair", "assign", "expand", "fund",
    "increase", "improve", "install", "build", "create", "new", "more", "other",
}
# Nouns, optionally preceded by adjectives or participles, so that phrases like
# "traffic calming measures" and "home delivered meals" stay together.
NP_GRAMMAR = r"NP: {<NN.*>*<JJ.*|VBG|VBN>*<NN.*>+}"


def noun_phrases(text: str, tagger=None, tokenizer=None) -> list[str]:
    """Extract lowercased noun phrases (adjectives + nouns) from one request.

    tagger/tokenizer default to NLTK's; tests can pass simple stand-ins.
    """
    import nltk

    tokenizer = tokenizer or nltk.word_tokenize
    tagger = tagger or nltk.pos_tag
    if not isinstance(text, str) or not text.strip():
        return []
    if text.strip().lower() in GENERIC_PHRASES:
        return []
    tree = nltk.RegexpParser(NP_GRAMMAR).parse(tagger(tokenizer(text)))
    phrases = []
    for subtree in tree.subtrees(lambda t: t.label() == "NP"):
        words = [w.lower() for w, _ in subtree.leaves()]
        if " ".join(words) in GENERIC_PHRASES:
            continue
        while words and words[0] in LEADING_VERBS:
            words = words[1:]
        phrase = " ".join(words)
        if len(phrase) > 2 and phrase not in GENERIC_PHRASES:
            phrases.append(phrase)
    return phrases


def top_keywords(texts: pd.Series, n: int = 10, **kwargs) -> pd.DataFrame:
    """Count noun phrases across requests. Each phrase counts once per request."""
    counts = Counter()
    for text in texts.dropna():
        counts.update(set(noun_phrases(text, **kwargs)))
    df = pd.DataFrame(counts.most_common(n), columns=["keyword", "requests"])
    df["share_of_requests"] = df["requests"] / max(texts.notna().sum(), 1)
    return df


def is_generic_request(texts: pd.Series) -> pd.Series:
    """True where the request text is only a generic category label."""
    return texts.astype("string").str.strip().str.lower().isin(GENERIC_PHRASES)


# ---------------------------------------------------------------------------
# 5. Statistics
# ---------------------------------------------------------------------------

@dataclass
class ChiSquareResult:
    table: pd.DataFrame
    chi2: float
    dof: int
    p_value: float
    cramers_v: float
    min_expected: float
    adjusted_residuals: pd.DataFrame


def chi_square_independence(table: pd.DataFrame) -> ChiSquareResult:
    """Chi-square test of independence on a contingency table, with effect size.

    Cramér's V reports how strong the association is (0 = none, 1 = complete),
    which matters because with large counts even trivial differences are
    "significant". Adjusted standardized residuals show which cells drive the
    result: |residual| > 2 is a rough guide to a notable cell.
    """
    if table.shape[0] < 2 or table.shape[1] < 2:
        raise ValueError(
            f"Chi-square needs at least 2 rows and 2 columns; got shape {table.shape}. "
            "Check that every selected board has requests in the selected year."
        )
    observed = table.to_numpy(dtype=float)
    chi2, p, dof, expected = stats.chi2_contingency(observed, correction=False)
    n = observed.sum()
    r, k = observed.shape
    cramers_v = float(np.sqrt(chi2 / (n * (min(r, k) - 1))))
    row_p = observed.sum(axis=1, keepdims=True) / n
    col_p = observed.sum(axis=0, keepdims=True) / n
    adj = (observed - expected) / np.sqrt(expected * (1 - row_p) * (1 - col_p))
    return ChiSquareResult(
        table=table,
        chi2=float(chi2),
        dof=int(dof),
        p_value=float(p),
        cramers_v=cramers_v,
        min_expected=float(expected.min()),
        adjusted_residuals=pd.DataFrame(adj, index=table.index, columns=table.columns),
    )


def collapse_categories(s: pd.Series, top_n: int, other: str = "All other agencies") -> pd.Series:
    """Keep the top_n most frequent values and group the rest, so the chi-square
    test is not run on sparse cells."""
    keep = s.value_counts().nlargest(top_n).index
    return s.where(s.isin(keep), other)
