"""Build small synthetic extracts that mimic the three NYC Open Data datasets.

They let the notebook and tests run offline (DATA_MODE=fixtures). Values are
made up; only the column layout and formats follow the real datasets. A few
known problems are planted on purpose (duplicates, blank fields, bad dates,
overlapping budget publications) so the data quality checks have something
to find.

Usage: python scripts/make_fixtures.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
rng = np.random.default_rng(2022)

AGENCIES = [
    "Department of Parks and Recreation",
    "Department of Housing Preservation & Development",
    "Department of Education",
    "Department of Transportation",
    "New York City Police Department",
    "Department of Sanitation",
    "Department for the Aging",
    "Department of Youth & Community Development",
    "Department of Environmental Protection",
    "Department of Health and Mental Hygiene",
]
REQUEST_TEXT = {
    AGENCIES[0]: ["Reconstruct playground at local park", "Renovate outdoor athletic field",
                  "Provide more park maintenance staff", "Other capital budget request"],
    AGENCIES[1]: ["Provide more housing for extremely low income households",
                  "Expand code enforcement for housing violations",
                  "Provide more affordable senior housing"],
    AGENCIES[2]: ["Renovate interior building component at elementary school",
                  "Provide new high school seats", "Other expense budget request"],
    AGENCIES[3]: ["Repair street lights on commercial corridor", "Install traffic calming measures",
                  "Reconstruct sidewalks near schools"],
    AGENCIES[4]: ["Assign additional uniformed officers", "Provide new patrol vehicles"],
    AGENCIES[5]: ["Increase litter basket collection", "Provide more street cleaning"],
    AGENCIES[6]: ["Fund senior center programs", "Expand home delivered meals"],
    AGENCIES[7]: ["Fund youth employment programs", "Provide after school programs"],
    AGENCIES[8]: ["Repair catch basins to prevent flooding", "Other capital budget request"],
    AGENCIES[9]: ["Fund mental health outreach programs", "Increase rodent control"],
}


def make_requests() -> pd.DataFrame:
    rows = []
    for board in range(1, 19):
        # Boards 4 and 14 lean toward different agencies so the test has signal.
        weights = np.ones(len(AGENCIES))
        if board == 4:
            weights[[1, 7]] = 3.0
        if board == 14:
            weights[[0, 3]] = 3.0
        weights /= weights.sum()
        carried = []  # requests still open from the previous year keep their code
        for year in (2021, 2022, 2023, 2024):
            n = rng.integers(60, 90) if board in (4, 14) else rng.integers(20, 35)
            new = []
            for i in range(n):
                agency = rng.choice(AGENCIES, p=weights)
                new.append((f"2{board:02d}{year % 100}{i:04d}C", agency, rng.choice(REQUEST_TEXT[agency])))
            this_year = new + carried
            carried = [r for r in this_year if rng.random() < 0.3]
            for code, agency, text in this_year:
                # Each request appears in 1 to 3 of the year's publications,
                # the way open requests are repeated in the real register.
                pubs = ["0216", "0426", "0614"][: rng.integers(1, 4)]
                for pub in pubs:
                    rows.append({
                        "boro": "2",  # Brooklyn in this dataset's coding
                        "board": f"{board:02d}" if rng.random() < 0.5 else str(board),
                        "publication": f"{year}{pub}",
                        "tracking_code": code,
                        "responsible_agency": agency,
                        "request": text,
                    })
    df = pd.DataFrame(rows)
    # Planted problems
    df.loc[df.sample(8, random_state=2).index, "responsible_agency"] = ""
    df.loc[df.sample(3, random_state=3).index, "publication"] = "not a date"
    df.loc[df.sample(4, random_state=8).index, "tracking_code"] = ""
    df.loc[df.sample(5, random_state=9).index, "publication"] = "20270115"  # future date
    return df.sample(frac=1, random_state=4).reset_index(drop=True)


def make_expense(fiscal_year: int = 2023) -> pd.DataFrame:
    agencies = [a.upper() for a in AGENCIES] + ["MISCELLANEOUS", "PENSION CONTRIBUTIONS"]
    base = dict(zip(agencies, rng.uniform(0.3, 30, len(agencies)) * 1e9))
    objects = ["FULL YEAR POSITIONS", "CONTRACTUAL SERVICES", "SUPPLIES AND MATERIALS",
               "FRINGE BENEFITS", "OTHER SERVICES AND CHARGES"]
    rows = []
    # Three publications restate the same budget with small revisions.
    for pub, drift in (("20220114", 0.97), ("20220426", 0.99), ("20220630", 1.0)):
        for agency in agencies:
            shares = rng.dirichlet(np.ones(len(objects)))
            for obj, share in zip(objects, shares):
                amt = base[agency] * share * drift
                rows.append({
                    "publication_date": pub,
                    "fiscal_year": str(fiscal_year),
                    "agency_name": agency,
                    "object_class_name": obj,
                    "adopted_budget_amount": f"{amt * 0.98:.2f}",
                    "current_modified_budget_amount": f"{amt:.2f}",
                    "financial_plan_amount": f"{amt * 1.01:.2f}",
                })
    df = pd.DataFrame(rows)
    df.loc[df.sample(4, random_state=5).index, "current_modified_budget_amount"] = "-125000.00"
    df.loc[df.sample(2, random_state=6).index, "financial_plan_amount"] = ""
    return df


def make_discretionary(fiscal_year: int = 2023) -> pd.DataFrame:
    sources = ["Local", "Youth", "Aging", "Food Pantries", "Cultural After-School Adventure (CASA)",
               "Speaker's Initiative", "Anti-Poverty"]
    orgs = ["Food Bank For New York City", "City University of New York", "Legal Aid Society",
            "Brooklyn Defender Services", "New York Public Library", "Brooklyn Public Library",
            "Bushwick Youth Services", "Flatbush Seniors Center", "Sunset Park Arts Collective"]
    rows = []
    for _ in range(900):
        rows.append({
            "fiscal_year": str(fiscal_year),
            "organization": rng.choice(orgs),
            "source": rng.choice(sources, p=[0.4, 0.15, 0.1, 0.1, 0.1, 0.1, 0.05]),
            "amount": f"{rng.lognormal(10, 1):.2f}",
        })
    df = pd.DataFrame(rows)
    df.loc[df.sample(5, random_state=7).index, "amount"] = ""
    return df


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    make_requests().to_csv(OUT / "requests.csv", index=False)
    make_expense().to_csv(OUT / "expense.csv", index=False)
    make_discretionary().to_csv(OUT / "discretionary.csv", index=False)
    print("Wrote fixtures to", OUT)
