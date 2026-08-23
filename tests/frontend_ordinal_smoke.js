const assert=require('assert');
const fs=require('fs');
const path=require('path');
const {JSDOM}=require('jsdom');

const root=path.resolve(__dirname,'..');
const html=fs.readFileSync(path.join(root,'index.html'),'utf8')
  .replace(/<script[^>]+src="https:[^"]+"[^>]*><\/script>/g,'')
  .replace(/<script src="src\/[^"]+"><\/script>/g,'');
const dom=new JSDOM(html,{url:'http://localhost/',runScripts:'outside-only',pretendToBeVisual:true});
const w=dom.window;
w.alert=msg=>{throw new Error(`Unexpected alert: ${msg}`)};
w.HTMLCanvasElement.prototype.getContext=function(){
  return new Proxy({},{get:(t,p)=>p==='measureText'?(()=>({width:10})):(p==='canvas'?this:(()=>{})),set:()=>true});
};
w.fetch=async()=>{throw new Error('Ordinal preparation smoke should not call the backend before Setup.');};

const scripts=[
  'src/state.js','src/app.js','src/analysis.js','src/advanced-stats.js','src/ai-analytics.js',
  'src/relationship-stats.js','src/data-profile.js','src/workflow-steps.js','src/result-drivers.js',
  'src/result-details.js','src/accessibility.js','src/journey.js'
];
w.eval(scripts.map(file=>fs.readFileSync(path.join(root,file),'utf8')).join('\n;\n'));
w.document.dispatchEvent(new w.Event('DOMContentLoaded',{bubbles:true}));
const tick=()=>new Promise(resolve=>w.setTimeout(resolve,0));

(async()=>{
  w.demo();
  await tick();
  w.goToJourneyStep('analyze');
  await tick();
  w.document.querySelector('[data-question-type="predict-outcome"]').click();
  const target=w.document.getElementById('analysisTarget');
  target.value='Satisfaction';
  target.dispatchEvent(new w.Event('change',{bubbles:true}));

  let state=w.KUAppState.getState();
  assert.strictEqual(state.analysisPlan.route,'regression');
  assert.strictEqual(state.analysisPlan.target,'Satisfaction');
  assert.strictEqual(w.KUAppState.canEnterStep('prepare'),true);

  w.document.getElementById('continuePrepare').click();
  await tick();
  state=w.KUAppState.getState();
  assert.strictEqual(state.currentStep,'prepare');
  assert.strictEqual(w.document.getElementById('continueSetup').disabled,false,'recognized ordinal target should be executable');
  const automatic=w.document.querySelector('.prep-status-panel.automatic').textContent;
  assert.ok(automatic.includes('Encode ordered categories'));
  assert.ok(automatic.includes('Low < Medium < High'));
  assert.strictEqual(w.document.querySelector('.prep-status-panel.review .prep-status-title b').textContent.trim(),'0');
  assert.strictEqual(w.document.getElementById('prepBlockers').textContent.trim(),'');

  // Simulate the validated backend payload after approved preparation.
  w.KUAppState.setPreparation({status:'approved',approved:true});
  w.KUAppState.setResultPayload({
    result:{
      status:'COMPLETE',route:'regression',analysis_type:'regression',target:'Satisfaction',
      method:{model:'XGBoost',target_encoding:{type:'ordinal_rank',mapping:{Low:1,Medium:2,High:3},order:['Low','Medium','High']}},
      evidence:{mae:.41,rmse:.53,r2:.68,tail_mae:.62,tail_bias:-.08},
      findings:[],
      warnings:['Ordinal target categories were encoded as ordered ranks. Regression treats the rank codes numerically; differences between adjacent categories should not be interpreted as proven equal intervals.']
    },
    report:{overview:[],method:[],evidence:[],findings:[]}
  });
  w.goToJourneyStep('results');
  await tick();
  assert.ok(w.document.querySelector('.result-answer h2')?.textContent.startsWith('Ordinal rank-coded target · '));
  const details=w.document.getElementById('familyResultDetails');
  assert.ok(details?.textContent.includes('Target Coding'));
  assert.ok(details?.textContent.includes('Low'));
  assert.ok(details?.textContent.includes('Medium'));
  assert.ok(details?.textContent.includes('High'));
  assert.ok(details?.textContent.includes('equal spacing'));
  assert.ok(details?.textContent.includes('Warnings / Guardrails'));
  assert.strictEqual(w.document.querySelector('.result-stale'),null,'fresh ordinal result should not be marked stale');

  // Metadata-only change: Ordinal -> Scale keeps the same Regression route but changes interpretation.
  w.goToJourneyStep('profile');
  await tick();
  const variableNames=[...w.document.querySelectorAll('#variableTable .variable-name')].map(node=>node.textContent.trim());
  const satisfactionIndex=variableNames.indexOf('Satisfaction');
  assert.ok(satisfactionIndex>=0,'demo should include Satisfaction');
  w.updateLevelByIndex(satisfactionIndex,'Scale');
  if(typeof w.syncKUJourneyDataset==='function')w.syncKUJourneyDataset();
  await tick();
  await tick();
  state=w.KUAppState.getState();
  assert.strictEqual(state.analysisPlan.route,'regression','Ordinal -> Scale should keep the Regression route');
  assert.strictEqual(state.result.validated,true,'metadata-only change should preserve previous result for comparison');
  assert.strictEqual(state.analysisPlan.preparation.approved,false,'metadata-only change should invalidate preparation approval');

  w.goToJourneyStep('results');
  await tick();
  const stale=w.document.querySelector('.result-stale');
  assert.ok(stale,'metadata-only mismatch should mark the previous result stale');
  assert.ok(stale.textContent.includes('Field storage or measurement metadata changed'));
  console.log('FRONTEND_ORDINAL_SMOKE_OK');
})().catch(err=>{console.error(err);process.exit(1)});
