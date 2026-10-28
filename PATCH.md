# candidate-01: COVID-19 data patch

Overwrite:
- `scripts/update_status.py`
- `.github/workflows/update-status.yml`

Behavior:
- Searches the previous 45 days, newest first.
- Tries both `YYYYMMDD-disease_YEAR.csv` and `YYYYMMDD_disease_YEAR.csv`.
- For COVID-19, also accepts both `covid-19` and `covid_19` disease labels.
- Validates the CSV header and uses the `横浜市` column.
- Writes influenza and COVID-19 into `data/status.json`.
- Preserves old top-level influenza keys so the current display should continue to work.
- Does not overwrite the existing JSON if either official CSV cannot be fetched or validated.

Not included:
- UI changes to `index.html`, `style.css`, and `app.js`, because their current repository contents could not be read from this environment.
- GitHub publication or Actions execution.
