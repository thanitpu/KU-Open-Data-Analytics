# KU Open Data Analytics — Functional App Handoff

## 1. Functional source of truth
The canonical Functional Analytics Application entry is now:

- `app.html`

Product runtime remains owned by the Functional workstream, including:

- `src/app.js`
- `src/app.css`
- `src/state.js`
- `src/journey.js`
- `src/workflow-steps.js`
- `src/data-profile.js`
- `src/analysis.js`
- `src/ai-analytics.js`
- `src/result-*.js`
- `backend/*`

## 2. Branch
`integration/v62-shell-state`

The authoritative current head SHA should be read from the branch/PR because documentation updates create later commits.

## 3. Entry migration completed
- `app.html` was created from the current Functional `index.html` shell without changing Product behavior.
- Frontend CI now uses `KU_APP_ENTRY=app.html`.
- Static, JSDOM, Ordinal, and Playwright browser tests target `app.html`.
- Runtime Product JS remains filename-independent and contains no hard-coded `index.html` navigation.
- Product CSS/JS includes remain relative to the repository root.

## 4. Temporary compatibility entry
During the transition only:

- `index.html` remains an exact compatibility mirror of `app.html` on the Functional branch.
- `tests/frontend_entry_guard.js` fails if the two Product shells diverge.

This mirror is temporary. In Final Integration, Public Landing will replace root `index.html` and the mirror assertion must be intentionally removed/changed in the same integration step.

## 5. Landing contract compatibility
The reviewed Landing handoff expects:

`Start analyzing → app.html`

This contract is now compatible with the Functional branch.

No Product deep-link behavior is implemented for `?demo=` or `?intent=`. Those remain deferred pending a separately approved contract.

## 6. Files created in this migration
- `app.html`
- `docs/FUNCTIONAL_APP_HANDOFF.md`

## 7. Files modified in this migration
- `.github/workflows/frontend-ci.yml`
- `tests/frontend_entry_guard.js`
- `tests/frontend_smoke.js`
- `tests/frontend_dom_smoke.js`
- `tests/frontend_ordinal_smoke.js`
- `tests/frontend_visual_smoke.js`
- `docs/APP_ENTRY_MIGRATION_UAT.md`

## 8. Files intentionally not modified
Landing-owned files are untouched:

- `landing-preview.html`
- `src/landing.css`
- `src/landing.js`
- `src/landing-copy.js`
- `src/landing-content.js`
- `assets/landing/*`

Backend is untouched.

## 9. Hard-coded entry dependencies found
The Functional runtime did not contain a blocking `index.html` dependency. Migration-specific references were limited to test/CI infrastructure:

- Frontend CI canonical entry value.
- Static frontend smoke shell reader.
- Full JSDOM journey shell reader.
- Ordinal JSDOM shell reader.
- Playwright default Product entry.

Those Product test/config references now use `app.html`.

Architecture/documentation references to `index.html` remain where they intentionally describe Public Home or Final Integration behavior.

## 10. Final Integration items still deferred
- Promote approved `landing-preview.html` to root `index.html`.
- Remove/adjust the temporary Product mirror assertion.
- Add Landing smoke to the combined integration CI if desired.
- Validate Landing → `app.html` CTA in a real browser.
- Run combined Public + Product visual UAT on GitHub Pages path semantics.
- Approve contact destination separately.
- Keep proposed deep links unimplemented until explicitly approved.

## 11. Required validation before Final Integration
- Frontend CI passes with `KU_APP_ENTRY=app.html`.
- Full six-step browser journey passes at desktop/tablet/mobile.
- Browser console/network checks remain clean.
- Backend CI remains unchanged/passing.
- PR #12 remains Draft and unmerged.
- Landing branch remains unmodified by the Functional workstream.

## 12. Recommended next step
After current Functional CI is green, return this handoff to the Landing workstream for cross-check. Then create a dedicated Final Integration step/branch that replaces the temporary root compatibility Product shell with the approved Public Landing while preserving `app.html` as the Product entry.
