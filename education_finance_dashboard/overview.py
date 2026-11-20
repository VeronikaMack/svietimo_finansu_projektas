from pathlib import Path

from special_school_comparison import show_special_school_explanation

import streamlit as st
import plotly.express as px
import json
import numpy as np

from education_spending import show_education_spending
from school_type_funding import show_school_type_funding
from municipality_funding import (
    load_funding,
    municipality_funding_records,
    summarize_municipality_funding,
)

# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------

funding = load_funding()

# --------------------------------------------------
# HEADER AND INTRODUCTION
# --------------------------------------------------

st.title("Where does Lithuania's education money go?")

st.markdown("""
Education budgets fund the people, services, buildings, and equipment that
schools need. Understanding these costs helps us interpret how funding is
distributed and why amounts differ between schools.

This dashboard explores three questions.

1. What is education money spent on?
2. How has recorded school funding changed over time?
3. How does funding differ between municipalities and schools?

**Data coverage**

Education expenditure for 2024 and recorded school funding for 2015-2024.
""")

show_education_spending()
st.divider()

st.header("From the education budget to school funding")

st.markdown("""
The expenditure breakdown shows the range of activities supported by the
education budget. The focus now narrows to **general education (grades 1-12)**
and the funding recorded for schools, including regular and special schools.

The first question is **how school funding has changed over time**.
This provides context before a closer look at a single year's funding sources
and differences across municipalities.

These figures come from a separate school funding dataset. They describe
reported funding income rather than a breakdown of spending, so the totals are
not directly comparable with the expenditure breakdown above.
""")

with st.expander("School groups and comparison notes"):
    st.markdown("""
    **Regular and special schools**

    Here, regular schools means the schools not flagged as special in the
    dataset. It does not mean that these schools have no pupils with special
    educational needs.

    The special-school group includes special schools, children's socialisation
    centres, and sanatorium or hospital schools, following the source classification.
    These institutions serve different educational and support needs, so their
    funding per student should be interpreted in that context. The later
    comparisons include an option to exclude this group.

    **Reading the comparisons**

    Amounts are in nominal euros, without adjustment for inflation. The schools
    represented can change between years.

    Source table: `finansavimas_mokykla_metai`.
    """)

st.divider()

# --------------------------------------------------
# FUNDING OVER TIME
# --------------------------------------------------

st.header("School Funding Over Time")

st.markdown("""
The expenditure breakdown provides a snapshot of 2024. For schools,
a longer view helps put that snapshot in context: **how has recorded school
funding changed over time?**

The line below shows total reported funding income for general education
schools in each year from **2015 to 2024**. Each point combines all recorded
funding sources for that year, showing the scale and pace of change.

These are the euro amounts reported in each year, without adjustment for
rising prices. A higher total therefore does not necessarily mean that schools
could afford proportionately more staff, equipment or services.
""")

funding_by_year = (
    funding.assign(suma=funding["suma"].astype("float64"))
    .groupby("metai", as_index=False)["suma"]
    .sum()
    .sort_values("metai")
)

fig_trend = px.line(
    funding_by_year,
    x="metai",
    y="suma",
    markers=True,
    labels={
        "metai": "Year",
        "suma": "Total Funding (€)",
    },
)

fig_trend.update_traces(
    line=dict(width=3),
    marker=dict(size=8),
    hovertemplate=("Year: %{x}<br>" "Total funding: €%{y:,.0f}" "<extra></extra>"),
)

fig_trend.update_layout(
    height=450,
    margin=dict(l=20, r=20, t=20, b=20),
    xaxis=dict(
        tickmode="linear",
        dtick=1,
    ),
    yaxis=dict(
        tickprefix="€",
        tickformat=".1f",
        tickvals=[0, 500e6, 1e9, 1.5e9, 2e9],
        ticktext=["€0", "€500M", "€1B", "€1.5B", "€2B"],
    ),
)

st.plotly_chart(fig_trend, use_container_width=True)

