(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;if(root)root.KUDerivedFeatureContract=api;})(typeof window!=='undefined'?window:globalThis,function(){
  'use strict';
  const VERSION='1.0';
  function create({name,sourceField,storageType,measurementLevel,method,values=null,metadata={}}){
    if(!name||!sourceField||!method)throw new Error('name, sourceField and method are required.');
    return {schemaVersion:VERSION,name,sourceField,storageType,measurementLevel,method,usableAsPredictor:true,values,metadata:{...metadata}};
  }
  return {VERSION,create};
});
