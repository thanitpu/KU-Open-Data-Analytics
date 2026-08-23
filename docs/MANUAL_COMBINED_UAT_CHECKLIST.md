# KU Open Data Analytics — Manual Combined UAT Checklist

Target architecture under test:

- `index.html` → Public Landing Page
- `app.html` → Functional Analytics Application
- Primary Landing CTA → relative `app.html`

Branch under test:

- `integration/final-public-product-ready`

## 0. Start the UAT environment

### Recommended on Windows

1. Checkout branch `integration/final-public-product-ready`.
   - GitHub Desktop: **Current Branch → Choose a branch → integration/final-public-product-ready**.
   - Command line alternative:

```bash
git fetch origin
git switch integration/final-public-product-ready
git pull --ff-only
```

2. In the repository, double-click:
   - `tools/start-manual-uat.bat`
3. Keep the server window open.
4. The browser should open:
   - `http://127.0.0.1:8000/index.html`

Port `8000` is intentional because the validated backend CORS configuration allows the local UAT origin at `127.0.0.1:8000` / `localhost:8000`.

### Manual alternative

From the repository root:

```bash
py -m http.server 8000 --bind 127.0.0.1
```

Then open:

`http://127.0.0.1:8000/index.html`

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
| C08 | Click **Load Demo** | Demo dataset loads; row/field summary populates; Data Profile becomes available | |
| C09 | Open **Data Profile** | Overview/Fields/Data Quality/Relationships render without errors | |
| C10 | Continue to **Analyze** | Question Type controls and target selection work | |
| C11 | Select **Predict an outcome** → target `Satisfaction` | Analytical family resolves to Regression | |
| C12 | Continue to **Prepare** | Recognized ordinal coding `Low < Medium < High` is shown under automatically handled; no unknown-order blocker | |
| C13 | Click **Approve Preparation →** | Setup unlocks | |
| C14 | Open **Setup** | Recommended Setup loads from validated backend; backend/API version is shown; Technical Run Specification remains secondary/collapsed | |
| C15 | Click **Run recommended analysis →** | Real backend analysis runs; no CORS/network error | |
| C16 | View **Results** | Answer-first result renders; Target Coding shows Low/Medium/High rank mapping; warning notes ordered ranks do not imply equal spacing | |
| C17 | Use browser Back to Landing or manually reopen `/index.html` | Public Landing still renders normally; Product state/scripts do not leak into Landing | |

### Core gate decision

- **PASS:** all C01–C17 pass, excluding only explicitly approved N/A items.
- **FAIL:** any navigation, backend execution, responsive, or entry-separation failure blocks merge.

## 2. CSV Classification Regression Check — required

Use the repository file:

`sample-data/uat-journey.csv`

| ID | Navigation / action | Expected result | Result |
|---|---|---|---|
| F01 | From `/app.html`, upload `sample-data/uat-journey.csv` | 30 rows and 8 fields load successfully | |
| F02 | Data Profile → Fields | `customer_id`, `age`, `income`, `visits`, `region`, `segment_label`, `churn`, `spend` are present | |
| F03 | Analyze → **Predict an outcome** → target `churn` | Route resolves to Binary Classification | |
| F04 | Review predictors | Identifier-like `customer_id` is not treated as a normal predictive feature by default | |
| F05 | Prepare | No class-count preflight blocker; both churn classes have sufficient observations | |
| F06 | Approve → Setup → Run | Backend execution completes successfully | |
| F07 | Results | Classification answer/evidence renders from validated payload; confusion-matrix/diagnostic content is present | |

## 3. XLSX Loader Check — required

Use a small `.xlsx` file with a header row and at least several data rows. The easiest controlled test is:

1. Open `sample-data/uat-journey.csv` in Excel.
2. Save As `uat-journey.xlsx`.
3. Upload that `.xlsx` in `/app.html`.

| ID | Navigation / action | Expected result | Result |
|---|---|---|---|
| X01 | Upload `uat-journey.xlsx` | Workbook loads without error | |
| X02 | If workbook has one sheet | Dataset loads directly; rows/fields match the source data | |
| X03 | If workbook has multiple sheets | Sheet selector works and selected sheet loads | |
| X04 | Data Preview | Values and headers are preserved correctly | |

## 4. Responsive Combined UAT — required

Use browser DevTools responsive mode or resize the browser.

### Desktop — approximately 1440 × 900

| ID | Check | Expected result | Result |
|---|---|---|---|
| R01 | Landing | Full navigation and Hero CTA visible; no horizontal page scroll | |
| R02 | App | Sidebar journey visible; tables stay within content area | |

### Tablet — approximately 900 × 1000

| ID | Check | Expected result | Result |
|---|---|---|---|
| R03 | Landing | Layout reflows without overlap or clipped content | |
| R04 | Landing CTA → App | Navigation still reaches `app.html` | |
| R05 | App | Journey becomes horizontal; active step remains visible; no page-level horizontal overflow | |

### Mobile — approximately 390 × 844

| ID | Check | Expected result | Result |
|---|---|---|---|
| R06 | Landing | Mobile menu/layout works; Hero CTA remains visible even if desktop/header CTA is hidden | |
| R07 | Landing CTA → App | Hero CTA opens `app.html` | |
| R08 | App | Horizontal journey works; active step remains in view; content does not widen the page | |
| R09 | Tables/details | Wide content scrolls inside its own container rather than widening the whole page | |

## 5. Separation / Regression Checks — required

| ID | Check | Expected result | Result |
|---|---|---|---|
| S01 | Landing `/index.html` | No Product sidebar/workspace appears | |
| S02 | App `/app.html` | No Landing header/footer appears | |
| S03 | Landing actions | Landing does not trigger analytics API calls by itself | |
| S04 | App analysis | `/capabilities` and `/analyze` remain Product-owned and functional | |
| S05 | Directly reload `/app.html` | App loads correctly without first visiting Landing | |
| S06 | Directly reload `/index.html` | Landing loads correctly without backend availability being required for rendering | |

## 6. Known deferred items — do not mark as defects

The following are intentionally outside this merge gate:

- Contact CTA endpoint is not yet approved.
- `app.html?demo=...` deep links are not implemented.
- `app.html?intent=...` deep links are not implemented.
- Production deployment / Render tracked-branch changes are not part of this UAT.

## 7. How to report a failure

For any failed item, send:

```text
UAT ID: C15
Status: FAIL
URL: http://127.0.0.1:8000/app.html
Browser / viewport: Chrome / Desktop 1440x900
Action: Clicked Run recommended analysis
Expected: Validated analysis completes
Actual: <what happened>
Console / network error: <if visible>
Screenshot: <attach if useful>
```

One failed UAT ID is enough for the Functional workstream to locate the relevant layer quickly.

## 8. Final manual sign-off

Fill this only after completing the required sections:

```text
MANUAL COMBINED UAT

Branch: integration/final-public-product-ready
Public Landing: PASS / FAIL
Landing → App CTA: PASS / FAIL
Functional Step 1–6: PASS / FAIL
Real backend execution: PASS / FAIL
CSV: PASS / FAIL
XLSX: PASS / FAIL
Desktop responsive: PASS / FAIL
Tablet responsive: PASS / FAIL
Mobile responsive: PASS / FAIL
Public/Product separation: PASS / FAIL

Blocking issues:
- NONE
or
- <UAT IDs>

Decision:
READY FOR MERGE REVIEW / NOT READY
```

Do not merge PR #13 or deploy solely because automated CI passed; manual sign-off is the final acceptance gate.
