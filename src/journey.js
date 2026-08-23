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
  const questionLabels={
    'predict-outcome':'Predict an outcome',
    'compare-groups':'Compare groups',
    'explain-drivers':'Explain relationships / drivers',
    'discover-segments':'Discover segments',
    'discover-association-rules':'Discover association rules'
  };
  const $=id=>document.getElementById(id);
  let lastDatasetSignature='';

  const escJourney=value=>String(value??'').replace(/[&<>"']/g,m=>({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[m]));
  const currentPlanLabel=plan=>plan.question||plan.analyticalFamily||'No analysis plan yet';

  function resetViewport(){
    const scroller=document.scrollingElement||document.documentElement;
    if(scroller)scroller.scrollTop=0;
    if(document.body)document.body.scrollTop=0;
  }

  function renderCurrentAnalysis(){
    if(!window.KUAppState)return;
    const {analysisPlan:p}=window.KUAppState.getState();
    const predictors=p.predictorMode==='all-suitable'
      ?`All suitable fields (${(p.predictors||[]).length})`
      :`${(p.predictors||[]).length} custom field${(p.predictors||[]).length===1?'':'s'}`;
    const questionType=questionLabels[p.questionType]||'Question not defined';
    const html=`<div class="current-analysis-main"><span>Current Analysis · ${escJourney(questionType)}</span><b>${escJourney(currentPlanLabel(p))}</b></div>
      <div class="current-analysis-item"><span>Target / Outcome</span><b>${escJourney(p.target||'Not required / selected')}</b></div>
      <div class="current-analysis-item"><span>Recommended Family</span><b>${escJourney(p.analyticalFamily||'Not derived')}</b></div>
      <div class="current-analysis-item"><span>Predictors</span><b>${escJourney(predictors)}</b></div>`;
    const nodes=new Set([...document.querySelectorAll('[data-current-analysis]')]);
    const primary=$('currentAnalysisBar');
    if(primary)nodes.add(primary);
    nodes.forEach(node=>node.innerHTML=html);
  }

  function renderJourney(){
    if(!window.KUAppState)return;
    const state=window.KUAppState.getState();
    document.querySelectorAll('[data-journey-step]').forEach(button=>{
      const key=button.dataset.journeyStep;
      const index=stepOrder.indexOf(key);
      const currentIndex=stepOrder.indexOf(state.currentStep);
      const enabled=window.KUAppState.canEnterStep(key);
      button.classList.toggle('active',key===state.currentStep);
      button.classList.toggle('done',index>=0&&index<currentIndex);
      button.disabled=!enabled;
      button.setAttribute('aria-current',key===state.currentStep?'step':'false');
      button.title=enabled?'':`${stepLabels[key]?.[0]||key} becomes available when the prior required state is complete.`;
    });
    renderCurrentAnalysis();
  }

  function hideView(id){
    const node=$(id);
    if(node)node.classList.add('hidden');
  }

  function showWorkflowFallback(step,message='Production workflow module is unavailable.'){
    let view=$('journeyPendingView');
    if(!view){
      view=document.createElement('section');
      view.id='journeyPendingView';
      document.querySelector('main')?.appendChild(view);
    }
    ['workspaceView','variablesView','analysisView','aiAnalyticsView'].forEach(hideView);
    view.classList.remove('hidden');
    view.innerHTML=`<div class="step-kicker">STEP ${stepOrder.indexOf(step)+1}</div><h1>${escJourney(stepLabels[step]?.[1]||step)}</h1><div class="journey-pending-card"><b>Workflow module unavailable</b><p>${escJourney(message)}</p></div>`;
  }

  function showProductionStep(step){
    const workflow=window.KUWorkflowSteps;
    if(!workflow)return showWorkflowFallback(step);
    try{
      workflow.show(step);
    }catch(err){
      showWorkflowFallback(step,err.message);
    }
  }

  function goToJourneyStep(step){
    if(!window.KUAppState||!window.KUAppState.canEnterStep(step))return;
    window.KUAppState.setStep(step);

    if(step==='start'||step==='profile'){
      hideView('aiAnalyticsView');
      hideView('journeyPendingView');
      if(typeof window.showView==='function')window.showView(step==='start'?'workspace':'variables');
    }else if(step==='analyze'&&typeof window.showAIAnalyticsView==='function'){
      hideView('journeyPendingView');
      window.showAIAnalyticsView();
    }else{
      showProductionStep(step);
    }

    renderJourney();
    resetViewport();
  }
  window.goToJourneyStep=goToJourneyStep;

  function installLegacyViewBridge(){
    const rawShowView=window.showView;
    if(typeof rawShowView==='function'&&!rawShowView.__kuJourneyBridge){
      const bridged=function(view){
        hideView('aiAnalyticsView');
        hideView('journeyPendingView');
        rawShowView(view);
        const step=view==='workspace'?'start':view==='variables'?'profile':null;
        if(step&&window.KUAppState?.canEnterStep(step))window.KUAppState.setStep(step);
        renderJourney();
        resetViewport();
      };
      bridged.__kuJourneyBridge=true;
      window.showView=bridged;
    }

    const rawShowAnalysis=window.showAnalysisView;
    if(typeof rawShowAnalysis==='function'&&!rawShowAnalysis.__kuJourneyBridge){
      const bridged=function(name){
        hideView('aiAnalyticsView');
        hideView('journeyPendingView');
        rawShowAnalysis(name);
        renderJourney();
        resetViewport();
      };
      bridged.__kuJourneyBridge=true;
      window.showAnalysisView=bridged;
    }

    document.querySelectorAll('.advanced-nav .nav').forEach(node=>{
      const text=node.textContent.trim();
      if(text==='Data Workspace')node.onclick=()=>goToJourneyStep('start');
      else if(text==='Variables')node.onclick=()=>goToJourneyStep('profile');
      else if(text==='Validated Analytics Engine')node.onclick=()=>goToJourneyStep('analyze');
    });
  }

  function syncDatasetFromLegacy(){
    if(!window.KUAppState||typeof headers==='undefined'||typeof data==='undefined')return;
    const loaded=Array.isArray(headers)&&headers.length>0&&Array.isArray(data)&&data.length>0;
    const signature=loaded
      ?`${data.length}|${headers.join('\u001f')}|${headers.map(h=>`${typeof types!=='undefined'?types[h]:''}:${typeof meta!=='undefined'?meta[h]?.level||'':''}`).join('\u001e')}`
      :'empty';
    if(signature===lastDatasetSignature)return;
    lastDatasetSignature=signature;
    window.KUAppState.setDataset(loaded?{
      loaded:true,
      rowCount:data.length,
      columnCount:headers.length,
      fields:headers.map(name=>({
        name,
        storage:typeof types!=='undefined'?types[name]:null,
        level:typeof meta!=='undefined'?meta[name]?.level:null
      }))
    }:null);
  }
  window.syncKUJourneyDataset=syncDatasetFromLegacy;

  document.addEventListener('ku:render-current-analysis',renderCurrentAnalysis);
  document.addEventListener('DOMContentLoaded',()=>{
    if(!window.KUAppState)return;
    if(typeof KU_ANALYTICS_API_BASE!=='undefined')window.KU_ANALYTICS_API_BASE=KU_ANALYTICS_API_BASE;
    installLegacyViewBridge();
    window.KUAppState.subscribe(renderJourney);
    document.querySelectorAll('[data-journey-step]').forEach(button=>{
      button.addEventListener('click',()=>goToJourneyStep(button.dataset.journeyStep));
    });
    const status=$('status'),variableTable=$('variableTable');
    if(status&&typeof MutationObserver!=='undefined'){
      new MutationObserver(syncDatasetFromLegacy).observe(status,{childList:true,subtree:true,characterData:true});
    }
    if(variableTable&&typeof MutationObserver!=='undefined'){
      new MutationObserver(syncDatasetFromLegacy).observe(variableTable,{childList:true,subtree:true});
    }
    syncDatasetFromLegacy();
    renderJourney();
  });
})();
