"""Two direct financial totals, without stacking expenses with income."""
import pandas as pd
import plotly.graph_objects as go
from funding_trends import style_annual_chart


def make_income_expense_chart(income, expenses, year):
    years = income.index.union(expenses.index).dropna()
    full_years = range(int(years.min()), int(years.max()) + 1) if len(years) else []
    figure = go.Figure()
    for name, series, color in [
        ("Total income", income, "#2563eb"),
        ("Total expenses", expenses, "#f97316"),
    ]:
        values = series.reindex(full_years)
        figure.add_bar(
            x=list(full_years), y=values.tolist(), name=name, marker_color=color,
            hovertemplate="Year: %{x}<br>€%{y:,.2f}<extra>%{fullData.name}</extra>",
        )
    figure.update_layout(barmode="group")
    style_annual_chart(figure, year, "Amount (€)")
    figure.update_layout(height=520)
    return figure
