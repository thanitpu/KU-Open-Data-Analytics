# Analytics App Entry Migration UAT

This checklist supports the accepted frontend architecture where the Public Landing Page will use `index.html` and the Functional Analytics Workspace uses `app.html`.

## Current transition state

- `app.html` is now the canonical Functional/Product entry.
- Frontend CI sets `KU_APP_ENTRY=app.html`.
- Root `index.html` remains a temporary compatibility mirror of `app.html` on the Functional branch only.
- `tests/frontend_entry_guard.js` requires that compatibility mirror to remain byte-equivalent during this transition, preventing silent Product-shell divergence.
- Product runtime code must not depend on the entry filename.
- Public Landing promotion has **not** happened yet.

## Functional migration checks

- `node tests/frontend_entry_guard.js` passes with `app.html` as the configured entry.
- Application shell CSS/JS references are relative, e.g. `src/app.css` and `src/app.js`, not `/src/...`.
- Runtime `src/*.js` contains no hard-coded `index.html` navigation.
- Runtime navigation contains no root-absolute redirect that assumes the app is hosted at `/`.
- Static smoke, JSDOM journey smoke, Ordinal target smoke, and browser visual smoke all read/open `${KU_APP_ENTRY}` and require it to be `app.html`.
- Static preview health check requests `${KU_APP_ENTRY}` rather than `/`.
- Current compatibility `index.html` still opens the same Functional Application until Final Integration.
- Backend/API contracts are unchanged by this migration.

## Final Landing integration checks — still deferred

1. Re-audit the Landing handoff branch/PR and confirm only Landing-owned files are promoted.
2. Replace the temporary Product compatibility `index.html` with the approved Public Landing source of truth.
3. In the same explicit integration step, remove/adjust the temporary `index.html === app.html` mirror assertion from `tests/frontend_entry_guard.js`.
4. Keep `app.html` as the canonical Product entry and keep Product CI/tests targeting `app.html`.
5. Verify Landing CTA opens relative `app.html`.
6. Verify Landing and Product CSS/JS remain isolated.
7. Verify GitHub Pages resolves relative Landing and Product assets correctly.
8. Run Landing smoke + full frontend CI + responsive Chromium UAT + route-level Functional UAT.
9. Verify API base/CORS behavior is unchanged.
10. Verify no Landing presentation/demo analytics enters Product state, analytical engines, or backend.
11. Do not add `app.html?demo=...` / `?intent=...` behavior until a separate Product-side deep-link contract is approved.

## Separation regression

Landing integration must not overwrite or substitute:

- `src/app.js`
- `src/analysis.js`
- `src/ai-analytics.js`
- `src/state.js`
- `src/journey.js`
- `src/workflow-steps.js`
- `src/data-profile.js`
- `src/result-*.js`
- `backend/*`
- analytical tests/engines

Prototype/Landing code is a visual/public-layer input only; the Functional GitHub codebase remains the source of truth for analytical behavior.
