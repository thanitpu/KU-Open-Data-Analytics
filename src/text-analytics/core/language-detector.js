(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;if(root)root.KULanguageDetector=api;})(typeof window!=='undefined'?window:globalThis,function(){
  'use strict';
  const thai=/[\u0E00-\u0E7F]/g,latin=/[A-Za-z]/g;
  function detectText(text){
    const value=String(text??''),th=(value.match(thai)||[]).length,en=(value.match(latin)||[]).length,total=th+en;
    if(!total)return {label:'other',thaiShare:0,englishShare:0};
    const thaiShare=th/total,englishShare=en/total;
    return {label:thaiShare>=.8?'th':englishShare>=.8?'en':th>0&&en>0?'mixed':'other',thaiShare,englishShare};
  }
  function summarize(values){
    const counts={th:0,en:0,mixed:0,other:0};
    for(const value of values)counts[detectText(value).label]++;
    const count=Math.max(1,values.length);
    return {counts,shares:Object.fromEntries(Object.entries(counts).map(([key,value])=>[key,value/count]))};
  }
  return {detectText,summarize};
});
