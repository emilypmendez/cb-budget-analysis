"""Unit tests for budget_utils. Run with: pytest -q"""
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import budget_utils as bu

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


# --- acquisition -------------------------------------------------------------

def test_resolve_fields_matches_display_names_and_types():
    meta = [
        {"name": "Fiscal Year", "fieldName": "fiscal_year", "dataTypeName": "number"},
        {"name": "Legal Name of Organization", "fieldName": "legal_name_of_organization", "dataTypeName": "text"},
        {"name": "Source", "fieldName": "source", "dataTypeName": "text"},
        {"name": "Amount ($)", "fieldName": "amount", "dataTypeName": "number"},
    ]
    out = bu.resolve_fields(bu.DISCRETIONARY, meta)
    assert out["organization"] == {"field": "legal_name_of_organization", "type": "text"}
    assert out["amount"]["field"] == "amount"


def test_resolve_fields_fails_loudly_when_a_column_is_missing():
    meta = [{"name": "Fiscal Year", "fieldName": "fiscal_year"}]
    with pytest.raises(KeyError, match="Legal Name of Organization"):
        bu.resolve_fields(bu.DISCRETIONARY, meta)


def test_soql_literal_quotes_text_but_not_numbers():
    assert bu.soql_literal(3, "number") == "3"
    assert bu.soql_literal("O'Brien", "text") == "'O''Brien'"


# --- cleaning ----------------------------------------------------------------

def test_to_number_handles_currency_blanks_and_junk():
    s = pd.Series(["$1,250.50", "-300", "", "n/a", None], dtype="string")
    out = bu.to_number(s)
    assert out.iloc[0] == 1250.50 and out.iloc[1] == -300
    assert out.iloc[2:].isna().all()


def test_to_date_handles_iso_and_compact_formats():
    s = pd.Series(["2022-01-15T00:00:00.000", "20220630", "not a date", None], dtype="string")
    out = bu.to_date(s)
    assert out.iloc[0] == pd.Timestamp("2022-01-15")
    assert out.iloc[1] == pd.Timestamp("2022-06-30")
    assert out.iloc[2:].isna().all()


def test_quality_report_counts_unparseable_and_duplicates():
    raw = pd.DataFrame({"amt": ["1", "x", "-2", "1"], "k": ["a", "b", None, "a"]}, dtype="string")
    clean = raw.assign(amt=bu.to_number(raw["amt"]))
    rep = bu.quality_report(raw, clean, key_cols=["k"], numeric_cols=["amt"],
                            duplicate_subset=["amt", "k"]).set_index("check")["rows"]
    assert rep["Missing k"] == 1
    assert rep["Unparseable number in amt"] == 1
    assert rep["Negative amt"] == 1
    assert rep["Rows with identical amt, k"] == 1


# --- keywords ----------------------------------------------------------------

nltk = pytest.importorskip("nltk")


def _nltk_ready():
    try:
        nltk.pos_tag(nltk.word_tokenize("test sentence"))
        return True
    except LookupError:
        return False


@pytest.mark.skipif(not _nltk_ready(), reason="NLTK tokenizer/tagger data not downloaded")
def test_noun_phrases_strip_instructions_and_skip_generic_labels():
    phrases = bu.noun_phrases("Provide more housing for extremely low income households")
    assert "housing" in phrases
    assert all(not p.startswith("provide") for p in phrases)
    assert bu.noun_phrases("Other capital budget request") == []


@pytest.mark.skipif(not _nltk_ready(), reason="NLTK tokenizer/tagger data not downloaded")
def test_top_keywords_counts_each_phrase_once_per_request():
    texts = pd.Series(["Repair playground and playground fence", "Renovate playground"])
    top = bu.top_keywords(texts, n=5).set_index("keyword")
    assert top.loc["playground", "requests"] == 2


# --- statistics ----------------------------------------------------------------

def test_chi_square_independent_table_has_no_effect():
    table = pd.DataFrame([[50, 50], [100, 100]], index=["x", "y"], columns=["a", "b"])
    res = bu.chi_square_independence(table)
    assert res.chi2 == pytest.approx(0.0)
    assert res.cramers_v == pytest.approx(0.0)
    assert res.p_value == pytest.approx(1.0)


def test_chi_square_matches_known_value():
    # 2x2 table with a hand-checkable result: chi2 = 100 * (40*40 - 10*10)^2 / (50^4) = 36
    table = pd.DataFrame([[40, 10], [10, 40]])
    res = bu.chi_square_independence(table)
    assert res.chi2 == pytest.approx(36.0)
    assert res.cramers_v == pytest.approx(0.6)
    assert np.allclose(np.abs(res.adjusted_residuals.to_numpy()), 6.0)


def test_collapse_categories_keeps_top_n():
    s = pd.Series(list("aaabbc"))
    assert set(bu.collapse_categories(s, 2, other="z")) == {"a", "b", "z"}


# --- SQL -----------------------------------------------------------------------

def test_expense_by_agency_uses_only_latest_publication():
    expense = pd.DataFrame({
        "publication_date": ["2022-01-14", "2022-06-30", "2022-06-30"],
        "agency_name": ["A", "A", "B"],
        "adopted_budget_amount": [9e9, 1e9, 3e9],
        "current_modified_budget_amount": [9e9, 1e9, 3e9],
        "financial_plan_amount": [9e9, 1e9, 3e9],
    })
    with sqlite3.connect(":memory:") as conn:
        expense.to_sql("expense", conn, index=False)
        out = pd.read_sql_query((SQL_DIR / "expense_by_agency.sql").read_text(), conn)
    totals = dict(zip(out.agency_name, out.modified_billions))
    assert totals == {"B": 3.0, "A": 1.0}  # the earlier 9e9 publication is ignored
    assert out.pct_of_citywide_modified.sum() == pytest.approx(100.0)


def test_agency_title_keeps_small_words_lowercase():
    assert bu.agency_title("DEPARTMENT OF PARKS AND RECREATION") == "Department of Parks and Recreation"


@pytest.mark.skipif(not _nltk_ready(), reason="NLTK tokenizer/tagger data not downloaded")
def test_noun_phrases_keep_participle_phrases_together():
    assert "traffic calming measures" in bu.noun_phrases("Install traffic calming measures")


def test_chi_square_rejects_a_single_column_table():
    with pytest.raises(ValueError, match="at least 2"):
        bu.chi_square_independence(pd.DataFrame({"only_board": [3, 4]}))


def test_latest_per_request_keeps_one_row_per_id_per_year():
    df = pd.DataFrame({
        "tracking_code": ["A", "A", "A", "B", None],
        "publication": pd.to_datetime(["2022-02-16", "2022-06-14", "2023-01-12", "2022-02-16", "2022-02-16"]),
        "publication_year": [2022, 2022, 2023, 2022, 2022],
        "request": ["old", "new", "next year", "b", "no id"],
    })
    out = bu.latest_per_request(df)
    assert list(out["request"]) == ["new", "next year", "b", "no id"]


def test_resolve_fields_accepts_current_requests_labels():
    meta = [{"name": n, "fieldName": f} for n, f in [
        ("Publication", "publication"), ("Borough", "boro"), ("Community Board", "board"),
        ("Tracking  Code ", "tracking_code"), ("Request ", "request"),
        ("Responsible Agency", "responsible_agency")]]
    out = bu.resolve_fields(bu.REQUESTS, meta)
    assert out["tracking_code"]["field"] == "tracking_code"
    assert out["request"]["field"] == "request"
