import io
from datetime import date
import requests
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from sklearn.metrics import mean_absolute_error, r2_score
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

st.set_page_config(page_title="Hispanic Heritage Historical Data Explorer", page_icon="📊", layout="wide")

COUNTRIES = {
    "Mexico": "MEX", "Brazil": "BRA", "Argentina": "ARG", "Colombia": "COL",
    "Chile": "CHL", "Peru": "PER", "Venezuela": "VEN", "Ecuador": "ECU", "Uruguay": "URY"
}
INDICATORS = {
    "Life expectancy at birth": ("SP.DYN.LE00.IN", "years", "Average number of years a newborn is expected to live if current mortality patterns continue."),
    "Unemployment rate (national estimate)": ("SL.UEM.TOTL.NE.ZS", "% of total labor force", "Share of the labor force without work but available for and seeking employment, using national estimates."),
    "GDP per capita": ("NY.GDP.PCAP.CD", "current US$ per person", "Gross domestic product divided by the population. This is not household income or average wealth."),
    "Crude birth rate": ("SP.DYN.CBRT.IN", "births per 1,000 people", "Annual number of live births per 1,000 people, not a total birth count."),
    "Net migration": ("SM.POP.NETM", "people", "Net number of migrants (immigration minus emigration) for the source period."),
    "Intentional homicide rate": ("VC.IHR.PSRC.P5", "homicides per 100,000 people", "Intentional homicides per 100,000 people."),
    "Consumer price inflation": ("FP.CPI.TOTL.ZG", "annual % change", "Annual percentage change in consumer prices."),
    "Central government debt": ("GC.DOD.TOTL.GD.ZS", "% of GDP", "Central government debt as a percentage of GDP; not all public-sector debt."),
    "Total reserves, including gold": ("FI.RES.TOTL.CD", "current US$", "Total reserves including gold, in current US dollars."),
    "External balance: goods and services": ("NE.RSB.GNFS.ZS", "% of GDP", "External balance on goods and services as a percentage of GDP; not the current account.")
}
WB_ROOT = "https://api.worldbank.org/v2/country/{country}/indicator/{indicator}"

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_world_bank(country_code, indicator_code, start_year, end_year):
    url = WB_ROOT.format(country=country_code, indicator=indicator_code)
    params = {"format": "json", "date": f"{start_year}:{end_year}", "per_page": 200}
    response = requests.get(url, params=params, timeout=25)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
        return pd.DataFrame(columns=["Year", "Value"])
    rows = [{"Year": int(item["date"]), "Value": float(item["value"])}
            for item in payload[1] if item.get("value") is not None]
    return pd.DataFrame(rows, columns=["Year", "Value"]).sort_values("Year").reset_index(drop=True)

def fit_polynomial(data, degree):
    clean = data.dropna(subset=["Year", "Value"]).copy()
    clean["Year"] = pd.to_numeric(clean["Year"], errors="coerce")
    clean["Value"] = pd.to_numeric(clean["Value"], errors="coerce")
    clean = clean.dropna().sort_values("Year")
    if clean["Year"].duplicated().any():
        raise ValueError("The working table contains duplicate years. Keep only one row per year.")
    if len(clean) < degree + 1:
        raise ValueError(f"Degree {degree} requires at least {degree + 1} distinct year/value rows; currently there are {len(clean)}.")
    years = clean["Year"].to_numpy(dtype=float)
    values = clean["Value"].to_numpy(dtype=float)
    base_year = int(np.min(years))
    t = years - base_year
    coeffs = np.polynomial.polynomial.polyfit(t, values, degree)
    predicted = np.polynomial.polynomial.polyval(t, coeffs)
    mae = float(mean_absolute_error(values, predicted))
    r2 = float(r2_score(values, predicted)) if len(values) > 1 else float("nan")
    return {"data": clean, "years": years, "values": values, "base": base_year,
            "coeffs": coeffs, "predicted": predicted, "mae": mae, "r2": r2,
            "degree": degree, "min_year": int(years.min()), "max_year": int(years.max())}

def predict(model, year):
    return float(np.polynomial.polynomial.polyval(float(year) - model["base"], model["coeffs"]))

