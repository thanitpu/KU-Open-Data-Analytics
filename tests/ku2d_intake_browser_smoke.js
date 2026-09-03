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
window.eval(fs.readFileSync(path.join(root,'src/ku2d-data-asset.js'),'utf8'));
window.eval(fs.readFileSync(path.join(root,'src/app.js'),'utf8'));
const fixture=name=>fs.readFileSync(path.join(root,'tests/fixtures/text-analytics',name),'utf8');

(async()=>{
  await window.handleKU2DFiles([
    {name:'approved.json',text:async()=>fixture('ku2d-approved-snapshot.json')},
    {name:'draft.json',text:async()=>fixture('ku2d-draft-snapshot.json')}
  ]);
  assert.strictEqual(window.document.getElementById('rows').textContent,'6');
  assert.ok(window.document.getElementById('status').textContent.includes('not production-approved'));
  const context=window.KUDataLoader.getContext();
  assert.strictEqual(context.origin,'ku2d');
  assert.strictEqual(context.assets.length,2);
  assert.strictEqual(context.approval.productionApproved,false);
  assert.notDeepStrictEqual(context.acquiredAt,context.effectiveAt);
  const loadedRows=window.KUDataLoader.getRows();
  assert.strictEqual(loadedRows[0].__ku2d_data_asset_id,'KU2D-ASSET-TEXT-001');
  const previous=JSON.stringify(loadedRows);
  const corrupt=JSON.parse(fixture('ku2d-approved-snapshot.json'));corrupt.record_count=99;
  await assert.rejects(()=>window.handleKU2DFiles([{name:'corrupt.json',text:async()=>JSON.stringify(corrupt)}]),/does not match/);
  assert.strictEqual(JSON.stringify(window.KUDataLoader.getRows()),previous,'invalid input must not replace the loaded dataset');
  console.log('KU2D_INTAKE_BROWSER_SMOKE_OK (multi-file UI intake + atomic rejection)');
})().catch(error=>{console.error(error);process.exit(1);});
