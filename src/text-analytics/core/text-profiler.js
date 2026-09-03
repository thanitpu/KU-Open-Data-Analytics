(function(root,factory){const api=factory(root);if(typeof module==='object'&&module.exports)module.exports=api;if(root)root.KUTextProfiler=api;})(typeof window!=='undefined'?window:globalThis,function(root){
  'use strict';
  const VERSION='1.0',missing=value=>value===null||value===undefined||String(value).trim()==='';
  function percentile(sorted,p){if(!sorted.length)return 0;const index=(sorted.length-1)*p,low=Math.floor(index),high=Math.ceil(index);return low===high?sorted[low]:sorted[low]+(sorted[high]-sorted[low])*(index-low);}
  function profile({fieldName='',values=[],sampleLimit=10000}={}){
    const all=Array.isArray(values)?values:[],observedAll=all.filter(value=>!missing(value));let observed=observedAll;
    if(observed.length>sampleLimit)observed=Array.from({length:sampleLimit},(_,index)=>observedAll[Math.floor((index+.5)*observedAll.length/sampleLimit)]);
    const strings=observed.map(value=>String(value).trim()),lengths=strings.map(value=>value.length).sort((a,b)=>a-b),unique=new Set(strings).size;
    const percent=fn=>strings.length?100*strings.filter(fn).length/strings.length:0;
    return {schemaVersion:VERSION,field:{name:fieldName,semanticType:'text'},provenance:{datasetRows:all.length,profileRows:strings.length,sampled:observedAll.length>strings.length,sampleLimit},documents:{total:all.length,observed:observedAll.length,missing:all.length-observedAll.length,uniqueEstimate:unique,duplicatePct:strings.length?100*(1-unique/strings.length):0},length:{min:lengths[0]||0,q1:percentile(lengths,.25),median:percentile(lengths,.5),q3:percentile(lengths,.75),max:lengths.at(-1)||0,mean:lengths.length?lengths.reduce((a,b)=>a+b,0)/lengths.length:0},language:(root.KULanguageDetector?.summarize||(()=>({counts:{},shares:{}})))(strings),quality:{urlPct:percent(value=>/https?:\/\/|www\./i.test(value)),emojiPct:percent(value=>/\p{Extended_Pictographic}/u.test(value)),repeatedCharacterPct:percent(value=>/(.)\1{3,}/u.test(value)),veryShortPct:percent(value=>value.length<5)}};
  }
  return {VERSION,profile};
});
