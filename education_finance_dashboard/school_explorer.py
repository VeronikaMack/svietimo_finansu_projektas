from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

from municipality_funding import load_funding


DATABASE_FILE = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "local"
    / "lithuanian_education_warehouse.duckdb"
)


@st.cache_data
def load_school_financial_results(school_code, year):
    with duckdb.connect(DATABASE_FILE, read_only=True) as conn:
        return conn.execute(
            """
            SELECT
                saskaita_lygis_1,
                kodas_lygis_2,
                saskaita_lygis_2,
                saskaita_lygis_3,
                CAST(suma AS DOUBLE) AS suma
            FROM mokyklu_veiklos_rezultatai
            WHERE mokyklos_kodas = ?
              AND YEAR(ataskaitinis_periodas) = ?
              AND saskaita_lygis_1 IN ('Pajamos', 'Sąnaudos')
            """,
            [school_code, year],
        ).df()


@st.cache_data
def load_school_expense_history(school_code):
    with duckdb.connect(DATABASE_FILE, read_only=True) as conn:
        return conn.execute(
            """
            SELECT
                YEAR(ataskaitinis_periodas) AS metai,
                -SUM(CAST(suma AS DOUBLE)) AS expenditure
            FROM mokyklu_veiklos_rezultatai
            WHERE mokyklos_kodas = ?
              AND saskaita_lygis_1 = 'Sąnaudos'
              AND ataskaitinis_periodas IS NOT NULL
            GROUP BY YEAR(ataskaitinis_periodas)
            ORDER BY metai
            """,
            [school_code],
        ).df()


def show_school_financial_history(school_code, school_funding):
    annual_funding = (
        school_funding.assign(suma=school_funding["suma"].astype("float64"))
        .groupby("metai")["suma"]
        .sum(min_count=1)
        .rename("Funding received")
    )
    annual_expenses = (
        load_school_expense_history(school_code)
        .set_index("metai")["expenditure"]
        .astype("float64")
        .rename("Total expenditure")
    )
    history = pd.concat([annual_funding, annual_expenses], axis=1).sort_index()
    history = (
        history.reindex(range(int(history.index.min()), int(history.index.max()) + 1))
        .rename_axis("Year")
        .reset_index()
    )

    st.subheader("Funding received and expenditure over time")
    chart = px.line(
        history,
        x="Year",
        y=["Funding received", "Total expenditure"],
        markers=True,
        color_discrete_map={
            "Funding received": "#2563eb",
            "Total expenditure": "#f97316",
        },
        labels={"value": "Amount (€)", "variable": ""},
    )
    chart.update_traces(
        connectgaps=False,
        hovertemplate="€%{y:,.2f}<extra>%{fullData.name}</extra>",
    )
    chart.update_layout(height=380, hovermode="x unified")
    chart.update_xaxes(dtick=1, tickformat="d")
    chart.update_yaxes(tickprefix="€", tickformat="~s")
    st.plotly_chart(chart, width="stretch", config={"displayModeBar": False})
    st.caption(
        "All available calendar years for this school · Nominal euros · "
        "Gaps indicate missing figures. Funding covers recorded funding income."
    )


def format_expense_share(share):
    if 0 < share < 0.001:
        return "<0.1%"
    if 0.9995 <= share < 1:
        return ">99.9%"
    return f"{share:.0%}" if share in (0, 1) else f"{share:.1%}"


def expense_bar_chart(
    categories, label_column, share_axis_title, display_mode, category_code=None
):
    categories = categories.sort_values("expense_eur", ascending=False, kind="stable")
    total = categories["expense_eur"].sum()
    has_shares = total > 0 and categories["expense_eur"].ge(0).all()
    show_shares = display_mode == "Percentages" and has_shares
    custom_data = [category_code, "expense_eur"] if category_code else ["expense_eur"]
    hover = "%{y}<br>€%{customdata[" + str(len(custom_data) - 1) + "]:,.2f}"
    if has_shares:
        shares = categories["expense_eur"] / total
        categories = categories.assign(
            share=shares, share_label=shares.map(format_expense_share)
        )
        hover += "<br>%{customdata[" + str(len(custom_data)) + "]}"
        custom_data.append("share_label")

    figure = px.bar(
        categories,
        x="share" if show_shares else "expense_eur",
        y=label_column,
        orientation="h",
        text="share_label" if show_shares else "expense_eur",
        custom_data=custom_data,
        labels={"share": share_axis_title, "expense_eur": "Net reported expenses (€)"},
    )
    if show_shares:
        figure.update_xaxes(
            range=[0, 1.08],
            tickvals=[0, 0.25, 0.5, 0.75, 1],
            tickformat=".0%",
        )
    else:
        figure.update_xaxes(tickprefix="€")
        figure.update_traces(texttemplate="€%{x:,.2f}")
    figure.update_traces(
        textposition="outside",
        textfont_size=15,
        cliponaxis=False,
        hovertemplate=hover + "<extra></extra>",
    )
    figure.update_yaxes(
        title=None,
        categoryorder="array",
        categoryarray=categories[label_column].tolist(),
        autorange="reversed",
        automargin=True,
        tickfont_size=15,
    )
    figure.update_layout(
        height=max(160, 80 + 42 * len(categories)),
        margin=dict(l=10, r=40 if show_shares else 100, t=8, b=40),
        hovermode="y",
    )
    return figure