st.caption(
    "Source: `finansavimas_mokykla_metai` | "
    f"Period: {int(funding_by_year['metai'].min())}"
    f"-{int(funding_by_year['metai'].max())} | "
    "Measure: Annual SUM(suma)"
)

with st.expander("How to interpret this chart"):
    st.markdown("""
    **What does it show?**

    The total annual funding recorded for Lithuanian schools.

    Each point represents the sum of all recorded funding
    sources for that calendar year.

    **Included:**
    - Regular and special schools represented in the dataset
    - All recorded funding sources
    - All municipalities represented in the dataset

    **Excluded:**
    - Universities and other higher education institutions
    - Institutions outside the dataset

    **Calculation:**

    Funding amounts (`suma`) are grouped by calendar year
    (`metai`) and summed.

    **Limitations:**

    - Values are in nominal euros, without inflation adjustment.
    - Changes in the number of schools covered can influence
      the total funding trend.
    - An increase in total funding does not necessarily mean
      an increase in funding per school or per student.

    **Source table:** `finansavimas_mokykla_metai`
    """)

st.divider()

# --------------------------------------------------
# YEAR FILTER
# --------------------------------------------------

years = sorted(funding["metai"].dropna().unique().tolist())

year = st.selectbox(
    "Select reporting year",
    options=years,
    index=len(years) - 1,
    key="overview_year",
    persist_state="session",
)

selected_funding = funding[funding["metai"] == year]

# --------------------------------------------------
# OVERVIEW METRICS
# --------------------------------------------------

st.header("School Funding Overview")

st.markdown(f"""
The trend shows how the overall total has changed. A closer look at **{year}**
now shows the funding recorded that year and the number of schools and
municipalities represented. The reporting year selector above updates this
overview and the single-year comparisons that follow.
""")

col1, col2, col3 = st.columns(3, gap="large")

with col1:
    st.metric(
        "Total Funding",
        f"€{selected_funding['suma'].astype('float64').sum():,.0f}",
    )

with col2:
    st.metric(
        "Schools",
        f"{selected_funding['mokyklos_kodas'].nunique():,}",
    )

with col3:
    st.metric(
        "Municipalities",
        f"{selected_funding['savivaldybes_kodas'].nunique():,}",
    )

st.caption(
    f"Source: `finansavimas_mokykla_metai` | "
    f"Year: {year} | "
    "Scope: Schools included in the dataset, including special schools"
)

st.divider()

# --------------------------------------------------
# FUNDING BY SOURCE
# --------------------------------------------------

st.header("Funding by Source")

st.markdown(f"""
The overview above puts total recorded school funding in **{year}** at
**€{selected_funding['suma'].astype('float64').sum():,.0f}**. Where did that funding come from?

The next chart breaks this total down by source - state budgets, municipal
budgets, EU and international funds, and other sources. The bars show how much
each contributed, revealing which sources schools relied on most that year.
""")

funding_sources = (
    selected_funding.assign(suma=selected_funding["suma"].astype("float64"))
    .groupby("finansavimo_saltinis", as_index=False)["suma"]
    .sum()
    .sort_values("suma", ascending=False, kind="stable")
)

fig = px.bar(
    funding_sources,
    x="suma",
    y="finansavimo_saltinis",
    orientation="h",
    text=[f"€{amount:,.0f}" for amount in funding_sources["suma"]],
    labels={
        "suma": "Recorded funding (€)",
        "finansavimo_saltinis": "Funding source",
    },
    color_discrete_sequence=["#2563eb"],
)

fig.update_traces(
    textposition="outside",
    cliponaxis=False,
    hovertemplate="%{y}<br>Funding: €%{x:,.2f}<extra></extra>",
)

fig.update_layout(
    height=350,
    margin=dict(l=20, r=120, t=20, b=40),
)
fig.update_xaxes(tickprefix="€", tickformat="", exponentformat="B")
fig.update_yaxes(
    categoryorder="array",
    categoryarray=funding_sources["finansavimo_saltinis"].tolist(),
    autorange="reversed",
    automargin=True,
    title=None,
)

