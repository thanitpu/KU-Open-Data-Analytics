(function(root,factory){const api=factory(root);if(typeof module==='object'&&module.exports)module.exports=api;if(root)root.KUPhraseExtractor=api;})(typeof window!=='undefined'?window:globalThis,function(root){
  'use strict';
  const STOP=new Set(['the','a','an','and','or','is','are','was','were','to','of','in','for','on','with','this','that','it','very','i','you','we','they','he','she','my','your','our','their','but','so','as','at','be','been','have','has','had','และ','หรือ','ที่','ใน','ของ','เป็น','ก็','มี','ได้','ให้','กับ','จาก','มาก','ครับ','ค่ะ','นะ','ไม่','แต่','แล้ว','เรา','ผม','ฉัน','มัน','เลย','ยัง','อยู่','ไป','มา','นี้','นั้น','เพราะ','ถ้า','ว่า','จริง','ๆ']);
  function tokenize(text,locale='th'){const fn=root.KUTextTokenizer?.tokenize;return (fn?fn(text,locale):String(text??'').match(/[\u0E00-\u0E7F]+|[A-Za-z]+|\d+/gu)||[]).map(token=>String(token).trim().toLowerCase()).filter(Boolean);}
  function meaningful(tokens){return tokens.filter(token=>token.length>=2&&!STOP.has(token)&&!/^\d+$/.test(token));}
  function count(values,{n=2,topN=30,minCount=2,locale='th'}={}){
    const counts=new Map();
    for(const value of values||[]){const tokens=meaningful(tokenize(value,locale));for(let index=0;index<=tokens.length-n;index++){const phrase=tokens.slice(index,index+n).join(' ');counts.set(phrase,(counts.get(phrase)||0)+1);}}
    return [...counts.entries()].filter(([,frequency])=>frequency>=minCount).sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0])).slice(0,topN).map(([phrase,frequency])=>({phrase,count:frequency}));
  }
  function representative(rows,phrase,{textField='review_text',labelField='sentiment_label',limit=5}={}){
    const query=String(phrase||'').toLowerCase();
    return (rows||[]).filter(row=>String(row?.[textField]??'').toLowerCase().includes(query)).slice(0,limit).map(row=>({text:row?.[textField]??'',label:row?.[labelField]??null}));
  }
  function contrast(rows,{textField='review_text',labelField='sentiment_label',topN=20,locale='th'}={}){
    const groups={positive:[],negative:[],neutral:[]},vocabulary=new Map();
    for(const row of rows||[]){const label=String(row?.[labelField]||'').toLowerCase();if(groups[label])groups[label].push(row?.[textField]??'');}
    for(const [label,documents] of Object.entries(groups)){const local=new Map();for(const document of documents)for(const term of new Set(meaningful(tokenize(document,locale))))local.set(term,(local.get(term)||0)+1);for(const [term,frequency] of local){if(!vocabulary.has(term))vocabulary.set(term,{term,positive:0,negative:0,neutral:0});vocabulary.get(term)[label]=frequency;}}
    const scored=[...vocabulary.values()].map(item=>({...item,logOdds:Math.log(((item.positive+.5)/(groups.positive.length+1))/((item.negative+.5)/(groups.negative.length+1)))}));
    return {positive:scored.filter(item=>item.logOdds>0).sort((a,b)=>b.logOdds-a.logOdds).slice(0,topN),negative:scored.filter(item=>item.logOdds<0).sort((a,b)=>a.logOdds-b.logOdds).slice(0,topN)};
  }
  return {count,contrast,representative,tokenize,meaningful};
});
