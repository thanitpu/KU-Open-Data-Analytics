(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;if(root)root.KUTextProfileContract=api;})(typeof window!=='undefined'?window:globalThis,function(){
  'use strict';
  const VERSION='1.0';
  function validate(profile){
    if(!profile||typeof profile!=='object')throw new Error('Profile must be an object.');
    if(profile.schemaVersion!==VERSION)throw new Error('Unsupported profile schema.');
    if(!profile.field||typeof profile.field.name!=='string')throw new Error('Profile field is required.');
    if(!profile.documents||typeof profile.documents.total!=='number')throw new Error('Document summary is required.');
    return true;
  }
  return {VERSION,validate};
});
