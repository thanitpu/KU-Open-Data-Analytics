# Architecture Decision: Public Landing Page vs Analytics Application

Status: Accepted

## Decision

KU Open Data Analytics will use two separate frontend entry layers:

- `index.html` — Public Landing Page / marketing and public navigation layer.
- `app.html` — Functional KU Open Data Analytics workspace.

The functional application currently remains in `index.html` temporarily so ongoing development and UAT are not disrupted. Future frontend work in the functional application must nevertheless assume that the final application entry file will be `app.html`.

## Responsibility boundaries

### Public layer — separate Landing workstream

- `index.html`
- `src/landing.css`
- `src/landing.js`
- `assets/landing/*`

### Product layer — functional application workstream

- `app.html`
- `src/app.css`
- `src/app.js`
- `src/analysis.js`
- `src/ai-analytics.js`
- `src/statistics/*`
- `src/visualization/*`
- `src/advisor/*`
- functional UX/state/tests

### Analytics service layer

- `backend/*`

The functional GitHub codebase remains the source of truth for analytical behavior. Prototype JavaScript or analytical logic must not replace production functional modules or backend engines.

## Migration constraints

Functional code should avoid assumptions that the application lives at `/` or is named `index.html`. Prefer relative asset paths and internal state/navigation that do not depend on the HTML filename.

When adding or editing frontend code, check:

- navigation links and redirects
- `window.location` / pathname assumptions
- CSS and JavaScript includes
- sample-data links
- query parameters and deep-link initialization
- home/return actions
- API configuration
- GitHub Pages path assumptions
- browser/JSDOM tests and static preview configuration
- README/UAT documentation

## Target migration

When Landing integration begins:

1. Move the current functional application shell from `index.html` to `app.html`.
2. Put the new Public Landing Page at `index.html`.
3. Landing primary CTA routes to `app.html`.
4. Preserve clean support for future deep links such as `app.html?demo=churn` or `app.html?intent=classification` without adding roadmap-external features prematurely.

## Current transition strategy

- Do **not** rename the production app shell yet while PR/UAT/deployment assumptions still use `index.html`.
- CI exposes the current app entry through `KU_APP_ENTRY`; changing the entry during migration should not require browser-test logic changes.
- Runtime product code must remain entry-file agnostic.
- Existing JSDOM tests that still read `index.html` directly are a recorded migration item; they should be switched when the actual shell moves, rather than causing a large test-only refactor now.
- Public Landing assets/code must remain outside functional product modules to minimize merge conflicts.

## Rationale

Separating the public marketing surface from the analytical workspace allows visual/marketing iteration to proceed independently while preserving the validated functional frontend/backend codebase and reducing merge conflict risk.