st.plotly_chart(fig, width="stretch")

st.caption(
    f"Source: `finansavimas_mokykla_metai` | "
    f"Year: {year} | "
    "Measure: Total funding by `finansavimo_saltinis`"
)

with st.expander("How to interpret this chart"):
    st.markdown("""
    **What does it show?**

    The total funding income reported by schools for each funding source
    in the selected year, ordered from largest to smallest.

    **Included:** All recorded funding sources for schools
    represented in the dataset, including special schools.

    **Excluded:** Universities, other higher education
    institutions, and institutions outside this dataset.

    **Calculation:**

    Funding amounts (`suma`) are summed separately for each
    funding source (`finansavimo_saltinis`).

    Bar labels show funding amounts rounded to whole euros.

    **Important:** This chart shows the origin of funding,
    not how schools spent the money.

    **Source table:** `finansavimas_mokykla_metai`
    """)

st.divider()

# --------------------------------------------------
# FUNDING BY MUNICIPALITY
# --------------------------------------------------

st.header("School Funding by School Type")
st.markdown("""
The previous chart showed where school funding came from. **How does funding
differ between school types across Lithuania?**

The bars compare average funding per school or funding per student within each
type. The national benchmark shows the overall figure across all school types,
placing each group's amount above or below the national average. Differences
can reflect school sizes, educational stages and support needs.
""")
type_include_special = st.toggle(
    "Include special schools", value=True,
    key="overview_type_include_special", persist_state="session",
)
show_school_type_funding(
    funding, year, type_include_special, key="overview_school_types"
)
st.divider()

st.header("School Funding by Municipality")

st.markdown(f"""
National school-type averages reveal differences between groups. **How does
the picture vary across municipalities?**

The map shows the funding reported by schools in each municipality in
**{year}**. Total funding highlights where the largest amounts are concentrated.
Larger totals can also reflect larger student populations, so **does the
picture change when funding is compared per student?**

The metric selector switches between these two views. Both follow the selected
reporting year.
""")

# --------------------------------------------------
# METRIC SELECTOR
# --------------------------------------------------

metric = st.radio(
    "Select funding metric",
    ["Total funding", "Funding per student"],
    horizontal=True,
    key="overview_map_metric",
    persist_state="session",
)
include_special = st.toggle(
    "Include special schools",
    value=True,
    help="Exclude schools flagged as special to compare the remaining schools. "
    "See the comparison below for funding per student.",
    key="overview_include_special",
    persist_state="session",
)
show_special_school_explanation(funding, year)
# --------------------------------------------------
# LOAD MUNICIPALITY BOUNDARIES
# --------------------------------------------------

with open(
    Path(__file__).resolve().parents[1] / "assets" / "municipality_boundaries.geojson",
    encoding="utf-8",
) as f:
    geojson = json.load(f)

map_funding = municipality_funding_records(selected_funding, include_special)
municipality_data = summarize_municipality_funding(map_funding)

# --------------------------------------------------
# MATCH MUNICIPALITY CODES AND NAMES
# --------------------------------------------------

municipality_data["code"] = (
    municipality_data["savivaldybes_kodas"].astype(int).astype(str)
)

municipality_names = {
    feature["properties"]["kodas"]: feature["properties"]["sav_pav"]
    for feature in geojson["features"]
}

municipality_data["municipality"] = municipality_data["code"].map(municipality_names)


def open_municipality(code):
    st.session_state["municipality_explorer_context"] = {
        "code": code,
        "year": year,
        "include_special": include_special,
    }
    st.switch_page("municipality_explorer.py")


def capture_map_selection():
    points = st.session_state["overview_funding_map"]["selection"]["points"]
    if len(points) == 1 and points[0].get("location") is not None:
        st.session_state["pending_municipality"] = str(points[0]["location"])


