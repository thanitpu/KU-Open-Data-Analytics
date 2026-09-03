# KU2A Repository Rename Cutover

Status: controlled cutover record

## Authoritative identity decision

- Previous GitHub repository: `thanitpu/KU-Open-Data-Analytics`
- Canonical GitHub repository after cutover: `thanitpu/KU2A-Analytics`
- Product name: **KU Open Data Analytics** (unchanged)
- Existing analytics API: `https://ku-open-data-analytics-api.onrender.com` (unchanged)
- Default branch: `main` (unchanged)

The repository name identifies the KU2A analytical system. It does not rename the public product, the Render service, API contracts, or established user-facing URLs. The old GitHub repository name must not be reused: GitHub redirects for repository links depend on that name remaining unclaimed.

## Scope and preservation rules

This cutover updates repository-bound runtime references and preserves the following boundaries:

1. KU2A owns the analytical workspace, Text Analytics, analytical execution, and consumption of reviewed data assets.
2. KU2D owns discovery, acquisition, provenance, audit, Human Approve, monitoring, and production data acquisition.
3. KU2C owns competencies and credits when that repository is introduced.
4. KU-Open is an integration/public-surface participant; its contracts must be explicit rather than implemented through repository-relative coupling.
5. The `trusted-data-asset-v1` contract remains the current KU2D-to-KU2A boundary. A repository rename is not authorization to change that contract or production approval state.
6. Secrets, acquisition runners, cookies, sessions, live-provider calls, and KU2D scheduling do not move into KU2A.

## Changes required for the rename

- `render.yaml` points its source repository to `https://github.com/thanitpu/KU2A-Analytics`.
- `preview.html` loads commit-pinned assets from the renamed raw.githack repository path.
- PR preview generation remains dynamic through `pull_request.head.repo.full_name`.
- GitHub Pages assets remain repository-relative. Because GitHub does not redirect project Pages URLs after a repository rename, consumers must use the new project path once Pages has published it.
- The local `origin` URL must be changed to `https://github.com/thanitpu/KU2A-Analytics.git` after the GitHub rename.
- Existing local working-directory names may remain unchanged during the active cutover. A fresh clone should use `KU2A-Analytics`; renaming an active Codex workspace directory is intentionally deferred to avoid invalidating the running workspace.

## KU2D work that is preserved, not promoted

The rename does not merge, replay, approve, or otherwise change acquisition work. At cutover planning time, the following open acquisition PRs existed and remain KU2D-bound historical/work-in-progress records: `#22`, `#36`, `#37`, `#38`, `#39`, `#40`, `#41`, `#42`, and `#43`.

Untracked local `services/` acquisition material and `docs/KU2D_CODEX_IMPLEMENTATION_AGENT_BOOTSTRAP.md` are user-owned migration inputs. They are deliberately excluded from the KU2A rename commit and must be handled by the reviewed KU2D extraction process.

## Verification contract

The cutover is complete only after all of these checks pass:

1. GitHub reports the repository as `thanitpu/KU2A-Analytics` with default branch `main`.
2. The local `origin` fetch and push URLs use the canonical repository URL.
3. The integration branch and all retained feature branches and open PRs remain present.
4. `tests/repository_identity_smoke.js`, the complete Frontend CI corpus, Backend CI, YAML parsing, and Python/JavaScript compilation pass.
5. The new GitHub Pages project URL is checked explicitly; the previous Pages project URL is not assumed to redirect.
6. Render source configuration names the canonical repository while the existing API hostname remains unchanged.
7. No secret, credential, live acquisition, production Human Approve action, or scheduler mutation occurs during the rename.

## Mandatory handoff for every other Codex/chat task

Before another task changes KU2A or continues a prior prompt, it must:

1. Confirm the repository is `thanitpu/KU2A-Analytics` and fetch the current remote state.
2. Read this document completely.
3. Inspect the current branch, status, remote, and latest commit before editing.
4. Treat older repository paths as migration history, not current instructions.
5. Do not replay a completed KU2D coordination Prompt unless its queue explicitly requests replay.
6. Do not move or modify KU2D-owned acquisition code, evidence, queues, approval state, or open PRs from this repository without a separate reviewed extraction prompt.
7. Preserve the KU2D-to-KU2A `trusted-data-asset-v1` boundary and provenance fields.

Use this continuation prompt:

> Work only in `thanitpu/KU2A-Analytics`. Fetch the latest remote state, then read `docs/KU2A_REPOSITORY_RENAME_CUTOVER.md` completely before taking any action. Confirm the current branch, status, origin, and latest commit. Do not reuse paths or assumptions from `thanitpu/KU-Open-Data-Analytics`; do not replay completed prompts. KU2D acquisition material and coordination state are out of scope unless a new reviewed migration prompt explicitly places them in scope. Preserve the `trusted-data-asset-v1` handoff, provenance, production-approval boundaries, and the existing Render API hostname.

## Rollback and redirect cautions

GitHub automatically redirects ordinary repository web and Git URLs after a rename, but project Pages URLs and GitHub Actions references are exceptions. Do not create another repository under `KU-Open-Data-Analytics`, because doing so removes the rename redirect. If a rollback is required, pause changes first, verify all branch and PR refs, restore repository-bound configuration, and repeat the complete verification contract rather than relying on redirects.
