// KU Open DA — Step 3 profile-aware analytical method selection.
(function(root,factory){
  const api=factory(root);
  if(typeof module==='object'&&module.exports)module.exports=api;
  if(root)root.KUMethodSelection=api;
  if(root?.document){
    if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>api.install());
    else api.install();
  }
})(typeof window!=='undefined'?window:globalThis,function(root){
'use strict';
const METHOD_MODE_RECOMMENDED='recommended';
const METHOD_MODE_CUSTOM='custom';
const CATALOG=Object.freeze([
  {id:'xgboost-regression',label:'XGBoost Regression',engine:'backend',questions:['predict-outcome','explain-drivers'],targetKinds:['continuous','ordinal'],routes:['regression'],summary:'Validated nonlinear predictive regression with cross-validation and model diagnostics.'},
  {id:'linear-regression',label:'Linear Regression (OLS)',engine:'browser',questions:['predict-outcome','explain-drivers'],targetKinds:['continuous'],routes:['regression'],requiresNumericPredictor:true,summary:'Classical local regression with coefficients, confidence intervals and residual diagnostics.'},
  {id:'pearson-correlation',label:'Pearson Correlation',engine:'browser',questions:['explain-drivers'],targetKinds:['continuous'],routes:['regression'],requiresNumericPredictor:true,supporting:true,summary:'Pairwise linear association between the outcome and numeric explanatory fields.'},
  {id:'spearman-correlation',label:'Spearman Correlation',engine:'browser',questions:['explain-drivers'],targetKinds:['continuous','ordinal'],routes:['regression'],requiresNumericPredictor:true,supporting:true,summary:'Pairwise rank-based monotonic association, more robust to skew and extreme values than Pearson.'},
  {id:'xgboost-binary',label:'XGBoost Binary Classification',engine:'backend',questions:['predict-outcome','explain-drivers'],targetKinds:['binary'],routes:['binary-classification'],summary:'Validated binary classification with class balancing, calibration and cross-validated metrics.'},
  {id:'xgboost-multiclass',label:'XGBoost Multiclass Classification',engine:'backend',questions:['predict-outcome','explain-drivers'],targetKinds:['nominal'],routes:['multiclass-classification'],summary:'Validated multiclass classification with stratified out-of-fold evaluation.'},
  {id:'validated-group-comparison',label:'Validated Group Comparison',engine:'backend',questions:['compare-groups'],targetKinds:['continuous'],routes:['group-comparison'],summary:'Validated comparison route; Step 4 uses the reviewed grouping field to select Welch t-test or one-way ANOVA.'},
  {id:'welch-t-test',label:'Welch Independent-Samples t-test',engine:'browser',questions:['compare-groups'],targetKinds:['continuous'],routes:['group-comparison'],requiresCategoricalPredictor:true,conditional:'Requires a grouping field with exactly 2 observed groups.',summary:'Local two-group mean comparison that does not assume equal variances.'},
  {id:'one-way-anova',label:'One-way ANOVA',engine:'browser',questions:['compare-groups'],targetKinds:['continuous'],routes:['group-comparison'],requiresCategoricalPredictor:true,conditional:'Requires a grouping field with 3 or more observed groups.',summary:'Local mean comparison across three or more groups.'},
  {id:'kmeans-clustering',label:'K-means Segmentation',engine:'backend',questions:['discover-segments'],targetKinds:['none'],routes:['clustering'],requiresNumericPredictors:2,summary:'Validated segmentation route using numeric fields with scaling and dimensionality reduction policy.'},
  {id:'mixed-association-screen',label:'Mixed-Type Association Screening',engine:'backend',questions:['discover-association-rules'],targetKinds:['none'],routes:['association'],summary:'Validated all-pairs association screening across mixed field types with multiplicity control.'}
]);
const RECOMMENDED_BY_ROUTE=Object.freeze({
  regression:'xgboost-regression',
  'binary-classification':'xgboost-binary',
  'multiclass-classification':'xgboost-multiclass',
  'group-comparison':'validated-group-comparison',
  clustering:'kmeans-clustering',
  association:'mixed-association-screen'
});
const safe=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot',"'":'&#39;'}[m]));
const unique=a=>[...new Set((Array.isArray(a)?a:[]).filter(Boolean))];
const same=(a,b)=>JSON.stringify(unique(a).sort())===JSON.stringify(unique(b).sort());
function manifestFromRoot(){
  const existing=root.KUProfileInsights?.getManifest?.();
  if(existing)return existing;
  try{return root.KUProfileManifest?.fromGlobals?.({})||null}catch(_){return null}
}
function fieldMap(manifest){return new Map((manifest?.fields||[]).map(f=>[f.name,f]))}
function targetKind(plan,manifest){
  if(!plan?.target)return'none';
  const f=fieldMap(manifest).get(plan.target);if(!f)return'unknown';
  const uniqueCount=Number(f.profile?.unique)||0;
  if(uniqueCount===2)return'binary';
  if(f.measurement_level==='Ordinal')return'ordinal';
  if(f.measurement_level==='Nominal')return'nominal';
  if(f.storage_type==='numeric'&&f.measurement_level==='Scale')return'continuous';
  return'nominal';
}
function predictorSummary(plan,manifest){
  const map=fieldMap(manifest),names=unique(plan?.predictors||[]),fields=names.map(n=>map.get(n)).filter(Boolean);
  const numeric=fields.filter(f=>f.storage_type==='numeric'&&f.measurement_level==='Scale');
  const categorical=fields.filter(f=>f.measurement_level==='Nominal'||f.measurement_level==='Ordinal');
  return{fields,numeric,categorical};
}
function targetSignals(plan,manifest){
  const f=fieldMap(manifest).get(plan?.target),shape=String(f?.distribution?.shape||''),iqr=Number(f?.outliers?.method_iqr?.pct)||0,mad=Number(f?.outliers?.method_mad?.pct)||0;
  return{field:f,shape,strongSkew:shape.includes('strong_'),skewed:shape.includes('skew'),outlierPct:Math.max(iqr,mad)};
}
function suitableMethods({plan={},manifest=null}={}){
  if(!plan.questionType||!plan.route)return[];
  const kind=targetKind(plan,manifest),pred=predictorSummary(plan,manifest),signals=targetSignals(plan,manifest),recommended=RECOMMENDED_BY_ROUTE[plan.route]||null;
  return CATALOG.filter(m=>{
    if(!m.questions.includes(plan.questionType)||!m.routes.includes(plan.route))return false;
    if(!m.targetKinds.includes(kind))return false;
    if(m.requiresNumericPredictor&&pred.numeric.length<1)return false;
    if(m.requiresNumericPredictors&&pred.numeric.length<m.requiresNumericPredictors)return false;
    if(m.requiresCategoricalPredictor&&pred.categorical.length<1)return false;
    return true;
  }).map(m=>{
    const notes=[];
    if(m.engine==='browser')notes.push('Runs locally in the browser.');
    else notes.push('Uses KU Analytical Intelligence / validated backend execution.');
    if(m.id==='linear-regression'&&(signals.strongSkew||signals.outlierPct>=5))notes.push('Target profile suggests reviewing transformations or influential observations in Prepare.');
    if(m.id==='pearson-correlation'&&(signals.skewed||signals.outlierPct>0))notes.push('Skew or outlier signals are present; Spearman may provide a useful robustness comparison.');
    if(m.id==='spearman-correlation'&&(signals.skewed||signals.outlierPct>0))notes.push('Rank-based association is suitable as a robustness check for the observed profile.');
    if(m.conditional)notes.push(m.conditional);
    return{...m,recommended:m.id===recommended,profile_notes:notes,numeric_predictors:pred.numeric.length,categorical_predictors:pred.categorical.length};
  });
}
function recommendedMethod(plan={},manifest=null){return suitableMethods({plan,manifest}).find(m=>m.recommended)||null}
function effectiveMethodIds(plan={},manifest=null){
  const methods=suitableMethods({plan,manifest}),allowed=new Set(methods.map(m=>m.id));
  if(plan.methodMode===METHOD_MODE_CUSTOM)return unique(plan.selectedMethods).filter(id=>allowed.has(id));
  const rec=methods.find(m=>m.recommended);return rec?[rec.id]:[];
}
function ensureStyles(){
  if(!root.document||root.document.querySelector('link[data-ku-method-selection]'))return;
  const link=root.document.createElement('link');link.rel='stylesheet';link.href='src/method-selection.css';link.dataset.kuMethodSelection='true';root.document.head.appendChild(link);
}
function engineBadge(method){return method.engine==='browser'?'<span class="method-engine browser">Local · Browser</span>':'<span class="method-engine backend">KU Validated Engine</span>'}
function methodCard(method,selected,custom){
  const note=method.profile_notes?.join(' ');
  return `<label class="method-option${selected?' selected':''}${method.recommended?' recommended':''}"><input type="checkbox" data-analysis-method="${safe(method.id)}" ${selected?'checked':''} ${custom?'':'disabled'}><span class="method-option-copy"><span class="method-option-head"><b>${safe(method.label)}</b>${method.recommended?'<em>Recommended</em>':''}</span><span>${safe(method.summary)}</span>${note?`<small>${safe(note)}</small>`:''}</span>${engineBadge(method)}</label>`;
}
function renderInto(section,plan,manifest){
  let host=section.querySelector('#kuMethodChoice');if(!host){host=root.document.createElement('div');host.id='kuMethodChoice';host.className='method-choice';section.appendChild(host)}
  const methods=suitableMethods({plan,manifest}),recommended=methods.find(m=>m.recommended),mode=plan.methodMode===METHOD_MODE_CUSTOM?METHOD_MODE_CUSTOM:METHOD_MODE_RECOMMENDED,selected=new Set(unique(plan.selectedMethods).filter(id=>methods.some(m=>m.id===id)));
  host.innerHTML=`<div class="recommended-method"><span class="method-kicker">Recommended method</span>${recommended?`<div class="recommended-method-row"><div><b>${safe(recommended.label)}</b><span>${safe(recommended.summary)}</span></div>${engineBadge(recommended)}</div>`:'<div class="method-empty">No executable method can be recommended from the current plan yet.</div>'}</div><div class="method-or"><span>OR</span></div><div class="method-custom-head"><div><b>Choose your method(s)</b><span>Only methods compatible with the question, target and current data profile are shown.</span></div><div class="method-mode"><label><input type="radio" name="analysisMethodMode" value="recommended" ${mode===METHOD_MODE_RECOMMENDED?'checked':''}> Use recommended</label><label><input type="radio" name="analysisMethodMode" value="custom" ${mode===METHOD_MODE_CUSTOM?'checked':''}> Choose methods</label></div></div><div class="method-options${mode===METHOD_MODE_CUSTOM?'':' readonly'}">${methods.map(m=>methodCard(m,selected.has(m.id),mode===METHOD_MODE_CUSTOM)).join('')||'<div class="method-empty">Complete the analytical question to see suitable methods.</div>'}</div>${mode===METHOD_MODE_CUSTOM&&selected.size===0?'<div class="method-selection-warning">Choose at least one method before continuing to Prepare.</div>':''}<div class="method-selection-note">Method selection is stored in the Analysis Plan. Step 4 will validate method-specific preparation requirements before execution.</div>`;
  host.querySelectorAll('input[name="analysisMethodMode"]').forEach(r=>r.addEventListener('change',()=>{
    if(!r.checked)return;
    root.KUAppState?.updateAnalysisPlan({methodMode:r.value,selectedMethods:r.value===METHOD_MODE_CUSTOM?unique(plan.selectedMethods):[]});
  }));
  host.querySelectorAll('[data-analysis-method]').forEach(c=>c.addEventListener('change',()=>{
    const now=root.KUAppState?.getState?.().analysisPlan||plan,set=new Set(unique(now.selectedMethods));c.checked?set.add(c.dataset.analysisMethod):set.delete(c.dataset.analysisMethod);root.KUAppState?.updateAnalysisPlan({methodMode:METHOD_MODE_CUSTOM,selectedMethods:[...set]});
  }));
  const continueButton=root.document.getElementById('continuePrepare');
  if(continueButton&&mode===METHOD_MODE_CUSTOM&&selected.size===0)continueButton.disabled=true;
}
function sync(){
  ensureStyles();
  const section=root.document?.querySelector('#aiAnalyticsView .recommendation-section');if(!section)return;
  const plan=root.KUAppState?.getState?.().analysisPlan||{},manifest=manifestFromRoot(),methods=suitableMethods({plan,manifest}),allowed=methods.map(m=>m.id),selected=unique(plan.selectedMethods).filter(id=>allowed.includes(id));
  if(plan.methodMode===METHOD_MODE_CUSTOM&&!same(selected,plan.selectedMethods)){
    root.KUAppState?.updateAnalysisPlan({selectedMethods:selected});return;
  }
  renderInto(section,plan,manifest);
}
let observer=null,installed=false;
function install(){
  if(installed||!root.document)return;installed=true;ensureStyles();
  const host=root.document.getElementById('aiAnalyticsView');
  if(host&&typeof MutationObserver!=='undefined'){observer=new MutationObserver(()=>queueMicrotask(sync));observer.observe(host,{childList:true,subtree:false})}
  root.document.addEventListener('ku:statechange',()=>queueMicrotask(sync));
  sync();
}
return Object.freeze({CATALOG,RECOMMENDED_BY_ROUTE,METHOD_MODE_RECOMMENDED,METHOD_MODE_CUSTOM,targetKind,suitableMethods,recommendedMethod,effectiveMethodIds,install,sync});
});
