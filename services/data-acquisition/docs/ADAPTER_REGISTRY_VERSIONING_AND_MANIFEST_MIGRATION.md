# Adapter Registry Versioning and Manifest Migration

P55 replaces singleton-registry coupling with immutable registry snapshots and explicit manifest supersession. It does not rewrite any executed manifest, select a registry implicitly, add a source connector, call a provider, or grant production authority.

## Resolution contract

Every executable run manifest pins a registry path and canonical SHA-256. Manifest v2 additionally pins the catalog path and canonical SHA-256. The runner validates the catalog, resolves exactly one `(registry_id, registry_version)` pair, checks that the resolved path and fingerprint equal the manifest pins, loads the contained repository path, and verifies the loaded registry fingerprint again.

There is deliberately no `latest`, default version, dynamic import, filesystem discovery, or implementation fallback. Missing, unlisted, substituted, mutated, path-drifted, or implementation-mismatched snapshots fail before connector execution.

## Historical compatibility

The following V1 artifacts remain byte-identical to integration baseline `ecd8614c6be78b662d637b1f2caa954fdb1b7dca`:

- `config/adapter_registry_v1.json`
- `config/run_manifests/youtube_qdiving_fixture_v1.json`
- `knowledge/v1/adapter-registry.schema.json`
- `knowledge/v1/immutable-run-manifest.schema.json`

`KU2D-RM-000001-V001` continues to resolve its pinned V1 snapshot directly. `KU2D-RM-000001-V002` is a new immutable identity, explicitly supersedes V001, and pins cataloged registry V2. Both replay the same sanitized fixture into the same ten ordered domain records with zero provider requests and zero quota.

## Additive evolution

To evolve the registry:

1. Preserve every earlier snapshot and fingerprint.
2. Create a new closed registry schema and immutable JSON snapshot.
3. Add the exact snapshot identity, contained path, canonical fingerprint, and supersession link to a versioned catalog revision.
4. Create a new run-manifest identity that explicitly supersedes its predecessor and pins both the catalog and exact snapshot.
5. Supply an implementation catalog whose keys exactly equal the selected registry's registrations.
6. Run byte-invariant, lineage, mutation, composition, replay-parity, full-corpus, and CI validation.

A source adapter is never discovered from registry text. Runtime implementations remain an explicit in-process composition supplied by the trusted caller. A synthetic second registration in the deterministic suite proves that the generic registry and runner compose additively without changing source-runner logic or adding a production adapter.

## Migration evidence

`knowledge/v1/registry-migrations/KU2D-SCOPE-000002.json` preserves the seven-field package and per-phase declarations. `KU2D-RMIG-000001.json` preserves baseline blobs, byte fingerprints, catalog and snapshot identities, manifest lineage, parity, and zero-provider evidence. Technical corrections are recorded in `KU2D-CJ-000005.json` and must have finalized commit links before review or closure.

## Authority boundaries

- Fixture replay only; provider requests and documented quota remain zero.
- Semantic quality remains owned by Analysis and is not inferred from record count.
- No connector lifecycle, quality gate, credentials, production store, scheduling, or `main` authority is added.
- `production_approved` remains `false` and `scheduler_action` remains `null`.
