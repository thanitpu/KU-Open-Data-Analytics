# Persistent + Batch Deep Workflow — v2.50

Monitoring is source-URL scoped but visually grouped by business.

Per source URL, the Operations DB persists:
- latest Deep Audit JSON and quality state
- repository-store approval
- latest Deep Acquire run and result
- current stage: not-audited / audit-failed / audit-passed / approved / acquired / acquire-failed

Refreshing the browser therefore does not erase the operational state. Selecting a previously processed URL restores its saved Audit and latest Acquire result.

Batch workflow:
1. Select one or more business groups or individual URLs.
2. Deep Audit Selected runs each URL independently.
3. Each result can be approved independently.
4. Deep Acquire Approved Selected processes only approved selected URLs; unapproved URLs are skipped and reported.
5. Batch state/results are persisted in Acquisition Operations DB.

Grouping by business is presentation only: each URL retains independent audit/accessibility/approval/acquisition provenance.
