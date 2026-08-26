// KU Open Data Analytics — authoritative application state
// Centralizes the six-step journey, Analysis Plan, and validated result payload.
(function(root){
  'use strict';
  const listeners=new Set();
  const emptyResult=()=>({payload:null,validated:false,source:null,lastRunAt:null,planSnapshot:null});
  const emptyPreparation=()=>({status:'not-reviewed',approved:false});
  const emptySetup=()=>({mode:'recommended',configuration:{}});
  const emptyDataset=()=>({loaded:false,name:null,rowCount:0,columnCount:0,revision:0,fields:[]});
  const emptyMethodSelection=()=>({methodMode:'recommended',selectedMethods:[]});
  const initialState=()=>({currentStep:'start',dataset:emptyDataset(),analysisPlan:{questionType:null,target:null,predictors:[],predictorMode:'all-suitable',analyticalFamily:null,route:null,question:'',...emptyMethodSelection(),preparation:emptyPreparation(),setup:emptySetup()},result:emptyResult()});
  let state=initialState();
  const copy=value=>JSON.parse(JSON.stringify(value));
  const unique=list=>[...new Set((Array.isArray(list)?list:[]).filter(Boolean))];
  function getState(){return copy(state)}
  function emit(reason){const snapshot=getState();listeners.forEach(fn=>{try{fn(snapshot,reason)}catch(err){console.error('KUAppState listener failed',err)}});if(typeof document!=='undefined'&&typeof CustomEvent!=='undefined')document.dispatchEvent(new CustomEvent('ku:statechange',{detail:{state:snapshot,reason}}))}
  function subscribe(fn){listeners.add(fn);return()=>listeners.delete(fn)}
  function setStep(step){const allowed=['start','profile','analyze','prepare','setup','results'];if(!allowed.includes(step))throw new Error(`Unknown KU Open DA step: ${step}`);if(state.currentStep===step)return;state={...state,currentStep:step};emit('journey:step')}
  function datasetIdentity(d){return `${d.loaded}|${d.revision||0}|${d.name||''}|${d.rowCount}|${d.columnCount}|${(d.fields||[]).map(f=>f.name||'').join('\u001f')}`}
  function datasetMetadataIdentity(d){return (d.fields||[]).map(f=>`${f.name||''}:${f.storage||''}:${f.level||''}`).join('\u001e')}
  function selectedFieldMetadata(p=state.analysisPlan,d=state.dataset){const selected=new Set([p.target,...(p.predictors||[])].filter(Boolean));return(d.fields||[]).filter(f=>selected.has(f.name)).map(f=>({name:f.name,storage:f.storage||null,level:f.level||null}))}
  function setDataset(dataset){
    const next=dataset&&dataset.loaded!==false?{loaded:true,name:dataset.name||null,rowCount:Number(dataset.rowCount)||0,columnCount:Number(dataset.columnCount)||0,revision:Number(dataset.revision)||0,fields:Array.isArray(dataset.fields)?copy(dataset.fields):[]}:emptyDataset();
    const datasetChanged=state.dataset.loaded&&datasetIdentity(state.dataset)!==datasetIdentity(next);
    if(datasetChanged){const fresh=initialState();state={...fresh,dataset:next,currentStep:'start'};emit('dataset:replace+analysis-reset');return}
    const metadataChanged=state.dataset.loaded&&next.loaded&&datasetMetadataIdentity(state.dataset)!==datasetMetadataIdentity(next);
    if(metadataChanged){state={...state,dataset:next,analysisPlan:{...state.analysisPlan,preparation:{status:'needs-review',approved:false},setup:emptySetup()}};emit('dataset:metadata+downstream-reset');return}
    state={...state,dataset:next};emit('dataset:update')
  }
  function updateAnalysisPlan(patch={}){
    const before=state.analysisPlan;
    const next={...before,...patch};
    if(Object.prototype.hasOwnProperty.call(patch,'predictors'))next.predictors=unique(patch.predictors);
    if(Object.prototype.hasOwnProperty.call(patch,'selectedMethods'))next.selectedMethods=unique(patch.selectedMethods);
    if(patch.preparation)next.preparation={...before.preparation,...patch.preparation};
    if(patch.setup)next.setup={...before.setup,...patch.setup};
    const questionOrTargetChanged=next.questionType!==before.questionType||next.target!==before.target;
    const predictorsChanged=JSON.stringify(next.predictors)!==JSON.stringify(before.predictors)||next.predictorMode!==before.predictorMode;
    const routeChanged=next.route!==before.route||next.analyticalFamily!==before.analyticalFamily;
    if(questionOrTargetChanged||routeChanged){next.methodMode='recommended';next.selectedMethods=[]}
    const methodsChanged=next.methodMode!==before.methodMode||JSON.stringify(unique(next.selectedMethods).sort())!==JSON.stringify(unique(before.selectedMethods).sort());
    if(questionOrTargetChanged){next.preparation=emptyPreparation();next.setup=emptySetup()}
    else if(predictorsChanged||routeChanged||methodsChanged){next.preparation={status:'needs-review',approved:false};next.setup=emptySetup()}
    const invalidateResult=questionOrTargetChanged||methodsChanged||routeChanged;
    state={...state,analysisPlan:next,result:invalidateResult?emptyResult():state.result};
    emit(questionOrTargetChanged?'analysis-plan:update+downstream-reset+result-reset':methodsChanged?'analysis-plan:methods+downstream-reset+result-reset':predictorsChanged?'analysis-plan:predictors+downstream-reset':routeChanged?'analysis-plan:route+downstream-reset+result-reset':'analysis-plan:update')
  }
  function setPredictors(predictors){updateAnalysisPlan({predictors})}
  function setPreparation(patch){updateAnalysisPlan({preparation:patch||{}})}
  function setSetup(patch){updateAnalysisPlan({setup:patch||{}})}
  function setResultPayload(payload,{validated=true,source='api'}={}){const p=state.analysisPlan;const planSnapshot={questionType:p.questionType,target:p.target,predictors:copy(p.predictors),predictorMode:p.predictorMode,analyticalFamily:p.analyticalFamily,route:p.route,question:p.question,methodMode:p.methodMode||'recommended',selectedMethods:copy(p.selectedMethods||[]),preparation:copy(p.preparation),fieldMetadata:copy(selectedFieldMetadata(p,state.dataset)),datasetRevision:state.dataset.revision||0};state={...state,result:{payload:copy(payload),validated:Boolean(validated),source,lastRunAt:new Date().toISOString(),planSnapshot}};emit('result:set')}
  function resetResult(){state={...state,result:emptyResult()};emit('result:reset')}
  function resetAnalysis(){const fresh=initialState();state={...fresh,dataset:state.dataset,currentStep:'start'};emit('analysis:reset')}
  function canEnterStep(step){if(step==='start')return true;if(step==='profile'||step==='analyze')return state.dataset.loaded;if(step==='prepare')return state.dataset.loaded&&Boolean(state.analysisPlan.questionType&&state.analysisPlan.route);if(step==='setup')return Boolean(state.analysisPlan.preparation.approved);if(step==='results')return Boolean(state.result.validated&&state.result.payload);return false}
  root.KUAppState=Object.freeze({getState,subscribe,setStep,setDataset,updateAnalysisPlan,setPredictors,setPreparation,setSetup,setResultPayload,resetResult,resetAnalysis,canEnterStep});
})(typeof window!=='undefined'?window:globalThis);
