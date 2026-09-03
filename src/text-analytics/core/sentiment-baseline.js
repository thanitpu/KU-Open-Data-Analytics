(function(root,factory){const api=factory(root);if(typeof module==='object'&&module.exports)module.exports=api;if(root)root.KUSentimentBaseline=api;})(typeof window!=='undefined'?window:globalThis,function(root){
  'use strict';
  const VERSION='0.1',LABELS=['negative','neutral','positive'];
  const cleanLabel=value=>String(value??'').trim().toLowerCase();
  function tokens(text,locale='th'){const raw=root.KUPhraseExtractor?.tokenize?root.KUPhraseExtractor.tokenize(text,locale):String(text??'').split(/\s+/);return root.KUPhraseExtractor?.meaningful?root.KUPhraseExtractor.meaningful(raw):raw.map(value=>String(value).toLowerCase()).filter(value=>value.length>=2);}
  function hashString(value){let hash=2166136261>>>0;for(let index=0;index<value.length;index++){hash^=value.charCodeAt(index);hash=Math.imul(hash,16777619);}return hash>>>0;}
  function splitRows(rows,{idField='review_id',labelField='sentiment_label',testFraction=.2}={}){
    const train=[],test=[];
    for(const row of rows||[]){const label=cleanLabel(row?.[labelField]);if(!LABELS.includes(label))continue;const key=String(row?.[idField]??JSON.stringify(row));((hashString(key)%10000)/10000<testFraction?test:train).push(row);}
    if(!test.length&&train.length>=5)test.push(...train.splice(-Math.max(1,Math.floor(train.length*testFraction))));
    return {train,test};
  }
  function train(rows,{textField='review_text',labelField='sentiment_label',locale='th',alpha=1}={}){
    const classDocs=new Map(),tokenCounts=new Map(),totalTokens=new Map(),vocab=new Set();
    for(const label of LABELS){classDocs.set(label,0);tokenCounts.set(label,new Map());totalTokens.set(label,0);}
    let totalDocs=0;
    for(const row of rows||[]){const label=cleanLabel(row?.[labelField]);if(!LABELS.includes(label))continue;totalDocs++;classDocs.set(label,classDocs.get(label)+1);for(const token of tokens(row?.[textField]??'',locale)){vocab.add(token);const counts=tokenCounts.get(label);counts.set(token,(counts.get(token)||0)+1);totalTokens.set(label,totalTokens.get(label)+1);}}
    const labels=LABELS.filter(label=>classDocs.get(label)>0);
    if(labels.length<2)throw new Error('Sentiment baseline requires at least two supported label classes.');
    return {version:VERSION,labels,totalDocs,classDocs,tokenCounts,totalTokens,vocab,alpha,locale};
  }
  function predict(model,text){
    const observed=tokens(text,model.locale),vocabulary=Math.max(1,model.vocab.size),scores={};
    for(const label of model.labels){let score=Math.log((model.classDocs.get(label)+1)/(model.totalDocs+model.labels.length));const denominator=model.totalTokens.get(label)+model.alpha*vocabulary,counts=model.tokenCounts.get(label);for(const token of observed)score+=Math.log(((counts.get(token)||0)+model.alpha)/denominator);scores[label]=score;}
    const entries=Object.entries(scores).sort((a,b)=>b[1]-a[1]),maximum=entries[0][1],weighted=entries.map(([label,score])=>[label,Math.exp(score-maximum)]),total=weighted.reduce((sum,[,value])=>sum+value,0)||1,probabilities=Object.fromEntries(weighted.map(([label,value])=>[label,value/total]));
    return {label:entries[0][0],confidence:Math.max(...Object.values(probabilities)),probabilities};
  }
  function metrics(actual,predicted,labels){
    const matrix=Object.fromEntries(labels.map(actualLabel=>[actualLabel,Object.fromEntries(labels.map(predictedLabel=>[predictedLabel,0]))]));
    actual.forEach((label,index)=>{if(matrix[label]&&Object.prototype.hasOwnProperty.call(matrix[label],predicted[index]))matrix[label][predicted[index]]++;});
    const perClass={};
    for(const label of labels){const tp=matrix[label][label],fp=labels.reduce((sum,item)=>sum+(item===label?0:matrix[item][label]),0),fn=labels.reduce((sum,item)=>sum+(item===label?0:matrix[label][item]),0),precision=tp/(tp+fp||1),recall=tp/(tp+fn||1);perClass[label]={precision,recall,f1:2*precision*recall/(precision+recall||1),support:actual.filter(item=>item===label).length};}
    return {accuracy:actual.length?actual.filter((label,index)=>label===predicted[index]).length/actual.length:0,macroF1:labels.length?labels.reduce((sum,label)=>sum+perClass[label].f1,0)/labels.length:0,perClass,confusionMatrix:matrix,total:actual.length};
  }
  function evaluate(rows,options={}){const split=splitRows(rows,options),model=train(split.train,options),predictions=split.test.map(row=>({row,actual:cleanLabel(row?.[options.labelField||'sentiment_label']),...predict(model,row?.[options.textField||'review_text']??'')}));return {model,split,metrics:metrics(predictions.map(item=>item.actual),predictions.map(item=>item.label),model.labels),predictions};}
  function predictRows(model,rows,{textField='review_text'}={}){return (rows||[]).map(row=>{const prediction=predict(model,row?.[textField]??'');return {...row,sentiment_predicted_label:prediction.label,sentiment_score:prediction.confidence};});}
  return {VERSION,LABELS,splitRows,train,predict,evaluate,predictRows};
});
