(function(root,factory){
  const api=factory();
  if(typeof module==="object"&&module.exports) module.exports=api;
  if(root) root.KUCrawlerCore=api;
})(typeof window!=="undefined"?window:globalThis,function(){
  "use strict";
  class RateLimiter{
    constructor({minDelayMs=1500}={}){this.minDelayMs=minDelayMs;this.last=0;}
    async wait(){
      const delay=Math.max(0,this.minDelayMs-(Date.now()-this.last));
      if(delay) await new Promise(r=>setTimeout(r,delay));
      this.last=Date.now();
    }
  }
  function normalizeRecord(r){
    return {
      review_id:String(r.review_id??""),
      review_text:String(r.review_text??"").trim(),
      rating:r.rating===null||r.rating===undefined||r.rating===""?null:Number(r.rating),
      category:r.category??null,
      date:r.date??null,
      source:r.source??null,
      source_url:r.source_url??null
    };
  }
  function weakSentiment(rating){
    const x=Number(rating);
    if(!Number.isFinite(x)) return {label:null,confidence:null};
    if(x<=2) return {label:"negative",confidence:x===1?.95:.8};
    if(x===3) return {label:"neutral",confidence:.55};
    return {label:"positive",confidence:x===5?.95:.8};
  }
  return {RateLimiter,normalizeRecord,weakSentiment};
});