def equation_text(model):
    terms = []
    for power, coefficient in enumerate(model["coeffs"]):
        terms.append(f"{coefficient:.6g}" if power == 0 else f"{coefficient:+.6g}·t^{power}")
    return "y = " + " ".join(terms) + f", where t = year − {model['base']}"

def make_chart(data, model, horizon, sample_step, comparison_frames, indicator, unit, single_year=None, single_value=None):
    fig, ax = plt.subplots(figsize=(10, 5.2))
    ax.scatter(data["Year"], data["Value"], label="Observed / working data", s=28)
    lo, hi = model["min_year"], model["max_year"]
    xs = np.linspace(lo, hi + horizon, max(200, (hi + horizon - lo) * 3))
    ys = np.array([predict(model, x) for x in xs])
    ax.plot(xs[xs <= hi], ys[xs <= hi], label="Polynomial fit (historical range)", linewidth=2)
    if horizon > 0:
        ax.plot(xs[xs > hi], ys[xs > hi], label="Extrapolated model segment", linewidth=2, linestyle="--")
    sampled = np.arange(lo, hi + horizon + 1, sample_step)
    ax.scatter(sampled, [predict(model, x) for x in sampled], marker="x", s=24, label=f"Sampled model points (every {sample_step} year(s))")
    for country_name, frame in comparison_frames:
        if not frame.empty:
            ax.plot(frame["Year"], frame["Value"], marker=".", linewidth=1.5, label=f"{country_name} observed")
    if single_year is not None and single_value is not None:
        ax.scatter([single_year], [single_value], marker="D", s=65, label=f"Estimate for {single_year}")
    ax.axvline(hi, linestyle=":", linewidth=1.5, label=f"Historical boundary ({hi})")
    ax.set_title(f"{indicator} — {unit}")
    ax.set_xlabel("Year")
    ax.set_ylabel(unit)
    ax.grid(True, alpha=.25)
    ax.legend(fontsize=8, loc="best")
    fig.tight_layout()
    return fig

def csv_bytes(df):
    return df.to_csv(index=False).encode("utf-8")

def xlsx_bytes(summary, data, results):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        pd.DataFrame([summary]).to_excel(writer, index=False, sheet_name="Summary")
        data.to_excel(writer, index=False, sheet_name="Working Data")
        if results is not None and not results.empty:
            results.to_excel(writer, index=False, sheet_name="Calculated Years")
    return output.getvalue()

def pdf_bytes(summary, data, results, chart_png):
    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(letter), rightMargin=28, leftMargin=28, topMargin=24, bottomMargin=24)
    styles = getSampleStyleSheet()
    story = [Paragraph("Hispanic Heritage Historical Data Explorer", styles["Title"]), Spacer(1, 8)]
    for key in ["Country", "Indicator", "Indicator code", "Units", "Source", "Retrieved", "Coverage", "Observations", "Degree", "Base year", "Equation", "R-squared (in-sample)", "MAE (in-sample)", "Data status"]:
        story.append(Paragraph(f"<b>{key}:</b> {str(summary.get(key, ''))}", styles["BodyText"]))
    story += [Spacer(1, 8), Image(io.BytesIO(chart_png), width=650, height=330), Spacer(1, 8)]
    story.append(Paragraph("<b>Limitations:</b> Polynomial fit metrics describe fit to the same data used for fitting. They do not prove forecasting accuracy. Extrapolations can become implausible; validated prediction intervals are not provided. Data gaps and differences in national statistical methods may affect comparisons.", styles["BodyText"]))
    story.append(Spacer(1, 8))
    preview = data.head(18).round(4).values.tolist()
    story.append(Paragraph("<b>Working data preview (first 18 rows)</b>", styles["Heading2"]))
    table_data = [["Year", "Value"]] + [[str(int(y)), str(v)] for y, v in preview]
    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0,0),(-1,0),colors.HexColor("#e7edf5")), ("GRID",(0,0),(-1,-1),.4,colors.grey), ("PADDING",(0,0),(-1,-1),4)]))
    story.append(table)
    if results is not None and not results.empty:
        story += [Spacer(1, 8), Paragraph("<b>Calculated-year results</b>", styles["Heading2"])]
        table_data = [list(results.columns)] + results.astype(str).values.tolist()
        table = Table(table_data[:31], repeatRows=1)
        table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e7edf5")),("GRID",(0,0),(-1,-1),.4,colors.grey),("FONTSIZE",(0,0),(-1,-1),8)]))
        story.append(table)
    doc.build(story)
    return output.getvalue()

