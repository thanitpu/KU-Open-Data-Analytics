# KU2D Data Acquisition Edge Runner

## Why this exists

KU2D separates deterministic CI from live acquisition validation. Some public sources accept normal end-user networks but reject cloud/datacenter IP ranges. Gourmet Market is the first confirmed example: the same public pages that were reachable in the Windows UAT environment returned HTTP 403 from GitHub-hosted Linux, Windows, and macOS runners.

An **Edge Runner** is a dedicated GitHub Actions self-hosted runner on a normal network that KU2D may use for public-source Explore / Deep Audit / Acquire jobs. It is not a bypass mechanism. It uses the same public URLs and the same access policy as the application; it merely runs from the intended operating environment.

## Governance

- Deterministic tests always run on GitHub-hosted CI first.
- Edge jobs run only after deterministic CI is healthy.
- No authentication, CAPTCHA solving, anti-bot circumvention, proxy rotation, or access-control bypass is permitted.
- Source access blocks are evidence and must be recorded.
- A source is not Approved merely because an Edge job can fetch it. It must still pass Deep Audit quality gates.
- Material technique-profile changes revoke prior approval until re-audited and re-approved.
- The runner must not contain production API keys in the repository checkout.

## Recommended topology

`GitHub branch → CI → Edge Runner → Explore → Deep Audit → staging approval → Scheduled Acquire → Observation Store → drift monitor`

For the initial deployment, a Windows PC/mini-PC in Thailand on a stable normal internet connection is appropriate because the current local Windows UAT environment has already demonstrated substantially better Gourmet Market access than cloud runners.

## One-time setup

1. In GitHub open **Settings → Actions → Runners → New self-hosted runner** for `thanitpu/KU-Open-Data-Analytics` and obtain the short-lived registration token.
2. Open an elevated PowerShell window on the dedicated Windows machine.
3. From this repository run:

```powershell
powershell -ExecutionPolicy Bypass -File services/data-acquisition/tools/SETUP_KU2D_EDGE_RUNNER_WINDOWS.ps1 -RegistrationToken '<token>'
```

The script downloads the current official GitHub Actions runner release, configures labels `ku2d-acquisition,thailand,windows`, and installs it as a Windows service.

The registration token is used only by `config.cmd`; it is never written into this repository.

## Validation

After the runner shows **Idle** in GitHub, use the `KU2D Edge Live Acquisition Validation` workflow. The initial target is Gourmet Market. The workflow uses an isolated operations DB and observation DB and will only set staging approval if the actual Deep Audit passes.

## Production scheduling

Do not use a user-interactive workstation as a long-term production scheduler if it is frequently powered off. After the technique profile and network requirements are understood, move the Edge Runner to an always-on, managed host on an appropriate network. Scheduled Acquire should remain governed by the approved profile fingerprint and drift checks.
