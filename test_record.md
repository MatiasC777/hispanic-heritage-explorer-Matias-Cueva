# Test record template

Record the actual result after testing locally and on Render. Do not mark a test passed until you have performed it.

| # | Test | Expected behavior | Actual result / correction |
|---|---|---|---|
| 1 | Compare two displayed source values with the official World Bank page | Values, units, and years agree | Pending |
| 2 | Edit one value, then reset | Model changes after edit; reset restores source data | Pending |
| 3 | Insert duplicate year / remove rows below degree minimum | Duplicate rejected; fitting explains minimum rows | Pending |
| 4 | Independently check one model prediction and R²/MAE | Displayed values agree within rounding | Pending |
| 5 | Calculate same year singly and in a batch | Estimates agree | Pending |
| 6 | Try invalid custom years and an unavailable series/API failure | Invalid entries are explained; no fake data appear | Pending |
| 7 | Change comparison, sample interval, horizon, and printer view | Each control visibly changes its intended output | Pending |
| 8 | Open CSV, XLSX, and PDF on the deployed app | All are valid files and reflect current selection | Pending |

Deployment URL: [add Render URL]