st.title("📊 Hispanic Heritage Historical Data Explorer")
st.caption("Investigate real historical indicators, fit polynomial models, and interpret trends with care.")

with st.sidebar:
    st.header("Explore the data")
    country = st.selectbox("Main country", list(COUNTRIES.keys()), index=list(COUNTRIES.keys()).index("Ecuador"))
    indicator = st.selectbox("Indicator", list(INDICATORS.keys()), index=list(INDICATORS.keys()).index("Unemployment rate (national estimate)"))
    degree = st.slider("Polynomial degree", 3, 8, 3)
    sample_step = st.slider("Model marker interval (years)", 1, 10, 5)
    horizon = st.slider("Extend graph into future (years)", 0, 50, 5)
    comparison_countries = st.multiselect("Compare same indicator with", [c for c in COUNTRIES if c != country], default=["Colombia"])
    printer_view = st.toggle("Printer-friendly report view", value=False)

code, unit, definition = INDICATORS[indicator]
current_year = date.today().year
start_year, end_year = current_year - 70, current_year - 1
st.caption(f"Featured question: How has {indicator.lower()} changed in {country}, and how does its trend compare with selected Latin American countries?")
st.info("Brazil is included as a Latin American comparison; it is not a Spanish-speaking Hispanic country.")

try:
    with st.spinner(f"Retrieving official World Bank data for {country}..."):
        source_data = fetch_world_bank(COUNTRIES[country], code, start_year, end_year)
except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
    source_data = pd.DataFrame(columns=["Year", "Value"])
    st.error(f"World Bank data could not be retrieved right now: {exc}. Check your connection and try again later. No replacement data are fabricated.")

if source_data.empty:
    st.warning("No usable observations were returned for this country/indicator in the requested window. Try another indicator or country.")
    st.markdown(f"Source: [World Bank indicator page](https://data.worldbank.org/indicator/{code})")
    st.stop()

source_data = source_data.sort_values("Year").drop_duplicates("Year").reset_index(drop=True)
source_data["Year"] = source_data["Year"].astype(int)
source_data["Value"] = pd.to_numeric(source_data["Value"], errors="coerce")
state_key = f"working_{country}_{code}"
if state_key not in st.session_state:
    st.session_state[state_key] = source_data.copy()

left, right = st.columns([1.1, 1])
with left:
    st.subheader("Indicator and source")
    st.write(definition)
    st.write(f"**Code:** `{code}` · **Units:** {unit}")
    st.write(f"**Source:** [World Bank Open Data](https://data.worldbank.org/indicator/{code})")
    st.write(f"**Retrieved:** {date.today().isoformat()} · **Available coverage:** {int(source_data.Year.min())}–{int(source_data.Year.max())} · **Observations:** {len(source_data)}")
    st.caption(f"Requested search window: {start_year}–{end_year}; actual coverage depends on available official data.")
with right:
    st.subheader("Edit working data")
    if st.button("Reset working data to official source"):
        st.session_state[state_key] = source_data.copy()
        st.rerun()
    edited = st.data_editor(st.session_state[state_key], num_rows="dynamic", use_container_width=True, key=f"editor_{country}_{code}")
    st.session_state[state_key] = edited.copy()

working = st.session_state[state_key].copy()
working["Year"] = pd.to_numeric(working["Year"], errors="coerce")
working["Value"] = pd.to_numeric(working["Value"], errors="coerce")
working = working.dropna(subset=["Year", "Value"])
if not np.all(np.equal(working["Year"], np.floor(working["Year"]))):
    st.error("Years must be whole numbers. Correct the working table before fitting.")
    st.stop()
working["Year"] = working["Year"].astype(int)
if working["Year"].duplicated().any():
    st.error("Duplicate years are not allowed. Correct the working table before fitting.")
    st.stop()
if indicator == "Life expectancy at birth" and ((working.Value < 0) | (working.Value > 125)).any():
    st.error("Life expectancy values must be between 0 and 125 years.")
    st.stop()
