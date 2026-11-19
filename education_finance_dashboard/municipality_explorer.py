from pathlib import Path

import json

import pandas as pd
import plotly.express as px
import streamlit as st

from municipality_funding import (
    load_funding,
    municipality_funding_records,
    school_funding_totals,
    summarize_school_funding,
)
from school_funding_charts import show_school_funding_charts

FUNDING_SOURCE_LABELS = {
    "Iš valstybės biudžeto": "State budget",
    "Iš savivaldybių biudžetų": "Municipal budgets",
    "Iš ES, užsienio valstybių ir tarptautinių organizacijų lėšų": (
        "EU, foreign and international funds"
    ),
    "Iš kitų finansavimo šaltinių": "Other sources",
}


st.title("Municipality Explorer")

with open(
    Path(__file__).resolve().parents[1] / "assets" / "municipality_boundaries.geojson",
    encoding="utf-8",
) as file:
    boundaries = json.load(file)

municipality_names = {
    feature["properties"]["kodas"]: feature["properties"]["sav_pav"]
    for feature in boundaries["features"]
}
municipality_codes = sorted(municipality_names, key=municipality_names.get)

# Apply the Overview settings once per handoff so local edits survive reruns.
incoming = st.session_state.pop("municipality_explorer_context", None)
if incoming and incoming["code"] in municipality_names:
    st.session_state["explorer_municipality"] = incoming["code"]

municipality_code = st.selectbox(
    "Choose a municipality",
    options=municipality_codes,
    format_func=municipality_names.__getitem__,
    index=None,
    key="explorer_municipality",
    persist_state="session",
)

