// KU Open Data Analytics — six-step journey controller
(function(){
  'use strict';
  const stepOrder=['start','profile','analyze','prepare','setup','results'];
  const stepLabels={
    start:['START','Choose / Upload Dataset'],profile:['DATA PROFILE','Understand the Dataset'],analyze:['ANALYZE','Define the Analytical Question'],
    prepare:['PREPARE','Review Data Preparation'],setup:['SETUP','Confirm How the Analysis Will Run'],results:['RESULTS','Understand the Results']
  };
  const questionLabels={'predict-outcome':'Predict an outcome','compare-groups':'Compare groups','explain-drivers':'Explain relationships / drivers','discover-segments':'Discover segments','discover-association-rules':'Discover association rules'};
  const $=id=>document.getElementById(id);
  let lastDatasetSignature='';
  const escJourney=value=>String(value??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const currentPlanLabel=plan=>plan.question||plan.analyticalFamily||'No analysis plan yet';

  function renderCurrentAnalysis(){
    if(!window.KUAppState)return;
    const {analysisPlan:p}=window.KUAppState.getState(),predictors=p.predictorMode==='all-suitable'?`All suitable fields (${(p.predictors||[]).length})`:`${(p.predictors||[]).length} custom field${(p.predictors||[]).length===1?'':'s'}`,questionType=questionLabels[p.questionType]||'Question not defined';
    const html=`<div class="current-analysis-main"><span>Current Analysis · ${escJourney(questionType)}</span><b>${escJourney(currentPlanLabel(p))}</b></div>
      <div class="current-analysis-item"><span>Target / Outcome</span><b>${escJourney(p.target||'Not required / selected')}</b></div>
      <div class="current-analysis-item"><span>Recommended Family</span><b>${escJourney(p.analyticalFamily||'Not derived')}</b></div>
      <div class="current-analysis-item"><span>Predictors</span><b>${escJourney(predictors)}</b></div>`;
    const nodes=new Set([...document.querySelectorAll('[data-current-analysis]')]);
    const primary=$('currentAnalysisBar');if(primary)nodes.add(primary);
    nodes.forEach(el=>el.innerHTML=html);
  }
  function renderJourney(){
    if(!window.KUAppState)return;const state=window.KUAppState.getState();
    document.querySelectorAll('[data-journey-step]').forEach(button=>{
      const key=button.dataset.journeyStep,index=stepOrder.indexOf(key),currentIndex=stepOrder.indexOf(state.currentStep),enabled=window.KUAppState.canEnterStep(key);
      button.classList.toggle('active',key===state.currentStep);button.classList.toggle('done',index>=0&&index<currentIndex);button.disabled=!enabled;
      button.setAttribute('aria-current',key===state.currentStep?'step':'false');button.title=enabled?'':`${stepLabels[key]?.[0]||key} becomes available when the prior required state is complete.`;
    });renderCurrentAnalysis();
  }
  function hideView(id){const el=$(id);if(el)el.classList.add('hidden')}
  function ensurePendingView(){
    let view=$('journeyPendingView');if(view)return view;
    view=document.createElement('section');view.id='journeyPendingView';view.className='hidden';document.querySelector('main')?.appendChild(view);return view;
  }
  function showPendingStep(step){
    const view=ensurePendingView(),label=stepLabels[step]||[step.toUpperCase(),step];
    ['workspaceView','variablesView','analysisView','aiAnalyticsView'].forEach(hideView);view.classList.remove('hidden');
    view.innerHTML=`<div class="step-kicker">STEP ${stepOrder.indexOf(step)+1} · ${escJourney(label[0])}</div><h1>${escJourney(label[1])}</h1><p class="lead">The Analysis Plan is preserved as you move through the workflow.</p><div class="current-analysis-bar" data-current-analysis></div><div class="journey-pending-card"><b>Analysis Plan saved</b><p>This integration branch has reached the ${escJourney(label[0])} boundary. The next production batch will connect this page to real preparation/setup metadata rather than showing prototype or example calculations.</p></div><div style="margin-top:16px"><button class="btn ghost" onclick="goToJourneyStep('analyze')">← Back to Analyze</button></div>`;
    renderCurrentAnalysis();
  }
  function goToJourneyStep(step){
    if(!window.KUAppState||!window.KUAppState.canEnterStep(step))return;
    window.KUAppState.setStep(step);
    if(step==='start'||step==='profile'){
      hideView('aiAnalyticsView');hideView('journeyPendingView');
      if(typeof showView==='function')showView(step==='start'?'workspace':'variables');
    }else if(step==='analyze'&&typeof showAIAnalyticsView==='function'){
      hideView('journeyPendingView');showAIAnalyticsView();
    }else showPendingStep(step);
    renderJourney();
  }
  window.goToJourneyStep=goToJourneyStep;

  function syncDatasetFromLegacy(){
    if(!window.KUAppState||typeof headers==='undefined'||typeof data==='undefined')return;
    const loaded=Array.isArray(headers)&&headers.length>0&&Array.isArray(data)&&data.length>0;
    const signature=loaded?`${data.length}|${headers.join('\u001f')}|${headers.map(h=>`${typeof types!=='undefined'?types[h]:''}:${typeof meta!=='undefined'?meta[h]?.level||'':''}`).join('\u001e')}`:'empty';
    if(signature===lastDatasetSignature)return;lastDatasetSignature=signature;
    window.KUAppState.setDataset(loaded?{loaded:true,rowCount:data.length,columnCount:headers.length,fields:headers.map(name=>({name,storage:typeof types!=='undefined'?types[name]:null,level:typeof meta!=='undefined'?meta[name]?.level:null}))}:null);
  }
  window.syncKUJourneyDataset=syncDatasetFromLegacy;

  document.addEventListener('ku:render-current-analysis',renderCurrentAnalysis);
  document.addEventListener('DOMContentLoaded',()=>{
    if(!window.KUAppState)return;window.KUAppState.subscribe(renderJourney);
    document.querySelectorAll('[data-journey-step]').forEach(button=>button.addEventListener('click',()=>goToJourneyStep(button.dataset.journeyStep)));
    const status=$('status'),variableTable=$('variableTable');
    if(status&&typeof MutationObserver!=='undefined')new MutationObserver(syncDatasetFromLegacy).observe(status,{childList:true,subtree:true,characterData:true});
    if(variableTable&&typeof MutationObserver!=='undefined')new MutationObserver(syncDatasetFromLegacy).observe(variableTable,{childList:true,subtree:true});
    syncDatasetFromLegacy();renderJourney();
  });
})();
