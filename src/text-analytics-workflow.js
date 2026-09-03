(function(root){
  'use strict';
  const esc=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const rows=()=>root.KUDataLoader?.getRows?.()||[];
  const state=()=>root.KUAppState?.getState?.()||{};
  const values=field=>rows().map(row=>row?.[field]);
  const text=()=>state().textAnalysis||{};
  const fmt=value=>Number.isFinite(Number(value))?Number(value).toFixed(3):'—';

  function candidates(){return (state().dataset?.fields||[]).map(field=>root.KUTextFieldDetector.detect({fieldName:field.name,values:values(field.name)})).filter(item=>item.semanticType==='text').sort((a,b)=>b.confidence-a.confidence);}
  function chooseTextField(field){
    if(!field)return;
    const profile=root.KUTextProfiler.profile({fieldName:field,values:values(field)});
    root.KUTextProfileContract.validate(profile);
    root.KUAppState.updateTextAnalysis({selectedTextField:field,profile,terms:root.KUKeywordExtractor.extract(values(field)),phrases:root.KUPhraseExtractor.count(values(field),{n:2}),sentiment:null,topics:null,topicSentiment:null,semantic:null,curation:{},derivedFeatures:[]});
    renderAll(true);
  }
  function selectField(event){chooseTextField(event.target.value);}
  function selectLabel(event){root.KUAppState.updateTextAnalysis({labelField:event.target.value||null,sentiment:null,topicSentiment:null,derivedFeatures:[]});renderAll(true);}
  function runSentiment(){
    const current=text(),field=current.selectedTextField,labelField=document.getElementById('textSentimentLabel')?.value||current.labelField;
    if(!field||!labelField)return root.alert('Choose a text field and a supervised sentiment label field first.');
    try{
      const sourceRows=rows(),model=root.KUSentimentBaseline.train(sourceRows,{textField:field,labelField}),predicted=root.KUSentimentBaseline.predictRows(model,sourceRows,{textField:field});let evaluation=null;
      try{evaluation=root.KUSentimentBaseline.evaluate(sourceRows,{textField:field,labelField});}catch(_error){}
      const sentiment={version:root.KUSentimentBaseline.VERSION,labelField,labels:model.labels,predictedLabels:predicted.map(row=>row.sentiment_predicted_label),scores:predicted.map(row=>row.sentiment_score),metrics:evaluation?.metrics||null,trainingRows:model.totalDocs};
      root.KUAppState.updateTextAnalysis({labelField,sentiment,topicSentiment:null,derivedFeatures:[]});renderAll(true);
    }catch(error){root.alert(error.message);}
  }
  function runTopics(){
    const current=text(),field=current.selectedTextField,count=Number(document.getElementById('textTopicCount')?.value||5);
    if(!field)return root.alert('Choose a text field first.');
    try{
      const topicResult=root.KUTopicDiscovery.discover(rows(),{textField:field,numTopics:count});
      let topicSentiment=null;
      if(current.sentiment){const annotated=rows().map((row,index)=>({...row,__ku2a_sentiment:current.sentiment.predictedLabels[index]}));topicSentiment=root.KUTopicSentiment.analyze(topicResult,annotated,{labelField:'__ku2a_sentiment'});}
      else if(current.labelField)topicSentiment=root.KUTopicSentiment.analyze(topicResult,rows(),{labelField:current.labelField});
      root.KUAppState.updateTextAnalysis({topics:topicResult,topicSentiment,curation:{},derivedFeatures:[]});renderAll(true);
    }catch(error){root.alert(error.message);}
  }
  function runSearch(){
    const current=text(),query=document.getElementById('textSemanticQuery')?.value||'';
    if(!current.selectedTextField)return root.alert('Choose a text field first.');
    try{root.KUAppState.updateTextAnalysis({semantic:{mode:'search',...root.KUSemanticBrowser.semanticSearch(values(current.selectedTextField),query,8)}});renderAll(true);}catch(error){root.alert(error.message);}
  }
  function runSimilar(index){
    const current=text();
    if(!current.selectedTextField)return;
    try{root.KUAppState.updateTextAnalysis({semantic:{mode:'similar',...root.KUSemanticBrowser.similarDocuments(values(current.selectedTextField),Number(index),5)}});renderAll(true);}catch(error){root.alert(error.message);}
  }
  function curate(topicId,property,value){
    const current=text(),existing=current.curation?.[topicId]||{label:current.topics?.topics?.find(topic=>topic.id===Number(topicId))?.label||'',action:'keep'};
    const patch=property==='action'&&String(value).startsWith('merge:')?{...existing,action:'merge',mergeInto:Number(String(value).split(':')[1])}:{...existing,[property]:value,mergeInto:property==='action'?null:existing.mergeInto};
    root.KUAppState.updateTextCuration(topicId,patch);root.KUAppState.updateTextAnalysis({derivedFeatures:[]});renderAll(true);
  }
  function buildFeatures(){
    const current=text(),features=[];
    if(current.sentiment)features.push(...root.KUTextAnalyticsAdapter.sentimentDerivedFeatures({sourceField:current.selectedTextField,predictedLabels:current.sentiment.predictedLabels,scores:current.sentiment.scores,modelVersion:`baseline-nb-${current.sentiment.version}`}));
    if(current.topics)features.push(...root.KUTextAnalyticsAdapter.topicDerivedFeatures({sourceField:current.selectedTextField,topicResult:current.topics,rows:rows(),curation:current.curation}));
    root.KUAppState.updateTextAnalysis({derivedFeatures:features});
    return features;
  }
  function exportDerived(){
    const features=buildFeatures();
    if(!features.length)return root.alert('Run sentiment or topic discovery before exporting derived features.');
    const enriched=root.KUTextAnalyticsAdapter.attachFeatures(rows(),features);
    root.KUCSVExporter.download('ku2a-text-derived-features.csv',root.KUCSVExporter.toCSV(enriched));
  }
  function exportManifest(){
    const current=text(),features=current.derivedFeatures?.length?current.derivedFeatures:buildFeatures(),manifest=root.KUTextAnalyticsAdapter.integrationManifest({sourceField:current.selectedTextField,features,datasetRows:rows().length,dataset:state().dataset});
    root.KUCSVExporter.download('ku2a-text-derived-feature-manifest.json',JSON.stringify(manifest,null,2),'application/json');
  }
  function evidence(){
    const current=text();
    return (current.topicSentiment||[]).map(topic=>({...topic,priorityScore:topic.share*topic.negativeShare})).sort((a,b)=>b.priorityScore-a.priorityScore).slice(0,5);
  }
  function fieldOptions(selected,filter=()=>true){return (state().dataset?.fields||[]).filter(filter).map(field=>`<option value="${esc(field.name)}" ${field.name===selected?'selected':''}>${esc(field.name)}</option>`).join('');}
  function renderProfile(){
    const node=document.getElementById('textAnalyticsProfile');if(!node)return;
    const profileSignature=JSON.stringify({revision:state().dataset?.revision,text:text()});
    if(node.dataset.signature===profileSignature)return;
    node.dataset.signature=profileSignature;
    if(!state().dataset?.loaded){node.innerHTML='<div class="empty">Load a dataset to inspect text fields.</div>';return;}
    const current=text(),found=candidates();
    if(!current.selectedTextField&&found[0])setTimeout(()=>chooseTextField(found[0].fieldName),0);
    const profile=current.profile;
    node.innerHTML=`<section class="card text-card"><div class="head">Text field profile <span class="text-badge">deterministic</span></div><div class="body"><label class="text-control"><span>Text field</span><select onchange="KUTextAnalyticsWorkflow.selectField(event)"><option value="">Choose a field</option>${found.map(item=>`<option value="${esc(item.fieldName)}" ${item.fieldName===current.selectedTextField?'selected':''}>${esc(item.fieldName)} · ${Math.round(item.confidence*100)}%</option>`).join('')}</select></label>${profile?`<div class="text-metrics"><span><b>${profile.documents.observed}</b> observed</span><span><b>${fmt(profile.documents.duplicatePct)}%</b> duplicates</span><span><b>${fmt(profile.length.median)}</b> median chars</span><span><b>${profile.language.counts.th||0}</b> Thai</span><span><b>${profile.language.counts.en||0}</b> English</span><span><b>${profile.language.counts.mixed||0}</b> mixed</span></div><p class="note">Profiled ${profile.provenance.profileRows} of ${profile.provenance.datasetRows} rows${profile.provenance.sampled?' using deterministic sampling':''}. No rows were modified.</p>`:'<div class="empty">Choose a detected text field.</div>'}</div></section>${profile?`<div class="text-grid"><section class="card"><div class="head">Terms</div><div class="body text-chip-list">${current.terms.map(item=>`<span>${esc(item.term)} <b>${item.count}</b></span>`).join('')||'<div class="empty">No repeated terms.</div>'}</div></section><section class="card"><div class="head">Phrases</div><div class="body text-chip-list">${current.phrases.map(item=>`<span>${esc(item.phrase)} <b>${item.count}</b></span>`).join('')||'<div class="empty">No repeated phrases.</div>'}</div></section></div>`:''}`;
  }
  function analyzeHTML(){
    const current=text();if(!current.selectedTextField)return '<div class="empty">Choose a text field in Data Profile first.</div>';
    const labels=fieldOptions(current.labelField,field=>field.name!==current.selectedTextField);
    const topics=(current.topics?.topics||[]).map(topic=>`<li><b>${esc(topic.label)}</b> · ${topic.size} documents</li>`).join('');
    const search=current.semantic?.results?.map(item=>`<li><button class="text-link" onclick="KUTextAnalyticsWorkflow.runSimilar(${item.index})">#${item.index}</button> ${esc(item.text).slice(0,180)} <small>${fmt(item.similarity)}</small></li>`).join('')||'';
    return `<div class="text-grid"><section class="card text-card"><div class="head">Sentiment baseline <span class="text-badge">supervised</span></div><div class="body"><p class="note">Requires an existing field whose values include at least two of negative, neutral, and positive. Labels remain authoritative training evidence.</p><label class="text-control"><span>Label field</span><select id="textSentimentLabel" onchange="KUTextAnalyticsWorkflow.selectLabel(event)"><option value="">Choose label field</option>${labels}</select></label><button class="btn secondary" onclick="KUTextAnalyticsWorkflow.runSentiment()">Train and evaluate baseline</button>${current.sentiment?`<div class="text-metrics"><span><b>${current.sentiment.trainingRows}</b> labelled rows</span><span><b>${current.sentiment.labels.length}</b> classes</span><span><b>${fmt(current.sentiment.metrics?.macroF1)}</b> test macro-F1</span></div>`:''}</div></section><section class="card text-card"><div class="head">Topic discovery <span class="text-badge">TF-IDF k-means</span></div><div class="body"><label class="text-control"><span>Requested topics</span><input id="textTopicCount" type="number" min="2" max="12" value="${current.topics?.numTopics||5}"></label><button class="btn secondary" onclick="KUTextAnalyticsWorkflow.runTopics()">Discover topics</button>${topics?`<ol class="text-result-list">${topics}</ol>`:''}</div></section></div><section class="card text-card"><div class="head">Semantic retrieval <span class="text-badge warning">browser lexical fallback</span></div><div class="body"><p class="note">This browser result is TF-IDF lexical similarity, not transformer output. The KU2A backend exposes a separately versioned semantic endpoint and identifies LSA fallback explicitly.</p><div class="row"><input id="textSemanticQuery" placeholder="Search this text field"><button class="btn secondary" onclick="KUTextAnalyticsWorkflow.runSearch()">Search</button></div>${search?`<ol class="text-result-list">${search}</ol>`:''}</div></section>`;
  }
  function prepareHTML(){
    const current=text();if(!current.topics)return '<div class="empty">Run topic discovery in Analyze before curating topics.</div>';
    return `<section class="card text-card"><div class="head">Topic curation <span class="text-badge">human decision</span></div><div class="body"><p class="note">Rename, keep, merge, or exclude a topic explicitly. Source assignments and evidence remain unchanged.</p>${current.topics.topics.map(topic=>{const rule=current.curation?.[topic.id]||{label:topic.label,action:'keep'};return `<div class="text-curation"><span>#${topic.id+1} · ${topic.size} rows</span><input value="${esc(rule.label)}" onchange="KUTextAnalyticsWorkflow.curate(${topic.id},'label',this.value)"><select onchange="KUTextAnalyticsWorkflow.curate(${topic.id},'action',this.value)"><option value="keep" ${rule.action==='keep'?'selected':''}>Keep</option>${current.topics.topics.filter(target=>target.id!==topic.id).map(target=>`<option value="merge:${target.id}" ${rule.action==='merge'&&Number(rule.mergeInto)===target.id?'selected':''}>Merge into #${target.id+1}</option>`).join('')}<option value="exclude" ${rule.action==='exclude'?'selected':''}>Exclude as noise</option></select></div>`;}).join('')}</div></section>`;
  }
  function setupHTML(){const current=text();return `<section class="card text-card"><div class="head">Text analysis setup</div><div class="body"><div class="text-metrics"><span><b>${esc(current.selectedTextField||'—')}</b> text field</span><span><b>${current.sentiment?'yes':'no'}</b> sentiment baseline</span><span><b>${current.topics?.numTopics||0}</b> discovered topics</span></div><p class="note">No imputation, row removal, target substitution, production scheduling, or operational inference is enabled.</p></div></section>`;}
  function resultsHTML(){
    const current=text(),summary=evidence();
    return `<section class="card text-card"><div class="head">Text evidence summary <span class="text-badge">descriptive</span></div><div class="body">${summary.length?`<ol class="text-result-list">${summary.map(item=>`<li><b>${esc(current.curation?.[item.topicId]?.label||item.topicLabel)}</b> · prevalence ${fmt(item.share*100)}% · negative ${fmt(item.negativeShare*100)}% · priority ${fmt(item.priorityScore)}</li>`).join('')}</ol>`:'<div class="empty">Run topic discovery and supply sentiment labels to calculate Topic × Sentiment evidence.</div>'}<div class="row"><button class="btn secondary" onclick="KUTextAnalyticsWorkflow.exportDerived()">Export rows + derived features</button><button class="btn" onclick="KUTextAnalyticsWorkflow.exportManifest()">Export feature manifest</button></div><p class="note">Exports preserve KU2D lineage fields on every imported row. Evidence is descriptive and does not create KU2B inference authority.</p></div></section>`;
  }
  function inject(step,html){const host=step==='analyze'?document.getElementById('aiAnalyticsView'):document.getElementById('journeyPendingView');if(!host||host.classList.contains('hidden'))return;let panel=host.querySelector('[data-text-analytics-stage]');if(!panel){panel=document.createElement('section');panel.dataset.textAnalyticsStage=step;panel.className='text-stage';host.appendChild(panel);}const signature=JSON.stringify(text())+step;if(panel.dataset.signature===signature)return;panel.dataset.signature=signature;panel.innerHTML=`<div class="step-kicker text-kicker">TEXT ANALYTICS</div>${html}`;}
  function renderAll(force=false){renderProfile();const step=state().currentStep;if(step==='analyze')inject(step,analyzeHTML());else if(step==='prepare')inject(step,prepareHTML());else if(step==='setup')inject(step,setupHTML());else if(step==='results')inject(step,resultsHTML());if(force)setTimeout(()=>renderAll(false),0);}
  const api={selectField,selectLabel,runSentiment,runTopics,runSearch,runSimilar,curate,exportDerived,exportManifest,buildFeatures,renderAll,candidates,evidence};
  root.KUTextAnalyticsWorkflow=Object.freeze(api);
  document.addEventListener('DOMContentLoaded',()=>{root.KUAppState?.subscribe(()=>setTimeout(()=>renderAll(false),0));const main=document.querySelector('main');if(main&&typeof MutationObserver!=='undefined')new MutationObserver(()=>setTimeout(()=>renderAll(false),0)).observe(main,{childList:true,subtree:true});renderAll(false);});
})(typeof window!=='undefined'?window:globalThis);
