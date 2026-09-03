(function(root,factory){const api=factory(root);if(typeof module==='object'&&module.exports)module.exports=api;if(root)root.KUKeywordExtractor=api;})(typeof window!=='undefined'?window:globalThis,function(root){
  'use strict';
  const STOP=new Set(['the','a','an','and','or','is','are','was','were','to','of','in','for','on','with','this','that','it','very','และ','หรือ','ที่','ใน','ของ','เป็น','ก็','มี','ได้','ให้','กับ','จาก','มาก','ครับ','ค่ะ','นะ','ไม่']);
  function extract(values,{topN=25,minLength=2,locale='th'}={}){
    const counts=new Map(),tokenizer=root.KUTextTokenizer?.tokenize;
    for(const value of values||[])for(let token of tokenizer?tokenizer(value,locale):String(value??'').split(/\s+/)){
      token=String(token).trim().toLowerCase();
      if(token.length<minLength||STOP.has(token)||/^\d+$/.test(token))continue;
      counts.set(token,(counts.get(token)||0)+1);
    }
    return [...counts.entries()].sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0])).slice(0,topN).map(([term,count])=>({term,count}));
  }
  return {extract};
});
