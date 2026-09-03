(function(root){
  'use strict';
  const VERSION='0.1';
  const PRODUCTS=new Set(['KUOpen','KU2A','KU2B','KU2C','KU2D']);
  const DEPTHS=new Set(['contextual','glossary','concept']);

  function requireText(value,name){if(typeof value!=='string'||!value.trim())throw new Error(name+' is required');return value.trim();}
  function buildRequest({knowledge_ref,surface,requested_depth='contextual',locale='th-TH',audience_level='default',request_id}){
    const ref=requireText(knowledge_ref,'knowledge_ref');
    const sf=requireText(surface,'surface');
    if(!DEPTHS.has(requested_depth))throw new Error('unsupported requested_depth');
    return {contract_version:VERSION,request_id:request_id||('ku2a-'+Date.now()),knowledge_ref:ref,source_product:'KU2A',surface:sf,requested_depth,locale,audience_level};
  }
  function validateResponse(payload,request){
    if(!payload||payload.contract_version!==VERSION)throw new Error('unsupported knowledge contract version');
    if(payload.request_id!==request.request_id)throw new Error('knowledge response request_id mismatch');
    if(payload.knowledge_ref!==request.knowledge_ref)throw new Error('knowledge response ref mismatch');
    if(payload.learning_owner!=='KU2C')throw new Error('KU2C must own learning representation');
    if(!PRODUCTS.has(payload.term_owner))throw new Error('unknown term_owner');
    return payload;
  }
  const api={VERSION,buildRequest,validateResponse};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  root.KU2AKnowledgeReference=api;
})(typeof window!=='undefined'?window:globalThis);
