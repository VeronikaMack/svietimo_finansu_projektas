from pathlib import Path
import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from education_spending_sankey import show_spending_sankey
from education_spending_labels import spending_label_english

DATA_DIRECTORY = Path(__file__).resolve().parents[1] / "data"
DATA_FILE = DATA_DIRECTORY / "public" / "education_expenditure_by_function_2024.csv"
DETAILED_DATA_FILE = (
    DATA_DIRECTORY / "local" / "national_budget_expenditure_quarters_2024.csv"
)
SOURCE_URL = "https://rinkiniai.lietuvosfinansai.lt/dataset/nac-exp"

FUNCTION_GROUP = "Val. funk. kodas (lygis 1)"
FUNCTION_CODE = "Val. funk. kodas (lygis 4)"
EXPENSE_CODE = "Ek. kodas (lygis 2)"
AREA, CATEGORY, EUROS = "ugdymo_sritis", "kategorija", "islaidos_eur"

GENERAL = "Bendrasis ugdymas – pagrindinis ir vidurinis"
MIXED = "Priešmokyklinis ir pradinis (bendra suma)"
AREA_ORDER = [
    "Ikimokyklinis ugdymas",
    MIXED,
    GENERAL,
    "Aukštasis mokslas",
    "Kitos švietimo sritys",
]
EXPENSE_TYPES = {
    "2.1.": "Wages and social insurance",
    "2.2.": "Goods and services",
    "3.1.": "Asset purchases",
}


@st.cache_data
def load_education_spending():
    return pd.read_csv(DATA_FILE, usecols=["kodas", AREA, CATEGORY, EUROS])


@st.cache_data
def load_expense_breakdown():
    data = pd.read_csv(
        DETAILED_DATA_FILE,
        usecols=[FUNCTION_GROUP, FUNCTION_CODE, EXPENSE_CODE, "Vykdymas"],
    )
    general = data.loc[
        (data[FUNCTION_GROUP] == "09.")
        & data[FUNCTION_CODE].isin(["09.02.01.01", "09.02.02.01"])
    ]
    expense_type = general[EXPENSE_CODE].map(EXPENSE_TYPES).fillna("Other expenditure")
    return general.groupby(expense_type)["Vykdymas"].sum().sort_values()



EXPENSE_LEVELS = [
    ("Ek. kodas (lygis 2)", "Išlaidų grupės  (lygis 2)"),
    ("Ek. kodas (lygis 3)", "Išlaidų pogrupiai (lygis 3)"),
    ("Ek. kodas (lygis 4)", "Išlaidų straipsniai (lygis 4)"),
    ("Ek. kodas (lygis 6)", "Detalūs išlaidų straipsniai (lygis 6)"),
]


@st.cache_data
def load_expenditure_details():
    columns = [FUNCTION_GROUP, FUNCTION_CODE, "Vykdymas"]
    for code, label in EXPENSE_LEVELS:
        columns.extend([code, label])
    data = pd.read_csv(DETAILED_DATA_FILE, usecols=columns)
    return data.loc[data[FUNCTION_GROUP] == "09."].copy()


