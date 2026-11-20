import streamlit as st

from cloud_data import DataSetupError, ensure_local_data

st.set_page_config(
    page_title="Lithuanian Education Finances",
    layout="wide",
)

page = st.navigation(
    [
        st.Page("overview.py", title="Overview", default=True),
        st.Page(
            "municipality_explorer.py",
            title="Municipality Explorer",
            url_path="municipality-explorer",
        ),
        st.Page(
            "school_explorer.py",
            title="School Explorer",
            url_path="school-explorer",
        ),
    ],
    position="top",
)
try:
    with st.spinner("Preparing dashboard data..."):
        ensure_local_data()
except DataSetupError as error:
    st.error(str(error))
    st.stop()

page.run()
