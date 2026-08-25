# Final Public + Product Integration UAT

Target architecture:

- `index.html` → Public Landing Page
- `app.html` → Functional Analytics Application

## Automated gates

- Public/Product entry separation guard passes.
- Landing static smoke passes against `index.html`.
- Product static/JSDOM tests pass against `app.html`.
- Text-size preference control (`A / A+ / A++`) and persistence smoke passes.
- CSV and XLSX loader smoke passes.
- Full six-step Start → Results journey passes.
- Ordinal target/state freshness smoke passes.
- Browser Landing → Product CTA navigation passes at desktop/tablet/mobile.
- Functional browser visual smoke passes at desktop/tablet/mobile with the new default `A+` text size.
- No page-level horizontal overflow or unexpected browser errors.
- Backend compile + pytest remains passing without integration-specific backend changes.

## Manual Combined UAT

Use the detailed step-by-step checklist:

- `docs/MANUAL_COMBINED_UAT_CHECKLIST.md`

Windows helper:

- `tools/start-manual-uat.bat`

The launcher now starts both:

- Public/Product web server: `http://127.0.0.1:8000/`
- validated local FastAPI: `http://127.0.0.1:8001/`

When `app.html` is opened from `localhost` or `127.0.0.1`, the Product automatically uses the local FastAPI on port `8001`. GitHub Pages/production continues to use the Render API unless an explicit API-base override is supplied. This prevents Manual UAT from depending on an undeployed Final Integration backend.

Manual UAT covers:

1. Public Landing rendering and TH/EN behavior.
2. Landing primary CTA → relative `app.html`.
3. Product text size control and persistence.
4. Functional Start → Data Profile → Analyze → Prepare → Setup → Results.
5. Real local backend execution, not a browser mock.
6. CSV classification regression check using `sample-data/uat-journey.csv`.
7. XLSX loader check.
8. Desktop/tablet/mobile responsive checks.
9. Public/Product separation and direct-entry reload checks.

## Separation regression

Public Landing must not import Product runtime such as `src/app.js`, `src/state.js`, `src/journey.js`, or `src/ai-analytics.js`.

Product `app.html` must not import `src/landing.css` or `src/landing*.js`.

Landing must not call `/analyze` or `/capabilities`; backend interaction remains Product-owned.

## API routing regression

- Local Product origin (`localhost` / `127.0.0.1`) defaults to `http://127.0.0.1:8001` for Manual UAT.
- Non-local Product origins default to `https://ku-open-data-analytics-api.onrender.com`.
- `window.KU_ANALYTICS_API_BASE` remains an explicit override contract.
- Step 5 `/capabilities` and Step 5/6 `/analyze` share the same resolved API base.

## GitHub Pages path regression

- Local authored assets use relative repository paths.
- Landing CTA uses relative `app.html`.
- Neither entry assumes deployment at domain root.

## Deferred / not part of this integration

- Contact endpoint remains separately approved work.
- `?demo=` / `?intent=` deep-link contracts remain unimplemented.
- Merge to `main` and production deployment require explicit approval.
