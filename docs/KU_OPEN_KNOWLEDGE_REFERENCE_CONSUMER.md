# KU2A Consumer — KU Open Knowledge Reference v0.1

KU2A must not copy KU2C explanatory content into analytical runtime code. Analytical surfaces reference stable `knowledge_ref` values and request the desired depth/context.

## Resolve known knowledge

```js
KU2AKnowledgeReference.buildRequest({
  knowledge_ref:'SR09_P_VALUE',
  surface:'analytics.results.hypothesis-test',
  requested_depth:'contextual'
})
```

The consumer validates version, request/ref correlation and ownership. KU2A remains authoritative for analytical outputs; KU2C is authoritative for learning representation.

## Discover newly published knowledge

KU2A may consume the metadata-only `knowledge-catalog.v0.1` through `discoverCatalog()`. Catalog entries may expose stable ref, canonical label, aliases, available depths, owner, content version and status, but must not become a copied store of KU2C contextual/glossary text.

KU2A declares potential learning locations through `knowledge-surface-manifest.v0.1`, for example `analytics.clustering.method-selector`. Catalog discovery means **available**, not **automatically inserted into the UI**. KU2A remains responsible for deciding whether a reference belongs on a particular analytical surface.

## Request missing learning support

If no suitable knowledge reference exists, or an existing entry needs a new context/depth, KU2A uses `buildEntryRequest()` for the C04 request lifecycle. Supported request types are `new_entry`, `new_context`, `new_depth`, `content_revision`, `alias_request`, `concept_link_request`, and `deprecation_review`.

For KU2A-owned analytical terms, KU2A supplies the authoritative domain definition/version and intended surfaces; KU2C creates or revises the reusable learning representation. A published request returns a stable `knowledge_ref` through the shared lifecycle rather than encouraging local glossary text.

Transport remains replaceable: KU Open Platform orchestration, REST, event/message, or a bundled catalog snapshot may carry the same contracts.

This integration does not alter analytics routing, backend execution, result payloads or model semantics.
