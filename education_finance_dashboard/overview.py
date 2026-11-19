from pathlib import Path

import streamlit as st
import plotly.express as px
import json
import numpy as np

from education_spending import show_education_spending
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

st.title("Lithuanian Education Finances")

st.markdown("""
    Explore how Lithuania spent its education budget in 2024 and how school
    funding has changed over time.
    """)

show_education_spending()
st.divider()

st.info(
    "The school funding charts below cover schools recorded in the funding dataset, "
    "including regular and special schools. "
    "It does not include universities or other higher education institutions."
)

with st.expander("About this dashboard and its data"):
    st.markdown("""
    ### What do the school funding charts cover?

    This section explores funding allocated to Lithuanian schools
    between 2015 and 2024.

    **Included:**
    - Regular schools
    - Special schools
    - Schools represented in the funding dataset
    - State, municipal, EU/international and other recorded funding sources

    **Not included:**
    - Universities and other higher education institutions
    - Institutions not represented in the source dataset

    ### Important considerations

    - Funding amounts are expressed in nominal euros
      and are not adjusted for inflation.
    - The number of schools represented may change between years.
    - Funding refers to recorded financial allocations,
      not necessarily actual expenditure.
    - Student counts are not summed across funding-source rows,
      because the same school may appear multiple times.

    **Data source:** `finansavimas_mokykla_metai`
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

st.header("1. School Funding Overview")

st.markdown(f"Key funding indicators for Lithuanian schools in **{year}**.")

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

st.header("2. Funding by Source")

st.markdown(f"""
    This chart shows **where school funding came from in {year}**.

    Each segment represents the proportion of total recorded funding
    provided by a particular source.
    """)

funding_sources = (
    selected_funding.assign(suma=selected_funding["suma"].astype("float64"))
    .groupby("finansavimo_saltinis", as_index=False)["suma"]
    .sum()
)

fig = px.pie(
    funding_sources,
    names="finansavimo_saltinis",
    values="suma",
    hole=0.55,
    color_discrete_sequence=px.colors.qualitative.Set2,
)

fig.update_traces(
    textinfo="percent",
    hovertemplate=(
        "%{label}<br>"
        "Funding: €%{value:,.0f}<br>"
        "Share: %{percent}"
        "<extra></extra>"
    ),
)

fig.update_layout(
    height=460,
    margin=dict(l=20, r=20, t=20, b=20),
    legend_title_text="Funding source",
)

st.plotly_chart(fig, use_container_width=True)

st.caption(
    f"Source: `finansavimas_mokykla_metai` | "
    f"Year: {year} | "
    "Measure: Total funding by `finansavimo_saltinis`"
)

with st.expander("How to interpret this chart"):
    st.markdown("""
    **What does it show?**

    The percentage of recorded school funding provided by
    each funding source in the selected year.

    **Included:** All recorded funding sources for schools
    represented in the dataset, including special schools.

    **Excluded:** Universities, other higher education
    institutions, and institutions outside this dataset.

    **Calculation:**

    Funding amounts (`suma`) are summed separately for each
    funding source (`finansavimo_saltinis`).

    Each source's percentage is calculated relative to the
    total recorded funding for the selected year.

    **Important:** This chart shows the origin of funding,
    not how schools spent the money.

    **Source table:** `finansavimas_mokykla_metai`
    """)

st.divider()

# --------------------------------------------------
# FUNDING OVER TIME
# --------------------------------------------------

st.header("3. School Funding Over Time")

st.markdown("""
This chart shows **how total recorded school funding has changed
between 2015 and 2024**.

Unlike the charts above, it displays all available years so that
you can compare funding over time.
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
    f"–{int(funding_by_year['metai'].max())} | "
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

st.caption(
    "Lithuanian Education Finances | "
    "School funding data from `finansavimas_mokykla_metai`"
)

st.divider()

# --------------------------------------------------
# FUNDING BY MUNICIPALITY
# --------------------------------------------------

st.divider()
st.header("4. School Funding by Municipality")

st.markdown("""
Explore how recorded school funding is distributed across
Lithuania's 60 municipalities.

Choose whether to compare **total funding** or **funding per student**.
The map updates automatically when you change the reporting year
at the top of the dashboard.
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
    help="Turn off to exclude schools classified as special.",
    key="overview_include_special",
    persist_state="session",
)
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

st.caption("Click a municipality on the map or choose one below.")
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
with st.expander("About this map — data and methodology"):
    st.markdown("""
    ### What does this map show?

    The geographical distribution of recorded school funding
    across Lithuania's municipalities for the selected year.

    You can switch between two funding metrics and choose
    whether special schools are included.

    ### Funding metrics

    **Total funding**

    The sum of all recorded funding amounts for schools
    in each municipality.

    **Funding per student**

    Total recorded school funding divided by the number
    of students in those schools. Each school's student
    count is included only once, even if it has multiple
    funding-source records.

    ### Special-school filter

    **Include special schools — ON (default)**

    Both regular and special schools are included
    in the calculations.

    **Include special schools — OFF**

    Schools classified as special are excluded.
    Both total funding and student counts are recalculated
    using only the remaining schools.

    This allows comparisons without the influence of
    schools classified as special.

    ### What is included?

    - Schools represented in the funding dataset
    - Regular schools
    - Special schools, when the filter is enabled
    - All recorded funding sources
    - All municipalities with matching data

    ### What is excluded?

    - Universities and other higher education institutions
    - Institutions not represented in the dataset
    - Special schools, when the filter is disabled

    ### How should the colors be interpreted?

    **Total funding:** Uses a logarithmic color scale
    to make differences between municipalities easier to see.

    **Funding per student:** Uses a linear color scale.

    Darker colors represent higher funding values.

    ### Limitations

    - Funding amounts are nominal euros and are not
      adjusted for inflation.
    - Funding per student is not the same as actual
      expenditure per student.
    - Schools with missing student counts can cause
      funding-per-student values to be overstated.
    - Differences between municipalities may reflect
      student populations, school sizes, school types,
      and special education needs.
    - Excluding special schools does not eliminate
      all differences between municipalities.

    **Financial data source:** `finansavimas_mokykla_metai`

    **Geographical data source:** Lithuanian municipality
    boundaries (GeoJSON), matched by municipality code.
    """)
