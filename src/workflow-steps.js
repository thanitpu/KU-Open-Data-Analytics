// KU Open DA — production Step 4 Prepare, Step 5 Setup, Step 6 Results
(function(root){
'use strict';

const el=id=>document.getElementById(id);
const safe=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const fmt=(v,d=3)=>Number.isFinite(Number(v))?Number(v).toFixed(d):'—';
const STANDARD_ORDINAL_SEQUENCES=[
  ['low','medium','high'],
  ['poor','fair','good','very good','excellent'],
  ['strongly disagree','disagree','neutral','agree','strongly agree']
];
let capabilitiesCache=null;

const plan=()=>root.KUAppState?.getState().analysisPlan||{};
const resultState=()=>root.KUAppState?.getState().result||{};

function selectedFields(p=plan()){
  return [...new Set([p.target,...(p.predictors||[])].filter(Boolean))];
}
function executionFields(p=plan()){
  try{return root.KUAnalyticsClient?.selectedCsvFields?.(p)||selectedFields(p)}catch(_){return selectedFields(p)}
}
function derivedFields(p=plan()){
  return [...new Set((p.preparation?.featureEngineering?.derivedFields||[]).filter(Boolean))];
}
function isPresent(v){return v!==''&&v!==null&&v!==undefined}
function observed(h){return data.map(r=>r[h]).filter(isPresent)}
function summary(h){
  const vals=observed(h),unique=new Set(vals.map(String)).size;
  return {name:h,storage:types[h],level:meta[h]?.level||'Nominal',missing:data.length-vals.length,unique,n:vals.length};
}
function valueCounts(h){
  const counts=new Map();
  for(const value of observed(h)){
    const key=String(value);
    counts.set(key,(counts.get(key)||0)+1);
  }
  return [...counts.entries()].sort((a,b)=>b[1]-a[1]);
}
function recognizedOrdinalEncoding(h){
  const representatives=new Map(),keys=[];
  for(const value of observed(h)){
    const label=String(value).trim(),key=label.toLocaleLowerCase();
    if(!representatives.has(key))representatives.set(key,label);
    keys.push(key);
  }
  const observedKeys=new Set(keys);
  if(observedKeys.size<2)return null;
  for(const sequence of STANDARD_ORDINAL_SEQUENCES){
    if([...observedKeys].every(key=>sequence.includes(key))){
      const ordered=sequence.filter(key=>observedKeys.has(key));
      return {
        order:ordered.map(key=>representatives.get(key)),
        mapping:Object.fromEntries(ordered.map((key,index)=>[representatives.get(key),index+1]))
      };
    }
  }
  return null;
}
function completeGroupCounts(target,group){
  const counts=new Map();
  if(!target||!group)return [];
  for(const row of data){
    if(!isPresent(row[target])||!isPresent(row[group])||!Number.isFinite(Number(row[target])))continue;
    const key=String(row[group]);
    counts.set(key,(counts.get(key)||0)+1);
  }
  return [...counts.entries()].sort((a,b)=>a[0].localeCompare(b[0]));
}
function hideMainViews(){
  ['workspaceView','variablesView','analysisView','aiAnalyticsView'].forEach(id=>el(id)?.classList.add('hidden'));
}
function host(){
  let view=el('journeyPendingView');
  if(!view){
    view=document.createElement('section');
    view.id='journeyPendingView';
    document.querySelector('main')?.appendChild(view);
  }
  hideMainViews();
  view.classList.remove('hidden');
  return view;
}
function currentBar(){return '<div class="current-analysis-bar" data-current-analysis></div>'}
function emitBar(){document.dispatchEvent(new CustomEvent('ku:render-current-analysis'))}
function routeLabel(route){
  return ({
    'regression':'Regression',
    'binary-classification':'Binary Classification',
    'multiclass-classification':'Multiclass Classification',
    'clustering':'Clustering / Segmentation',
    'association':'Association Analysis',
    'group-comparison':'Group Comparison'
  })[route]||route||'Not derived';
}

function prepRule(p,s){
  const isTarget=s.name===p.target;
  if(isTarget){
    if(p.route==='regression'&&s.storage!=='numeric'){
      const encoding=s.level==='Ordinal'?recognizedOrdinalEncoding(s.name):null;
      if(encoding){
        return [
          'Encode ordered categories',
          encoding.order.join(' < '),
          'The validated regression engine rank-encodes recognized ordinal scales before fitting. Rank spacing is numeric for modeling but should be interpreted cautiously.',
          'ok'
        ];
      }
      return ['Blocked','Recognized ordinal coding required','This text target cannot be safely ordered from the validated standard ordinal sequences, so KU Open DA will not invent a category order.','block'];
    }
    if(['binary-classification','multiclass-classification'].includes(p.route)){
      const counts=valueCounts(s.name);
      const smallest=counts.length?Math.min(...counts.map(([,n])=>n)):0;
      return [
        s.missing?'Exclude rows with missing target':'Keep observed target rows',
        `${s.missing} missing · ${counts.length} classes · smallest class ${smallest}`,
        'Validated classification uses 5-fold stratified out-of-fold validation, so each class needs enough observed rows.',
        smallest<5?'block':'ok'
      ];
    }
    return [
      s.missing?'Exclude rows with missing target':'Keep observed target rows',
      `${s.missing} missing`,
      'Validated target-based engines remove rows where the target is missing.',
      'ok'
    ];
  }
  if(p.route==='clustering'){
    return [s.missing?'Median imputation':'Use as numeric feature',`${s.missing} missing`,'Segmentation uses median imputation, StandardScaler, then PCA before KMeans.','ok'];
  }
  if(['regression','binary-classification','multiclass-classification'].includes(p.route)){
    if(s.storage==='numeric'){
      return [s.missing?'Median imputation':'Use numeric predictor',`${s.missing} missing`,'Validated model preprocessing imputes numeric predictors with the median.','ok'];
    }
    return [s.missing?'Most-frequent imputation + one-hot':'One-hot encode',`${s.missing} missing · ${s.unique} levels`,'Validated model preprocessing imputes categorical predictors with the most frequent value and one-hot encodes them.','ok'];
  }
  if(p.route==='association'){
    return ['Pairwise complete observations',`${s.missing} missing · ${s.unique} unique`,'Association tests use complete observations for each field pair; IDs/constants are excluded by the backend.','ok'];
  }
  if(p.route==='group-comparison'){
    return ['Complete-case comparison',`${s.missing} missing · ${s.unique} unique`,'The group-comparison route removes rows missing the numeric outcome or selected grouping field.','ok'];
  }
  return ['Review','—','No route-specific preparation rule is available.','review'];
}

function candidateGroups(p){
  return (p.predictors||[]).filter(h=>{
    const s=summary(h);
    return h!==p.target&&(s.level==='Nominal'||s.level==='Ordinal')&&s.unique>=2;
  });
}
function selectedPreparationMethods(p){
  if(p.methodMode==='custom')return [...new Set((p.selectedMethods||[]).filter(Boolean))];
  try{return root.KUMethodSelection?.effectiveMethodIds?.(p,root.KUProfileInsights?.getManifest?.())||[]}
  catch(_){return[]}
}
function groupMethodNote(p,groupCounts=[]){
  const methods=new Set(selectedPreparationMethods(p));
  if(p.methodMode==='custom'){
    const labels=[];
    if(methods.has('welch-t-test'))labels.push('Welch independent-samples t-test');
    if(methods.has('one-way-anova'))labels.push('One-way ANOVA');
    if(methods.has('validated-group-comparison'))labels.push('Validated Group Comparison');
    const selected=labels.length?`Selected method${labels.length===1?'':'s'}: ${labels.join(', ')}.`:'Selected methods will be validated against the observed groups.';
    return `${selected}${groupCounts.length?` Complete observations by group: ${groupCounts.map(([name,n])=>`${name}=${n}`).join(', ')}.`:''}`;
  }
  return `Two observed groups will use Welch t-test; three or more will use one-way ANOVA in the validated backend.${groupCounts.length?` Complete observations by group: ${groupCounts.map(([name,n])=>`${name}=${n}`).join(', ')}.`:''}`;
}
function prepareBlockers(p,group){
  const blockers=[];
  if(p.route==='regression'&&p.target){
    if(types[p.target]!=='numeric'){
      const targetSummary=summary(p.target);
      const encoding=targetSummary.level==='Ordinal'?recognizedOrdinalEncoding(p.target):null;
      if(!encoding){
        blockers.push(`Target ${p.target} is stored as text and its ordinal order is not one of the validated standard sequences. KU Open DA will not guess the category order.`);
      }else if(targetSummary.n<5){
        blockers.push(`Regression requires at least 5 observed target values; ${targetSummary.n} are available.`);
      }
    }else{
      const numericObserved=observed(p.target).filter(v=>Number.isFinite(Number(v))).length;
      if(numericObserved<5)blockers.push(`Regression requires at least 5 numeric target observations; ${numericObserved} are available.`);
    }
  }
  if(['binary-classification','multiclass-classification'].includes(p.route)&&p.target){
    const counts=valueCounts(p.target);
    const requiredClasses=p.route==='binary-classification'?2:3;
    if((p.route==='binary-classification'&&counts.length!==2)||(p.route==='multiclass-classification'&&counts.length<requiredClasses)){
      blockers.push(`${routeLabel(p.route)} target class count is no longer compatible with the selected route.`);
    }
    const small=counts.filter(([,n])=>n<5);
    if(small.length){
      blockers.push(`5-fold stratified validation requires at least 5 observations in every class. Too small: ${small.map(([name,n])=>`${name} (${n})`).join(', ')}.`);
    }
  }
  if(p.route==='clustering'&&data.length<3){
    blockers.push(`Segmentation requires at least 3 observations for a two-cluster solution and silhouette evidence; ${data.length} are available.`);
  }
  if(p.route==='group-comparison'){
    if(!group){
      blockers.push('Select one grouping field before continuing.');
    }else{
      const counts=completeGroupCounts(p.target,group),methods=new Set(selectedPreparationMethods(p));
      if(counts.length<2)blockers.push('Compare Groups requires at least two observed groups after complete-case filtering.');
      const small=counts.filter(([,n])=>n<2);
      if(small.length)blockers.push(`Each compared group needs at least 2 complete observations. Too small: ${small.map(([name,n])=>`${name} (${n})`).join(', ')}.`);
      if(methods.has('welch-t-test')&&counts.length!==2){
        blockers.push(`Welch t-test requires exactly 2 complete groups; ${counts.length} are currently observed. Choose a compatible grouping field or method.`);
      }
      if(methods.has('one-way-anova')&&counts.length<3){
        blockers.push(`One-way ANOVA requires 3 or more complete groups; ${counts.length} are currently observed. Choose a compatible grouping field or method.`);
      }
    }
  }
  return blockers;
}
function prepEntries(p,fields){
  return fields.map(field=>({field,rule:prepRule(p,field)}));
}
function automaticPreparation(entries){
  const items=entries.filter(x=>x.rule[3]==='ok');
  if(!items.length)return '<p class="prep-clear">No automatic preparation actions are required for the current field selection.</p>';
  return `<div class="prep-action-list">${items.map(({field,rule})=>`<div class="prep-action-item"><b>${safe(field.name)}</b><span>${safe(rule[0])}</span><small>${safe(rule[1])}</small></div>`).join('')}</div>`;
}
function reviewPreparation(blockers){
  if(!blockers.length)return '<p class="prep-clear">No blocking issues detected. Preparation can be approved.</p>';
  return `<div class="prep-review-list">${blockers.map(message=>`<div class="prep-review-item"><b>Review required</b><span>${safe(message)}</span></div>`).join('')}</div>`;
}

function renderPrepare(){
  const p=plan(),view=host(),fields=selectedFields(p).map(summary),saved=p.preparation||{},groups=candidateGroups(p);
  const group=saved.groupField&&groups.includes(saved.groupField)?saved.groupField:(groups.length===1?groups[0]:'');
  const blockers=prepareBlockers(p,group),entries=prepEntries(p,fields);
  const groupCounts=p.route==='group-comparison'&&group?completeGroupCounts(p.target,group):[];

  view.innerHTML=`<div class="step-kicker">STEP 4 · PREPARE</div><h1>Review Data Preparation</h1><p class="lead">Review what the selected production route will do with the real fields before confirming execution.</p>${currentBar()}
  <section class="card prep-summary-card"><div class="head">Preparation Summary</div><div class="body"><div class="prep-route"><span>Selected route</span><b>${safe(routeLabel(p.route))}</b><small>${fields.length} selected field${fields.length===1?'':'s'}</small></div><div class="prep-status-grid"><section class="prep-status-panel automatic"><div class="prep-status-title"><span>Automatically handled</span><b>${entries.filter(x=>x.rule[3]==='ok').length}</b></div>${automaticPreparation(entries)}</section><section class="prep-status-panel review"><div class="prep-status-title"><span>Needs review</span><b>${blockers.length}</b></div>${reviewPreparation(blockers)}</section></div></div></section>
  ${p.route==='group-comparison'?`<section class="card route-prep-card"><div class="head">Group comparison setup</div><div class="body"><label class="field-control"><span>Grouping field</span><select id="prepareGroupField"><option value="">Choose grouping field…</option>${groups.map(h=>`<option value="${safe(h)}" ${h===group?'selected':''}>${safe(h)} · ${summary(h).unique} groups</option>`).join('')}</select></label><div class="note">${safe(groupMethodNote(p,groupCounts))}</div></div></section>`:''}
  <details class="card field-review-details"><summary>View Field-by-Field Preparation Details</summary><div class="body"><div class="prep-table"><table><thead><tr><th>Field</th><th>Recommended Action</th><th>Detected Issues</th><th>Planned Action</th><th>Reason</th></tr></thead><tbody>${entries.map(({field,rule})=>`<tr class="${rule[3]==='block'?'prep-block-row':''}"><td><b>${safe(field.name)}</b><small>${safe(field.storage)} · ${safe(field.level)}</small></td><td>${safe(rule[0])}</td><td>${safe(rule[1])}</td><td>${safe(rule[0])}</td><td>${safe(rule[2])}</td></tr>`).join('')}</tbody></table></div></div></details>
  ${blockers.length?`<div id="prepBlockers" class="workflow-blocker"><b>Preparation cannot be approved yet</b>${blockers.map(x=>`<p>${safe(x)}</p>`).join('')}</div>`:'<div id="prepBlockers"></div>'}
  <div class="workflow-footer"><button class="btn ghost" onclick="goToJourneyStep('analyze')">← Edit Question</button><button id="continueSetup" class="btn primary" ${blockers.length?'disabled':''}>Approve Preparation →</button></div>`;

  el('prepareGroupField')?.addEventListener('change',event=>{
    root.KUAppState.setPreparation({status:'pending-review',approved:false,groupField:event.target.value||null});
    renderPrepare();
  });
  el('continueSetup')?.addEventListener('click',()=>{
    const selectedGroup=el('prepareGroupField')?.value||saved.groupField||null;
    const currentBlockers=prepareBlockers(p,selectedGroup);
    if(currentBlockers.length)return;
    root.KUAppState.setPreparation({status:'approved',approved:true,groupField:selectedGroup});
    root.goToJourneyStep('setup');
  });
  emitBar();
}

async function loadCapabilities(){
  if(capabilitiesCache)return capabilitiesCache;
  const response=await fetch(`${KU_ANALYTICS_API_BASE}/capabilities`);
  if(!response.ok)throw new Error(`HTTP ${response.status}`);
  capabilitiesCache=await response.json();
  return capabilitiesCache;
}
function capabilityRows(cap){
  if(!cap)return'';
  const policy=cap.policy||{},prep=cap.preparation||{};
  const rows=[
    ['Intent',cap.intent],
    ['Validation',cap.validation],
    ...Object.entries(policy).map(([k,v])=>[k,typeof v==='object'?JSON.stringify(v):v]),
    ...Object.entries(prep).map(([k,v])=>[`Preparation: ${k}`,v])
  ];
  return rows.map(([k,v])=>`<div class="setup-kv"><span>${safe(k.replaceAll('_',' '))}</span><b>${safe(v)}</b></div>`).join('');
}
function renderSetupShell(message='Loading backend execution metadata…'){
  const view=host();
  view.innerHTML=`<div class="step-kicker">STEP 5 · SETUP</div><h1>How Will the Analysis Run?</h1><p class="lead">The recommended setup comes from the validated backend policy, not from a frontend model preset.</p>${currentBar()}<section class="card"><div class="head">Recommended Setup</div><div class="body" id="setupBody"><div class="empty">${safe(message)}</div></div></section><div class="workflow-footer"><button class="btn ghost" onclick="goToJourneyStep('prepare')">← Back to Prepare</button><button id="runAnalysisBtn" class="btn primary" disabled>Run recommended analysis →</button></div>`;
  emitBar();
}
async function renderSetup(){
  renderSetupShell();
  const p=plan();
  try{
    const caps=await loadCapabilities(),cap=caps.routes?.[p.route];
    if(!cap)throw new Error(`Backend capability metadata does not include route ${p.route}.`);
    const group=p.preparation?.groupField||null,metrics=(cap.metrics||[]).join(', '),serviceVersion=caps.service?.version||'—';
    const derived=derivedFields(p),runFields=executionFields(p),originalPredictors=(p.predictors||[]).length;
    const feOwner=p.preparation?.featureEngineering?.reviewed?'Browser · reviewed FE manifest':'Backend legacy compatibility';
    el('setupBody').innerHTML=`<div class="setup-grid"><div class="setup-hero"><span>Recommended route</span><b>${safe(routeLabel(p.route))}</b><small>${safe(cap.intent||'Validated backend')}</small></div><div class="setup-kv"><span>Target</span><b>${safe(p.target||'Not required')}</b></div><div class="setup-kv"><span>Original predictors / inputs</span><b>${originalPredictors}</b></div><div class="setup-kv"><span>Derived fields</span><b>${derived.length?safe(derived.join(', ')):'None selected'}</b></div><div class="setup-kv"><span>Deterministic feature construction</span><b>${safe(feOwner)}</b></div><div class="setup-kv"><span>Validation-safe preprocessing</span><b>Backend pipeline</b></div>${group?`<div class="setup-kv"><span>Grouping field</span><b>${safe(group)}</b></div>`:''}</div><div class="setup-policy">${capabilityRows(cap)}</div><details class="technical-run-spec"><summary>Technical Run Specification</summary><div class="body"><div class="setup-kv"><span>Backend API</span><b>${serviceVersion==='—'?'—':`v${safe(serviceVersion)}`}</b></div><div class="setup-kv"><span>Endpoint</span><b>POST /analyze</b></div><div class="setup-kv"><span>Mode</span><b>fast</b></div><div class="setup-kv"><span>Metrics returned</span><b>${safe(metrics||'Route-defined evidence')}</b></div><div class="setup-kv"><span>Fields uploaded</span><b>${safe(runFields.join(', '))}</b></div><div class="setup-kv"><span>Prepared matrix contract</span><b>${p.preparation?.featureEngineering?.reviewed?'Browser FE Manifest v1':'Legacy client compatibility'}</b></div></div></details>`;
    root.KUAppState.setSetup({mode:'recommended',confirmed:false,configuration:{intent:cap.intent,route:p.route,groupField:group,capability:cap,serviceVersion,executionFields:runFields,derivedFields:derived,featureOwner:feOwner}});
    const run=el('runAnalysisBtn');
    run.disabled=false;
    run.addEventListener('click',runAnalysisFromSetup);
  }catch(err){
    el('setupBody').innerHTML=`<div class="workflow-blocker"><b>Backend setup metadata unavailable</b><p>${safe(err.message)}</p><p>The analysis has not been run. Confirm that the updated FastAPI service is deployed before continuing.</p></div>`;
  }
}
async function runAnalysisFromSetup(){
  const btn=el('runAnalysisBtn'),p=plan();
  btn.disabled=true;
  btn.textContent='Running analysis…';
  root.KUAppState.setSetup({confirmed:true});
  try{
    await root.KUAnalyticsClient.runPlan(p);
    root.goToJourneyStep('results');
  }catch(err){
    btn.disabled=false;
    btn.textContent='Run recommended analysis →';
    el('setupBody')?.insertAdjacentHTML('beforeend',`<div class="workflow-blocker"><b>Analysis could not run</b><p>${safe(err.message)}</p></div>`);
  }
}

function evidenceMap(r){return r?.evidence||{}}
function answerText(r){
  const e=evidenceMap(r);
  if(r.route==='regression')return `The validated regression run achieved R² ${fmt(e.r2)} with RMSE ${fmt(e.rmse)} and MAE ${fmt(e.mae)}.`;
  if(r.route==='classification'&&r.analysis_type==='binary')return `The binary model achieved ROC-AUC ${fmt(e.roc_auc)} and PR-AUC ${fmt(e.pr_auc)}, with F1 ${fmt(e.f1)} at the validated threshold.`;
  if(r.route==='classification'&&r.analysis_type==='multiclass')return `The multiclass model achieved macro F1 ${fmt(e.macro_f1)} and balanced accuracy ${fmt(e.balanced_accuracy)}.`;
  if(r.route==='segmentation')return `The segmentation produced the validated cluster solution with silhouette ${fmt(e.silhouette)} and retained ${fmt(Number(e.pca_variance)*100,1)}% PCA variance.`;
  if(r.route==='association')return `${e.practical_supported??0} practically meaningful relationship${e.practical_supported===1?'':'s'} were supported after the backend association workflow.`;
  if(r.route==='compare_groups')return `The ${r.method?.test||'group comparison'} returned p = ${Number(e.p_value)<.001?'< .001':fmt(e.p_value,4)}${Number.isFinite(Number(e.hedges_g))?` with Hedges g ${fmt(e.hedges_g)}`:Number.isFinite(Number(e.eta_squared))?` with η² ${fmt(e.eta_squared)}`:''}.`;
  return `The validated analysis completed with status ${r.status||'COMPLETE'}.`;
}
function evidenceValue(v){
  if(typeof v!=='number')return safe(v);
  if(Number.isInteger(v))return String(v);
  return fmt(v,4);
}
function evidenceCards(r){
  return Object.entries(r.evidence||{})
    .filter(([,v])=>['number','string','boolean'].includes(typeof v))
    .slice(0,12)
    .map(([k,v])=>`<div class="result-metric"><span>${safe(k.replaceAll('_',' '))}</span><b>${evidenceValue(v)}</b></div>`)
    .join('');
}
function confusion(r){
  const e=r.evidence||{};
  if(!['tn','fp','fn','tp'].every(k=>Number.isFinite(Number(e[k]))))return'';
  return `<section class="card"><div class="head">Confusion matrix</div><div class="body"><div class="confusion"><div class="cm-corner"></div><div class="cm-head">Predicted −</div><div class="cm-head">Predicted +</div><div class="cm-head">Actual −</div><div class="cm-cell correct"><b>${e.tn}</b><span>TN</span></div><div class="cm-cell error"><b>${e.fp}</b><span>FP</span></div><div class="cm-head">Actual +</div><div class="cm-cell error"><b>${e.fn}</b><span>FN</span></div><div class="cm-cell correct"><b>${e.tp}</b><span>TP</span></div></div></div></section>`;
}
function sameFields(a=[],b=[]){return JSON.stringify([...a].sort())===JSON.stringify([...b].sort())}
function resultMatchesCurrentPlan(state,p){
  const snapshot=state.planSnapshot;
  if(!snapshot)return true;
  return snapshot.questionType===p.questionType
    &&snapshot.target===p.target
    &&snapshot.route===p.route
    &&sameFields(snapshot.predictors,p.predictors)
    &&(snapshot.preparation?.groupField||null)===(p.preparation?.groupField||null);
}
function renderResults(){
  const state=resultState(),p=plan(),payload=state.payload||{},r=payload.result||{},view=host();
  if(!state.validated||!r.status){
    view.innerHTML='<div class="workflow-blocker"><b>No validated result is available.</b></div>';
    return;
  }
  const current=resultMatchesCurrentPlan(state,p);
  view.innerHTML=`<div class="step-kicker">STEP 6 · RESULTS</div><h1>Understand the Results</h1><p class="lead">Start with the answer, then inspect evidence and technical details as needed.</p>${currentBar()}${current?'':`<div class="result-stale"><b>Previous validated result</b><span>This result was generated from an earlier predictor or preparation selection. It is preserved for comparison; review Setup and run again to refresh it for the Current Analysis.</span></div>`}<section class="result-answer"><span>Answer</span><h2>${answerText(r)}</h2><p>${safe(r.warnings?.length?`Review ${r.warnings.length} warning${r.warnings.length===1?'':'s'} below before acting on the result.`:'This summary is generated only from the returned validated result payload.')}</p></section><section class="card"><div class="head">Key evidence</div><div class="body"><div class="result-metrics">${evidenceCards(r)}</div></div></section>${confusion(r)}<section class="card"><div class="head">Interpretation report</div><div class="body" id="workflowReport"></div></section><details class="card result-technical"><summary>Technical result / payload</summary><div class="body"><pre>${safe(JSON.stringify(payload,null,2))}</pre></div></details><div class="workflow-footer"><button class="btn ghost" onclick="goToJourneyStep('analyze')">← Review Analysis Plan</button><button class="btn primary" onclick="goToJourneyStep('setup')">Run Again / Review Setup</button></div>`;
  root.KUAnalyticsClient?.renderExecutiveReport(payload.report,el('workflowReport'));
  emitBar();
}
function show(step){
  if(step==='prepare')renderPrepare();
  else if(step==='setup')renderSetup();
  else if(step==='results')renderResults();
}
root.KUWorkflowSteps=Object.freeze({show,renderPrepare,renderSetup,renderResults,loadCapabilities});
})(window);