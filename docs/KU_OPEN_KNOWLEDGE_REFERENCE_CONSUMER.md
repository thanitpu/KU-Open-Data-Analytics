# KU2A Consumer Proof — KU Open Knowledge Reference v0.1

KU2A must not copy KU2C explanatory content into analytical runtime code. Analytical surfaces reference stable `knowledge_ref` values and request the desired depth/context.

Example:

```js
KU2AKnowledgeReference.buildRequest({
  knowledge_ref:'SR09_P_VALUE',
  surface:'analytics.results.hypothesis-test',
  requested_depth:'contextual'
})
```

The consumer validates version, request/ref correlation and ownership. Transport is intentionally not fixed in this proof; a future KU Open gateway, REST endpoint or bundled registry snapshot may supply the response.

KU2A remains authoritative for the analytical output it produces. KU2C is authoritative for the learning representation. The UI may render the resolved contextual text, open a glossary-depth view, or deep-link to the returned `concept_ref`.

This proof does not alter analytics routing, backend execution, results payloads or model semantics.