def show_school_expense_breakdown(expenses, school_code, year):
    st.subheader("Reported expenses by category")
    expense_lines = expenses.dropna(subset=["suma"]).assign(
        expense_eur=lambda lines: -lines["suma"]
    )
    if expense_lines.empty:
        st.info("No expense amounts were reported for this school and year.")
        return

    broad = expense_lines.groupby(
        ["kodas_lygis_2", "saskaita_lygis_2"], as_index=False
    )["expense_eur"].sum()
    category_labels = broad.set_index("kodas_lygis_2")["saskaita_lygis_2"].to_dict()
    chart_key = f"expense_chart_{school_code}_{year}"
    category_key = f"expense_category_{school_code}_{year}"

    def select_category_from_chart():
        points = st.session_state[chart_key]["selection"]["points"]
        data = points[0].get("customdata") if len(points) == 1 else None
        if data and data[0] in category_labels:
            st.session_state[category_key] = data[0]

    display_mode = st.radio(
        "Show expenses as",
        ["Percentages", "Euro amounts"],
        horizontal=True,
        key="school_expense_display_mode",
        persist_state="session",
        help="The charts use euros for breakdowns with a negative amount or a zero total.",
    )
    st.caption(
        "Hover for the exact amount. Click a bar or use the picker to see the details."
    )
    figure = expense_bar_chart(
        broad,
        "saskaita_lygis_2",
        "Share of total school expenses",
        display_mode,
        category_code="kodas_lygis_2",
    )
    figure.update_layout(clickmode="event+select")
    figure.update_traces(unselected=dict(marker=dict(opacity=1)))
    st.plotly_chart(
        figure,
        width="stretch",
        key=chart_key,
        on_select=select_category_from_chart,
        selection_mode="points",
        config={"displayModeBar": False},
    )

    category = st.selectbox(
        "Expense category to expand",
        options=list(category_labels),
        format_func=category_labels.__getitem__,
        index=None,
        key=category_key,
    )
    if category is not None:
        detail = (
            expense_lines[expense_lines["kodas_lygis_2"] == category]
            .groupby("saskaita_lygis_3", as_index=False)["expense_eur"]
            .sum()
        )
        st.markdown(f"**{category_labels[category]}**")
        detail_chart = expense_bar_chart(
            detail, "saskaita_lygis_3", "Share of this expense category", display_mode
        )
        detail_chart.update_layout(dragmode=False)
        scroll_height = 360
        scrollable = detail_chart.layout.height > scroll_height
        if scrollable:
            st.caption("Scroll inside the chart to see more expense types.")
        detail_panel = st.container(
            height=scroll_height if scrollable else "content",
            border=False,
            key=f"{category_key}_{category}_detail",
        )
        detail_panel.plotly_chart(
            detail_chart,
            width="stretch",
            config={"displayModeBar": False, "scrollZoom": False},
        )

    st.caption("Source table `mokyklu_veiklos_rezultatai` · `Sąnaudos`")


st.title("School Explorer")

funding = load_funding()
school_index = (
    funding.dropna(subset=["mokyklos_kodas", "metai"])
    .sort_values("metai", ascending=False, kind="stable")
    .drop_duplicates(subset="mokyklos_kodas")
    .set_index("mokyklos_kodas")
)
labels = (
    school_index["mokykla"].fillna("School").str.strip()
    + " · "
    + school_index["mokyklos_savivaldybe"].fillna("Municipality unavailable")
)
duplicate_labels = labels.duplicated(keep=False)
school_labels = {
    int(code): f"{label} ({code})" if duplicate_labels.loc[code] else label
    for code, label in labels.items()
}

incoming = st.session_state.pop("school_explorer_context", None)
if incoming and incoming["code"] in school_labels:
    st.session_state["school_explorer_school"] = incoming["code"]
    st.session_state["school_explorer_year"] = incoming["year"]

school_column, year_column = st.columns([3, 1], vertical_alignment="bottom")
with school_column:
    school_code = st.selectbox(
        "Choose a school",
        options=sorted(school_labels, key=lambda code: school_labels[code].casefold()),
        format_func=school_labels.__getitem__,
        index=None,
        placeholder="Search by school name or municipality",
        key="school_explorer_school",
        persist_state="session",
    )

if school_code is None:
    st.stop()

school_funding = funding[funding["mokyklos_kodas"] == school_code]
years = sorted(school_funding["metai"].dropna().unique().tolist())
if st.session_state.get("school_explorer_year") not in years:
    st.session_state["school_explorer_year"] = years[-1]

with year_column:
    year = st.selectbox(
        "Reporting year",
        options=years,
        index=None,
        key="school_explorer_year",
        persist_state="session",
    )

st.subheader("School income and expenses")
results = load_school_financial_results(school_code, int(year))
if results.empty:
    st.info("No income or expense records were found for this school and year.")
    show_school_financial_history(school_code, school_funding)
    st.stop()

income = results[results["saskaita_lygis_1"] == "Pajamos"]
expenses = results[results["saskaita_lygis_1"] == "Sąnaudos"]

funding_income = (
    school_funding.loc[school_funding["metai"] == year, "suma"]
    .astype("float64")
    .sum(min_count=1)
)
other_rows = income.loc[income["saskaita_lygis_2"] != "Finansavimo pajamos", "suma"]
other_income = 0.0 if other_rows.empty else other_rows.sum(min_count=1)
total_income = income["suma"].sum(min_count=1)
total_expenses = -expenses["suma"].sum(min_count=1)

metrics = [
    ("Funding income", funding_income),
    ("Other reported income", other_income if pd.notna(total_income) else None),
    ("Total reported income", total_income),
    ("Total reported expenses", total_expenses),
]
for column, (label, amount) in zip(st.columns(4), metrics):
    column.metric(label, f"€{amount:,.2f}" if pd.notna(amount) else "—")
st.caption("Funding income and other reported income make up total reported income.")
st.caption(
    "Source tables `finansavimas_mokykla_metai` and `mokyklu_veiklos_rezultatai`"
)

show_school_financial_history(school_code, school_funding)

show_school_expense_breakdown(expenses, school_code, year)