if indicator in ["Unemployment rate (national estimate)", "Central government debt", "Consumer price inflation"] and (working.Value < 0).any() and indicator != "Consumer price inflation":
    st.error("This indicator cannot contain negative values. Correct the working table.")
    st.stop()
if indicator == "Crude birth rate" and (working.Value < 0).any():
    st.error("Crude birth rate cannot be negative.")
    st.stop()
if working.empty:
    st.error("There are no valid numeric rows in the working table.")
    st.stop()

edited_flag = not (len(working) == len(source_data) and
                   np.array_equal(working.sort_values("Year")["Year"].to_numpy(), source_data.sort_values("Year")["Year"].to_numpy()) and
                   np.allclose(working.sort_values("Year")["Value"].to_numpy(), source_data.sort_values("Year")["Value"].to_numpy()))
data_status = "User-modified scenario" if edited_flag else "Official source data (working copy unchanged)"
try:
    model = fit_polynomial(working, degree)
except ValueError as exc:
    st.error(str(exc))
    st.stop()

comparison_frames = []
for comparison_country in comparison_countries:
    try:
        frame = fetch_world_bank(COUNTRIES[comparison_country], code, start_year, end_year)
        if not frame.empty:
            comparison_frames.append((comparison_country, frame))
        else:
            st.warning(f"No data available for {comparison_country} for this indicator in the requested window; it was not substituted.")
    except requests.RequestException as exc:
        st.warning(f"Could not retrieve comparison data for {comparison_country}: {exc}")

st.subheader("Historical data and polynomial model")
metric_cols = st.columns(4)
metric_cols[0].metric("Observations", len(model["data"]))
metric_cols[1].metric("R² (in-sample)", f"{model['r2']:.4f}")
metric_cols[2].metric("MAE (in-sample)", f"{model['mae']:.4g} {unit}")
metric_cols[3].metric("Model degree", degree)
st.write(f"**Model equation:** `{equation_text(model)}`")
st.write(f"**Fitted range:** {model['min_year']}–{model['max_year']} · **Base year:** {model['base']} · **Data status:** {data_status}")
st.caption("R² and MAE describe the fit to the data used to build the model. They are not proof of forecasting accuracy. Validated prediction intervals are not provided.")
chart = make_chart(working, model, horizon, sample_step, comparison_frames, indicator, unit)
if printer_view:
    st.markdown("---")
    st.subheader("Printer-friendly summary")
    st.write(f"{country}: {indicator} ({unit}). Data coverage {model['min_year']}–{model['max_year']}; polynomial degree {degree}; MAE {model['mae']:.4g}. Extrapolations are uncertain and may be implausible.")
st.pyplot(chart, use_container_width=True)
if comparison_frames:
    st.write("**Comparison coverage:** " + "; ".join(f"{name}: {int(df.Year.min())}–{int(df.Year.max())} ({len(df)} observations)" for name, df in comparison_frames if not df.empty))

st.subheader("Calculate an estimate")
single_year = st.number_input("Year (1950–2100)", min_value=1950, max_value=2100, value=min(max(model["max_year"], 1950), 2100), step=1)
if st.button("Calculate value"):
    value = predict(model, int(single_year))
    kind = "within fitted range" if model["min_year"] <= single_year <= model["max_year"] else "extrapolation outside fitted range"
    observed = working.loc[working.Year == int(single_year), "Value"]
    st.session_state["single_result"] = {"Year": int(single_year), "Estimate": value, "Units": unit, "Calculation type": kind,
                                         "Observed value (if available)": float(observed.iloc[0]) if not observed.empty else None}
if "single_result" in st.session_state:
    res = st.session_state["single_result"]
    st.write(f"**{res['Year']}:** {res['Estimate']:.6g} {res['Units']} — {res['Calculation type']}.")
    if res["Observed value (if available)"] is not None:
        st.write(f"Observed value at this year: {res['Observed value (if available)']:.6g} {unit}. The model estimate is a fitted value, not a replacement for the observation.")
    if res["Calculation type"] == "extrapolation outside fitted range":
        st.warning("This is an extrapolation. Check whether it is plausible in context; polynomial models can behave unrealistically outside their data range.")

