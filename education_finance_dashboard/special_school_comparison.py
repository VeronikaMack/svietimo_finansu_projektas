import pandas as pd
import plotly.express as px
import streamlit as st

from municipality_funding import municipality_funding_records, school_funding_totals


GROUP_ORDER = ["Other schools", "Special schools"]


def prepare_special_school_comparison(funding, year):
    records = municipality_funding_records(funding.loc[funding["metai"] == year], True)
    schools = school_funding_totals(records)
    school_flags = records.groupby(
        ["savivaldybes_kodas", "mokyklos_kodas"], as_index=False
    ).agg(special=("ar_specialioji_mokykla", "first"))
    schools = schools.merge(
        school_flags,
        on=["savivaldybes_kodas", "mokyklos_kodas"],
        validate="one_to_one",
    )
    usable = (
        schools["students"].gt(0)
        & schools["funding"].notna()
        & schools["special"].notna()
    )
    comparison = schools.loc[usable].copy()
    comparison["funding_per_student"] = (
        comparison["funding"] / comparison["students"]
    )
    comparison["group"] = comparison["special"].map(
        {False: "Other schools", True: "Special schools"}
    )
    return comparison, len(schools) - len(comparison)


def show_special_school_explanation(funding, year):
    st.caption(
        "Special schools typically have higher recorded funding per student in this "
        "dataset. This switch lets you view comparisons with or without them."
    )
    with st.expander("Why offer a special-school filter? See the comparison"):
        st.markdown(
            f"**National comparison — {year}.** The chart compares school-level "
            "funding per student across Lithuania, using the selected reporting year. "
            "It includes both groups regardless of the filter setting or selected municipality."
        )
        comparison, excluded_count = prepare_special_school_comparison(funding, year)
        if comparison.empty:
            st.info("No schools have usable funding and student counts for this year.")
            return

        summary = (
            comparison.groupby("group")["funding_per_student"]
            .agg(median="median", school_count="size")
            .reindex(GROUP_ORDER)
        )
        for column, group in zip(st.columns(2), GROUP_ORDER):
            median = summary.loc[group, "median"]
            column.metric(
                f"Median funding per student · {group.lower()}",
                f"€{median:,.2f}" if pd.notna(median) else "Unavailable",
            )

        logarithmic = bool(comparison["funding_per_student"].gt(0).all())
        chart = px.box(
            comparison,
            x="group",
            y="funding_per_student",
            color="group",
            category_orders={"group": GROUP_ORDER},
            color_discrete_map={
                "Other schools": "#2563eb",
                "Special schools": "#f97316",
            },
            points="outliers",
            log_y=logarithmic,
            labels={
                "group": "School group",
                "funding_per_student": "Funding per student (€)",
            },
        )
        chart.update_traces(quartilemethod="linear")
        chart.update_layout(
            height=400,
            showlegend=False,
            margin=dict(l=20, r=20, t=20, b=40),
        )
        counts = summary["school_count"].fillna(0).astype(int)
        chart.update_xaxes(
            title=None,
            tickmode="array",
            tickvals=GROUP_ORDER,
            ticktext=[f"{group}<br>{counts[group]:,} schools" for group in GROUP_ORDER],
        )
        chart.update_yaxes(
            title=(
                "Funding per student (€, logarithmic scale)"
                if logarithmic else "Funding per student (€)"
            ),
            tickprefix="€",
            tickformat=",.0f",
        )
        st.plotly_chart(chart, width="stretch", config={"displayModeBar": False})
        st.caption(
            "The line inside each box is the median; the box contains the middle "
            "50% of schools. Points beyond the whiskers show outlying values."
        )
        if logarithmic:
            st.caption(
                "The vertical axis is logarithmic so both distributions and their "
                "outliers remain visible. Axis labels show euro amounts."
            )

        other_median = summary.loc["Other schools", "median"]
        special_median = summary.loc["Special schools", "median"]
        if pd.notna(other_median) and pd.notna(special_median) and other_median > 0:
            st.write(
                f"The special-school median is {special_median / other_median:.2f} "
                "times the median for other schools in this year."
            )
        if counts.eq(0).any():
            st.info("One group has no usable records in this year; its median is unavailable.")
        if excluded_count:
            st.caption(
                f"{excluded_count:,} schools are omitted because student counts are "
                "missing or zero, or funding or classification is unavailable."
            )
        st.caption(
            "Funding is summed across sources before dividing by each school's first "
            "available student count. Special-school status follows the dataset flag "
            "`ar_specialioji_mokykla`. Values are recorded amounts in nominal euros."
        )
