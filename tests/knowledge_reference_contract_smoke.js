const assert=require('assert');
const adapter=require('../src/knowledge-reference.js');
const req=adapter.buildRequest({knowledge_ref:'SR09_P_VALUE',surface:'analytics.results.hypothesis-test',request_id:'req-001'});
assert.deepStrictEqual(req,{contract_version:'0.1',request_id:'req-001',knowledge_ref:'SR09_P_VALUE',source_product:'KU2A',surface:'analytics.results.hypothesis-test',requested_depth:'contextual',locale:'th-TH',audience_level:'default'});
const res={contract_version:'0.1',request_id:'req-001',knowledge_ref:'SR09_P_VALUE',resolved_depth:'contextual',locale:'th-TH',label:'p-value',text:'resolved by KU2C',concept_ref:'SR09_P_VALUE',related_refs:[],content_version:'0.1',term_owner:'KU2C',learning_owner:'KU2C',source_definition_version:null,status:'draft'};
assert.strictEqual(adapter.validateResponse(res,req),res);
assert.throws(()=>adapter.validateResponse({...res,knowledge_ref:'OTHER'},req),/ref mismatch/);
console.log('KU2A knowledge reference consumer smoke PASS');
