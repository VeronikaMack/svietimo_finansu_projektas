# Lithuanian Education Finances

This project explores Lithuanian education expenditure and school funding
through an interactive Streamlit dashboard and three Jupyter notebooks.

The analysis covers national expenditure, municipality-level funding,
and individual school income and expenditure.

## Dashboard

The `education_finance_dashboard/` folder contains the Streamlit application.

- **Overview** shows education expenditure, school funding indicators,
  funding sources, annual trends, and municipality maps.
- **Municipality Explorer** compares funding sources, school types,
  total school funding, and funding per student within a selected municipality.
- **School Explorer** shows an individual school's income, expenditure,
  annual financial trends, and expense categories.

The dashboard supports interactive selections for schools, municipalities,
reporting years, and other filters.

## Notebooks

The `notebooks/` folder contains three notebooks corresponding to the
dashboard pages. Each notebook presents data preparation, charts,
and short explanations using fixed selections.

| Notebook | Contents |
| --- | --- |
| `overview.ipynb` | National education expenditure, school funding indicators, funding sources, annual trends, and municipality maps with and without special schools. |
| `municipality_explorer.ipynb` | Vilnius city in 2024, including funding indicators, funding sources, school types, and the top 10 schools by total funding and funding per student. |
| `school_explorer.ipynb` | Vilniaus Antakalnio gimnazija, including 2024 financial indicators, annual funding and expenditure trends, and expense breakdowns. |

The notebook charts use Plotly with interaction disabled.
Image or PDF exports can be prepared for viewing the results independently
of the notebook environment.

## Data

- `data/public/education_expenditure_by_function_2024.csv` contains the
  aggregated education expenditure figures used by the overview.
- `assets/municipality_boundaries.geojson` contains municipality boundaries.
- `data/local/` contains the warehouse and additional source datasets
  required to run the analysis. These files are excluded from Git tracking
  and must be supplied separately.

The main warehouse tables used by the dashboard and notebooks are
`finansavimas_mokykla_metai` and `mokyklu_veiklos_rezultatai`.

## Run the dashboard

From the project root, install the dependencies.

```bash
python3 -m pip install -r requirements.txt
```

Launch the dashboard.

```bash
python3 -m streamlit run education_finance_dashboard/dashboard.py
```

## Run the notebooks

Open a notebook in VS Code with Jupyter support, select the Python environment
containing the dependencies, and run the cells from top to bottom.

The notebook working directory should be `notebooks/`, since the data paths
are relative to that folder.

## Interpretation

- Amounts are expressed in nominal euros, without adjustment for inflation.
- The schools represented in the data may differ between years.
- Student counts are included once per school when calculating funding
  per student.
- Missing student counts can overstate municipality funding per student
  when the associated funding remains included.
- Funding income, other income, and expenditure are separate measures.

## Sources

The financial data draws on the Lithuanian Ministry of Finance datasets.
Credit the original providers when using the data.

- [Budget expenditure data](https://rinkiniai.lietuvosfinansai.lt/dataset/nac-exp)
- [Public-sector financial statements](https://rinkiniai.lietuvosfinansai.lt/dataset/sub-is)

