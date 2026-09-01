# P59 Multi-source Round-robin and Domain Export

This checkpoint implements the one-time, non-production campaign authorized by
`KU2D-P-000059` and `KU2D-H-000028`. TikTok public video and TikTok Shop are
excluded. The campaign never approves a source, writes a production database,
creates a recurring schedule, or sends retained data to KU2A automatically.

## Immutable inventory

The inventory is derived from the reviewed Acquisition Consolidation Readiness
artifact. Only four Tier-A sources have both a reviewed executable method lock
and an immutable total request cap:

| Domain | Source | Locked live technique | Total provider-operation cap | Record cap |
| --- | --- | --- | ---: | ---: |
| Supermarket | Tops | `tops_product_catalog` + `generic_sitemap` | 80 | 8 |
| Supermarket | Lotus's | `lotus_catalog_api` | 80 | 792 |
| Supermarket | Big C | `bigc_product_catalog` + `generic_sitemap` | 80 | 8 |
| Supermarket | Makro | `makro_pro_catalog` | 24 | 160 |

Gourmet Market and JIB remain Tier B and are preflight-skipped because P59 does
not enter the Thailand Edge caveat or production approval, and neither source
has a reviewed immutable total campaign cap. The twelve Tier-C sources are also
preflight-skipped with exact reasons and zero provider access. Registry-only or
candidate-only evidence is not promoted into an executable technique.

The immutable order is domain then stable source ID. Execution is serial with
concurrency one and no work stealing. Each visit accepts at most 100 new stable
identities, performs at most 25 tracked provider operations for at most ten
minutes, and then advances. A single transient failure retries next round; two
separate transient rounds, two visits with no new identity, an access boundary,
or source budget exhaustion makes the source terminal for this campaign.

## Evidence-before-next-operation

Every network operation is routed through `VisitContext.provider_call`. Before
the operation, an atomic checkpoint records the sanitized host/path, operation
ID, source ID, and intent state. After the operation, another atomic checkpoint
records only status, byte count, error type, and whether the provider may have
been reached. Query strings, headers, credentials, cookies, response bodies,
browser state, and raw payloads are not written to the ledger.

If the process stops after the intent checkpoint, resume conservatively counts
that operation once as `outcome_unknown_after_crash`. A sealed ledger cannot be
resumed. The runner also enforces the two-second same-host interval, per-visit
limits, source totals, the 5,000-operation global ceiling, and the 12-hour global
ceiling before another provider call.

HTTP 401, 403, or 429 stops that source. No login, CAPTCHA handling, challenge
solving, proxy, browser fallback, automatic endpoint discovery, technique
switch, or execution-environment switch is available.

## Artifact boundary and export

The CLI refuses an output directory inside the Git worktree and proves the
external directory is writable before live access. After live acquisition it
seals the ledger, performs zero-provider replay of every declared available
fixture, and only then creates domain-separated UTF-8 CSV, JSONL, and XLSX
artifacts. XLSX files contain `Records`, `Source Summary`, and `Failures` sheets.
CSV uses `\N` for null, JSONL preserves native null, and XLSX represents null as
an absent cell while empty text remains an inline string. Text beginning with
`=`, `+`, `-`, or `@` is prefixed with an apostrophe.

The ZIP contains `campaign_manifest.json`, both failure-report formats, the
fixture report, and each domain's three record formats. The embedded campaign
manifest pins every non-self member. A cryptographic archive cannot contain its
own final hash—or the hash of the embedded manifest that contains that value—
without changing the hash. The detached `.delivery.json` manifest therefore
pins every ZIP member including `campaign_manifest.json`, plus the exact ZIP
size and SHA-256. Both manifests are required for verification. This explicit
two-manifest construction avoids a false or circular self-hash claim.

## Controlled commands

All commands require `--no-production-store`. The canary and execute modes also
require `--acknowledge-one-time-p59`.

```powershell
python tools/LIVE_MULTI_SOURCE_ROUND_ROBIN.py `
  --mode preflight --run-id P59-PREFLIGHT `
  --output-dir "$env:TEMP\KU2D\P59" --no-production-store
```

The preflight performs zero provider operations. `--mode canary` performs one
public request per live-eligible source. `--mode execute` performs the one-time
campaign. An interrupted unsealed run may use `--resume`; a sealed run cannot.
Neither mode is a recurring scheduler or production Human Approve.

## Deterministic verification

- `SELF_TEST_MULTI_SOURCE_ROUND_ROBIN.py` covers manifest rejection, ordering,
  fairness, atomic intent/outcome checkpoints, conservative crash resume,
  cadence, access boundaries, terminal skip semantics, record and provider
  limits, external delivery preflight, and zero-provider fixture replay.
- `SELF_TEST_DOMAIN_EXPORT_BUNDLE.py` covers UTF-8, null and empty separation,
  formula neutralization, XLSX structure, deterministic ZIP membership, member
  hashes, detached ZIP hash, and round-trip parsing.
- Both suites are aggregated by `SELF_TEST_FOUNDATION_CONSOLIDATION.py`, which is
  already part of the full Data Acquisition CI corpus.
