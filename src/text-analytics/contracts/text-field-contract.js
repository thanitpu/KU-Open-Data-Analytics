(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;if(root)root.KUTextFieldContract=api;})(typeof window!=='undefined'?window:globalThis,function(){
  'use strict';
  const SEMANTIC_TYPES=Object.freeze(['text','categorical','identifier','numeric_like_text','empty']);
  function validate(result){
    if(!result||typeof result!=='object')throw new Error('Text field result must be an object.');
    if(!SEMANTIC_TYPES.includes(result.semanticType))throw new Error('Unknown semanticType.');
    if(typeof result.fieldName!=='string')throw new Error('fieldName is required.');
    return true;
  }
  return {SEMANTIC_TYPES,validate};
});
