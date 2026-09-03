const assert=require('assert');
const adapter=require('../src/knowledge-reference.js');

const req=adapter.buildRequest({knowledge_ref:'SR09_P_VALUE',surface:'analytics.results.hypothesis-test',request_id:'req-001'});
assert.deepStrictEqual(req,{contract_version:'0.1',request_id:'req-001',knowledge_ref:'SR09_P_VALUE',source_product:'KU2A',surface:'analytics.results.hypothesis-test',requested_depth:'contextual',locale:'th-TH',audience_level:'default'});
const res={contract_version:'0.1',request_id:'req-001',knowledge_ref:'SR09_P_VALUE',resolved_depth:'contextual',locale:'th-TH',label:'p-value',text:'resolved by KU2C',concept_ref:'SR09_P_VALUE',related_refs:[],content_version:'0.1',term_owner:'KU2C',learning_owner:'KU2C',source_definition_version:null,status:'draft'};
assert.strictEqual(adapter.validateResponse(res,req),res);
assert.throws(()=>adapter.validateResponse({...res,knowledge_ref:'OTHER'},req),/ref mismatch/);

const catalog={contract_version:'0.1',catalog_version:'0.1.1',published_at:'2026-09-03T16:30:00Z',entries:[
  {knowledge_ref:'C08_KMEANS',canonical_label:'K-Means',aliases:['k means clustering'],available_depths:['contextual','glossary','concept'],term_owner:'KU2C',content_version:'0.1',status:'published'},
  {knowledge_ref:'KU2D.FIXTURE_REPLAY',canonical_label:'Fixture Replay',aliases:[],available_depths:['contextual','glossary'],term_owner:'KU2D',content_version:'1.0',status:'published'}
]};
const discovered=adapter.discoverCatalog(catalog,{query:'clustering',depth:'concept'});
assert.deepStrictEqual(discovered.map(item=>item.knowledge_ref),['C08_KMEANS']);
assert.ok(!Object.prototype.hasOwnProperty.call(discovered[0],'text'),'catalog discovery must remain metadata-only');

const manifest=adapter.buildSurfaceManifest({manifest_version:'0.1',surfaces:[{surface:'analytics.clustering.method-selector',supports:['contextual','glossary','concept'],bound_refs:[],keywords:['K-Means','clustering']}]});
assert.strictEqual(manifest.product,'KU2A');
assert.deepStrictEqual(manifest.surfaces[0].supports,['contextual','glossary','concept']);

const proposal=adapter.buildEntryRequest({request_type:'new_entry',proposed_label:'Probability Calibration',term_owner:'KU2A',source_definition:'Agreement between predicted probabilities and observed outcome frequencies.',source_definition_version:'ku2a-calibration-v1',needed_depths:['contextual','glossary'],intended_surfaces:['analytics.results.calibration'],locales:['en','th'],reason:'New calibration diagnostic needs reusable learning support.',request_id:'KR-KU2A-000041'});
assert.strictEqual(proposal.requester,'KU2A');
assert.strictEqual(proposal.term_owner,'KU2A');
assert.strictEqual(proposal.request_type,'new_entry');
assert.deepStrictEqual(proposal.intended_surfaces,['analytics.results.calibration']);
assert.throws(()=>adapter.buildEntryRequest({request_type:'unknown',reason:'x'}),/unsupported request_type/);

console.log('KU2A knowledge reference + C04 discovery/request consumer smoke PASS');
