(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;if(root)root.KUTextTokenizer=api;})(typeof window!=='undefined'?window:globalThis,function(){
  'use strict';
  function tokenize(text,locale='th'){
    const value=String(text??'').trim();
    if(!value)return [];
    if(typeof Intl!=='undefined'&&Intl.Segmenter){
      try{return [...new Intl.Segmenter(locale,{granularity:'word'}).segment(value)].filter(item=>item.isWordLike).map(item=>item.segment);}catch(_error){}
    }
    return value.match(/[\u0E00-\u0E7F]+|[A-Za-z]+(?:'[A-Za-z]+)?|\d+(?:\.\d+)?/gu)||[];
  }
  return {tokenize};
});
