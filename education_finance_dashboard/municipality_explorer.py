from pathlib import Path

from special_school_filter import special_school_filter

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
from year_filter import show_year_filter
from school_type_funding import show_school_type_funding, SPECIAL_SCHOOL_HELP

FUNDING_SOURCE_LABELS = {
    "Iš valstybės biudžeto": "State budget",
    "Iš savivaldybių biudžetų": "Municipal budgets",
    "Iš ES, užsienio valstybių ir tarptautinių organizacijų lėšų": (
        "EU, foreign and international funds"
    ),
    "Iš kitų finansavimo šaltinių": "Other sources",
}


st.title("Municipality Explorer")

st.markdown("""
The national overview showed how school funding varies across municipalities.
A closer look within one municipality raises another question: **how does its
funding reach different types of schools, and how much do individual schools report?**

The charts show where funding comes from and how it differs between school
types and individual schools. Comparing total funding with funding per student
helps put differences between larger and smaller schools in context.
""")

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

funding = load_funding()
year = show_year_filter(funding, incoming.get("year") if incoming else None)

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

    if incoming:
        st.session_state["explorer_include_special"] = incoming["include_special"]
    else:
        st.session_state.setdefault("explorer_include_special", True)
    include_special = special_school_filter(funding, year, "explorer_include_special")

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

        st.markdown(f"""
For **{municipality_names[municipality_code]}** in **{year}**, the figures below
establish the scale of recorded school funding and the schools and students
represented. The sidebar year and special-school setting above update the comparisons
that follow.
        """)

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
        st.markdown(f"""
The schools shown report **€{totals['total_funding']:,.0f}** in funding income.
**Where does this funding come from?**

The bars break that total down by source, with a switch between euro amounts and
percentage shares. This shows the relative contribution of state, municipal and
other funding to schools in this municipality, adding local detail to the
national funding-source picture.
        """)
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

        source_display = st.radio(
            "Show funding sources as", ["Euro amounts", "Percentages"],
            horizontal=True, key="municipality_source_display", persist_state="session",
        )
        show_percent = source_display == "Percentages" and total_funding > 0
        sources["share_value"] = sources["suma"] / total_funding if total_funding > 0 else 0
        sources["display_label"] = sources["share"] if show_percent else sources["suma"].map(lambda value: f"€{value:,.2f}")
        chart = px.bar(
            sources,
            x="share_value" if show_percent else "suma",
            y="source",
            orientation="h",
            text="display_label",
            custom_data=["share", "suma"],
            labels={"suma": "Recorded funding (€)", "source": "Funding source"},
        )
        chart.update_traces(
            textposition="outside",
            cliponaxis=False,
            hovertemplate=(
                "%{y}<br>Funding: €%{customdata[1]:,.2f}<br>"
                "Share of total: %{customdata[0]}<extra></extra>"
            ),
        )
        chart.update_layout(
            height=max(270, 80 + 48 * len(sources)),
            margin=dict(l=8, r=120, t=8, b=40),
            xaxis_tickprefix="€",
            yaxis_title=None,
        )
        chart.update_xaxes(
            title="Share of funding" if show_percent else "Recorded funding (€)",
            tickprefix="" if show_percent else "€",
            tickformat=".0%" if show_percent else ",.0f",
            range=[0, 1.15] if show_percent else None,
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
            .agg(
                average_funding=("funding", "mean"),
                school_count=("mokyklos_kodas", "size"),
            )
            .sort_values("average_funding", ascending=False, kind="stable")
        )
        st.subheader("Funding by School Type")
        st.markdown("""
The previous chart showed where the municipality's school funding came from.
**How does funding differ between school types, and how do their figures
compare with the municipality and Lithuania overall?**

Each bar shows average funding per school or funding per student within that
type. The two benchmark lines show the municipality-wide and national averages
across all school types. Both follow the selected year and special-school
setting. The toggle here is linked to the one at the top of the page.
A higher figure can reflect differences in school size,
educational stages and support needs.
        """)
        show_school_type_funding(
            funding, year, include_special, key="municipality_school_types",
            municipality_code=municipality_code,
            special_scope_key="explorer_include_special",
        )

        st.subheader("School funding comparison")
        st.markdown("""
School-type averages summarise groups, but they can hide differences between
individual schools. **Which schools report the most funding, and does the
ranking change when student numbers are taken into account?**

The two charts compare schools in this municipality by **total recorded
funding** and **funding per student**. A larger school may rank highly by total
funding simply because it serves more students. Comparing the two rankings
shows whether a high total also corresponds to higher funding per student.

The school-type filter narrows the comparison to similar institutions.
Differences can still reflect educational stages and support needs, so these
rankings provide a starting point for closer examination rather than a measure
of school quality or efficiency.
        """)
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
