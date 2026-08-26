// KU Open DA — Step 2 browser profile insight views powered by Profile Manifest v1.
(function(root,factory){
  const api=factory(root);
  if(typeof module==='object'&&module.exports)module.exports=api;
  if(root)root.KUProfileInsights=api;
  if(root?.document){
    if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>api.install());
    else api.install();
  }
})(typeof window!=='undefined'?window:globalThis,function(root){
'use strict';
let installed=false,lastManifest=null,selectedDistribution='',selectedCategorical='',selectedTemporal='';
const el=id=>root.document?.getElementById(id);
const safe=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const fmt=(v,d=2)=>Number.isFinite(Number(v))?Number(v).toLocaleString(undefined,{maximumFractionDigits:d}):'—';
const pct=v=>Number.isFinite(Number(v))?`${Number(v).toFixed(1)}%`:'—';
const shapeText=shape=>({strong_right_skew:'Strong right skew',right_skew:'Right skew',mild_right_skew:'Mild right skew',strong_left_skew:'Strong left skew',left_skew:'Left skew',mild_left_skew:'Mild left skew',roughly_symmetric:'Roughly symmetric',constant:'Constant'})[shape]||String(shape||'Unknown').replaceAll('_',' ');
function buildViewModel(manifest={}){
  const fields=Array.isArray(manifest.fields)?manifest.fields:[];
  const numeric=fields.filter(f=>f.distribution&&f.profile);
  const categorical=fields.filter(f=>f.frequency&&!f.temporal);
  const temporal=fields.filter(f=>f.temporal?.detected);
  const skewed=numeric.filter(f=>String(f.distribution?.shape||'').includes('skew'));
  const symmetric=numeric.filter(f=>f.distribution?.shape==='roughly_symmetric');
  const constant=numeric.filter(f=>f.distribution?.shape==='constant');
  const outlierSignals=numeric.filter(f=>Math.max(Number(f.outliers?.method_iqr?.pct)||0,Number(f.outliers?.method_mad?.pct)||0)>0);
  const highOutlier=numeric.filter(f=>Math.max(Number(f.outliers?.method_iqr?.pct)||0,Number(f.outliers?.method_mad?.pct)||0)>=5);
  const rareCategoryFields=categorical.filter(f=>(f.frequency?.rare_level_count||0)>0);
  return{manifest,numeric,categorical,temporal,shapeCounts:{numeric:numeric.length,skewed:skewed.length,symmetric:symmetric.length,constant:constant.length},outlierSignals,highOutlier,rareCategoryFields};
}
function analysisIntent(){
  const p=root.KUAppState?.getState?.().analysisPlan||{};
  return{question_type:p.questionType||null,target:p.target||null,analytical_family:p.analyticalFamily||null};
}
function createManifest(){
  if(!root.KUProfileManifest?.fromGlobals)return null;
  try{return root.KUProfileManifest.fromGlobals(analysisIntent())}catch(_){return null}
}
function ensureStyles(){
  if(root.document?.querySelector('link[data-ku-profile-insights]'))return;
  const link=root.document.createElement('link');link.rel='stylesheet';link.href='src/profile-insights.css';link.dataset.kuProfileInsights='true';root.document.head.appendChild(link);
}
function makeTab(key,label){
  const b=root.document.createElement('button');b.type='button';b.className='profile-tab';b.dataset.profileTab=key;b.textContent=label;b.addEventListener('click',()=>root.setProfileTab?.(key));return b;
}
function makePane(key){
  const p=root.document.createElement('div');p.className='profile-pane profile-insight-pane';p.dataset.profilePane=key;return p;
}
function ensureStaticStructure(){
  const tabs=root.document?.querySelector('.profile-tabs'),relTab=tabs?.querySelector('[data-profile-tab="relationships"]'),relPane=root.document?.querySelector('[data-profile-pane="relationships"]');
  if(!tabs||!relTab||!relPane)return false;
  for(const [key,label] of [['distribution','Distribution'],['outliers','Outliers'],['categorical','Categorical']]){
    if(!tabs.querySelector(`[data-profile-tab="${key}"]`))tabs.insertBefore(makeTab(key,label),relTab);
    if(!root.document.querySelector(`[data-profile-pane="${key}"]`))relPane.parentNode.insertBefore(makePane(key),relPane);
  }
  return true;
}
function ensureTemporalStructure(show){
  const tabs=root.document?.querySelector('.profile-tabs'),relTab=tabs?.querySelector('[data-profile-tab="relationships"]'),relPane=root.document?.querySelector('[data-profile-pane="relationships"]');
  if(!tabs||!relTab||!relPane)return;
  let tab=tabs.querySelector('[data-profile-tab="temporal"]'),pane=root.document.querySelector('[data-profile-pane="temporal"]');
  if(show){
    if(!tab){tab=makeTab('temporal','Temporal');relTab.after(tab)}
    if(!pane){pane=makePane('temporal');relPane.after(pane)}
  }else{
    if(tab?.classList.contains('active'))root.setProfileTab?.('overview');
    tab?.remove();pane?.remove();
  }
}
function metric(label,value,detail=''){return `<div class="profile-insight-metric"><span>${safe(label)}</span><b>${safe(value)}</b>${detail?`<small>${safe(detail)}</small>`:''}</div>`}
function empty(message){return `<div class="empty">${safe(message)}</div>`}
function histogramHtml(field){
  const h=field?.distribution?.histogram||{},bins=Array.isArray(h.bins)?h.bins:[],edges=Array.isArray(h.edges)?h.edges:[];
  if(!bins.length)return empty('Histogram summary is unavailable for this field.');
  const max=Math.max(1,...bins);
  return `<div class="manifest-histogram" aria-label="Histogram for ${safe(field.name)}">${bins.map((n,i)=>`<div class="manifest-histogram-bin" title="${safe(`${fmt(edges[i])} – ${fmt(edges[i+1])}: ${n}`)}"><span style="height:${Math.max(3,100*n/max)}%"></span></div>`).join('')}</div><div class="manifest-histogram-axis"><span>${safe(fmt(edges[0]))}</span><span>${safe(fmt(edges[edges.length-1]))}</span></div>`;
}
function renderDistribution(vm){
  const host=root.document?.querySelector('[data-profile-pane="distribution"]');if(!host)return;
  if(!vm.numeric.length){host.innerHTML=empty('No numeric fields are available for distribution profiling.');return}
  if(!vm.numeric.some(f=>f.name===selectedDistribution))selectedDistribution=vm.numeric[0].name;
  const field=vm.numeric.find(f=>f.name===selectedDistribution)||vm.numeric[0],p=field.profile||{};
  host.innerHTML=`<section class="card"><div class="head">Distribution Shape</div><div class="body"><div class="profile-insight-kpis">${metric('Numeric fields',vm.shapeCounts.numeric)}${metric('Skewed fields',vm.shapeCounts.skewed)}${metric('Roughly symmetric',vm.shapeCounts.symmetric)}${metric('Constant',vm.shapeCounts.constant)}</div><div class="profile-insight-note">Calculated locally in your browser from the same Profile Manifest that can later be sent to KU Analytical Intelligence.</div></div></section><section class="card"><div class="head">Inspect a numeric field</div><div class="body"><label class="profile-insight-select"><span>Field</span><select id="profileDistributionField">${vm.numeric.map(f=>`<option value="${safe(f.name)}" ${f.name===field.name?'selected':''}>${safe(f.name)} · ${safe(shapeText(f.distribution?.shape))}</option>`).join('')}</select></label><div class="distribution-detail-grid"><div><div class="profile-insight-kpis compact">${metric('Shape',shapeText(field.distribution?.shape))}${metric('Skewness',fmt(p.skewness,3))}${metric('Kurtosis',fmt(p.excess_kurtosis,3))}${metric('Median',fmt(p.median))}</div><div class="profile-insight-summary">Range ${safe(fmt(p.min))} to ${safe(fmt(p.max))} · Q1 ${safe(fmt(p.q1))} · Q3 ${safe(fmt(p.q3))} · SD ${safe(fmt(p.sd))}</div></div><div>${histogramHtml(field)}</div></div></div></section>`;
  el('profileDistributionField')?.addEventListener('change',e=>{selectedDistribution=e.target.value;renderDistribution(vm)});
}
function outlierLabel(f){const a=Number(f.outliers?.method_iqr?.pct)||0,b=Number(f.outliers?.method_mad?.pct)||0,m=Math.max(a,b);return m>=5?'Strong signal':m>0?'Review':'None'}
function renderOutliers(vm){
  const host=root.document?.querySelector('[data-profile-pane="outliers"]');if(!host)return;
  if(!vm.numeric.length){host.innerHTML=empty('No numeric fields are available for outlier screening.');return}
  const rows=[...vm.numeric].sort((a,b)=>Math.max(Number(b.outliers?.method_iqr?.pct)||0,Number(b.outliers?.method_mad?.pct)||0)-Math.max(Number(a.outliers?.method_iqr?.pct)||0,Number(a.outliers?.method_mad?.pct)||0));
  host.innerHTML=`<section class="card"><div class="head">Outlier Detection</div><div class="body"><div class="profile-insight-kpis">${metric('Numeric fields',vm.numeric.length)}${metric('Fields with signals',vm.outlierSignals.length)}${metric('≥5% outlier signal',vm.highOutlier.length)}${metric('Methods','IQR + MAD')}</div><div class="profile-insight-note">Outliers are unusual observations, not automatically errors. KU Open DA reports robust signals here; the analytical question determines whether treatment is appropriate.</div></div></section><section class="card"><div class="head">Field-level outlier signals</div><div class="body"><div class="profile-insight-table"><table><thead><tr><th>Field</th><th>IQR count</th><th>IQR %</th><th>MAD count</th><th>MAD %</th><th>Signal</th></tr></thead><tbody>${rows.map(f=>`<tr><td><b>${safe(f.name)}</b></td><td>${safe(f.outliers?.method_iqr?.count??'—')}</td><td>${safe(pct(f.outliers?.method_iqr?.pct))}</td><td>${safe(f.outliers?.method_mad?.count??'—')}</td><td>${safe(pct(f.outliers?.method_mad?.pct))}</td><td><span class="profile-signal-badge ${outlierLabel(f)==='Strong signal'?'strong':outlierLabel(f)==='Review'?'review':''}">${safe(outlierLabel(f))}</span></td></tr>`).join('')}</tbody></table></div></div></section>`;
}
function renderCategorical(vm){
  const host=root.document?.querySelector('[data-profile-pane="categorical"]');if(!host)return;
  if(!vm.categorical.length){host.innerHTML=empty('No categorical fields are available for categorical profiling.');return}
  if(!vm.categorical.some(f=>f.name===selectedCategorical))selectedCategorical=vm.categorical[0].name;
  const field=vm.categorical.find(f=>f.name===selectedCategorical)||vm.categorical[0],fr=field.frequency||{},top=Array.isArray(fr.top)?fr.top:[];
  host.innerHTML=`<section class="card"><div class="head">Categorical Variables Analysis</div><div class="body"><div class="profile-insight-kpis">${metric('Categorical fields',vm.categorical.length)}${metric('With rare levels',vm.rareCategoryFields.length)}${metric('Top values retained','Up to 20')}${metric('Raw rows sent','No')}</div><div class="profile-insight-note">Frequency summaries are calculated locally. Identifier- or sensitive-like category values are redacted from the Profile Manifest before it can be sent to the backend.</div></div></section><section class="card"><div class="head">Inspect a categorical field</div><div class="body"><label class="profile-insight-select"><span>Field</span><select id="profileCategoricalField">${vm.categorical.map(f=>`<option value="${safe(f.name)}" ${f.name===field.name?'selected':''}>${safe(f.name)}</option>`).join('')}</select></label><div class="profile-insight-kpis compact">${metric('Unique',field.profile?.unique??'—')}${metric('Dominant level',pct(fr.dominant_pct))}${metric('Rare levels',fr.rare_level_count??'—')}${metric('Entropy',fmt(fr.entropy_normalized,3))}</div>${fr.redacted?`<div class="profile-insight-redacted"><b>Category values hidden in manifest</b><span>This field looks identifier- or sensitive-like. Counts and structural signals are retained without sending the actual category values.</span></div>`:`<div class="profile-insight-table"><table><thead><tr><th>Value</th><th>Count</th><th>%</th></tr></thead><tbody>${top.map(x=>`<tr><td>${safe(x.value)}</td><td>${safe(x.count)}</td><td>${safe(pct(x.pct))}</td></tr>`).join('')}${fr.other_count?`<tr><td><i>Other categories</i></td><td>${safe(fr.other_count)}</td><td>—</td></tr>`:''}</tbody></table></div>`}</div></section>`;
  el('profileCategoricalField')?.addEventListener('change',e=>{selectedCategorical=e.target.value;renderCategorical(vm)});
}
function regularity(t){const cv=Number(t?.interval_cv);if(!Number.isFinite(cv))return'Insufficient intervals';if(cv<=.1)return'Highly regular';if(cv<=.35)return'Moderately regular';return'Irregular'}
function shortDate(v){if(!v)return'—';const d=new Date(v);return Number.isNaN(d.getTime())?String(v):d.toISOString().slice(0,10)}
function renderTemporal(vm){
  const host=root.document?.querySelector('[data-profile-pane="temporal"]');if(!host)return;
  if(!vm.temporal.length){host.innerHTML=empty('No temporal field was detected.');return}
  if(!vm.temporal.some(f=>f.name===selectedTemporal))selectedTemporal=vm.temporal[0].name;
  const field=vm.temporal.find(f=>f.name===selectedTemporal)||vm.temporal[0],t=field.temporal||{};
  host.innerHTML=`<section class="card"><div class="head">Temporal / Time-Series Patterns</div><div class="body"><div class="profile-insight-kpis">${metric('Temporal fields',vm.temporal.length)}${metric('Detected granularity',t.granularity||'—')}${metric('Unique timestamps',t.unique_timestamps??'—')}${metric('Interval regularity',regularity(t))}</div><div class="profile-insight-note">This browser profile establishes the usable time axis and interval structure. Trend, seasonality, lag and rolling-feature recommendations can use this temporal context in later analytical steps.</div></div></section><section class="card"><div class="head">Inspect a temporal field</div><div class="body"><label class="profile-insight-select"><span>Field</span><select id="profileTemporalField">${vm.temporal.map(f=>`<option value="${safe(f.name)}" ${f.name===field.name?'selected':''}>${safe(f.name)}</option>`).join('')}</select></label><div class="profile-insight-kpis compact">${metric('First timestamp',shortDate(t.min))}${metric('Last timestamp',shortDate(t.max))}${metric('Median interval',Number.isFinite(Number(t.median_interval_days))?`${fmt(t.median_interval_days)} days`:'—')}${metric('Parse rate',pct(100*Number(t.parse_rate)))}</div><div class="temporal-context"><b>${safe(field.name)}</b><span>${safe(regularity(t))} ${safe(t.granularity||'')} time axis covering ${safe(shortDate(t.min))} to ${safe(shortDate(t.max))}.</span></div></div></section>`;
  el('profileTemporalField')?.addEventListener('change',e=>{selectedTemporal=e.target.value;renderTemporal(vm)});
}
function render(){
  ensureStyles();if(!ensureStaticStructure())return null;
  const manifest=createManifest();lastManifest=manifest;
  if(!manifest){
    for(const key of ['distribution','outliers','categorical']){const p=root.document.querySelector(`[data-profile-pane="${key}"]`);if(p)p.innerHTML=empty('Load a dataset to calculate this profile.')}
    ensureTemporalStructure(false);root.KUAccessibility?.syncProfileTabs?.();return null;
  }
  const vm=buildViewModel(manifest);ensureTemporalStructure(vm.temporal.length>0);renderDistribution(vm);renderOutliers(vm);renderCategorical(vm);renderTemporal(vm);root.KUAccessibility?.syncProfileTabs?.();
  try{root.document.dispatchEvent(new CustomEvent('ku:profile-manifest',{detail:manifest}))}catch(_){}
  return manifest;
}
function install(){
  ensureStyles();ensureStaticStructure();if(installed){render();return}
  installed=true;
  const status=el('status');if(status&&typeof MutationObserver!=='undefined')new MutationObserver(()=>render()).observe(status,{childList:true,subtree:true,characterData:true});
  el('variableTable')?.addEventListener('change',()=>setTimeout(render,0));
  root.document?.addEventListener('ku:statechange',()=>setTimeout(render,0));
  render();
}
return Object.freeze({install,render,buildViewModel,getManifest:()=>lastManifest});
});
