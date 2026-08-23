// KU Open Data Analytics — six-step journey controller
(function(){
  'use strict';
  const stepOrder=['start','profile','analyze','prepare','setup','results'];
  const stepLabels={
    start:['START','Choose / Upload Dataset'],
    profile:['DATA PROFILE','Understand the Dataset'],
    analyze:['ANALYZE','Define the Analytical Question'],
    prepare:['PREPARE','Review Data Preparation'],
    setup:['SETUP','Confirm How the Analysis Will Run'],
    results:['RESULTS','Understand the Results']
  };
  const $=id=>document.getElementById(id);
  let lastDatasetSignature='';

  function currentPlanLabel(plan){
    if(plan.question)return plan.question;
    if(plan.analyticalFamily)return plan.analyticalFamily;
    return 'No analysis plan yet';
  }
  function escJourney(value){return String(value??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}
  function renderCurrentAnalysis(){
    const el=$('currentAnalysisBar');
    if(!el||!window.KUAppState)return;
    const {analysisPlan:p}=window.KUAppState.getState();
    const predictors=p.predictorMode==='all-suitable'?'All suitable fields':String((p.predictors||[]).length);
    el.innerHTML=`
      <div class="current-analysis-main"><span>Current Analysis</span><b>${escJourney(currentPlanLabel(p))}</b></div>
      <div class="current-analysis-item"><span>Question Type</span><b>${escJourney(p.questionType||'Not defined')}</b></div>
      <div class="current-analysis-item"><span>Target / Outcome</span><b>${escJourney(p.target||'Not selected')}</b></div>
      <div class="current-analysis-item"><span>Predictors</span><b>${escJourney(predictors)}</b></div>`;
  }

  function renderJourney(){
    if(!window.KUAppState)return;
    const state=window.KUAppState.getState();
    document.querySelectorAll('[data-journey-step]').forEach(button=>{
      const key=button.dataset.journeyStep;
      const index=stepOrder.indexOf(key);
      const currentIndex=stepOrder.indexOf(state.currentStep);
      button.classList.toggle('active',key===state.currentStep);
      button.classList.toggle('done',index>=0&&index<currentIndex);
      const enabled=window.KUAppState.canEnterStep(key);
      button.disabled=!enabled;
      button.setAttribute('aria-current',key===state.currentStep?'step':'false');
      button.title=enabled?'':`${stepLabels[key]?.[0]||key} becomes available when the prior required state is complete.`;
    });
    renderCurrentAnalysis();
  }

  function goToJourneyStep(step){
    if(!window.KUAppState||!window.KUAppState.canEnterStep(step))return;
    window.KUAppState.setStep(step);
    if(step==='start'&&typeof showView==='function')showView('workspace');
    else if(step==='profile'&&typeof showView==='function')showView('variables');
    else if(step==='analyze'&&typeof showAIAnalyticsView==='function')showAIAnalyticsView();
    // Prepare, Setup, and Results receive their production pages in subsequent migration batches.
    renderJourney();
  }
  window.goToJourneyStep=goToJourneyStep;

  function syncDatasetFromLegacy(){
    if(!window.KUAppState||typeof headers==='undefined'||typeof data==='undefined')return;
    const loaded=Array.isArray(headers)&&headers.length>0&&Array.isArray(data)&&data.length>0;
    const signature=loaded?`${data.length}|${headers.join('\u001f')}|${headers.map(h=>`${typeof types!=='undefined'?types[h]:''}:${typeof meta!=='undefined'?meta[h]?.level||'':''}`).join('\u001e')}`:'empty';
    if(signature===lastDatasetSignature)return;
    lastDatasetSignature=signature;
    window.KUAppState.setDataset(loaded?{
      loaded:true,rowCount:data.length,columnCount:headers.length,
      fields:headers.map(name=>({name,storage:typeof types!=='undefined'?types[name]:null,level:typeof meta!=='undefined'?meta[name]?.level:null}))
    }:null);
  }
  window.syncKUJourneyDataset=syncDatasetFromLegacy;

  document.addEventListener('DOMContentLoaded',()=>{
    if(!window.KUAppState)return;
    window.KUAppState.subscribe(renderJourney);
    document.querySelectorAll('[data-journey-step]').forEach(button=>button.addEventListener('click',()=>goToJourneyStep(button.dataset.journeyStep)));
    const status=$('status');
    if(status&&typeof MutationObserver!=='undefined')new MutationObserver(syncDatasetFromLegacy).observe(status,{childList:true,subtree:true,characterData:true});
    const variableTable=$('variableTable');
    if(variableTable&&typeof MutationObserver!=='undefined')new MutationObserver(syncDatasetFromLegacy).observe(variableTable,{childList:true,subtree:true});
    syncDatasetFromLegacy();
    renderJourney();
  });
})();
