# Analytics App Entry Migration UAT

This checklist supports the accepted frontend architecture where the Public Landing Page will use `index.html` and the functional analytics workspace will use `app.html`.

## Current transition state

- Functional app entry remains `index.html` temporarily.
- Frontend CI sets `KU_APP_ENTRY=index.html`.
- Product runtime code must not depend on the entry filename.

## Checks to run now

- `node tests/frontend_entry_guard.js` passes.
- Application shell CSS/JS references are relative, e.g. `src/app.css` and `src/app.js`, not `/src/...`.
- Runtime `src/*.js` contains no hard-coded `index.html` navigation.
- Runtime navigation contains no root-absolute redirect that assumes the app is hosted at `/`.
- Browser smoke opens the app using `${KU_APP_ENTRY}` rather than the site root.
- Static preview health check requests `${KU_APP_ENTRY}` rather than `/`.

## Checks when Landing integration begins

1. Move/copy the functional shell to `app.html` and make it the authoritative Product-layer entry.
2. Change frontend CI `KU_APP_ENTRY` from `index.html` to `app.html`.
3. Update the remaining JSDOM tests that directly read `index.html` to use the configured app entry.
4. Put the Public Landing Page at `index.html` without importing Product analytical logic into Landing JS.
5. Verify Landing CTA opens `app.html`.
6. Verify GitHub Pages resolves relative Product assets correctly from `app.html`.
7. Run full frontend CI, responsive Chromium visual smoke, and route-level functional UAT.
8. Verify API base/CORS behavior is unchanged by the entry-file move.
9. Verify future query strings on `app.html` do not interfere with the existing six-step initial state when no supported deep-link behavior is requested.

## Separation regression

Landing integration must not overwrite or substitute:

- `src/app.js`
- `src/analysis.js`
- `src/ai-analytics.js`
- functional state/journey modules
- `backend/*`
- analytical tests/engines

Prototype/Landing code is a visual/public-layer input only; the functional GitHub codebase remains the source of truth for analytical behavior.
