const assert=require('assert');
const fs=require('fs');
const path=require('path');
const {JSDOM}=require('jsdom');

const root=path.resolve(__dirname,'..');
const appEntry=process.env.KU_APP_ENTRY||'app.html';
const html=fs.readFileSync(path.join(root,appEntry),'utf8')
  .replace(/<script[^>]+src="https:[^"]+"[^>]*><\/script>/g,'')
  .replace(/<script src="src\/[^"]+"><\/script>/g,'');
const dom=new JSDOM(html,{url:`http://localhost/${appEntry}`,runScripts:'outside-only',pretendToBeVisual:true});
const w=dom.window;
const alerts=[];
w.alert=msg=>alerts.push(String(msg));
w.HTMLCanvasElement.prototype.getContext=function(){return new Proxy({},{get:(t,p)=>p==='measureText'?(()=>({width:10})):(p==='canvas'?this:(()=>{})),set:()=>true})};
w.eval(fs.readFileSync(path.join(root,'src/app.js'),'utf8'));

(async()=>{
  assert.strictEqual(appEntry,'app.html','file-loader smoke must use canonical app.html');

  const csvFile={
    name:'customers.csv',
    text:async()=> 'Group,Score\nA,72\nB,88'
  };
  await w.handleFile(csvFile);
  assert.strictEqual(w.document.getElementById('rows').textContent,'2','CSV loader should render two rows');
  assert.strictEqual(w.document.getElementById('cols').textContent,'2','CSV loader should render two fields');
  assert.ok(w.document.getElementById('preview').textContent.includes('88'),'CSV preview should include parsed values');

  w.clearAll();
  w.XLSX={
    read:buf=>{
      assert.ok(buf instanceof ArrayBuffer,'XLSX loader should pass an ArrayBuffer to XLSX.read');
      return {SheetNames:['Data'],Sheets:{Data:{}}};
    },
    utils:{sheet_to_json:(sheet,opts)=>{
      assert.ok(sheet,'selected workbook sheet should be passed to sheet_to_json');
      assert.deepStrictEqual(opts,{header:1,defval:''});
      return [['Group','Score'],['A',91],['B',84],['C',77]];
    }}
  };
  const xlsxFile={
    name:'customers.xlsx',
    arrayBuffer:async()=>new ArrayBuffer(8)
  };
  await w.handleFile(xlsxFile);
  assert.strictEqual(w.document.getElementById('rows').textContent,'3','XLSX loader should render three data rows');
  assert.strictEqual(w.document.getElementById('cols').textContent,'2','XLSX loader should render two fields');
  assert.ok(w.document.getElementById('status').textContent.includes('sheet: Data'),'XLSX loader should report the selected sheet');
  assert.ok(w.document.getElementById('preview').textContent.includes('91'),'XLSX preview should include sheet values');
  assert.deepStrictEqual(alerts,[],'CSV/XLSX loader smoke should not raise alerts');

  console.log(`FRONTEND_FILE_LOADER_SMOKE_OK (${appEntry}; CSV + XLSX)`);
})().catch(err=>{console.error(err);process.exit(1)});
