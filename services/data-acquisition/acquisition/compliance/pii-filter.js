(function(root,factory){
  const api=factory();
  if(typeof module==="object"&&module.exports) module.exports=api;
  if(root) root.KUPIIFilter=api;
})(typeof window!=="undefined"?window:globalThis,function(){
  "use strict";
  function redact(text){
    return String(text??"")
      .replace(/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi,"<EMAIL>")
      .replace(/(?:\+?66|0)[\s-]?\d(?:[\s-]?\d){7,9}/g,"<PHONE>");
  }
  return {redact};
});
