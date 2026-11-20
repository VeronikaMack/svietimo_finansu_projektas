"""Comparable school-type funding metrics and overall benchmarks."""

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from municipality_funding import municipality_funding_records, school_funding_totals

TYPE_LABELS = {
    "Gimnazija": "Gymnasium",
    "Progimnazija": "Progymnasium",
    "Pagrindinė mokykla": "Basic school",
    "Pradinė mokykla": "Primary school",
}
METRICS = ["Average funding per school", "Funding per student"]


def prepare_type_schools(funding, year, include_special):
    records = municipality_funding_records(funding.loc[funding["metai"] == year], include_special)
    schools = school_funding_totals(records)
    types = records.groupby(["savivaldybes_kodas", "mokyklos_kodas"])["mokyklos_tipas"].first()
    schools = schools.join(types, on=["savivaldybes_kodas", "mokyklos_kodas"])
    schools["mokyklos_tipas"] = (
        schools["mokyklos_tipas"].str.strip().replace("", pd.NA).fillna("Unspecified type")
    )
    return schools


def summarize_types(schools, metric):
    eligible = schools.loc[np.isfinite(schools["funding"])].copy()
    if metric == "Funding per student":
        eligible = eligible.loc[np.isfinite(eligible["students"]) & (eligible["students"] > 0)]
    groups = eligible.groupby("mokyklos_tipas", as_index=False).agg(
        funding=("funding", "sum"),
        students=("students", "sum"),
        school_count=("mokyklos_kodas", "size"),
    )
    denominator = "students" if metric == "Funding per student" else "school_count"
    groups["amount"] = groups["funding"] / groups[denominator]
    overall_denominator = eligible["students"].sum() if metric == "Funding per student" else len(eligible)
    benchmark = eligible["funding"].sum() / overall_denominator if overall_denominator else None
    return groups.sort_values("amount", ascending=False, kind="stable"), benchmark, len(schools) - len(eligible)


def show_school_type_funding(
    funding, year, include_special, key, municipality_code=None, special_scope_key=None
):
    if special_scope_key is not None:
        metric_column, special_column = st.columns([3, 1], vertical_alignment="bottom")
    else:
        metric_column = st.container()
    with metric_column:
        metric = st.radio(
            "School-type funding metric", METRICS, horizontal=True,
            key=f"{key}_metric", persist_state="session",
        )
    if special_scope_key is not None:
        toggle_key = f"{key}_include_special"
        st.session_state[toggle_key] = include_special

        def sync_special_school_scope():
            st.session_state[special_scope_key] = st.session_state[toggle_key]

        with special_column:
            include_special = st.toggle(
                "Include special schools", key=toggle_key,
                on_change=sync_special_school_scope,
                help="Linked to the special-school setting at the top of this page.",
                persist_state="session",
            )
    national_schools = prepare_type_schools(funding, year, include_special)
    schools = national_schools if municipality_code is None else national_schools.loc[
        national_schools["savivaldybes_kodas"] == int(municipality_code)
    ]
    groups, local_average, excluded = summarize_types(schools, metric)
    _, national_average, _ = summarize_types(national_schools, metric)
    if groups.empty:
        st.info("No comparable school funding figures are available for these settings.")
        return
    names = groups["mokyklos_tipas"].replace(TYPE_LABELS)
    groups["label"] = names + groups["school_count"].map(
        lambda count: f" · {count:,} {'school' if count == 1 else 'schools'}"
    )
    figure = px.bar(
        groups, x="amount", y="label", orientation="h",
        text=[f"€{value:,.0f}" for value in groups["amount"]],
        labels={"amount": f"{metric} (€)", "label": ""},
        color_discrete_sequence=["#2563eb"],
    )
    figure.update_traces(
        textposition="outside", cliponaxis=False,
        hovertemplate="%{y}<br>" + metric + ": €%{x:,.2f}<extra></extra>",
    )
    benchmarks = [("National average", national_average, "#d97706", "dash")]
    if municipality_code is not None:
        benchmarks.insert(0, ("Municipality average", local_average, "#059669", "dot"))
    limits = [0, *groups["amount"].tolist()]
    for name, value, color, dash in benchmarks:
        if value is not None and np.isfinite(value):
            limits.append(value)
            figure.add_vline(
                x=float(value), line_color=color, line_dash=dash, line_width=2,
                name=f"{name} - €{value:,.0f}", showlegend=True,
            )
    low, high = min(limits), max(limits)
    padding = (high - low) * 0.15 or 1
    figure.update_xaxes(tickprefix="€", tickformat=",.0f", range=[low - padding if low < 0 else 0, high + padding])
    figure.update_yaxes(
        categoryorder="array", categoryarray=groups["label"].tolist(),
        autorange="reversed", automargin=True,
    )
    figure.update_layout(
        height=max(350, 160 + 48 * len(groups)),
        margin=dict(l=8, r=65, t=15, b=45),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    st.plotly_chart(figure, width="stretch", key=f"{key}_chart")
    scope = "including special schools" if include_special else "excluding special schools"
    calculation = (
        "Funding per student is total funding divided by total students within each group, "
        "rather than an average of individual school rates. Only schools with positive, "
        "recorded student counts are included in both funding and student totals."
        if metric == "Funding per student" else
        "Average funding per school is total funding divided by the number of schools in each group."
    )
    st.caption(f"{calculation} Benchmarks combine all school types using the same calculation. Year: {year}, {scope}.")
    if excluded:
        st.caption(f"{excluded:,} schools in this selection lack the figures needed for this comparison and are omitted.")
    st.caption("Source table: `finansavimas_mokykla_metai`.")
