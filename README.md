# Hispanic Heritage Historical Data Explorer

A Streamlit app for exploring real historical World Bank indicators for Mexico, Brazil, Argentina, Colombia, Chile, Peru, Venezuela, Ecuador, and Uruguay.

## Featured research question
How has the national-estimate unemployment rate changed in Ecuador, and how does its trend compare with Colombia?

## Features
- Retrieves official World Bank data for the previous 70 calendar years, ending last year.
- Selects countries and ten required indicators.
- Shows actual available coverage, indicator code, units, and source.
- Editable working data table with reset to official source.
- Fits centered-time polynomial models (degree 3–8), showing in-sample R² and MAE.
- Compares same-indicator observations across countries.
- Calculates individual-year and batch estimates.
- Exports working data to CSV, a genuine XLSX workbook, and a PDF report.
- Warns that extrapolation is uncertain and that validated prediction intervals are not provided.

## Run locally
```bash
pip install -r requirements.txt
python -m streamlit run app.py
```

## Deploy with GitHub and Render
1. Create a GitHub repository and upload `app.py`, `requirements.txt`, `README.md`, and `sources.md`.
2. In Render, create a **Web Service** and connect the repository.
3. Choose Python.
4. Build command: `pip install -r requirements.txt`
5. Start command (one line): `python -m streamlit run app.py --server.address=0.0.0.0 --server.port=$PORT`
6. Deploy, review build/runtime logs, and test the public `onrender.com` URL.

The PDF also allows Streamlit Community Cloud as an alternative deployment host.

## Data definitions
The app uses the official indicator codes in `sources.md`. Brazil is included as a Latin American comparison, not as a Spanish-speaking Hispanic country.

## Limitations and verification
- Missing observations are not fabricated.
- National-estimate unemployment may not be directly comparable across countries due to methodology.
- R² and MAE are in-sample metrics, not proof of forecast skill.
- Polynomial extrapolations may be implausible.
- Validated prediction intervals are not provided.
- Verify at least two source values against the World Bank website, test editing/reset, check a single estimate against a batch estimate, and open all three export formats before submitting.

## AI-use disclosure
AI assistance was used to draft and explain the app structure. The student team must test the code, verify the source data and outputs, document revisions, and explain its mathematical decisions.

## Team roles
Replace this section with each student's actual contribution.

## Live URL
Add the Render URL after deployment.
