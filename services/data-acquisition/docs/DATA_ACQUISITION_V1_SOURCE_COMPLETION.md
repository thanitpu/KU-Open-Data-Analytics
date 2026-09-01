# KU2D Data Acquisition v1 Source Completion

## Target architecture

KU2D Data Acquisition v1 uses:

```text
Shared Connector Kit
  + Domain Capability Profile
  + Thin Source Adapter
  + Source-specific Parser
  + Analysis-owned Semantic Quality
```

The Connector Kit owns lifecycle execution, bounded request plans, runtime
credential injection, timeout and retry policy, request/quota accounting,
sanitized evidence and logging, failure classification, validation and fixture
replay. An adapter declares access, parameters, pagination, parser selection and
capabilities. A parser interprets one source payload. A separate mapper creates
domain records. Neither adapter nor parser may write production data, create a
coordination queue, persist credentials, decide semantic quality or introduce a
parallel evidence system.

Domain Capability Profiles are explicit and versioned. A domain may use any
combination of `available`, `partial`, `unverified`, `blocked`, `unsupported`
and `not_applicable`; Product, Price and Promotion are not universal
requirements. Each profile separately marks the capabilities required for its
Minimum Trusted Connection (MTC).

## One Source Completion Queue

Each source is developed in an isolated Source Lab and uses one queue, one
coherent PR and one final Result:

```text
Technique Library reuse
→ Explore
→ Deep Audit
→ Minimum Trusted Connection
→ Integration
→ Closure
```

Explore compares proven techniques first and uses bounded samples. Deep Audit
checks stability, pagination, variants, failure modes, policy, provenance and
repeatability. If proven techniques fail, bounded discovery may identify a new
method and preserve that result for reuse. MTC is reached when at least one
useful capability is reproducible with schema-valid output, provenance, shared
failure classification, sanitized evidence, fixture replay and documented
limitations. Full capability completeness is not required.

Codex self-corrects technical issues inside the same queue. Syntax, fixture,
parser, schema, evidence and in-scope CI corrections are recorded in one local
technical-correction journal and aggregated into one PR. Assistant review occurs
on the final Result and material evidence. A Human gate is reserved for legal or
policy ambiguity, restricted or personal data, material scope/quota expansion,
new spending, production writes or elevated authority. The standard handoff
commands remain `Continue from KU2D queue` and `ต่อครับ`.

## Three-tier testing

1. Level 1: unit and adapter-specific fixture tests after each material
   correction affecting that component.
2. Level 2: source-level integration and evidence validation before the PR.
3. Level 3: the full deterministic corpus once on the exact final PR head before
   merge or closure. It is rerun only if code, schema, fixture, policy or test
   input changes, unless the merge tree is proven identical to that head.

## YouTube Q-Diving reference closure

YouTube v1 reuses the existing official YouTube Data API v3 implementation and
the immutable sanitized P50 packet. The thin reference adapter selects that
fixture, the source parser preserves all YouTube candidate fields and provenance,
and the public-video mapper leaves semantic fields unassessed for Analysis under
`KU2D-KP-000003` and `KU2D-AI-000001`.

The public-video Q-Diving profile requires only `video_metadata` and
`channel_identity` for MTC. Both are available for all ten preserved candidates.
Comments, captions and transcripts remain blocked and do not delay v1 closure.
MTC is not production Human Approve: production storage and scheduling remain
disabled.

The generic lifecycle template is intentionally source-neutral. It makes no
claim about a future TikTok access surface or capability set; TikTok must open a
separate Source Completion Queue.
