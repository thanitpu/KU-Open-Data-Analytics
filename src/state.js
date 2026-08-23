// KU Open Data Analytics — authoritative application state
// Centralizes the six-step journey, Analysis Plan, and validated result payload.
(function(root){
  'use strict';

  const listeners=new Set();
  const emptyResult=()=>({payload:null,validated:false,source:null,lastRunAt:null});
  const initialState=()=>({
    currentStep:'start',
    dataset:{loaded:false,name:null,rowCount:0,columnCount:0,fields:[]},
    analysisPlan:{
      questionType:null,
      target:null,
      predictors:[],
      predictorMode:'all-suitable',
      analyticalFamily:null,
      route:null,
      question:'',
      preparation:{status:'not-reviewed',approved:false},
      setup:{mode:'recommended',configuration:{}}
    },
    result:emptyResult()
  });

  let state=initialState();
  const copy=value=>JSON.parse(JSON.stringify(value));
  const unique=list=>[...new Set((Array.isArray(list)?list:[]).filter(Boolean))];

  function getState(){return copy(state)}
  function emit(reason){
    const snapshot=getState();
    listeners.forEach(fn=>{try{fn(snapshot,reason)}catch(err){console.error('KUAppState listener failed',err)}});
    if(typeof document!=='undefined'&&typeof CustomEvent!=='undefined'){
      document.dispatchEvent(new CustomEvent('ku:statechange',{detail:{state:snapshot,reason}}));
    }
  }
  function subscribe(fn){listeners.add(fn);return()=>listeners.delete(fn)}

  function setStep(step){
    const allowed=['start','profile','analyze','prepare','setup','results'];
    if(!allowed.includes(step))throw new Error(`Unknown KU Open DA step: ${step}`);
    if(state.currentStep===step)return;
    state={...state,currentStep:step};
    emit('journey:step');
  }

  function setDataset(dataset){
    const next=dataset&&dataset.loaded!==false?{
      loaded:true,
      name:dataset.name||null,
      rowCount:Number(dataset.rowCount)||0,
      columnCount:Number(dataset.columnCount)||0,
      fields:Array.isArray(dataset.fields)?copy(dataset.fields):[]
    }:{loaded:false,name:null,rowCount:0,columnCount:0,fields:[]};
    state={...state,dataset:next};
    emit('dataset:update');
  }

  function updateAnalysisPlan(patch={}){
    const before=state.analysisPlan;
    const next={...before,...patch};
    if(Object.prototype.hasOwnProperty.call(patch,'predictors'))next.predictors=unique(patch.predictors);
    if(patch.preparation)next.preparation={...before.preparation,...patch.preparation};
    if(patch.setup)next.setup={...before.setup,...patch.setup};

    // Product rule: validated results are invalidated ONLY by Question Type or Target changes.
    const invalidatesResult=next.questionType!==before.questionType||next.target!==before.target;
    state={...state,analysisPlan:next,result:invalidatesResult?emptyResult():state.result};
    emit(invalidatesResult?'analysis-plan:update+result-reset':'analysis-plan:update');
  }

  function setPredictors(predictors){updateAnalysisPlan({predictors})}
  function setPreparation(patch){updateAnalysisPlan({preparation:patch||{}})}
  function setSetup(patch){updateAnalysisPlan({setup:patch||{}})}

  function setResultPayload(payload,{validated=true,source='api'}={}){
    state={...state,result:{payload:copy(payload),validated:Boolean(validated),source,lastRunAt:new Date().toISOString()}};
    emit('result:set');
  }
  function resetResult(){state={...state,result:emptyResult()};emit('result:reset')}
  function resetAnalysis(){
    const fresh=initialState();
    state={...fresh,dataset:state.dataset,currentStep:'start'};
    emit('analysis:reset');
  }

  function canEnterStep(step){
    if(step==='start')return true;
    if(step==='profile'||step==='analyze')return state.dataset.loaded;
    if(step==='prepare')return state.dataset.loaded&&Boolean(state.analysisPlan.questionType||state.analysisPlan.analyticalFamily);
    if(step==='setup')return Boolean(state.analysisPlan.preparation.approved);
    if(step==='results')return Boolean(state.result.validated&&state.result.payload);
    return false;
  }

  root.KUAppState=Object.freeze({
    getState,subscribe,setStep,setDataset,updateAnalysisPlan,setPredictors,setPreparation,setSetup,
    setResultPayload,resetResult,resetAnalysis,canEnterStep
  });
})(typeof window!=='undefined'?window:globalThis);
