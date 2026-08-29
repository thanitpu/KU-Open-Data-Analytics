/*
  Intentionally no automatic robots.txt bypass or scraper logic here.
  Each source adapter must document:
  - public URL pattern
  - robots.txt review date
  - Terms/API constraints
  - rate limit
  - fields collected
  - fields deliberately excluded (username/profile/photo/PII)
*/
(function(root,factory){
  const api=factory();
  if(typeof module==="object"&&module.exports) module.exports=api;
  if(root) root.KURobotsCompliance=api;
})(typeof window!=="undefined"?window:globalThis,function(){
  "use strict";
  function checklist(source){
    return {
      source,
      robotsReviewed:false,
      termsReviewed:false,
      loginRequired:null,
      apiPreferred:null,
      piiExcluded:true,
      approvedForPOC:false,
      notes:[]
    };
  }
  return {checklist};
});
