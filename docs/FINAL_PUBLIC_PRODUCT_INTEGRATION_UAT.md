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

## Manual Combined UAT

Use the detailed step-by-step checklist:

- `docs/MANUAL_COMBINED_UAT_CHECKLIST.md`

Windows helper:

- `tools/start-manual-uat.bat`

The launcher serves the repository from `http://127.0.0.1:8000/` so the manual browser test uses a local origin already allowed by the validated backend CORS defaults.

Manual UAT covers:

1. Public Landing rendering and TH/EN behavior.
2. Landing primary CTA → relative `app.html`.
3. Functional Start → Data Profile → Analyze → Prepare → Setup → Results.
4. Real backend execution, not a browser mock.
5. CSV classification regression check using `sample-data/uat-journey.csv`.
6. XLSX loader check.
7. Desktop/tablet/mobile responsive checks.
8. Public/Product separation and direct-entry reload checks.

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
