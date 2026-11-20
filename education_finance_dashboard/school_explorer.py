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


@st.cache_data
def load_school_income_history(school_code):
    with duckdb.connect(DATABASE_FILE, read_only=True) as conn:
        return conn.execute(
            """
            SELECT
                YEAR(ataskaitinis_periodas) AS metai,
                SUM(CAST(suma AS DOUBLE)) AS income
            FROM mokyklu_veiklos_rezultatai
            WHERE mokyklos_kodas = ?
              AND saskaita_lygis_1 = 'Pajamos'
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
        .rename("Funding income")
    )
    annual_expenses = (
        load_school_expense_history(school_code)
        .set_index("metai")["expenditure"]
        .astype("float64")
        .rename("Total expenses")
    )
    annual_income = (
        load_school_income_history(school_code)
        .set_index("metai")["income"]
        .astype("float64")
        .rename("Total income")
    )
    history = pd.concat(
        [annual_income, annual_funding, annual_expenses], axis=1
    ).sort_index()
    history = (
        history.reindex(range(int(history.index.min()), int(history.index.max()) + 1))
        .rename_axis("Year")
        .reset_index()
    )

    st.subheader("Income and expenses over time")
    st.markdown("""
A single year provides a snapshot. **How have the school's income and
expenses changed over time, and has income kept pace with costs?**

The chart compares total expenses with either total income or funding income.
Total income includes funding and other reported income; funding income shows
only the funding component. The selector changes the income line while keeping
total expenses visible.
    """)
    income_measure = st.radio(
        "Compare total expenses with",
        ["Total income", "Funding income"],
        horizontal=True,
        key="school_history_income_measure",
        persist_state="session",
    )
    if income_measure == "Funding income":
        st.caption(
            "Funding income is only part of total income, so the gap between "
            "these lines is not the school's surplus or deficit."
        )
    chart = px.line(
        history,
        x="Year",
        y=[income_measure, "Total expenses"],
        markers=True,
        color_discrete_map={
            "Total income": "#2563eb",
            "Funding income": "#2563eb",
            "Total expenses": "#f97316",
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
        "Gaps indicate missing figures. Amounts are not adjusted for inflation."
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


EXPENSE_LABELS = {
    "Pagrindinės veiklos sąnaudos": "Main operating expenses",
    "Kitos veiklos sąnaudos": "Other activity expenses",
    "Finansinės ir investicinės veiklos sąnaudos": "Financial and investment expenses",
    "Baudų ir delspinigių sąnaudos": "Fines and late-payment penalties",
    "Kitos finansinės ir investicinės veiklos sąnaudos": "Other financial and investment expenses",
    "Nuostolis dėl valiutos kurso pasikeitimo": "Foreign exchange losses",
    "Palūkanų sąnaudos": "Interest expenses",
    "Darbo užmokesčio ir socialinio draudimo sąnaudos": "Wages and social insurance",
    "Darbo užmokesčio ir socialinio draudimo": "Wages and social insurance",
    "Ilgalaikio turto nusidėvėjimo ir amortizacijos sąnaudos": "Depreciation and amortisation",
    "Nusidėvėjimo ir amortizacijos": "Depreciation and amortisation",
    "Kitos veiklos mokesčių sąnaudos": "Taxes on other activities",
    "Nuostoliai iš ilgalaikio turto perleidimo": "Losses on disposal of fixed assets",
    "Paslaugų sąnaudos": "Services",
    "Sunaudotų ir parduotų atsargų savikaina": "Cost of supplies used and sold",
    "Finansavimo": "Financing expenses",
    "Kitos": "Other expenses",
    "Kitų paslaugų": "Other services",
    "Komandiruočių": "Business travel",
    "Komunalinių paslaugų ir ryšių": "Utilities and communications",
    "Kvalifikacijos kėlimo": "Professional development",
    "Nuomos": "Rent",
    "Nuvertėjimo ir nurašytų sumų": "Impairment and write-offs",
    "Paprastojo remonto ir eksploatavimo": "Routine repairs and maintenance",
    "Socialinių išmokų": "Social benefits",
    "Transporto": "Transport",
}


def show_school_expense_breakdown(expenses, school_code, year):
    st.subheader("Reported expenses by category")
    st.markdown(f"""
The trend shows how expenses have changed over time. **What makes up those
costs in {year}?**

The bars compare the school's reported expense categories, showing which
account for the largest amounts. Expanding a category reveals its individual
costs, such as wages, utilities and maintenance. This connects the overall
expense total to the activities and resources behind it.
    """)
    expense_lines = expenses.dropna(subset=["suma"]).assign(
        expense_eur=lambda lines: -lines["suma"]
    )
    if expense_lines.empty:
        st.info("No expense amounts were reported for this school and year.")
        return

    broad = expense_lines.groupby(
        ["kodas_lygis_2", "saskaita_lygis_2"], as_index=False
    )["expense_eur"].sum()
    broad["label"] = broad["saskaita_lygis_2"].replace(EXPENSE_LABELS)
    category_labels = broad.set_index("kodas_lygis_2")["label"].to_dict()
    category_key = f"expense_category_{school_code}_{year}"

    def return_to_overview():
        st.session_state[category_key] = None

    display_mode = st.radio(
        "Show expenses as",
        ["Percentages", "Euro amounts"],
        horizontal=True,
        key="school_expense_display_mode",
        persist_state="session",
        help="Euros are used when a breakdown contains negative amounts or has a zero total.",
    )
    st.button(
        "← Back to all expenses",
        key=f"expense_back_{school_code}_{year}",
        disabled=st.session_state.get(category_key) is None,
        on_click=return_to_overview,
    )
    category = st.selectbox(
        "Expense category",
        options=list(category_labels),
        format_func=category_labels.__getitem__,
        index=None,
        placeholder="All expenses - select a category to expand",
        key=category_key,
    )
    chart_key = f"expense_chart_{school_code}_{year}_{category or 'overview'}"

    def select_category_from_chart():
        points = st.session_state[chart_key]["selection"]["points"]
        data = points[0].get("customdata") if len(points) == 1 else None
        if data and data[0] in category_labels:
            st.session_state[category_key] = data[0]

    if category is None:
        st.markdown("**All expenses**")
        st.caption("Clicking a bar expands that category in this chart. Hovering shows exact amounts.")
        figure = expense_bar_chart(
            broad, "label", "Share of total school expenses", display_mode,
            category_code="kodas_lygis_2",
        )
        figure.update_layout(clickmode="event+select")
        figure.update_traces(unselected=dict(marker=dict(opacity=1)))
    else:
        st.markdown(f"**All expenses / {category_labels[category]}**")
        detail = (
            expense_lines[expense_lines["kodas_lygis_2"] == category]
            .groupby("saskaita_lygis_3", as_index=False, dropna=False)["expense_eur"]
            .sum()
        )
        detail["label"] = detail["saskaita_lygis_3"].replace(EXPENSE_LABELS).fillna("Unspecified expense")
        figure = expense_bar_chart(
            detail, "label", "Share of this expense category", display_mode
        )
        figure.update_layout(dragmode=False)
        st.caption("This is the most detailed expense level available. Percentages refer to the selected category.")

    scrollable = figure.layout.height > 420
    if scrollable:
        st.caption("Scroll inside the chart to see all expense types.")
    panel = st.container(height=420 if scrollable else "content", border=False)
    panel.plotly_chart(
        figure,
        width="stretch",
        key=chart_key,
        on_select=select_category_from_chart if category is None else "ignore",
        selection_mode="points",
        config={"displayModeBar": False, "scrollZoom": False},
    )
    st.caption("Source table `mokyklu_veiklos_rezultatai` · `Sąnaudos`")


st.title("School Explorer")

st.markdown("""
The municipality comparison showed differences between schools. A closer look
at one school raises the next question: **what does its funding support?**

The figures below bring together the school's reported income and expenses.
The trend shows how funding income and expenses have changed over time, while
the expense breakdown shows which costs account for the largest amounts.
Together, they put the school's position in the earlier comparisons into context.
""")

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
st.markdown(f"""
For **{year}**, how much income did the school report, and how much did it
record in expenses? The figures below separate funding income from other
reported income and show total expenses alongside them. This establishes the
school's financial picture for the selected year before examining its costs
in more detail.
""")
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
