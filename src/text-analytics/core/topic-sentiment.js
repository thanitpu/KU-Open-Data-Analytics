(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;if(root)root.KUTopicSentiment=api;})(typeof window!=='undefined'?window:globalThis,function(){
  'use strict';
  function analyze(topicResult,rows,{labelField='sentiment_label'}={}){return topicResult.topics.map(topic=>{const counts={positive:0,negative:0,neutral:0,unknown:0};for(const index of topic.docIds){const label=String(rows[index]?.[labelField]??'').toLowerCase();counts[Object.prototype.hasOwnProperty.call(counts,label)?label:'unknown']++;}const known=counts.positive+counts.negative+counts.neutral;return {topicId:topic.id,topicLabel:topic.label,size:topic.size,share:topic.share,counts,positiveShare:known?counts.positive/known:0,negativeShare:known?counts.negative/known:0,neutralShare:known?counts.neutral/known:0,representatives:topic.representatives};});}
  return {analyze};
});
