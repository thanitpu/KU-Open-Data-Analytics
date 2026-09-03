const assert=require('assert');
const path=require('path');
const root=path.resolve(__dirname,'..');
function load(relative){return require(path.join(root,relative));}

globalThis.KUTextFieldContract=load('src/text-analytics/contracts/text-field-contract.js');
globalThis.KUTextProfileContract=load('src/text-analytics/contracts/text-profile-contract.js');
globalThis.KUDerivedFeatureContract=load('src/text-analytics/contracts/derived-feature-contract.js');
globalThis.KUTextNormalizer=load('src/text-analytics/core/text-normalizer.js');
globalThis.KULanguageDetector=load('src/text-analytics/core/language-detector.js');
globalThis.KUTextTokenizer=load('src/text-analytics/core/tokenizer.js');
globalThis.KUTextFieldDetector=load('src/text-analytics/core/text-field-detector.js');
globalThis.KUTextProfiler=load('src/text-analytics/core/text-profiler.js');
globalThis.KUKeywordExtractor=load('src/text-analytics/core/keyword-extractor.js');
globalThis.KUPhraseExtractor=load('src/text-analytics/core/phrase-extractor.js');
globalThis.KUSentimentBaseline=load('src/text-analytics/core/sentiment-baseline.js');
globalThis.KUTopicDiscovery=load('src/text-analytics/core/topic-discovery.js');
globalThis.KUTopicSentiment=load('src/text-analytics/core/topic-sentiment.js');
globalThis.KUSemanticBrowser=load('src/text-analytics/core/semantic-browser.js');
globalThis.KUCSVExporter=load('src/text-analytics/core/csv-exporter.js');
globalThis.KUTextAnalyticsAdapter=load('src/text-analytics/adapters/ku-open-da-adapter.js');

const rows=[
  {review_id:'1',review_text:'good service helpful staff',sentiment_label:'positive'},
  {review_id:'2',review_text:'slow service long wait',sentiment_label:'negative'},
  {review_id:'3',review_text:'good response helpful service',sentiment_label:'positive'},
  {review_id:'4',review_text:'slow response long wait',sentiment_label:'negative'},
  {review_id:'5',review_text:'service response acceptable',sentiment_label:'neutral'},
  {review_id:'6',review_text:'acceptable staff response',sentiment_label:'neutral'}
];
const detected=KUTextFieldDetector.detect({fieldName:'review_text',values:rows.map(row=>row.review_text)});
assert.strictEqual(detected.semanticType,'text');KUTextFieldContract.validate(detected);
const profile=KUTextProfiler.profile({fieldName:'review_text',values:rows.map(row=>row.review_text)});KUTextProfileContract.validate(profile);assert.strictEqual(profile.documents.total,6);
assert.ok(KUKeywordExtractor.extract(rows.map(row=>row.review_text)).some(item=>item.term==='service'));
assert.ok(KUPhraseExtractor.count(rows.map(row=>row.review_text),{n:2,minCount:1}).length>0);
const contrast=KUPhraseExtractor.contrast(rows,{textField:'review_text',labelField:'sentiment_label'});assert.ok(contrast.positive.length>0);assert.ok(KUPhraseExtractor.representative(rows,'good',{textField:'review_text',labelField:'sentiment_label'}).length>0);
const model=KUSentimentBaseline.train(rows,{textField:'review_text',labelField:'sentiment_label'});assert.deepStrictEqual(model.labels,['negative','neutral','positive']);
const predicted=KUSentimentBaseline.predictRows(model,rows,{textField:'review_text'});assert.strictEqual(predicted.length,rows.length);
const topics=KUTopicDiscovery.discover(rows,{textField:'review_text',numTopics:2,minDocFreq:1});assert.strictEqual(topics.topics.length,2);
const matrix=KUTopicSentiment.analyze(topics,rows,{labelField:'sentiment_label'});assert.strictEqual(matrix.length,2);
const search=KUSemanticBrowser.semanticSearch(rows.map(row=>row.review_text),'slow wait',2);assert.strictEqual(search.engine.semantic,false);assert.strictEqual(search.results.length,2);
const similar=KUSemanticBrowser.similarDocuments(rows.map(row=>row.review_text),0,2);assert.strictEqual(similar.results.length,2);
const features=[...KUTextAnalyticsAdapter.sentimentDerivedFeatures({sourceField:'review_text',predictedLabels:predicted.map(row=>row.sentiment_predicted_label),scores:predicted.map(row=>row.sentiment_score)}),...KUTextAnalyticsAdapter.topicDerivedFeatures({sourceField:'review_text',topicResult:topics,rows})];
assert.strictEqual(KUTextAnalyticsAdapter.sentimentDerivedFeatures({sourceField:'review_text',rows:predicted})[0].values.length,rows.length,'P68 row-oriented adapter contract remains supported');
const enriched=KUTextAnalyticsAdapter.attachFeatures(rows,features);assert.strictEqual(enriched.length,rows.length);assert.ok(enriched[0].review_text_topic_label);
const curated=KUTextAnalyticsAdapter.topicDerivedFeatures({sourceField:'review_text',topicResult:topics,rows,curation:{0:{action:'merge',mergeInto:1},1:{action:'keep',label:'Retained topic'}}});assert.ok(curated[0].values.every(value=>value===1));
const csv=KUCSVExporter.toCSV(enriched);assert.ok(csv.includes('review_text_sentiment_label'));

load('src/state.js');
const state=globalThis.KUAppState;
state.setDataset({loaded:true,revision:1,rowCount:6,columnCount:3,fields:[{name:'review_id'},{name:'review_text'},{name:'sentiment_label'}]});
state.updateTextAnalysis({selectedTextField:'review_text',profile,topics});
state.setStep('profile');state.setStep('analyze');
assert.strictEqual(state.getState().textAnalysis.selectedTextField,'review_text','navigation must preserve text state');
state.setDataset({loaded:true,revision:2,rowCount:6,columnCount:3,fields:[{name:'review_id'},{name:'review_text'},{name:'sentiment_label'}]});
assert.strictEqual(state.getState().textAnalysis.selectedTextField,null,'dataset replacement must reset text state');
console.log('TEXT_ANALYTICS_SMOKE_OK (profile + sentiment + topics + retrieval + export + state)');
