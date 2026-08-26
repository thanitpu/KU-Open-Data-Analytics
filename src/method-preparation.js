// KU Open DA — method-specific Step 4 preparation guard.
(function(root,factory){
  const api=factory(root);
  if(typeof module==='object'&&module.exports)module.exports=api;
  if(root)root.KUMethodPreparation=api;
  if(root?.document){
    if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>api.install());
    else api.install();
  }
})(typeof window!=='undefined'?window:globalThis,function(root){
'use strict';
let installed=false;
const missing=v=>v===''||v===null||v===undefined||(typeof v==='number'&&Number.isNaN(v));
const finite=v=>{if(missing(v))return null;const n=Number(v);return Number.isFinite(n)?n:null};
const safe=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
function rows(){try{return typeof data!=='undefined'&&Array.isArray(data)?data:[]}catch(_){return[]}}
function selectedMethodIds(plan={}){
  try{return root.KUMethodSelection?.effectiveMethodIds?.(plan,root.KUProfileInsights?.getManifest?.())||[]}
  catch(_){return plan.methodMode==='custom'?[...(plan.selectedMethods||[])]:[]}
}
function currentGroup(plan={}){return plan.preparation?.groupField||root.document?.getElementById('prepareGroupField')?.value||null}
function completeGroupCount(plan={},group=currentGroup(plan)){
  if(!group||!plan.target)return 0;
  const groups=new Set();
  for(const row of rows()){
    if(finite(row?.[plan.target])===null||missing(row?.[group]))continue;
    groups.add(String(row[group]));
  }
  return groups.size;
}
function blockers(plan={}){
  if(plan.route!=='group-comparison')return[];
  const ids=new Set(selectedMethodIds(plan)),group=currentGroup(plan),count=completeGroupCount(plan,group),out=[];
  if(ids.has('welch-t-test')){
    if(!group)out.push('Welch t-test requires a grouping field before Setup.');
    else if(count!==2)out.push(`Welch t-test requires exactly 2 complete groups; ${count} are currently observed. Choose a compatible grouping field or method.`);
  }
  if(ids.has('one-way-anova')){
    if(!group)out.push('One-way ANOVA requires a grouping field before Setup.');
    else if(count<3)out.push(`One-way ANOVA requires 3 or more complete groups; ${count} are currently observed. Choose a compatible grouping field or method.`);
  }
  return out;
}
function sync(){
  const state=root.KUAppState?.getState?.();if(state?.currentStep!=='prepare')return;
  const view=root.document?.getElementById('journeyPendingView'),footer=view?.querySelector('.workflow-footer');if(!view||!footer)return;
  const issues=blockers(state.analysisPlan||{});let box=view.querySelector('#methodPrepBlockers');
  if(issues.length){
    if(!box){box=root.document.createElement('div');box.id='methodPrepBlockers';box.className='workflow-blocker method-prep-blocker';footer.before(box)}
    box.innerHTML=`<b>Selected method needs preparation review</b>${issues.map(x=>`<p>${safe(x)}</p>`).join('')}`;
  }else box?.remove();
  const button=root.document.getElementById('continueSetup');if(!button)return;
  const baseBlocked=Boolean(root.document.getElementById('prepBlockers')?.classList.contains('workflow-blocker'));
  const fe=root.KUFeatureEngineeringReview,feReady=fe?.isApprovalReady?fe.isApprovalReady(state.analysisPlan||{}):true;
  button.disabled=baseBlocked||issues.length>0||!feReady;
}
function install(){
  if(installed||!root.document)return;installed=true;
  root.document.addEventListener('ku:render-current-analysis',()=>queueMicrotask(sync));
  root.document.addEventListener('ku:statechange',()=>queueMicrotask(sync));
  root.document.addEventListener('change',event=>{if(event.target?.id==='prepareGroupField')queueMicrotask(sync)});
  sync();
}
return Object.freeze({selectedMethodIds,currentGroup,completeGroupCount,blockers,sync,install});
});
