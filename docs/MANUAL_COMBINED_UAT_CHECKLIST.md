# KU Open Data Analytics — Manual Combined UAT Checklist

Target architecture under test:

- `index.html` → Public Landing Page
- `app.html` → Functional Analytics Application
- Primary Landing CTA → relative `app.html`

Branch under test:

- `integration/final-public-product-ready`

## 0. Start the UAT environment

### Recommended on Windows

1. Checkout/download branch `integration/final-public-product-ready`.
2. In the repository, double-click:
   - `tools/start-manual-uat.bat`
3. On the first run, the launcher checks the Python backend dependencies and installs `backend/requirements.txt` if required.
4. Keep **both** command windows open:
   - Public/Product web server: `http://127.0.0.1:8000/`
   - Local FastAPI: `http://127.0.0.1:8001/`
5. The launcher validates `/health`, `/capabilities`, and CORS before opening the browser.
6. The browser should open:
   - `http://127.0.0.1:8000/index.html`

When the Product is opened from `localhost` or `127.0.0.1`, it automatically uses the validated local FastAPI on port `8001`. On GitHub Pages/production it continues to use the configured Render API. This lets Manual UAT validate the branch backend without deploying it first.

### Manual alternative

From the repository root, open two terminals.

Terminal 1 — backend:

```bash
py -m pip install -r backend/requirements.txt
py -m uvicorn app.api:app --app-dir backend --host 127.0.0.1 --port 8001
```

Terminal 2 — frontend:

```bash
py tools/uat_static_server.py
```

Then open:

`http://127.0.0.1:8000/index.html`

You can verify the backend directly at:

`http://127.0.0.1:8001/health`

Expected response contains `"status":"ok"`.

## 1. Core Combined UAT — required before merge

Record each item as `PASS`, `FAIL`, or `N/A`.

| ID | Navigation / action | Expected result | Result |
|---|---|---|---|
| C01 | Open `/index.html` | Public Landing loads; Product workspace/sidebar is not shown | |
| C02 | Review Landing header + Hero | KU branding, Thai copy, Hero visual, and primary CTA render correctly | |
| C03 | Click TH / EN | Language switches without broken layout; switching back works | |
| C04 | Refresh after language switch | Selected language preference remains consistent | |
| C05 | Click Product / Services / Training / Organizations / About navigation | Page moves to the expected Landing section | |
| C06 | Click Hero **เริ่มวิเคราะห์ข้อมูล / Start analyzing** | URL changes to `/app.html` and Functional Application opens | |
| C07 | On `/app.html` | Six-step journey appears: Start → Data Profile → Analyze → Prepare → Setup → Results | |
| C07A | Header → **Text size** | `A`, `A+`, `A++` are available; default is `A+`; changing size enlarges/reduces analytical text without breaking layout; refresh preserves the selected size | |
| C08 | Click **Load Demo** | Demo dataset loads; row/field summary populates; Data Profile becomes available | |
| C09 | Step 2 → Data Profile | Overview / Fields / Data Quality / Relationships render from the loaded dataset | |
| C10 | Step 3 → Analyze | Question Type, Target, and Predictors work; recommended analytical family is derived | |
| C11 | Continue to Prepare | Step 4 shows preparation summary for the current analysis | |
| C12 | Complete any required review | Required review items unblock approval | |
| C13 | Click **Approve Preparation →** | Step 5 Setup opens successfully | |
| C14 | Review Recommended Setup | Backend capability metadata loads; no `Backend setup metadata unavailable` or `Failed to fetch`; Technical Run Specification shows Backend API version | |
| C15 | Click **Run recommended analysis →** | Real local backend analysis completes | |
| C16 | Results | Answer-first validated result, evidence, diagnostics/details, warnings, and technical payload render correctly | |
| C17 | Change predictor / relevant metadata after a validated result | Previous result is preserved only for comparison and marked stale according to freshness rules | |

## 2. Loader regression

- CSV: load `sample-data/uat-journey.csv`; preview, row count, and fields must populate.
- XLSX: load an Excel workbook; if it has multiple sheets, change sheet and load it; preview and metadata must follow the selected sheet.

## 3. Responsive regression

Check Product `app.html` at approximately:

- Desktop: 1440 × 900
- Tablet: 900 × 1000
- Mobile: 390 × 844

Expected:

- no page-level horizontal overflow;
- active workflow step stays visible in the horizontal journey on Tablet/Mobile;
- header and Step Workflow both remain sticky on Tablet/Mobile;
- Step Workflow stays immediately below the actual wrapped header height, including after changing A/A+/A++;
- Font Size / Load Demo / Import CSV/XLSX controls remain inside the header and never float over main content;
- main content begins below the Step Workflow and remains reachable while scrolling;
- tables may scroll inside their own containers without widening the page.

## 4. Public / Product separation regression

- Reload `/index.html`: Landing remains independent from Product state and FastAPI.
- Reload `/app.html`: Product opens directly without requiring Landing first.
- Landing CTA remains relative `app.html`.
- Landing styling/runtime does not appear inside Product and Product analytical runtime does not appear inside Landing.

## 5. Sign-off

Manual Combined UAT can be accepted when the Public journey, Product Steps 1–6, CSV/XLSX, real local FastAPI execution, and responsive checks above are all PASS. Merge to `main` and production deployment remain separate explicit approvals.
