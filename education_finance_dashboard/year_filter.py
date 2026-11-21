"""One reporting year, shared by all dashboard views."""
import streamlit as st

YEAR_FILTER_CSS = """
<style>
/* Label the existing native sidebar button without replacing its behavior. */
[data-testid="stExpandSidebarButton"] {
    width: auto !important;
    min-width: 112px;
    padding: 6px 10px !important;
    gap: 6px;
    border: 1px solid currentColor;
    border-radius: 7px;
}
[data-testid="stExpandSidebarButton"]::after {
    content: "Year filter";
    white-space: nowrap;
    font-size: 14px;
    font-weight: 600;
}
</style>
"""


def show_year_filter(funding, incoming_year=None):
    years = sorted(int(year) for year in funding["metai"].dropna().unique())
    if incoming_year in years:
        st.session_state["reporting_year"] = int(incoming_year)
    if st.session_state.get("reporting_year") not in years:
        previous = st.session_state.get("overview_year")
        st.session_state["reporting_year"] = previous if previous in years else years[-1]
    st.html(YEAR_FILTER_CSS)
    with st.sidebar:
        st.header("Year filter")
        year = st.selectbox(
            "Reporting year", options=years, key="reporting_year",
            help="Shared across Overview, Municipality Explorer and School Explorer.",
            persist_state="session",
        )
        st.caption(
            "This year applies across all three views. It updates single-year "
            "school comparisons and highlights the year in historical charts. "
            "The national expenditure Sankey always covers 2024."
        )
    return year
