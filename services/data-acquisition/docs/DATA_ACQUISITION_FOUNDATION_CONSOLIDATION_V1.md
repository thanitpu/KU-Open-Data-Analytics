# KU2D Data Acquisition Foundation Consolidation v1

## Authoritative execution path

P53 consolidates deterministic source execution into one source-neutral path:

```text
Immutable Run Manifest v1
→ Adapter Registry v1
→ Generic Source Runner
→ Connector Kit v1
→ registered adapter / parser / mapper
→ Early Acquisition Quality Gate
→ Analysis handoff records
```

The Run Manifest pins the run and source-manifest identities, registry and
adapter/parser/mapper contract versions, Domain Capability Profile, requested
capabilities, fixture and evidence references, request policy, timestamps,
canonical SHA-256 fingerprints and authority boundaries. The runner validates
every pin before transport. Fixture replay permits no runtime credential, live
provider request or quota. A manifest is immutable once execution begins; a
correction creates a new manifest ID/version and identifies the superseded
manifest instead of changing executed evidence.

Adapter Registry v1 is closed metadata plus an explicit implementation catalog.
It never imports an arbitrary module name from JSON. Duplicate identities,
unknown adapters, implementation drift, incompatible Connector Kit versions and
unsupported transport/capability combinations fail closed. Registration
metadata stays separate from adapter/parser/mapper code.

The Generic Source Runner contains no source ID, endpoint, selector, payload
parser or domain semantic-quality rule. It resolves only an exact registered
identity. Exact identical records replayed for multiple technical capabilities
are collapsed in first-seen order; a repeated identity with different content
is rejected. The result distinguishes connector attempts from provider requests
and documented quota.

## Early Acquisition Quality Gate

The early gate checks only technical handoff fitness:

- authority remains fail-closed;
- mapped record schema and identity exist;
- provenance and timezone-aware observation timestamps exist;
- sanitized output contains no credential/session material;
- exact technical duplicates or identity conflicts are rejected;
- every requested capability has complete response/evidence fingerprints.

The gate never scores semantic relevance or quality, ranks candidates, groups
analytical equivalents, or decides final inclusion. Those fields remain
Analysis-owned and null at Acquisition handoff.

## YouTube reference path and parity

The P50 sanitized Q-Diving packet is the reference fixture. Its ten candidates,
ordering, public video/channel identity, query-profile provenance and Analysis
handoff are preserved through the complete manifest-to-runner path. Comments,
captions, transcripts and raw provider payloads remain blocked. Fixture replay
records zero provider requests and zero quota. MTC remains technical evidence,
not production Human Approve.

The direct Connector Kit API remains available to existing deterministic tests,
but the manifest/registry/runner path is authoritative for consolidated source
runs. This is not a compatibility wrapper. Direct reference execution may be
removed only after all source-run entry points use immutable manifests and the
P54 source proves the generic seam.

## P54 extension seam

A next source adds only:

1. one thin adapter and source parser/domain mapper;
2. one Domain Capability Profile and Source Manifest;
3. one Adapter Registry registration plus explicit composition entry;
4. one immutable Run Manifest and sanitized fixture set;
5. adapter fixture tests and source-level evidence validation.

It does not modify the Generic Source Runner or the platform CI workflow. A
source needing new generic mechanics must stop for foundation review rather than
put source-specific behavior into the runner.

## Operating contract

Foundation work retains one Source Completion Queue, one coherent PR, one
multi-correction journal, and three testing levels: unit/adapter fixture,
source-level integration/evidence, and the complete deterministic corpus on the
exact final PR-head tree. Technical corrections stay in `KU2D-CJ-000003` with
sanitized provider/quota impact and finalized commit links.

P53 performs no TikTok execution, live provider request, production write,
scheduling, production approval or `main` modification.
