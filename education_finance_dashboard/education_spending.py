from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

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
    "2.1.": "Darbo užmokestis ir socialinis draudimas",
    "2.2.": "Prekės ir paslaugos",
    "3.1.": "Turto įsigijimas",
}


@st.cache_data
def load_education_spending():
    return pd.read_csv(DATA_FILE, usecols=[AREA, CATEGORY, EUROS])


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
    expense_type = general[EXPENSE_CODE].map(EXPENSE_TYPES).fillna("Kitos išlaidos")
    return general.groupby(expense_type)["Vykdymas"].sum().sort_values()


def make_spending_chart(education):
    by_area = education.groupby(AREA)[EUROS].sum().reindex(AREA_ORDER)
    total = by_area.sum()

    general = education.loc[education[AREA] == GENERAL]
    by_category = general.groupby(CATEGORY)[EUROS].sum().sort_values(ascending=False)

    display_names = {GENERAL: "Bendrasis ugdymas"}
    area_labels = [
        f"{display_names.get(name, name)} ({amount / total:.1%})"
        for name, amount in by_area.items()
    ]
    detail_labels = [
        f"{name} ({amount / by_area[GENERAL]:.1%})"
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
                label=["Švietimo finansavimas", *area_labels, *detail_labels],
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
                hovertemplate="%{label}<br>€%{value:,.2f}<extra></extra>",
            ),
            link=dict(
                source=[0] * len(by_area) + [general_node] * len(by_category),
                target=area_nodes + detail_nodes,
                value=by_area.tolist() + by_category.tolist(),
                color=area_link_colors + ["rgba(37, 99, 235, 0.34)"] * len(by_category),
                hovertemplate=(
                    "%{source.label} → %{target.label}<br>"
                    "€%{value:,.2f}<extra></extra>"
                ),
            ),
        )
    )
    chart.update_layout(height=440, margin=dict(l=12, r=12, t=12, b=12), font_size=14)
    return chart


def show_expense_breakdown():
    with st.expander("Pagrindinio ir vidurinio ugdymo išlaidos pagal išlaidų rūšį"):
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
            xaxis_title="Išlaidos (€)",
        )
        st.plotly_chart(chart, width="stretch", config={"displayModeBar": False})


def show_education_spending():
    st.header("Švietimo finansavimas 2024 m.")
    if not DATA_FILE.is_file():
        st.error(f"Missing data file: {DATA_FILE}")
        return

    education = load_education_spending()
    st.metric("Iš viso", f"€{education[EUROS].sum():,.2f}")
    diagram, explanation = st.columns([3, 1], gap="medium")
    with diagram:
        st.plotly_chart(
            make_spending_chart(education),
            width="stretch",
            config={"displayModeBar": False},
        )
        st.caption(
            "Rodomos faktinės visų keturių 2024 m. ketvirčių biudžeto išlaidos. "
            f"[Finansų ministerijos duomenys]({SOURCE_URL})"
        )
    with explanation:
        st.markdown("""
**Ką rodo diagrama?**

- **Ikimokyklinis ugdymas** – darželiai ir kitos ikimokyklinio ugdymo įstaigos.
- **Priešmokyklinis ir pradinis** – pasirengimas mokyklai prieš 1 klasę ir
  pradinis ugdymas (1–4 klasės). Šaltinyje šių dviejų pakopų išlaidos pateiktos kartu.
- **Bendrasis ugdymas** apima 1–12 klases. Šioje šakoje rodomos pagrindinio
  ugdymo (5–10 klasės) ir vidurinio ugdymo (11–12 klasės) išlaidos.
- **Aukštasis mokslas** – kolegijos ir universitetai.
- **Kitos švietimo sritys** – pavyzdžiui, profesinis mokymas, būreliai ir švietimo pagalba.

Procentai prie švietimo sričių skaičiuojami nuo visų švietimo išlaidų. Dešinėje
procentai rodo, kaip pagrindinio ir vidurinio ugdymo išlaidos pasidalija
tarp šių dviejų pakopų. Užvedus pelę ant srauto matoma tiksli suma eurais.
        """)
    if DETAILED_DATA_FILE.is_file():
        show_expense_breakdown()


if __name__ == "__main__":
    show_education_spending()