if municipality_code is not None:
    st.header(municipality_names[municipality_code])

    funding = load_funding()
    years = sorted(funding["metai"].dropna().unique().tolist())
    latest_year = years[-1] if years else None
    if incoming:
        incoming_year = incoming["year"]
        st.session_state["explorer_year"] = (
            incoming_year if incoming_year in years else latest_year
        )
        st.session_state["explorer_include_special"] = incoming["include_special"]
    else:
        st.session_state.setdefault("explorer_year", latest_year)
        st.session_state.setdefault("explorer_include_special", True)

    year_column, schools_column = st.columns(2, vertical_alignment="bottom")
    with year_column:
        year = st.selectbox(
            "Reporting year",
            options=years,
            index=None,
            key="explorer_year",
            persist_state="session",
        )
    with schools_column:
        include_special = st.toggle(
            "Include special schools",
            key="explorer_include_special",
            persist_state="session",
        )

    selected_funding = funding[
        (funding["metai"] == year)
        & (funding["savivaldybes_kodas"] == int(municipality_code))
    ]
    records = municipality_funding_records(selected_funding, include_special)
    schools = school_funding_totals(records)
    summary = summarize_school_funding(schools)

    if summary.empty:
        st.info(
            "No school funding records match this municipality and filter selection."
        )
    else:
        totals = summary.iloc[0]
        funding_per_student = totals["funding_per_student"]
        missing_counts = int(totals["missing_students"])

        total, school_count, students, per_student = st.columns(4)
        total.metric("Total recorded funding", f"€{totals['total_funding']:,.0f}")
        school_count.metric("Schools represented", f"{totals['school_count']:,.0f}")
        students.metric(
            "Students with recorded counts", f"{totals['total_students']:,.0f}"
        )
        per_student.metric(
            "Funding per student",
            f"€{funding_per_student:,.2f}" if pd.notna(funding_per_student) else "—",
        )
        st.caption("Source: `finansavimas_mokykla_metai`")

        if missing_counts:
            st.warning(
                f"Student counts are missing for {missing_counts:,} of the schools shown. "
                "Funding per student may be overstated."
            )

        st.subheader("Funding by Source")
        sources = (
            records.groupby("finansavimo_saltinis", as_index=False, dropna=False)[
                "suma"
            ]
            .sum()
            .sort_values("suma", ascending=False, kind="stable")
        )
        source_names = sources["finansavimo_saltinis"]
        sources["source"] = (
            source_names.map(FUNDING_SOURCE_LABELS)
            .fillna(source_names)
            .fillna("Unspecified source")
        )
        total_funding = totals["total_funding"]
        sources["share"] = (
            (sources["suma"] / total_funding).map("{:.1%}".format)
            if total_funding
            else "—"
        )

        chart = px.bar(
            sources,
            x="suma",
            y="source",
            orientation="h",
            text="share",
            custom_data=["share"],
            labels={"suma": "Recorded funding (€)", "source": "Funding source"},
        )
        chart.update_traces(
            textposition="outside",
            cliponaxis=False,
            hovertemplate=(
                "%{y}<br>Funding: €%{x:,.0f}<br>"
                "Share of total: %{customdata[0]}<extra></extra>"
            ),
        )
        chart.update_layout(
            height=max(270, 80 + 48 * len(sources)),
            margin=dict(l=8, r=48, t=8, b=40),
            xaxis_tickprefix="€",
            yaxis_title=None,
        )
        chart.update_yaxes(
            categoryorder="array",
            categoryarray=sources["source"].tolist(),
            autorange="reversed",
        )
        st.plotly_chart(chart, width="stretch")
        st.caption(
            "Source table `finansavimas_mokykla_metai` · Field `finansavimo_saltinis`"
        )

        school_details = records.groupby("mokyklos_kodas")[
            ["mokykla", "mokyklos_tipas"]
        ].first()
        schools = schools.join(school_details, on="mokyklos_kodas")
        schools["mokyklos_tipas"] = (
            schools["mokyklos_tipas"]
            .str.strip()
            .replace("", pd.NA)
            .fillna("Unspecified type")
        )
        types = (
            schools.groupby("mokyklos_tipas", as_index=False)
            .agg(funding=("funding", "sum"), school_count=("mokyklos_kodas", "size"))
            .sort_values("funding", ascending=False, kind="stable")
        )
        school_counts = types["school_count"].map(
            lambda count: f"{count:,} {'school' if count == 1 else 'schools'}"
        )
        types["type_label"] = types["mokyklos_tipas"] + " · " + school_counts

        st.subheader("Funding by School Type")
        if (types["funding"] == 0).all():
            st.info(
                "Total recorded funding is €0 for each school type in this selection."
            )
            st.caption(" | ".join(types["type_label"]))
        else:
            if (types["funding"] >= 0).all():
                type_chart = px.pie(
                    types,
                    names="type_label",
                    values="funding",
                    hole=0.55,
                    color_discrete_sequence=px.colors.qualitative.Set2,
                )
                type_chart.update_traces(
                    textinfo="percent",
                    hovertemplate="%{label}<br>Funding: €%{value:,.0f}<br>Share: %{percent}<extra></extra>",
                )
                type_chart.update_layout(legend=dict(orientation="h"))
            else:
                type_chart = px.bar(
                    types,
                    x="funding",
                    y="type_label",
                    orientation="h",
                    labels={"funding": "Recorded funding (€)", "type_label": ""},
                )
                type_chart.update_yaxes(autorange="reversed")
                type_chart.update_xaxes(tickprefix="€")
            type_chart.update_layout(height=350, margin=dict(l=8, r=8, t=8, b=8))
            st.plotly_chart(type_chart, width="stretch")
        st.caption("Source table `finansavimas_mokykla_metai` · Field `mokyklos_tipas`")

        st.subheader("School funding comparison")
        selected_types = st.multiselect(
            "School types to compare",
            options=sorted(types["mokyklos_tipas"]),
            placeholder="All school types",
            key="explorer_school_types",
            persist_state="session",
        )
        st.caption(
            "Both charts rank the schools within the selected types. Clear the filter to compare all types."
        )
        if selected_types:
            schools = schools[schools["mokyklos_tipas"].isin(selected_types)]
        st.caption("Select a school name in either chart to open School Explorer.")
        open_school = show_school_funding_charts(schools)
        if (
            isinstance(open_school, int)
            and (schools["mokyklos_kodas"] == open_school).any()
        ):
            st.session_state["school_explorer_context"] = {
                "code": open_school,
                "year": year,
            }
            st.switch_page("school_explorer.py")
        st.caption("Source table `finansavimas_mokykla_metai`")
