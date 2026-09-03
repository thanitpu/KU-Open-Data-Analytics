(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;if(root)root.KUTextNormalizer=api;})(typeof window!=='undefined'?window:globalThis,function(){
  'use strict';
  function normalize(text,{lowercaseEnglish=false,replaceUrls=true,collapseWhitespace=true}={}){
    let value=String(text??'').normalize('NFKC');
    if(replaceUrls)value=value.replace(/https?:\/\/\S+|www\.\S+/gi,' <URL> ');
    if(lowercaseEnglish)value=value.replace(/[A-Z]+/g,match=>match.toLowerCase());
    if(collapseWhitespace)value=value.replace(/\s+/g,' ').trim();
    return value;
  }
  return {normalize};
});
