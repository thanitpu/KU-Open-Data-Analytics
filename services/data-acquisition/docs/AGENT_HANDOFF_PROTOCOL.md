# KU2D Agent Handoff Protocol v1

## Purpose and boundary

Agent Handoff Protocol v1 preserves GitHub-mediated coordination between Codex, an assistant reviewer, and a human decision maker. It is logically separate from Acquisition Learning Memory: coordination history is not automatically ML data, Ground Truth, source authorization, or production approval.

The protocol is storage-neutral. Records are JSON/JSONL-ready repository artifacts. It adds no database, daemon, webhook, autonomous runner, model, embeddings, scheduler, or normal acquisition-runtime write.

Every artifact carries these boundaries:

```json
{
  "coordination_only": true,
  "production_authorized": false,
  "automatic_learning_memory_export": false,
  "scheduler_action": null
}
```

## Record contracts

| Record | Schema | ID family | Authority and purpose |
|---|---|---|---|
| Prompt | `ku2d.agent-handoff-prompt.v1` | `KU2D-P-xxxxxx` | Assistant or human creates a bounded work request. |
| Result | `ku2d.agent-handoff-result.v1` | `KU2D-R-xxxxxx` | Codex reports the exact Prompt outcome and verification evidence. |
| Assistant Review | `ku2d.agent-handoff-assistant-review.v1` | `KU2D-V-xxxxxx` | Assistant reviews a consistent Prompt/Result chain without claiming human authority. |
| Human Decision | `ku2d.agent-handoff-human-decision.v1` | `KU2D-H-xxxxxx` | A genuine human answers an Assistant Review that explicitly requested human authority. |
| Queue | `ku2d.agent-handoff-queue.v1` | one current state | Points to the latest chain and names exactly who acts next. |

Records are append-only in meaning. A Result references its Prompt. An Assistant Review references its Result and the same Prompt. A Human Decision references the review, result, and prompt it answers. Corrections create new artifacts; they do not rewrite prior coordination evidence.

When coordination has durable learning value, provenance may link to a separately validated Learning Memory record. The coordination artifact itself is never silently exported.

## Actors and prompt states

`next_action.actor` is one of `codex`, `assistant`, `human`, or `none`.

Prompt state is one of:

```text
draft
ready_for_codex
in_progress
result_submitted
reviewed
human_decision_required
completed
superseded
```

Only validated transitions are allowed. Completed and superseded prompts cannot return to `ready_for_codex` unless `replay_requested=true` is explicit. Completed prompt history cannot be removed from later queue state.

Queue linkage is fail-closed:

- `codex` requires a ready or in-progress Prompt and no downstream record;
- `assistant` requires the latest submitted, unreviewed Result;
- `human` requires an Assistant Review that explicitly requests a Human Decision;
- `none` represents no pending actor and carries no next-action record IDs.

The bundle validator rejects duplicate/orphan IDs, inconsistent chains, self-reference, fabricated human authority, invalid state transitions, implicit replay, missing completed history, contradictory queue pointers, sensitive material, and non-JSON-safe values.

## Authoritative branch safeguard

New Prompt records may declare top-level `authoritative_branch`; existing v1 records that use `provenance.authoritative_branch` remain valid. If both locations are present they must match exactly. When either is present, the current Queue must repeat the exact value as `authoritative_branch`. Before reading or executing `next_action`, Codex must fetch the remote branch, verify the checked-out branch, and call the equivalent of `validate_authoritative_branch(prompt, queue, checked_out_branch)`. A contradiction or mismatch is a stale-branch handoff and fails closed before task work begins.

The field is optional for backward compatibility: existing v1 records are not rewritten and continue to validate when both Prompt and Queue omit it. A Queue cannot invent branch authority that its Prompt did not declare, and branch metadata coordinates repository state only; it does not authorize production, acquisition, scheduling, or replay.

## Operating workflow

1. **ChatGPT/assistant reads GitHub state.** It reads the queue, referenced records, commits, checks, and review evidence.
2. **Assistant writes a Prompt or Assistant Review artifact.** Chat text alone is not authoritative repository state.
3. **Codex verifies branch authority, then reads a `ready_for_codex` Prompt.** It fetches the named branch, fails closed on a mismatch, executes only the bounded request, creates a Result, and updates the queue to `result_submitted` with `next_action.actor=assistant`.
4. **Assistant reviews the Result.** It either records a non-human Assistant Review or requests explicit human authority.
5. **Human acts only when queued.** A person is asked only when `next_action.actor=human`; explicit input is serialized as a Human Decision.
6. **Queue completes or advances.** GitHub remains the shared source of truth throughout.

The queue is a mutable pointer/index, while Prompt, Result, Assistant Review, and Human Decision records preserve append-only history.

## Bootstrap migration for PR #44

`coordination/prompts/KU2D-P-000001.json` remains the immutable `bootstrap.v0` input. Its validated v1 projection lives separately at `coordination/v1/prompts/KU2D-P-000001.json` and cites the bootstrap source plus the independent review comment. This prevents migration from silently rewriting history.

Codex Result `KU2D-R-000001` is emitted only after deterministic verification. The v1 queue then points to that Result with `next_action.actor=assistant`. No Human Decision is created without later explicit human input.

## Security and runtime isolation

The shared KU2D safe-JSON boundary rejects credential/session material, cookies, authorization values, private browser state, device identifiers, raw NetLogs, and credential-bearing URLs. Normal API, repository, control-plane, and service modules do not import this protocol or write coordination artifacts.

No protocol state can perform production Human Approve, enable production storage, schedule acquisition, initiate a live request, or train a model.
