from pathlib import Path

import duckdb
import numpy as np
import streamlit as st


@st.cache_data
def load_funding():
    with duckdb.connect(
        Path(__file__).resolve().parents[1] / "data" / "local" / "lithuanian_education_warehouse.duckdb",
        read_only=True,
    ) as conn:
        return conn.sql("""
            SELECT *
            FROM finansavimas_mokykla_metai
        """).df()


def municipality_funding_records(funding, include_special):
    if not include_special:
        funding = funding[funding["ar_specialioji_mokykla"] == False]
    funding = funding.dropna(subset=["savivaldybes_kodas", "mokyklos_kodas"])
    return funding.assign(suma=funding["suma"].astype("float64"))


def summarize_municipality_funding(records, include_special=None):
    # Earlier Overview pages pass the school filter here with unfiltered records.
    if include_special is not None:
        records = municipality_funding_records(records, include_special)

    return summarize_school_funding(school_funding_totals(records))


def school_funding_totals(records):
    # Sum all funding sources and use the first available student count per school.
    return records.groupby(
        ["savivaldybes_kodas", "mokyklos_kodas"], as_index=False
    ).agg(funding=("suma", "sum"), students=("mokiniu_skaicius", "first"))


def summarize_school_funding(schools):
    summary = schools.groupby("savivaldybes_kodas", as_index=False).agg(
        total_funding=("funding", "sum"),
        school_count=("funding", "size"),
        total_students=("students", "sum"),
        missing_students=("students", lambda counts: counts.isna().sum()),
    )
    summary["funding_per_student"] = summary["total_funding"] / summary[
        "total_students"
    ].replace(0, np.nan)
    return summary