clicked_code = st.session_state.pop("pending_municipality", None)
if clicked_code in municipality_names:
    open_municipality(clicked_code)

# --------------------------------------------------
# PREPARE MAP COLORS
# --------------------------------------------------

# Logarithmic transformation makes differences between
# smaller municipalities more visible.

municipality_data["funding_log"] = np.log10(
    municipality_data["total_funding"].where(municipality_data["total_funding"] > 0)
)

if metric == "Total funding":
    color_column = "funding_log"
    color_label = "Total funding (€)"

    colorbar_settings = dict(
        title=color_label,
        tickvals=[6, 7, 8, 9],
        ticktext=["€1M", "€10M", "€100M", "€1B"],
    )

else:
    color_column = "funding_per_student"
    color_label = "Funding per student (€)"

    colorbar_settings = dict(title=color_label, tickprefix="€", tickformat=",.0f")

# --------------------------------------------------
# CREATE INTERACTIVE MAP
# --------------------------------------------------

fig_map = px.choropleth_map(
    municipality_data,
    geojson=geojson,
    locations="code",
    featureidkey="properties.kodas",
    color=color_column,
    hover_name="municipality",
    hover_data={
        "code": False,
        "funding_log": False,
        "total_funding": ":,.0f",
        "total_students": ":,.0f",
        "funding_per_student": ":,.2f",
        "missing_students": True,
    },
    color_continuous_scale="YlOrRd",
    labels={
        "total_funding": "Total funding (€)",
        "total_students": "Students",
        "funding_per_student": "Funding per student (€)",
        "missing_students": "Schools missing student counts",
    },
    center={"lat": 55.17, "lon": 23.88},
    zoom=6,
    opacity=0.85,
    map_style="carto-positron",
)

fig_map.update_layout(
    height=650,
    margin=dict(l=0, r=0, t=0, b=0),
    coloraxis_colorbar=colorbar_settings,
    clickmode="event+select",
)

st.caption(
    "Clicking a municipality on the map opens its detailed overview. "
    "The dropdown below provides another way to select a municipality and open its overview."
)
st.plotly_chart(
    fig_map,
    use_container_width=True,
    key="overview_funding_map",
    on_select=capture_map_selection,
    selection_mode="points",
)

municipality_code = st.selectbox(
    "Choose a municipality",
    options=sorted(municipality_names, key=municipality_names.get),
    format_func=municipality_names.__getitem__,
    index=None,
    key="overview_municipality",
)
if st.button("Open Explorer", disabled=municipality_code is None):
    open_municipality(municipality_code)

# --------------------------------------------------
# SOURCE INFORMATION
# --------------------------------------------------

school_scope = (
    "Regular and special schools" if include_special else "Excluding special schools"
)

st.caption(
    f"Source: `finansavimas_mokykla_metai` | "
    f"Year: {year} | "
    f"Scope: {school_scope} | "
    "Boundaries: Lithuanian municipality GeoJSON"
)

# --------------------------------------------------
# DATA QUALITY WARNING
# --------------------------------------------------

missing_municipalities = (municipality_data["missing_students"] > 0).sum()

if metric == "Funding per student" and missing_municipalities > 0:
    st.warning(
        f"{missing_municipalities} municipalities have at least "
        "one school with missing student counts. Their funding "
        "per student may be overstated."
    )

# --------------------------------------------------
# METHODOLOGY AND EXPLANATIONS
# --------------------------------------------------
with st.expander("About this map"):
    st.markdown("""
    - **Total funding** adds up recorded school funding in each municipality.
    - **Funding per student** divides that total by the student count for the
      same schools. The special-school filter updates both figures.
    - **Darker colours mean higher values.** Total funding uses a logarithmic
      scale; funding per student uses a linear scale.

    Differences can reflect school sizes, school types and support needs.
    Higher funding per student does not by itself indicate better outcomes
    or inefficient spending.

    Source table: `finansavimas_mokykla_metai`.
    """)