st.subheader("Batch estimates")
batch_mode = st.radio("Request type", ["Year range", "Custom years"], horizontal=True)
requested_years = []
if batch_mode == "Year range":
    c1, c2, c3 = st.columns(3)
    with c1: batch_start = st.number_input("Start year", 1950, 2100, max(1950, model["min_year"]), 1)
    with c2: batch_end = st.number_input("End year", 1950, 2100, min(2100, max(model["min_year"] + 5, model["min_year"] + 1)), 1)
    with c3: batch_step = st.number_input("Step (1–10)", 1, 10, 1, 1)
    if batch_end > batch_start:
        requested_years = list(range(int(batch_start), int(batch_end) + 1, int(batch_step)))
    else:
        st.warning("End year must be greater than start year.")
else:
    custom_text = st.text_input("Comma-separated years", value=f"{model['min_year']},{model['max_year']},{min(2100, model['max_year']+5)}")
    valid, invalid = [], []
    for token in custom_text.split(","):
        token = token.strip()
        try:
            yr = int(token)
            if 1950 <= yr <= 2100: valid.append(yr)
            else: invalid.append(token)
        except ValueError:
            if token: invalid.append(token)
    requested_years = list(dict.fromkeys(valid))
    if invalid: st.warning("Ignored invalid or out-of-range entries: " + ", ".join(invalid))
st.write("**Valid years to calculate:** " + (", ".join(map(str, requested_years)) if requested_years else "None"))
if st.button("Calculate batch", disabled=not requested_years):
    rows = []
    for yr in requested_years:
        typ = "within fitted range" if model["min_year"] <= yr <= model["max_year"] else "extrapolation outside fitted range"
        if yr in set(working.Year):
            typ = "fitted value at observed year"
        rows.append({"Year": yr, "Estimate": predict(model, yr), "Units": unit, "Calculation type": typ})
    st.session_state["batch_results"] = pd.DataFrame(rows)
if "batch_results" in st.session_state:
    batch_results = st.session_state["batch_results"]
    st.dataframe(batch_results, use_container_width=True)
else:
    batch_results = pd.DataFrame()

st.subheader("Download reports")
summary = {"Country": country, "Indicator": indicator, "Indicator code": code, "Units": unit,
           "Source": f"https://data.worldbank.org/indicator/{code}", "Retrieved": date.today().isoformat(),
           "Coverage": f"{model['min_year']}–{model['max_year']}", "Observations": len(model["data"]),
           "Degree": degree, "Base year": model["base"], "Equation": equation_text(model),
           "R-squared (in-sample)": model["r2"], "MAE (in-sample)": model["mae"], "Data status": data_status}
results_for_export = st.session_state.get("batch_results", pd.DataFrame())
st.download_button("Download working data (CSV)", csv_bytes(working.sort_values("Year")), file_name=f"{country}_{code}_working_data.csv", mime="text/csv")
st.download_button("Download Excel workbook (.xlsx)", xlsx_bytes(summary, working.sort_values("Year"), results_for_export), file_name=f"{country}_{code}_explorer.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
chart_buffer = io.BytesIO()
chart.savefig(chart_buffer, format="png", dpi=160, bbox_inches="tight")
st.download_button("Download PDF report", pdf_bytes(summary, working.sort_values("Year"), results_for_export, chart_buffer.getvalue()), file_name=f"{country}_{code}_report.pdf", mime="application/pdf")

st.markdown("---")
st.subheader("Research notes")
st.markdown("""
- **Finding prompt 1:** Describe the overall direction of the observed series without claiming that the indicator alone explains why it changed.
- **Finding prompt 2:** Compare the two countries only where the same indicator, units, and coverage make the comparison reasonable.
- **Finding prompt 3:** Compare degree 3 with another degree and discuss changes in the graph, R², MAE, and residuals.
- **Limitations:** World Bank series can have missing years; national estimates may use different methods; a polynomial fitted to past observations can behave implausibly in future years.
- **Uncertainty:** Residual error/MAE summarizes historical fit error. This app does not provide statistically validated prediction intervals.
""")
st.caption("Built for a student research showcase. Verify source values, calculations, and downloads before presenting.")
