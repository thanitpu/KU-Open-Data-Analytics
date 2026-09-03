(function(root,factory){const api=factory(root);if(typeof module==='object'&&module.exports)module.exports=api;if(root)root.KUTopicDiscovery=api;})(typeof window!=='undefined'?window:globalThis,function(root){
  'use strict';
  const VERSION='0.2-tfidf-kmeans';
  function tokens(text){return root.KUPhraseExtractor?root.KUPhraseExtractor.meaningful(root.KUPhraseExtractor.tokenize(text,'th')):String(text??'').toLowerCase().match(/[\u0E00-\u0E7F]+|[a-z]+/gu)||[];}
  function normMap(map){let sum=0;for(const value of map.values())sum+=value*value;sum=Math.sqrt(sum)||1;return new Map([...map].map(([key,value])=>[key,value/sum]));}
  function cosine(a,b){let score=0,small=a.size<=b.size?a:b,large=small===a?b:a;for(const [key,value] of small)score+=value*(large.get(key)||0);return score;}
  function meanVector(vectors,ids){const mean=new Map();for(const id of ids)for(const [key,value] of vectors[id])mean.set(key,(mean.get(key)||0)+value);for(const [key,value] of mean)mean.set(key,value/ids.length);return normMap(mean);}
  function discover(rows,{textField='review_text',numTopics=5,minDocFreq=2,maxTerms=600,maxIter=12}={}){
    if(!Array.isArray(rows)||rows.length<2)throw new Error('Topic discovery requires at least two records.');
    const documents=rows.map((row,index)=>({index,tokens:tokens(row?.[textField]??'')})),count=documents.length,documentFrequency=new Map();
    for(const document of documents)for(const token of new Set(document.tokens))documentFrequency.set(token,(documentFrequency.get(token)||0)+1);
    const vocabulary=[...documentFrequency].filter(([,frequency])=>frequency>=minDocFreq&&frequency/count<=.8).sort((a,b)=>b[1]-a[1]).slice(0,maxTerms).map(([term])=>term);
    if(!vocabulary.length)throw new Error('Topic discovery found no repeated informative terms.');
    const allowed=new Set(vocabulary),idf=new Map(vocabulary.map(term=>[term,Math.log((count+1)/((documentFrequency.get(term)||0)+1))+1]));
    const vectors=documents.map(document=>{const frequency=new Map();for(const token of document.tokens)if(allowed.has(token))frequency.set(token,(frequency.get(token)||0)+1);return normMap(new Map([...frequency].map(([term,value])=>[term,(1+Math.log(value))*idf.get(term)])));});
    const topicCount=Math.max(1,Math.min(Number(numTopics)||5,count)),seeds=[Math.max(0,vectors.findIndex(vector=>vector.size))];
    while(seeds.length<topicCount){let best=-1,bestDistance=-1;for(let index=0;index<count;index++){if(seeds.includes(index))continue;const distance=1-Math.max(...seeds.map(seed=>cosine(vectors[index],vectors[seed])));if(distance>bestDistance){bestDistance=distance;best=index;}}if(best<0)break;seeds.push(best);}
    let centroids=seeds.map(index=>vectors[index]),assignments=Array(count).fill(0);
    for(let iteration=0;iteration<maxIter;iteration++){let changed=0;for(let index=0;index<count;index++){let best=0,bestSimilarity=-Infinity;centroids.forEach((centroid,topic)=>{const similarity=cosine(vectors[index],centroid);if(similarity>bestSimilarity){bestSimilarity=similarity;best=topic;}});if(assignments[index]!==best){assignments[index]=best;changed++;}}const groups=Array.from({length:centroids.length},()=>[]);assignments.forEach((topic,index)=>groups[topic].push(index));centroids=groups.map((ids,index)=>ids.length?meanVector(vectors,ids):centroids[index]);if(!changed&&iteration>0)break;}
    const topics=centroids.map((centroid,oldId)=>{const docIds=assignments.map((topic,index)=>topic===oldId?index:-1).filter(index=>index>=0),terms=[...centroid].map(([term,weight])=>({term,score:weight*(idf.get(term)||1),count:docIds.filter(index=>documents[index].tokens.includes(term)).length})).sort((a,b)=>b.score-a.score).slice(0,10);return {oldId,docIds,size:docIds.length,share:docIds.length/count,terms,label:terms.slice(0,3).map(item=>item.term).join(' · ')||`Topic ${oldId+1}`,representatives:docIds.map(index=>({index,similarity:cosine(vectors[index],centroid)})).sort((a,b)=>b.similarity-a.similarity).slice(0,5).map(item=>({...item,text:String(rows[item.index]?.[textField]??'')}))};}).sort((a,b)=>b.size-a.size);
    topics.forEach((topic,id)=>{topic.id=id;delete topic.oldId;});
    return {version:VERSION,textField,totalDocuments:count,numTopics:topics.length,vocabularySize:vocabulary.length,topics};
  }
  function assignDerived(result,rows){const topicIds=Array(rows.length).fill(null),topicLabels=Array(rows.length).fill(null);for(const topic of result.topics)for(const index of topic.docIds){topicIds[index]=topic.id;topicLabels[index]=topic.label;}return {topicIds,topicLabels};}
  return {VERSION,discover,assignDerived};
});
