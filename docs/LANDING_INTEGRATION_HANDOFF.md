# KU Open Data Analytics — Public Landing Handoff

## 1. Landing source of truth
During handoff/staging, the Landing source of truth is:

- `landing-preview.html`
- `src/landing.css`
- `src/landing-copy.js`
- `src/landing-content.js`
- `src/landing.js`
- `assets/landing/*`

The root `index.html` remains the Functional Analytics Application and is intentionally untouched.

## 2. Branch
`integration/public-landing`

Implementation head immediately before this handoff document was added:
`491ed2fbfe81ff73b43792c9c251089ff008f0ec`

The current authoritative head SHA should be read from the branch/PR because this document itself creates a later commit.

## 3. Files created
- `landing-preview.html`
- `src/landing.css`
- `src/landing-copy.js`
- `src/landing-content.js`
- `src/landing.js`
- `assets/landing/brand/KU_Logo_AI.svg`
- `assets/landing/brand/KU_Logo_Accent_Color.svg`
- `assets/landing/brand/KU_Logo_White_Transparent.svg`
- `tests/landing_smoke.js`
- `docs/LANDING_INTEGRATION_HANDOFF.md`

## 4. Files modified
None of the pre-existing Functional Application files are modified.

## 5. Files deleted
None.

## 6. External dependencies
- Google Fonts CSS: `Mitr` weight 600 and `Kanit` weights 300/400/500/600.
- Google Fonts font delivery via `fonts.gstatic.com`.
- No external JavaScript libraries.
- No external image or video dependencies.
- No iframe.
- No analytics API/FastAPI dependency for Landing rendering.
- KU logos are local SVG assets under `assets/landing/brand/`.

If Google Fonts are unavailable, the page falls back to system sans-serif fonts and remains usable.

## 7. CTA contract
Primary Landing CTA:

`href="app.html"`

Final architecture dependency:
- `index.html` → Public Landing
- `app.html` → Functional Analytics Application

During staging, `app.html` may not yet exist. Do not redirect the Landing CTA to `index.html` because that would become a loop after final integration.

## 8. Proposed deep links
None implemented.

Potential future parameters such as `app.html?demo=...` or `app.html?intent=...` require a separately approved Product-side contract before use.

## 9. GitHub Pages/path assumptions
All authored repository links and local assets use relative paths. No GitHub Pages domain is hard-coded. Landing should therefore remain compatible with project-path hosting such as a repository-level GitHub Pages deployment.

## 10. Landing tests
`tests/landing_smoke.js` checks:
- `app.html` CTA contract exists.
- Landing CSS/JS dependencies are present.
- No root-absolute authored resource paths.
- No import of protected Product JS/CSS.
- No `/analyze`, `fetch()`, or XHR API dependency.
- All three KU SVG brand assets exist.
- Reveal animation has a content-visible fail-safe.
- Tablet and mobile CSS breakpoints exist.
- TH/EN preference persistence exists.
- Natural Thai copy layer is present.

Run:

```bash
node tests/landing_smoke.js
```

## 11. Responsive validation
Responsive CSS is isolated in `src/landing.css` with desktop base layout plus:
- Tablet/compact layout: `max-width: 1050px`
- Mobile layout: `max-width: 700px`

Static responsive smoke checks pass. A headless Chromium visual capture was attempted in the handoff environment but the container browser timed out before rendering; therefore final visual browser validation should still be performed by the reviewing workstream before merge.

## 12. Known issues
1. `app.html` is an integration dependency and may not exist until the Functional workstream completes the entry-point migration.
2. Contact CTA remains a deliberate placeholder; no fake form endpoint is introduced.
3. Google Fonts need network access for Mitr/Kanit; fallbacks remain usable.
4. Final browser visual UAT is still required at desktop/tablet/mobile widths.
5. The Hero/product walkthrough contains static marketing-demo sample values only. It performs no analytics and must not be treated as Product logic.

## 13. Placeholders / mocks
- Contact destination is not yet approved.
- Product motion/demo is presentation-only sample content; it does not parse datasets, call FastAPI, or run models.
- Example solution visuals are illustrative marketing visuals, not claims of deployed customer systems.

## 14. Approved visual/content areas
Preserve during technical integration unless a separate design/content change is requested:
- Section order and editorial rhythm.
- Product-first Hero.
- Analyze / Advise / Build / Build Capability positioning.
- Thai-first natural copy with TH/EN switching.
- Mitr SemiBold for display highlights; Kanit for Thai body/navigation/UI.
- KU logo assignments: AI logo on white/header, accent logo in Why KU, white logo on dark footer.
- Relative `app.html` CTA contract.

## 15. Areas safe for technical adjustment
Without changing approved appearance/meaning, the integration reviewer may adjust:
- HTML formatting/indentation.
- Script loading order if equivalent behavior is preserved.
- Accessibility attributes.
- Metadata/SEO details.
- Asset cache-busting/versioning.
- Test harness details.

Do not silently rewrite Thai/English messaging or replace the visual architecture during handoff.

## 16. Integration risks
- Final entry-point rename can conflict if both workstreams modify root `index.html`; therefore Functional migration must happen first or be coordinated in a dedicated integration branch.
- Landing expects `app.html` but intentionally does not implement Product-side behavior.
- Shared design tokens are not extracted yet; Landing does not import `app.css`.
- Contact integration may introduce a new service/dependency and should be reviewed separately.

## 17. Shared-file changes
**NONE.**

The Landing workstream has not modified:
- root `index.html`
- Product CSS/JS/state/journey/workflow/result files
- backend
- existing Functional analytics tests

## 18. Recommended integration sequence
1. Functional workstream reviews this branch/PR.
2. Functional workstream completes/validates `index.html` → `app.html` migration in its own integration work.
3. In a dedicated final integration step, promote `landing-preview.html` → root `index.html`.
4. Connect approved contact destination.
5. Run Landing smoke + full Functional regression + browser responsive UAT.
6. Merge/deploy only after explicit approval.

This branch must not perform the final integration automatically.