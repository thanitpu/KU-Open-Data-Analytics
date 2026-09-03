(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;if(root)root.KUTextFieldDetector=api;})(typeof window!=='undefined'?window:globalThis,function(){
  'use strict';
  const missing=value=>value===null||value===undefined||String(value).trim()==='';
  const numericLike=value=>/^[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?$/.test(value.replace(/,/g,''));
  function sampleValues(values,limit=5000){
    const observed=(Array.isArray(values)?values:[]).filter(value=>!missing(value));
    if(observed.length<=limit)return observed;
    return Array.from({length:limit},(_,index)=>observed[Math.floor((index+.5)*observed.length/limit)]);
  }
  function detect({fieldName='',values=[]}={}){
    const strings=sampleValues(values).map(value=>String(value).trim());
    if(!strings.length)return {fieldName,semanticType:'empty',confidence:1,reasons:['No observed values'],stats:{observed:0}};
    const count=strings.length,unique=new Set(strings).size,uniqueRatio=unique/count;
    const numericRatio=strings.filter(numericLike).length/count;
    const avgChars=strings.reduce((sum,value)=>sum+value.length,0)/count;
    const whitespaceRatio=strings.filter(value=>/\s/.test(value)).length/count;
    const longRatio=strings.filter(value=>value.length>=30).length/count;
    const sentenceLikeRatio=strings.filter(value=>/[.!?…。！？]|[\u0E00-\u0E7F].{8,}/u.test(value)).length/count;
    const identifierName=/(^|_)(id|uuid|sku|code|invoice|receipt|order|customer_no|serial)(_|$)/i.test(fieldName);
    const textHint=/(comment|review|message|description|feedback|remark|reason|note|text|content|caption)/i.test(fieldName);
    let semanticType='categorical',confidence=.72,reasons=['Values are better represented as repeated categories than free text.'];
    if(numericRatio>=.95){semanticType='numeric_like_text';confidence=.97;reasons=['Most observed values are numeric strings.'];}
    else if(identifierName&&uniqueRatio>=.8){semanticType='identifier';confidence=.97;reasons=['Field name is identifier-like and values are highly unique.'];}
    else if(uniqueRatio>=.98&&avgChars<28&&whitespaceRatio<.15&&!textHint){semanticType='identifier';confidence=.88;reasons=['Very high uniqueness with short token-like values.'];}
    else if(textHint||avgChars>=45||longRatio>=.35||sentenceLikeRatio>=.25||(uniqueRatio>=.7&&whitespaceRatio>=.35)){
      semanticType='text';confidence=Math.min(.99,.72+(textHint?.12:0)+(longRatio>=.35?.08:0)+(sentenceLikeRatio>=.25?.07:0));
      reasons=[textHint?'Field name suggests free text.':'Observed values have free-text characteristics.'];
    }
    return {fieldName,semanticType,confidence:Number(confidence.toFixed(3)),reasons,stats:{observed:count,unique,uniqueRatio,avgChars,numericRatio,whitespaceRatio,longRatio,sentenceLikeRatio}};
  }
  return {detect,sampleValues};
});
