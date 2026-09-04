# KU2A — Cloudflare Online UAT

## Purpose

This document defines the standard way to test the KU2A browser UI online while keeping the GitHub repository private.

The intended flow is:

```text
private GitHub repository
        ↓
Cloudflare Pages Git integration
        ↓
production branch (`main`) → stable UAT URL
feature branch / PR          → preview URL
```

Cloudflare is a deployment surface, not the source of truth. GitHub `main` remains the known-good source baseline.

## What is published

Do **not** deploy the repository root directly. KU2A contains backend, contracts, tests, documentation, and other repository-internal material that should not become part of the public static UAT site.

Cloudflare must run:

```bash
bash tools/build_cloudflare_preview.sh
```

The script creates:

```text
_cloudflare_site/
├── index.html      # Landing page
├── app.html        # Functional analytics workspace
├── preview.html
├── assets/
└── src/
```

Only this staged directory should be published.

## Cloudflare Pages project settings

Recommended project name:

```text
ku2a-analytics
```

Use these settings:

| Setting | Value |
|---|---|
| Git repository | `thanitpu/KU2A-Analytics` |
| Production branch | `main` |
| Framework preset | None |
| Build command | `bash tools/build_cloudflare_preview.sh` |
| Build output directory | `_cloudflare_site` |
| Root directory | leave empty / repository root |

The expected stable URL will normally resemble:

```text
https://ku2a-analytics.pages.dev
```

The exact `pages.dev` name is assigned by Cloudflare and may differ if the name is already taken.

## Pull-request / branch previews

Leave Cloudflare preview deployments enabled. A feature branch or pull request should receive its own preview deployment without changing the stable `main` URL.

Recommended development flow:

```text
feature/fix branch
      ↓
GitHub CI
      ↓
Cloudflare preview URL
      ↓
UI UAT
      ↓
correction if needed
      ↓
squash merge to main
      ↓
stable UAT URL updates
```

Do not merge merely because a Cloudflare build succeeded. Existing GitHub CI remains the regression gate.

## UAT scope

The Cloudflare Pages site is primarily for browser/frontend UAT, including:

- Landing page and navigation
- Start → Data Profile → Analyze → Prepare → Setup → Results journey
- CSV/XLSX browser import
- Browser-side data profiling and visual behavior
- Responsive/layout checks
- KU2D trusted-asset intake UI
- Knowledge/contextual-help integration surfaces

KU2A also has validated backend analyses. A static Cloudflare deployment does **not** by itself prove that backend/API execution is available from the Pages origin. Backend/API connectivity must be tested separately against the configured analytics service and must continue to pass backend CI.

## Minimum online UAT checklist

1. Open the stable or PR preview URL.
2. Verify the Landing page loads without missing CSS/assets.
3. Open `app.html` from the Landing CTA.
4. Load a demo or local CSV/XLSX file.
5. Verify Data Profile tabs and relationship exploration.
6. Verify Analyze route selection and state persistence.
7. Verify Prepare and Setup gating.
8. Verify example Results payloads and visual layout.
9. Check browser console for runtime errors.
10. Test a narrow viewport/mobile layout.

If a backend analysis is being tested, record the backend environment separately from the Cloudflare frontend URL.

## Security / publication rule

Never change repository visibility merely to enable online UAT.

Never set Cloudflare Build output directory to `.` for KU2A. That would publish repository-internal files beyond the intended browser surface.

The publish boundary is `_cloudflare_site` only.

## Ownership

- GitHub: source, branch, PR, CI, known-good `main`
- Cloudflare Pages: online static UAT deployment
- KU2A backend service: validated analytical execution
- Reviewer/user: UI UAT decision before merge when visual review is required
