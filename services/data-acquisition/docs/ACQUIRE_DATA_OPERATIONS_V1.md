# KU2D Acquire Data Operations — v2.35

v2.35 turns Acquire Data from a dashboard/planning layer into an operational workflow.

## 1. Monitoring Queue
Approved sources from Commerce/Retail, Q Diving and General registries are normalized into one queue.

Actions:
- Run Due Sources: normal manual operation; executes only sources whose cadence is due.
- Run Selected: manual override for checked sources.
- Run All Enabled: manual full refresh.
- Refresh: updates due/status information.

Persistent operational state is stored outside version folders in:
`G:\My Drive\My Projects\KU Open Data Analytics\Archive\Text Analysis\Data Repository\ku2d_acquisition_ops.sqlite3`

This stores run history, last success, errors and exploration audit records.

## 2. Automatic Scheduled Monitoring
Run `tools\INSTALL_KU2D_MONITORING_TASK_v2.35.bat` once on Windows.
It creates a Windows Task Scheduler task that starts the KU2D acquisition worker hourly.
The worker checks each source's cadence (daily/weekly/etc.) and only runs due sources.

The browser and FastAPI server do not need to stay open.
The PC must be on, Python must be available, internet access must work and the repository drive must be mounted.
After moving/upgrading the version folder, re-run the installer so the task points at the new worker path.

## 3. Explore New URL
Workflow:
URL -> Sample Fetch -> Extraction/Profile -> Record Count -> Quality -> Tags -> Sample/Diagnostics -> Approve.

Approval routes the URL to the appropriate monitoring registry:
- Retail / Competitive Intelligence -> Commerce source registry
- Diving Knowledge -> Q Diving registry
- Other purposes -> General registry

No exploration data is silently promoted to recurring monitoring.

## 4. Discover New Sources
Input can be a:
- Domain
- Source
- Specific Product
- Topic

KU2D uses the configured Serper provider only after the user explicitly clicks Discover Sources.
Candidate URLs are deduplicated and domain-diversified.
A candidate must then be explicitly selected and explored/sampled before it can be approved.

## 5. Acquisition Principle
Discover -> Explore -> Evaluate -> Approve -> Monitor -> Acquire -> Validate -> Store -> Refresh/Health.

The same Acquire Data platform serves Retail, Knowledge, Evidence Verification, Voice of Customer,
Competitive Intelligence, Destination/Service Intelligence and Research Evidence.