def build_spending_hierarchy(education, details):
    nodes = {}

    def add_node(label, amount, parent):
        node_id = str(len(nodes))
        nodes[node_id] = {
            "id": node_id,
            "label": " ".join(str(label).split()),
            "amount": round(float(amount), 2),
            "parent": parent,
            "children": [],
        }
        if parent is not None:
            nodes[parent]["children"].append(node_id)
        return node_id

    def add_expense_levels(records, parent, level):
        if level == len(EXPENSE_LEVELS):
            return
        code_column, label_column = EXPENSE_LEVELS[level]
        groups = list(records.groupby([code_column, label_column], dropna=False))
        groups.sort(key=lambda group: group[1]["Vykdymas"].sum(), reverse=True)
        for (code, label), rows in groups:
            amount = round(float(rows["Vykdymas"].sum()), 2)
            if amount == 0:
                continue
            if amount < 0:
                raise ValueError(f"Negative expenditure for {spending_label_english(label)}: {amount}")
            label = "Nedetalizuojama" if pd.isna(label) else " ".join(str(label).split())
            # Skip a repeated label when the next level is the same single category.
            if len(groups) == 1 and label == nodes[parent]["label"]:
                add_expense_levels(rows, parent, level + 1)
                continue
            child = add_node(label, amount, parent)
            add_expense_levels(rows, child, level + 1)

    root = add_node("Švietimo išlaidos", education[EUROS].sum(), None)
    area_nodes = []
    function_nodes = {}
    for area in AREA_ORDER:
        categories = education.loc[education[AREA] == area].sort_values(
            EUROS, ascending=False, kind="stable"
        )
        area_label = "Bendrasis ugdymas" if area == GENERAL else area
        area_id = add_node(area_label, categories[EUROS].sum(), root)
        area_nodes.append(area_id)
        for _, category in categories.iterrows():
            records = details.loc[details[FUNCTION_CODE] == category["kodas"]]
            if not math.isclose(
                records["Vykdymas"].sum(), category[EUROS], rel_tol=0, abs_tol=0.01
            ):
                raise ValueError(
                    f"The total for {spending_label_english(category[CATEGORY])} does not match the expenditure dataset."
                )
            if len(categories) == 1:
                function_id = area_id
            else:
                function_id = add_node(category[CATEGORY], category[EUROS], area_id)
            function_nodes[category["kodas"]] = function_id
            add_expense_levels(records, function_id, 0)

    for node in nodes.values():
        if node["children"]:
            child_total = sum(nodes[child]["amount"] for child in node["children"])
            if not math.isclose(child_total, node["amount"], rel_tol=0, abs_tol=0.01):
                raise ValueError(f"Expenditure flows do not balance for {spending_label_english(node['label'])}.")

    general_categories = education.loc[education[AREA] == GENERAL].sort_values(
        EUROS, ascending=False, kind="stable"
    )
    overview_ids = [root, *area_nodes]
    overview_ids.extend(function_nodes[code] for code in general_categories["kodas"])
    for node in nodes.values():
        node["label"] = spending_label_english(node["label"])
    return nodes, overview_ids


def make_spending_chart(education):
    by_area = education.groupby(AREA)[EUROS].sum().reindex(AREA_ORDER)
    total = by_area.sum()

    general = education.loc[education[AREA] == GENERAL]
    by_category = general.groupby(CATEGORY)[EUROS].sum().sort_values(ascending=False)

    display_names = {GENERAL: "General education"}
    area_labels = [
        f"{display_names.get(name, spending_label_english(name))} ({amount / total:.1%})"
        for name, amount in by_area.items()
    ]
    detail_labels = [
        f"{spending_label_english(name)} ({amount / by_area[GENERAL]:.1%})"
        for name, amount in by_category.items()
    ]
    area_nodes = list(range(1, len(by_area) + 1))
    detail_nodes = list(range(len(by_area) + 1, len(by_area) + len(by_category) + 1))
    general_node = 1 + AREA_ORDER.index(GENERAL)
    area_link_colors = [
        "rgba(37, 99, 235, 0.50)" if name == GENERAL else "rgba(100, 116, 139, 0.24)"
        for name in AREA_ORDER
    ]

    chart = go.Figure(
        go.Sankey(
            node=dict(
                align="left",
                label=["", *area_labels, *detail_labels],
                color=[
                    "#334155",
                    "#94a3b8",
                    "#d6a535",
                    "#2563eb",
                    "#94a3b8",
                    "#94a3b8",
                    *(["#2563eb"] * len(by_category)),
                ],
                pad=24,
                thickness=16,
                hovertemplate=[
                    "Total education expenditure<br>€%{value:,.2f}<extra></extra>",
                    *(["%{label}<br>€%{value:,.2f}<extra></extra>"] * (len(area_labels) + len(detail_labels))),
                ],
            ),
            link=dict(
                source=[0] * len(by_area) + [general_node] * len(by_category),
                target=area_nodes + detail_nodes,
                value=by_area.tolist() + by_category.tolist(),
                color=area_link_colors + ["rgba(37, 99, 235, 0.34)"] * len(by_category),
                hovertemplate=[
                    *(["Total education expenditure → %{target.label}<br>€%{value:,.2f}<extra></extra>"] * len(by_area)),
                    *(["%{source.label} → %{target.label}<br>€%{value:,.2f}<extra></extra>"] * len(by_category)),
                ],
            ),
        )
    )
    chart.update_layout(
        height=440,
        margin=dict(l=65, r=12, t=12, b=12),
        font_size=14,
        annotations=[dict(
            text="<b>Total education expenditure</b>",
            textangle=-90,
            x=-0.025,
            y=0.5,
            xref="paper",
            yref="paper",
            xanchor="right",
            yanchor="middle",
            showarrow=False,
            font=dict(size=14, color="#334155"),
        )],
    )
    return chart


