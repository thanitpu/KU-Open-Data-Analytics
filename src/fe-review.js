// KU Open DA — Step 4 Feature Engineering Intelligence review + browser execution plan.
(function(root,factory){
  const api=factory(root);
  if(typeof module==='object'&&module.exports)module.exports=api;
  if(root)root.KUFeatureEngineeringReview=api;
  if(root?.document){
    if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>api.install());
    else api.install();
  }
})(typeof window!=='undefined'?window:globalThis,function(root){
'use strict';
const STATUS_LOADING='loading';
const STATUS_READY='ready';
const STATUS_ERROR='error';
const STATUS_SKIPPED='skipped';
const REQUEST_TIMEOUT_MS=45000;
let installed=false,requestSerial=0,activeRequest=null;
const safe=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const unique=a=>[...new Set((Array.isArray(a)?a:[]).filter(Boolean))];
const plan=()=>root.KUAppState?.getState?.().analysisPlan||{};
function currentReview(p=plan()){return p.preparation?.featureEngineering||null}
function analysisIntent(p=plan()){return{question_type:p.questionType||null,target:p.target||null,analytical_family:p.analyticalFamily||null,route:p.route||null,method_mode:p.methodMode||'recommended',selected_methods:unique(p.selectedMethods||[]),question:p.question||null}}
function buildRequest(p=plan()){
  if(!root.KUProfileManifest?.fromGlobals)throw new Error('Profile Manifest is unavailable.');
  const intent=analysisIntent(p),manifest=root.KUProfileManifest.fromGlobals(intent),selected=new Set(p.predictors||[]);
  manifest.fields=(manifest.fields||[]).map(field=>({...field,selected_for_analysis:field.name===p.target||selected.has(field.name),analysis_role:field.name===p.target?'target':selected.has(field.name)?'selected_predictor':'context'}));
  manifest.reference_date=new Date().toISOString().slice(0,10);return manifest;
}
function fingerprintRequest(request={}){
  const compact={schema_version:request.schema_version,analysis_intent:request.analysis_intent,dataset_profile:request.dataset_profile,fields:(request.fields||[]).map(f=>({name:f.name,role:f.analysis_role,selected:f.selected_for_analysis,storage:f.storage_type,level:f.measurement_level,profile:f.profile,distribution:f.distribution,outliers:f.outliers,frequency:f.frequency,temporal:f.temporal,privacy:f.privacy}))};
  const text=JSON.stringify(compact);let hash=2166136261;for(let i=0;i<text.length;i++){hash^=text.charCodeAt(i);hash=Math.imul(hash,16777619)}return`fev1-${(hash>>>0).toString(16)}`;
}
function ensureStyles(){if(!root.document||root.document.querySelector('link[data-ku-fe-review]'))return;const link=root.document.createElement('link');link.rel='stylesheet';link.href='src/fe-review.css';link.dataset.kuFeReview='true';root.document.head.appendChild(link)}
function confidenceLabel(value){const n=Number(value);return n>=.85?'High':n>=.7?'Moderate':'Exploratory'}
function basisLabel(values=[]){return values.map(x=>String(x).replaceAll('_',' ')).join(' · ')}
function operationLabel(value){return String(value||'').replaceAll('_',' ')}
function updateReview(patch){const p=plan(),before=currentReview(p)||{};root.KUAppState?.setPreparation?.({featureEngineering:{...before,...patch}})}
function executionPlanFor(review=currentReview(),p=plan()){if(!root.KUFeatureEngineeringExecutor?.compilePlan)throw new Error('Browser Feature Engineering Executor is unavailable.');const fe={...(review||{}),reviewed:true},preparedPlan={...p,preparation:{...(p.preparation||{}),featureEngineering:fe}},base=[...new Set([p.target,...(p.predictors||[])].filter(Boolean))];return root.KUFeatureEngineeringExecutor.compilePlan({plan:preparedPlan,baseColumns:base})}
function confirmChoices(){try{const executionPlan=executionPlanFor();updateReview({reviewed:true,executionPlan,lineage:executionPlan.lineage,derivedFields:executionPlan.derived_fields,executionError:null})}catch(error){updateReview({reviewed:false,executionPlan:null,lineage:[],derivedFields:[],executionError:error?.message||String(error)})}render();syncApprovalGate()}
function hasPreparationBlockers(){return Boolean(root.document?.getElementById('prepBlockers')?.classList.contains('workflow-blocker'))}
function isApprovalReady(p=plan()){const review=currentReview(p);if(!review)return false;if(review.status===STATUS_SKIPPED)return Boolean(review.reviewed);if(review.status!==STATUS_READY||!review.reviewed)return false;return!review.executionError}
function syncApprovalGate(){const button=root.document?.getElementById('continueSetup');if(!button)return;button.disabled=hasPreparationBlockers()||!isApprovalReady();button.title=!isApprovalReady()?'Review and validate the feature engineering choices before approving preparation.':''}
function recommendationCard(item,selected,locked){const sources=(item.source_fields||[]).join(', '),output=item.output_field||'Derived feature';return`<label class="fe-rec-item${selected?' selected':''}${locked?' locked':''}"><input type="checkbox" data-fe-rec="${safe(item.id)}" ${selected?'checked':''} ${locked?'disabled':''}><span class="fe-rec-copy"><span class="fe-rec-head"><b>${safe(output)}</b><em>${safe(confidenceLabel(item.confidence))} confidence</em></span><span class="fe-rec-transform">${safe(sources)} → ${safe(operationLabel(item.operation))}</span><span>${safe(item.reason)}</span><small>${safe(basisLabel(item.basis||[]))} · Browser execution</small></span></label>`}
function lineageHtml(review){const rows=Array.isArray(review?.lineage)?review.lineage:[];if(!rows.length)return'<div class="fe-confirmed"><b>No derived fields selected</b><span>The analytical matrix will use the original reviewed predictors only.</span></div>';return`<div class="fe-confirmed"><b>${rows.length} derived field${rows.length===1?'':'s'} ready for local execution</b><span>They will be materialized in the browser and automatically added to the analytical matrix sent to the selected analysis/ML engine.</span></div><div class="fe-rec-list">${rows.map(x=>`<div class="fe-rec-item locked selected"><span class="fe-rec-copy"><span class="fe-rec-head"><b>${safe(x.output_field)}</b><em>Derived predictor</em></span><span class="fe-rec-transform">${safe((x.source_fields||[]).join(', '))} → ${safe(operationLabel(x.operation))}</span><small>Lineage · recommended by KU Analytical Intelligence · executed by browser</small></span></div>`).join('')}</div>`}
function render(){
  ensureStyles();const view=root.document?.getElementById('journeyPendingView');if(!view||plan().questionType==null||root.KUAppState?.getState?.().currentStep!=='prepare')return;
  let host=view.querySelector('#feRecommendationReview');if(!host){host=root.document.createElement('section');host.id='feRecommendationReview';host.className='card fe-review-card';const anchor=view.querySelector('.prep-summary-card');if(anchor)anchor.after(host);else view.prepend(host)}
  const review=currentReview()||{status:STATUS_LOADING},items=Array.isArray(review.recommendations)?review.recommendations:[],selected=new Set(unique(review.selectedIds||[]));
  if(review.status===STATUS_LOADING){
    // Keep an already-rendered loading panel intact. State-change events can fire while the
    // request is active; replacing identical markup caused a visible flash/flicker.
    if(host.dataset.feStatus!=='loading'){host.innerHTML='<div class="head">Feature Engineering Recommendations</div><div class="body"><div class="fe-loading"><b>Asking KU Analytical Intelligence…</b><span>Sending the aggregated Profile Manifest, field names, distributions/frequencies, and analytical objective. Raw dataset rows are not sent.</span><small>The first request may take 10–30 seconds while the analytics service starts.</small></div></div>';host.dataset.feStatus='loading'}
    syncApprovalGate();return;
  }
  host.dataset.feStatus=review.status||'';
  if(review.status===STATUS_ERROR){host.innerHTML=`<div class="head">Feature Engineering Recommendations</div><div class="body"><div class="fe-error"><b>Recommendation service unavailable</b><span>${safe(review.error||'The recommendation request could not be completed.')}</span></div><div class="fe-actions"><button type="button" class="btn" data-fe-retry>Retry recommendations</button><button type="button" class="btn ghost" data-fe-skip>Continue without FE recommendations</button></div></div>`;host.querySelector('[data-fe-retry]')?.addEventListener('click',()=>ensureRecommendations({force:true}));host.querySelector('[data-fe-skip]')?.addEventListener('click',()=>{updateReview({status:STATUS_SKIPPED,reviewed:true,selectedIds:[],executionPlan:{schema_version:'1.0',lineage:[],derived_fields:[]},lineage:[],derivedFields:[],skippedReason:'service_unavailable'});render();syncApprovalGate()});syncApprovalGate();return}
  if(review.status===STATUS_SKIPPED){host.innerHTML='<div class="head">Feature Engineering Recommendations</div><div class="body"><div class="fe-confirmed"><b>Feature engineering recommendations skipped</b><span>The current analysis will continue without intelligence-recommended derived features.</span></div><div class="fe-actions"><button type="button" class="btn" data-fe-retry>Try recommendations again</button></div></div>';host.querySelector('[data-fe-retry]')?.addEventListener('click',()=>ensureRecommendations({force:true}));syncApprovalGate();return}
  const locked=Boolean(review.reviewed),domain=(review.domainHints||[]).map(x=>String(x).replaceAll('_',' ')).join(', ')||'general tabular';
  if(!items.length){host.innerHTML=`<div class="head">Feature Engineering Recommendations</div><div class="body"><div class="fe-intro"><div><b>No additional derived features recommended</b><span>KU Analytical Intelligence reviewed the current question and Profile Manifest and did not find a rule-based feature engineering recommendation that requires review.</span></div><span class="fe-domain">Domain hint · ${safe(domain)}</span></div><div class="fe-privacy-note">Profile-only request · field names and aggregate distribution/frequency summaries were sent; raw rows were not sent.</div></div>`;if(!review.reviewed)updateReview({reviewed:true,selectedIds:[],executionPlan:{schema_version:'1.0',lineage:[],derived_fields:[]},lineage:[],derivedFields:[]});syncApprovalGate();return}
  host.innerHTML=`<div class="head">Feature Engineering Recommendations</div><div class="body"><div class="fe-intro"><div><b>${locked?'Feature choices confirmed':'Review suggested derived features'}</b><span>Recommendations use field semantics, the analytical objective, and each field’s observed profile. Confirmed features are executed locally in the browser and enter the actual analytical matrix.</span></div><span class="fe-domain">Domain hint · ${safe(domain)}</span></div><div class="fe-privacy-note">Profile-only request · field names and aggregate distribution/frequency summaries were sent; raw rows were not sent.</div>${review.executionError?`<div class="fe-error"><b>Browser execution plan could not be compiled</b><span>${safe(review.executionError)}</span></div>`:''}<div class="fe-rec-list">${items.map(item=>recommendationCard(item,selected.has(item.id),locked)).join('')}</div>${locked?`${lineageHtml(review)}<div class="fe-actions"><button type="button" class="btn ghost" data-fe-edit>Edit feature choices</button></div>`:`<div class="fe-actions"><button type="button" class="btn ghost" data-fe-all>Select all</button><button type="button" class="btn ghost" data-fe-none>Clear all</button><button type="button" class="btn primary" data-fe-confirm>Confirm feature choices</button></div>`}</div>`;
  host.querySelectorAll('[data-fe-rec]').forEach(box=>box.addEventListener('change',()=>{const next=new Set(unique(currentReview()?.selectedIds||[]));box.checked?next.add(box.dataset.feRec):next.delete(box.dataset.feRec);updateReview({selectedIds:[...next],reviewed:false,executionPlan:null,lineage:[],derivedFields:[],executionError:null});render()}));host.querySelector('[data-fe-all]')?.addEventListener('click',()=>{updateReview({selectedIds:items.map(x=>x.id),reviewed:false,executionPlan:null,lineage:[],derivedFields:[],executionError:null});render()});host.querySelector('[data-fe-none]')?.addEventListener('click',()=>{updateReview({selectedIds:[],reviewed:false,executionPlan:null,lineage:[],derivedFields:[],executionError:null});render()});host.querySelector('[data-fe-confirm]')?.addEventListener('click',confirmChoices);host.querySelector('[data-fe-edit]')?.addEventListener('click',()=>{updateReview({reviewed:false,executionPlan:null,lineage:[],derivedFields:[],executionError:null});render();syncApprovalGate()});syncApprovalGate();
}
async function ensureRecommendations({force=false}={}){
  if(root.KUAppState?.getState?.().currentStep!=='prepare')return null;let request;
  try{request=buildRequest()}catch(error){updateReview({status:STATUS_ERROR,reviewed:false,error:error.message||String(error)});render();return null}
  const fp=fingerprintRequest(request),existing=currentReview();
  if(!force&&activeRequest?.fingerprint===fp)return activeRequest.promise;
  if(!force&&existing?.requestFingerprint===fp&&[STATUS_LOADING,STATUS_READY,STATUS_SKIPPED].includes(existing.status)){render();return existing}
  if(force&&activeRequest){activeRequest.controller.abort();activeRequest=null}
  const serial=++requestSerial,controller=new AbortController();
  updateReview({status:STATUS_LOADING,reviewed:false,requestFingerprint:fp,recommendations:[],selectedIds:[],domainHints:[],error:null,recommenderVersion:null,executionPlan:null,lineage:[],derivedFields:[],executionError:null});render();
  const promise=(async()=>{let timer=null;try{
    const base=String(root.KU_ANALYTICS_API_BASE||'').replace(/\/$/,'');if(!base)throw new Error('Analytics API base is unavailable.');
    timer=setTimeout(()=>controller.abort(),REQUEST_TIMEOUT_MS);
    const response=await fetch(`${base}/recommend/feature-engineering`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request),signal:controller.signal});
    let payload=null;try{payload=await response.json()}catch(_){payload=null}if(!response.ok)throw new Error(payload?.detail||`HTTP ${response.status}`);if(serial!==requestSerial||root.KUAppState?.getState?.().currentStep!=='prepare')return null;
    const recs=Array.isArray(payload?.recommendations)?payload.recommendations:[];updateReview({status:STATUS_READY,reviewed:recs.length===0,requestFingerprint:fp,recommendations:recs,selectedIds:recs.map(x=>x.id),domainHints:payload?.domain_hints||[],warnings:payload?.warnings||[],recommenderVersion:payload?.recommender_version||null,error:null,executionPlan:recs.length?null:{schema_version:'1.0',lineage:[],derived_fields:[]},lineage:[],derivedFields:[],executionError:null});render();return payload;
  }catch(error){if(serial!==requestSerial)return null;const message=error?.name==='AbortError'?`The recommendation service did not respond within ${Math.round(REQUEST_TIMEOUT_MS/1000)} seconds. Please retry, or continue without FE recommendations.`:error?.message||String(error);updateReview({status:STATUS_ERROR,reviewed:false,requestFingerprint:fp,error:message,recommendations:[],selectedIds:[],executionPlan:null,lineage:[],derivedFields:[]});render();return null}
  finally{if(timer)clearTimeout(timer);if(activeRequest?.serial===serial)activeRequest=null}})();
  activeRequest={fingerprint:fp,serial,controller,promise};return promise;
}
function sync(){if(root.KUAppState?.getState?.().currentStep==='prepare')setTimeout(()=>{ensureRecommendations();render();syncApprovalGate()},0)}
function install(){if(installed||!root.document)return;installed=true;ensureStyles();root.document.addEventListener('ku:statechange',sync);root.document.addEventListener('click',event=>{const button=event.target.closest?.('#continueSetup');if(!button)return;if(!isApprovalReady()){event.preventDefault();event.stopImmediatePropagation();syncApprovalGate()}},true);sync()}
return Object.freeze({STATUS_LOADING,STATUS_READY,STATUS_ERROR,STATUS_SKIPPED,REQUEST_TIMEOUT_MS,analysisIntent,buildRequest,fingerprintRequest,currentReview,executionPlanFor,confirmChoices,isApprovalReady,ensureRecommendations,render,syncApprovalGate,install});
});
