"""Annual school funding comparisons with consistent student denominators."""

import math
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
import plotly.graph_objects as go
from special_school_filter import special_school_filter

from school_type_funding import prepare_type_schools, summarize_types, TYPE_LABELS, SPECIAL_SCHOOL_HELP

SOURCE_LABELS = {
    "Iš valstybės biudžeto": "State budget",
    "Iš savivaldybių biudžetų": "Municipal budgets",
    "Iš ES, užsienio valstybių ir tarptautinių organizacijų lėšų": "EU, foreign and international funds",
    "Iš kitų finansavimo šaltinių": "Other funding sources",
}


@st.cache_data
def annual_school_comparisons(funding, include_special):
    annual, types = [], []
    for year in sorted(funding["metai"].dropna().unique()):
        schools = prepare_type_schools(funding, year, include_special)
        _, per_student, excluded = summarize_types(schools, "Funding per student")
        annual.append(dict(year=int(year), per_student=per_student, excluded=excluded))
        for metric in ("Average funding per school", "Funding per student"):
            groups, _, _ = summarize_types(schools, metric)
            for row in groups.itertuples():
                types.append(dict(
                    year=int(year), school_type=TYPE_LABELS.get(row.mokyklos_tipas, row.mokyklos_tipas),
                    metric=metric, amount=row.amount, funding=row.funding,
                ))
    return pd.DataFrame(annual), pd.DataFrame(types)


SOURCE_COLORS = {
    "State budget": "#2563eb",
    "Municipal budgets": "#059669",
    "EU, foreign and international funds": "#9333ea",
    "Other funding sources": "#d97706",
}


def compact_euros(value):
    absolute = abs(value)
    if absolute >= 1e9:
        return f"€{value / 1e9:g}B"
    if absolute >= 1e6:
        return f"€{value / 1e6:g}M"
    return f"€{value:,.0f}"


def style_annual_chart(figure, year, y_title):
    values = [float(v) for trace in figure.data for v in trace.y if v is not None and np.isfinite(v)]
    low, high = min([0, *values]), max([1, *values])
    # Include stack totals when setting the scale.
    if figure.layout.barmode in ("stack", "relative"):
        stacked = {}
        for trace in figure.data:
            if trace.type == "bar":
                for x, y in zip(trace.x, trace.y):
                    if y is not None and np.isfinite(y):
                        stacked[x] = stacked.get(x, 0) + max(float(y), 0)
        high = max([high, *stacked.values()])
    raw_step = (high - low) / 8
    magnitude = 10 ** math.floor(math.log10(raw_step))
    step = next(value * magnitude for value in (1, 2, 2.5, 5, 10) if value * magnitude >= raw_step)
    ticks = np.arange(math.floor(low / step) * step, math.ceil(high * 1.12 / step) * step + step / 2, step).tolist()
    figure.update_layout(
        height=480, margin=dict(l=20, r=25, t=65, b=25),
        legend=dict(orientation="h", yanchor="bottom", y=1.04), bargap=0.22,
    )
    figure.update_xaxes(dtick=1, tickformat="d", title="Year")
    figure.update_yaxes(
        title=y_title, tickmode="array", tickvals=ticks,
        ticktext=[compact_euros(value) for value in ticks],
        range=[low * 1.12 if low < 0 else 0, high * 1.22],
    )
    figure.add_vrect(
        x0=int(year)-0.45, x1=int(year)+0.45, fillcolor="rgba(217,119,6,0.10)",
        line_width=0, layer="below",
    )
    return figure


def funding_source_history(records):
    data = records.assign(suma=records["suma"].astype(float))
    grouped = data.groupby(["metai", "finansavimo_saltinis"], dropna=False)["suma"].sum(min_count=1)
    result = grouped.unstack("finansavimo_saltinis", fill_value=0).sort_index()
    result.columns = [SOURCE_LABELS.get(source, str(source)) for source in result.columns]
    return result.reindex(columns=[name for name in SOURCE_COLORS if name in result.columns] + [name for name in result.columns if name not in SOURCE_COLORS])


def stacked_funding_chart(sources, year):
    figure = go.Figure()
    for source in sources:
        figure.add_bar(
            x=sources.index.tolist(), y=sources[source].tolist(), name=source,
            marker_color=SOURCE_COLORS.get(source, "#64748b"),
            hovertemplate="Year: %{x}<br>€%{y:,.2f}<extra>%{fullData.name}</extra>",
        )
    figure.update_layout(barmode="relative")
    style_annual_chart(figure, year, "Funding income (€)")
    return figure


def show_source_details(sources, key):
    with st.expander("Exact amounts by funding source"):
        table = sources.copy()
        table["Total funding income"] = table.sum(axis=1, min_count=1)
        table.index.name = "Year"
        st.dataframe(table.map(lambda value: f"€{value:,.2f}" if pd.notna(value) else "Unavailable"), width="stretch", key=key)


def show_overview_trends(funding, year):
    st.header("School Funding Over Time")
    st.markdown("""
The expenditure breakdown provides a snapshot of 2024. **How has school
funding changed over time, and where did it come from?** Each annual bar is
stacked by funding source, with colours separating each source's contribution.
Exact amounts are available on hover and in the table below.

Amounts are not adjusted for rising prices. Small contributions remain to
scale; their exact amounts are available on hover and in the table below.
    """)
    include_special = special_school_filter(funding, year, "overview_history_include_special")
    scope = funding if include_special else funding.loc[funding["ar_specialioji_mokykla"] == False]
    sources = funding_source_history(scope)
    st.plotly_chart(stacked_funding_chart(sources, year), width="stretch", key="overview_annual_total")
    show_source_details(sources, "overview_source_details")

    st.subheader("School Types Over Time")
    st.markdown("""
The national average can hide different trends between school types.
**Have those groups changed at the same pace?** Each line follows one school
type, using average funding per school or average funding per student. Exact values
are shown on hover. Amounts are not adjusted for inflation.
    """)
    type_special = special_school_filter(funding, year, "overview_type_history_special")
    annual, types = annual_school_comparisons(funding, type_special)
    metric = st.radio(
        "School-type trend metric", ["Average funding per school", "Funding per student"],
        horizontal=True, key="overview_type_trend_metric", persist_state="session",
        format_func=lambda value: "Average funding per student" if value == "Funding per student" else value,
    )
    selected = types.loc[types["metric"] == metric]
    by_type = px.line(
        selected.sort_values(["school_type", "year"]), x="year", y="amount", color="school_type", markers=True,
        labels={"school_type": "School type"},
        color_discrete_sequence=["#2563eb", "#059669", "#d97706", "#9333ea"],
    )
    by_type.update_traces(
        line_width=3, marker_size=7,
        hovertemplate="Year: %{x}<br>€%{y:,.2f}<extra>%{fullData.name}</extra>",
    )
    display_metric = "Average funding per student" if metric == "Funding per student" else metric
    style_annual_chart(by_type, year, f"{display_metric} (€)")
    by_type.update_layout(height=460, hovermode="x unified")
    st.plotly_chart(by_type, width="stretch", key="overview_annual_types")
    st.caption("Each historical chart has its own special-school filter. The shaded band marks the sidebar year. Source table: `finansavimas_mokykla_metai`.")
    if annual["excluded"].gt(0).any():
        st.caption("Schools with missing or non-positive student counts are omitted from per-student calculations. School coverage can change between years.")
