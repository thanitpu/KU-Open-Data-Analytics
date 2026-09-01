# Q-Diving Manual Workflow Default-Branch Launcher Plan

The launcher is prepared but not deployed to `main`. GitHub exposes a `workflow_dispatch` workflow from the default branch, so a later reviewed promotion must copy only `.github/workflows/youtube-qdiving-identity-discovery.yml` to `main`. P39 does not authorize that promotion or any dispatch.

Before promotion, an assistant review and explicit Human Decision must identify an immutable 40-character integration implementation SHA. The Human Decision is then committed separately, so its own immutable record SHA can be known without a self-referential commit. The promotion PR must replace all three fail-closed placeholders in the workflow with the implementation SHA, the confirmed Human Decision ID, and the decision-record SHA. Until all anchors are replaced, every dispatch fails before checkout and before the API secret enters any step. The decision record at the pinned record revision must contain:

- `authorized_execution_revision`: the exact reviewed integration commit;
- `authorized_execution_branch`: `integration/data-acquisition-platform`;
- `authorized_scope`: the exact two-profile H12 limits enforced by the runner.

At dispatch, the launcher accepts the decision ID, execution revision, and authorization-record revision as deliberate operator confirmation. Before checkout, it compares them with the trusted constants embedded by the reviewed `main` promotion. It first checks out the exact record revision and validates the decision and complete scope. It then checks out only the embedded execution SHA and verifies `HEAD` before the API secret enters the runtime step. A placeholder or mismatch fails before checkout and before any YouTube request. The checked-out implementation cannot select or self-authorize its own revision, and the Human Decision can authorize an earlier reviewed implementation SHA without an impossible self-hash.

The runtime secret exists only as `KU2D_YOUTUBE_API_KEY` in the discovery step environment. Neither the launcher, runner, summary nor sanitized artifact prints or serializes it. Exit 0 means candidate evidence obtained; exit 2 means evidence withheld and still permits summary/artifact completion; every other nonzero exit is a technical job failure.

Promotion checklist:

1. Assistant accepts the exact implementation head and launcher contract.
2. Human Decision authorizes the exact integration SHA and unchanged H12 scope.
3. Replace the three trust-anchor placeholders and open a one-file PR to `main` containing only the launcher workflow.
4. Verify the default-branch file still has only `workflow_dispatch` and `contents: read`.
5. Merge only after review; do not dispatch automatically.
6. Dispatch once with the exact decision ID and SHA, then review sanitized evidence before any Human Review or acquisition step.