def show_expense_breakdown():
    with st.expander("Basic and upper secondary expenditure by expense type"):
        expenses = load_expense_breakdown()
        chart = go.Figure(
            go.Bar(
                x=expenses.tolist(),
                y=expenses.index.tolist(),
                orientation="h",
                marker_color="#2563eb",
                text=[f"{share:.1%}" for share in expenses / expenses.sum()],
                textposition="outside",
                cliponaxis=False,
                hovertemplate="%{y}<br>€%{x:,.2f} · %{text}<extra></extra>",
            )
        )
        chart.update_layout(
            height=300,
            margin=dict(l=12, r=48, t=12, b=28),
            xaxis_title="Expenditure (€)",
        )
        st.plotly_chart(chart, width="stretch", config={"displayModeBar": False})


def show_education_spending():
    st.header("Education expenditure in 2024")
    if not DATA_FILE.is_file():
        st.error(f"Missing data file: {DATA_FILE}")
        return

    st.markdown("""
The total education budget gives a sense of scale, but it does not show
what the money pays for. This diagram traces actual public expenditure
in 2024 across education areas, with wider flows representing larger amounts.

It shows which areas account for the largest shares of spending and how
their expenditure breaks down into wages, goods and services, asset purchases
and other costs. This connects the overall total to the activities and
resources it funds, providing context for the school funding comparisons below.
    """)
    education = load_education_spending()
    st.metric("Total expenditure", f"€{education[EUROS].sum():,.2f}")
    diagram, explanation = st.columns([3, 1], gap="medium")
    with diagram:
        chart = make_spending_chart(education)
        if DETAILED_DATA_FILE.is_file():
            nodes, overview_ids = build_spending_hierarchy(
                education, load_expenditure_details()
            )
            chart.data[0].node.customdata = overview_ids
            chart.data[0].link.customdata = [
                overview_ids[target] for target in chart.data[0].link.target
            ]
            show_spending_sankey(chart, nodes)
        else:
            st.plotly_chart(
                chart, width="stretch", config={"displayModeBar": False}
            )
            st.info("Detailed expenditure requires the quarterly expenditure dataset.")
        st.caption(
            "Actual budget expenditure across all four quarters of 2024. "
            f"[Ministry of Finance data]({SOURCE_URL})"
        )
    with explanation:
        st.markdown("""
**What does the diagram show?**

- **Pre-school education** - kindergartens and other pre-school institutions.
- **Pre-primary and primary education** - preparation before grade 1 and
  primary education (grades 1-4). The source reports these stages together.
- **General education** - this branch shows basic education (grades 5-10)
  and upper secondary education (grades 11-12).
- **Higher education** - colleges and universities.
- **Other education areas** - including vocational schools, non-formal
  education and educational support.

Selecting an education area or category makes it the main flow. Further
levels show expense groups, subgroups and detailed items. The navigation
above the diagram returns to earlier levels or the overall view.

Percentages in the overall view refer to the corresponding parent flow.
Expanded views show amounts in euros. Each breakdown adds up to the
selected category's total.
        """)


if __name__ == "__main__":
    show_education_spending()
