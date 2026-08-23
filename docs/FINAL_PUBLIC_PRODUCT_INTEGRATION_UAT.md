# Final Public + Product Integration UAT

Target architecture:

- `index.html` → Public Landing Page
- `app.html` → Functional Analytics Application

## Automated gates

- Public/Product entry separation guard passes.
- Landing static smoke passes against `index.html`.
- Product static/JSDOM tests pass against `app.html`.
- CSV and XLSX loader smoke passes.
- Full six-step Start → Results journey passes.
- Ordinal target/state freshness smoke passes.
- Browser Landing → Product CTA navigation passes at desktop/tablet/mobile.
- Functional browser visual smoke passes at desktop/tablet/mobile.
- No page-level horizontal overflow or unexpected browser errors.
- Backend compile + pytest remains passing without integration-specific backend changes.

## Manual navigation UAT

1. Open `index.html`.
   - Expected: Public KU Open Data Analytics Landing renders.
   - Expected: TH/EN controls and Landing navigation remain usable.
2. Click **Start analyzing / เริ่มวิเคราะห์ข้อมูล**.
   - Expected: browser opens relative `app.html`.
3. Confirm Product Start page.
   - Expected: six-step Analysis Journey is visible.
4. Load Demo.
   - Expected: rows/fields populate and Data Profile unlocks.
5. Continue through Data Profile → Analyze → Prepare → Setup → Results.
   - Expected: validated Product behavior remains unchanged.
6. Upload a CSV and an XLSX file.
   - Expected: both load without entry-path regressions.

## Separation regression

Public Landing must not import Product runtime such as `src/app.js`, `src/state.js`, `src/journey.js`, or `src/ai-analytics.js`.

Product `app.html` must not import `src/landing.css` or `src/landing*.js`.

Landing must not call `/analyze` or `/capabilities`; backend interaction remains Product-owned.

## GitHub Pages path regression

- Local authored assets use relative repository paths.
- Landing CTA uses relative `app.html`.
- Neither entry assumes deployment at domain root.

## Deferred / not part of this integration

- Contact endpoint remains separately approved work.
- `?demo=` / `?intent=` deep-link contracts remain unimplemented.
- Merge to `main` and production deployment require explicit approval.
