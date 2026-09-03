const assert=require('assert');
const fs=require('fs');
const path=require('path');
const {JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..');
const html=fs.readFileSync(path.join(root,'app.html'),'utf8').replace(/<script[^>]+src="https:[^"]+"[^>]*><\/script>/g,'').replace(/<script src="src\/[^"]+"><\/script>/g,'');
const dom=new JSDOM(html,{url:'http://localhost/app.html',runScripts:'outside-only',pretendToBeVisual:true});
const window=dom.window;
window.alert=message=>{throw new Error(String(message));};
window.HTMLCanvasElement.prototype.getContext=function(){return new Proxy({},{get:(target,property)=>property==='measureText'?(()=>({width:10})):(property==='canvas'?this:(()=>{})),set:()=>true});};
window.refreshAnalysisSelectors=()=>{};
const scripts=[
  'src/state.js','src/ku2d-data-asset.js',
  'src/text-analytics/contracts/text-field-contract.js','src/text-analytics/contracts/text-profile-contract.js','src/text-analytics/contracts/derived-feature-contract.js',
  'src/text-analytics/core/text-normalizer.js','src/text-analytics/core/language-detector.js','src/text-analytics/core/tokenizer.js','src/text-analytics/core/text-field-detector.js','src/text-analytics/core/text-profiler.js','src/text-analytics/core/keyword-extractor.js','src/text-analytics/core/phrase-extractor.js','src/text-analytics/core/sentiment-baseline.js','src/text-analytics/core/topic-discovery.js','src/text-analytics/core/topic-sentiment.js','src/text-analytics/core/semantic-browser.js','src/text-analytics/core/csv-exporter.js','src/text-analytics/adapters/ku-open-da-adapter.js',
  'src/app.js','src/text-analytics-workflow.js'
];
for(const script of scripts)window.eval(fs.readFileSync(path.join(root,script),'utf8'));
window.document.dispatchEvent(new window.Event('DOMContentLoaded'));
const rows=[
  {review_id:'1',review_text:'good service helpful staff',sentiment_label:'positive'},
  {review_id:'2',review_text:'slow service long wait',sentiment_label:'negative'},
  {review_id:'3',review_text:'good response helpful service',sentiment_label:'positive'},
  {review_id:'4',review_text:'slow response long wait',sentiment_label:'negative'},
  {review_id:'5',review_text:'service response acceptable',sentiment_label:'neutral'},
  {review_id:'6',review_text:'acceptable staff response',sentiment_label:'neutral'}
];

(async()=>{
  window.KUDataLoader.loadObjectRows(rows,['review_id','review_text','sentiment_label'],{origin:'local',name:'browser fixture'});
  window.KUAppState.setDataset({loaded:true,revision:1,rowCount:6,columnCount:3,fields:[{name:'review_id',storage:'text',level:'Nominal'},{name:'review_text',storage:'text',level:'Nominal'},{name:'sentiment_label',storage:'text',level:'Nominal'}]});
  window.KUTextAnalyticsWorkflow.renderAll();
  await new Promise(resolve=>setTimeout(resolve,20));
  assert.strictEqual(window.KUAppState.getState().textAnalysis.selectedTextField,'review_text');
  assert.ok(window.document.getElementById('textAnalyticsProfile').textContent.includes('Terms'));
  window.document.getElementById('aiAnalyticsView').classList.remove('hidden');
  window.KUAppState.setStep('analyze');window.KUTextAnalyticsWorkflow.renderAll();
  await new Promise(resolve=>setTimeout(resolve,10));
  assert.ok(window.document.querySelector('[data-text-analytics-stage="analyze"]'));
  window.KUTextAnalyticsWorkflow.selectLabel({target:{value:'sentiment_label'}});
  await new Promise(resolve=>setTimeout(resolve,10));
  window.KUTextAnalyticsWorkflow.runSentiment();window.KUTextAnalyticsWorkflow.runTopics();
  const textState=window.KUAppState.getState().textAnalysis;
  assert.ok(textState.sentiment);assert.ok(textState.topics);assert.ok(textState.topicSentiment);
  window.KUAppState.setStep('profile');window.KUAppState.setStep('analyze');
  assert.strictEqual(window.KUAppState.getState().textAnalysis.selectedTextField,'review_text','navigation must preserve the selected field');
  assert.strictEqual(window.KUAppState.getState().textAnalysis.sentiment.labelField,'sentiment_label','navigation must preserve sentiment evidence');
  console.log('TEXT_ANALYTICS_BROWSER_SMOKE_OK (progressive UI + state persistence)');
})().catch(error=>{console.error(error);process.exit(1);});
