# KU2D Core Intelligence Quality Foundation v1

The Quality Foundation strengthens how KU2D preserves evidence, develops codes, challenges emerging patterns, and verifies findings before any future recommendation layer is built. It is deterministic and storage-neutral. It performs no acquisition, runtime write, production authorization, scheduling, ML training or inference, embedding, vector storage, or dataset export.

## Evidence before interpretation

The quality chain is explicit and non-destructive:

```text
Raw / Observed Evidence
  -> Prepared Evidence
  -> Descriptor
  -> Semantic Code
  -> Interpretation
  -> Decision
```

Raw evidence remains immutable and retains provenance. Preparation records transformations but references the raw evidence rather than replacing it. A descriptor states what is visible. A code applies a defined codebook concept. An interpretation explains what the codes mean in context. A decision identifies its authority source. These stages are validated separately because evidence is not interpretation and observation is not Ground Truth.

## Codebook discipline

`config/core_knowledge_codebook.json` is a backward-compatible guidance adapter over `core_knowledge_taxonomy.json`; it does not change existing taxonomy IDs or schemas. Applicable semantic codes contain:

- a definition and evidence requirement;
- `include_when` and `exclude_when` guidance;
- positive examples and counter-examples;
- optional parent/child relationships;
- commonly confused taxonomy codes.

The validator rejects descriptor or theme identifiers masquerading as semantic codes. Code, theme, and descriptor are different analytical objects even when they use similar words.

The ontology remains open. An observation may return `no_existing_code_fits` or `novel_pattern_candidate`. Neither state is coerced into the nearest code, claims authority, or modifies the taxonomy. A novel code requires later independent review.

## Iterative coding

First-cycle coding captures the initial system/Codex classification. A second-cycle refinement must reference that first coding record, and the first cycle remains visible. Refinement appends meaning; it never overwrites history. The historical fixtures demonstrate an initially novel bare-counter observation later refined under the human-confirmed unknown-counter policy.

This preserves the difference between an early working classification and a later reviewed interpretation. It also makes corrections and disagreement auditable.

## Analytical memos and negative cases

An Analytical Memo records a working hypothesis or pattern candidate with supporting evidence, counter-evidence, unresolved questions, author type, status, and provenance. Memo history is append-only in meaning. A memo is not Ground Truth and cannot authorize production.

Negative and deviant cases are first-class learning evidence. Each record preserves the expected pattern, contradictory observation, alternative explanations, policy or taxonomy impact, learning value, and evidence references. Application shells and the cloud-versus-approved-Edge boundary illustrate why technically completed or blocked attempts must not be discarded or flattened into a single failure class.

## Finding Verification

A future finding must pass a separate verification gate before it can become eligible for reviewed Core Knowledge. The gate represents:

- return to raw evidence;
- provenance completeness;
- alternative-explanation review;
- negative/deviant-case search;
- cross-episode or cross-source support where applicable;
- a limitation statement;
- Human Confirmation when policy authority is required.

Not every check is required for every finding, but a skipped check must be explicit and justified. A pending or failed required check withholds eligibility. Even a fully eligible result is only `eligible_for_separate_review`; the quality module never auto-promotes it.

## Independent coding and semantic reliability

The Independent Coding contract supports future blinded Codex/Assistant comparisons using sample ID, task, codebook version, coder identity/type, labels, agreement state, and adjudication need. This checkpoint contains deterministic fixture coders only. It does not fabricate Assistant labels, human labels, or human inter-rater reliability.

Agreement helpers calculate exact agreement rate and Cohen's kappa when one categorical label per coder and enough variation are present. Insufficient, multilabel, or zero-denominator inputs return `not_applicable`. A Semantic Reliability report preserves sample size, disagreement cases, and chance-corrected results per task—such as price semantics, counter semantics, source classification, technique selection, evidence strength, or review prioritization. It provides no aggregate score that could hide task-level disagreement.

Disagreement requires adjudication. Future Assistant or human labels must come from genuinely independent records, never synthesized by this module.

## Analysis displays

Storage-neutral projections can represent Source × Technique, Evidence × Interpretation, and pattern/negative-case summaries. Every cell links to evidence or provenance, and display never confers authority merely because a relationship appears in a matrix.

## Quality Loop

The optional ordered state model is:

```text
observed_evidence
  -> first_cycle_code
  -> codebook_check
  -> second_cycle_code
  -> negative_case_check
  -> analytical_memo
  -> pattern_candidate
  -> finding_verification
  -> independent_coding_check
  -> human_adjudication_if_needed
  -> reviewed_pattern_core_knowledge
```

Not every acquisition episode must reach every stage. A stage may be pending, withheld, or not required with a reason. The model preserves learning history without forcing a source outcome through an inappropriate workflow.

## Knowledge and future ML boundary

The existing separation remains unchanged:

```text
Learning Memory -> Reviewed Learning Corpus -> future task-specific ML Training Dataset
```

No ML Training Dataset is created here. Candidate Learning Evidence remains candidate-only; all 11 unmerged source-history candidates remain unpromoted. This foundation does not add sources, perform live requests, expand domains, or authorize production.

The pure validators and deterministic agreement helpers live in `acquisition/core_intelligence_quality.py`. Normal API, control-plane, repository, service, and acquisition-orchestrator paths do not import it. Run its tests explicitly with:

```powershell
python tools/SELF_TEST_CORE_INTELLIGENCE_QUALITY.py
```

