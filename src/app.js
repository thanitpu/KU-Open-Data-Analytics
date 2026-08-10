let data=[],headers=[],types={},meta={},workbook=null;
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));

function showView(view){
  $('workspaceView').classList.toggle('hidden',view!=='workspace');
  $('variablesView').classList.toggle('hidden',view!=='variables');
  $('analysisView').classList.add('hidden');
  document.querySelectorAll('.analysis-panel').forEach(p=>p.classList.add('hidden'));
  document.querySelectorAll('.nav').forEach(n=>n.classList.remove('active'));
  const navs=[...document.querySelectorAll('.nav')];
  (view==='workspace'?navs[0]:navs[1]).classList.add('active');
}
function showAnalysisView(name){
  if(!headers.length){alert('Import a dataset first.');return;}
  $('workspaceView').classList.add('hidden');
  $('variablesView').classList.add('hidden');
  $('analysisView').classList.remove('hidden');
  document.querySelectorAll('.analysis-panel').forEach(p=>p.classList.add('hidden'));
  $(name+'Panel').classList.remove('hidden');
  refreshAnalysisSelectors();
}

function detectDelimiter(text){
  const first=(text.split(/\r?\n/).find(x=>x.trim())||'');
  const counts=[
    [',',(first.match(/,/g)||[]).length],
    ['\t',(first.match(/\t/g)||[]).length],
    [';',(first.match(/;/g)||[]).length]
  ].sort((a,b)=>b[1]-a[1]);
  return counts[0][1]>0?counts[0][0]:',';
}

function parseDelimitedRows(text, delimiter){
  const rows=[]; let row=[], cell='', quoted=false;
  const src=text.replace(/^\uFEFF/,'');
  for(let i=0;i<src.length;i++){
    const ch=src[i];
    if(ch==='"'){
      if(quoted && src[i+1]==='"'){cell+='"';i++;}
      else quoted=!quoted;
    }else if(ch===delimiter && !quoted){
      row.push(cell.trim()); cell='';
    }else if((ch==='\n' || ch==='\r') && !quoted){
      if(ch==='\r' && src[i+1]==='\n') i++;
      row.push(cell.trim()); cell='';
      if(row.some(v=>v!=='')) rows.push(row);
      row=[];
    }else{
      cell+=ch;
    }
  }
  row.push(cell.trim());
  if(row.some(v=>v!=='')) rows.push(row);
  return rows;
}

function normalizeHeaders(raw){
  const used={};
  return raw.map((value,i)=>{
    const base=String(value??'').trim() || `Variable_${i+1}`;
    used[base]=(used[base]||0)+1;
    return used[base]===1?base:`${base}_${used[base]}`;
  });
}

function parseDelimited(text){
  const delimiter=detectDelimiter(text);
  const rows=parseDelimitedRows(text,delimiter);
  if(rows.length<2)throw Error('Please provide a header and at least one data row.');
  headers=normalizeHeaders(rows[0]);
  data=rows.slice(1).map(r=>{
    const o={};
    headers.forEach((h,i)=>o[h]=r[i]??'');
    return o;
  });
  inferMetadata();
  render();
}

function loadAOA(rows){
  rows=rows.filter(r=>Array.isArray(r) && r.some(v=>v!==null && v!==undefined && String(v).trim()!==''));
  if(rows.length<2)throw Error('Selected sheet needs a header row and at least one data row.');
  headers=normalizeHeaders(rows[0]);
  data=rows.slice(1).map(r=>{
    const o={};
    headers.forEach((h,i)=>o[h]=(r[i]===null||r[i]===undefined)?'':String(r[i]).trim());
    return o;
  });
  inferMetadata();
  render();
}

function inferMetadata(){
  types={}; meta={};
  headers.forEach(h=>{
    const vals=data.map(r=>r[h]).filter(v=>v!=='');
    const numericCount=vals.filter(v=>Number.isFinite(Number(v))).length;
    const storage=(vals.length && numericCount/vals.length>=.9)?'numeric':'text';
    types[h]=storage;
    const unique=[...new Set(vals)];
    let level='Nominal';
    if(storage==='numeric'){
      const mostlyInteger=vals.filter(v=>Number.isInteger(Number(v))).length/Math.max(1,vals.length)>=.95;
      level=(mostlyInteger && unique.length<=7)?'Ordinal':'Scale';
    } else {
      const orderWords=['low','medium','high','poor','fair','good','very good','excellent','strongly disagree','disagree','neutral','agree','strongly agree'];
      const normalized=unique.map(v=>String(v).toLowerCase());
      level=(normalized.length && normalized.every(v=>orderWords.includes(v)))?'Ordinal':'Nominal';
    }
    meta[h]={label:'',storage,level};
  });
}

function render(){
  const numeric=headers.filter(h=>types[h]==='numeric');
  const missing=data.reduce((n,r)=>n+headers.filter(h=>r[h]==='').length,0);
  $('rows').textContent=data.length;
  $('cols').textContent=headers.length;
  $('nums').textContent=numeric.length;
  $('miss').textContent=missing;
  $('status').textContent=`${data.length} rows × ${headers.length} variables loaded`;

  let h='<div class="table"><table><thead><tr>'+headers.map(x=>`<th>${esc(x)}<br><span class="pill">${esc(meta[x].level)}</span></th>`).join('')+'</tr></thead><tbody>';
  data.slice(0,50).forEach(r=>h+='<tr>'+headers.map(x=>`<td>${esc(r[x])}</td>`).join('')+'</tr>');
  $('preview').innerHTML=h+'</tbody></table></div>';

  renderVariables();
  refreshScaleVariableSelect();
  refreshAnalysisSelectors();
  advisor();
  analyze();
}

function renderVariables(){
  if(!headers.length){$('variableTable').innerHTML='<div class="empty">Import data first.</div>';return}
  let h=`<div class="table"><table><thead><tr>
    <th>Name</th><th>Label</th><th>Storage type</th><th>Measurement level</th><th>Unique values</th><th>Missing</th>
  </tr></thead><tbody>`;
  headers.forEach(name=>{
    const unique=new Set(data.map(r=>r[name]).filter(v=>v!=='')).size;
    const missing=data.filter(r=>r[name]==='').length;
    const idx=headers.indexOf(name);
    h+=`<tr>
      <td class="variable-name">${esc(name)}</td>
      <td><input type="text" value="${esc(meta[name].label)}" placeholder="Optional label" onchange="updateLabelByIndex(${idx},this.value)"></td>
      <td>${esc(meta[name].storage)}</td>
      <td>
        <select onchange="updateLevelByIndex(${idx},this.value)">
          ${['Nominal','Ordinal','Scale'].map(v=>`<option ${meta[name].level===v?'selected':''}>${v}</option>`).join('')}
        </select>
      </td>
      <td>${unique}</td><td>${missing}</td>
    </tr>`;
  });
  $('variableTable').innerHTML=h+'</tbody></table></div>';
}

function updateLabelByIndex(index,val){
  const name=headers[index];
  if(!name)return;
  meta[name].label=val;
}
function updateLevelByIndex(index,val){
  const name=headers[index];
  if(!name)return;
  meta[name].level=val;
  refreshScaleVariableSelect(); advisor(); analyze();
  renderPreviewHeadersOnly();
}
function renderPreviewHeadersOnly(){
  if(!headers.length)return;
  const table=$('preview').querySelector('table');
  if(!table)return;
  const ths=table.querySelectorAll('th');
  headers.forEach((h,i)=>ths[i].innerHTML=`${esc(h)}<br><span class="pill">${esc(meta[h].level)}</span>`);
}

function refreshScaleVariableSelect(){
  const scale=headers.filter(h=>meta[h]?.level==='Scale' && types[h]==='numeric');
  $('var').innerHTML=scale.length?scale.map(x=>`<option>${esc(x)}</option>`).join(''):'<option>No scale variables</option>';
}

function values(h){return data.map(r=>Number(r[h])).filter(Number.isFinite)}
function mean(a){return a.reduce((s,x)=>s+x,0)/a.length}
function q(a,p){let s=[...a].sort((x,y)=>x-y),i=(s.length-1)*p,b=Math.floor(i),r=i-b;return s[b+1]!==undefined?s[b]+r*(s[b+1]-s[b]):s[b]}
function f(x){return Number.isFinite(x)?x.toFixed(3):'—'}

function analyze(){
  const h=$('var').value;
  if(!data.length || !meta[h] || meta[h].level!=='Scale' || types[h]!=='numeric'){
    $('stats').innerHTML='<div class="empty">No scale variable available.</div>'; clearCanvas(); return;
  }
  const a=values(h),m=mean(a),sd=Math.sqrt(a.reduce((s,x)=>s+(x-m)**2,0)/Math.max(1,a.length-1));
  $('stats').innerHTML=`<div class="table"><table>
  <tr><th>N</th><td>${a.length}</td><th>Mean</th><td>${f(m)}</td></tr>
  <tr><th>Std. deviation</th><td>${f(sd)}</td><th>Median</th><td>${f(q(a,.5))}</td></tr>
  <tr><th>Minimum</th><td>${f(Math.min(...a))}</td><th>Maximum</th><td>${f(Math.max(...a))}</td></tr>
  <tr><th>Q1</th><td>${f(q(a,.25))}</td><th>Q3</th><td>${f(q(a,.75))}</td></tr>
  </table></div>`;
  hist(a,h);
}

function clearCanvas(){
  const c=$('hist'),x=c.getContext('2d');x.clearRect(0,0,c.width,c.height);
  x.fillStyle='#879080';x.textAlign='center';x.font='13px system-ui';x.fillText('Histogram will appear here',c.width/2,c.height/2);
}
function hist(a,label){
  let c=$('hist'),x=c.getContext('2d');x.clearRect(0,0,c.width,c.height);
  let mn=Math.min(...a),mx=Math.max(...a),k=Math.max(5,Math.min(14,Math.ceil(Math.sqrt(a.length)))),w=(mx-mn||1)/k,n=Array(k).fill(0);
  a.forEach(v=>n[Math.min(k-1,Math.floor((v-mn)/w))]++);
  let L=45,T=30,W=c.width-65,H=c.height-70,M=Math.max(...n,1);
  x.strokeStyle='#bcc7b3';x.beginPath();x.moveTo(L,T);x.lineTo(L,T+H);x.lineTo(L+W,T+H);x.stroke();
  n.forEach((v,i)=>{let bh=H*v/M;x.fillStyle='#6b8e23';x.fillRect(L+i*W/k+1,T+H-bh,W/k-2,bh)});
  x.fillStyle='#364033';x.textAlign='center';x.font='13px system-ui';x.fillText(label,c.width/2,18);x.font='11px system-ui';x.fillText(f(mn),L,T+H+20);x.fillText(f(mx),L+W,T+H+20)
}

function advisor(){
  if(!headers.length){$('advisor').textContent='Import data first. The advisor will inspect measurement levels and suggest suitable analyses.';return}
  const scale=headers.filter(h=>meta[h].level==='Scale').length;
  const validScale=headers.filter(h=>meta[h].level==='Scale' && types[h]==='numeric').length;
  const ordinal=headers.filter(h=>meta[h].level==='Ordinal').length;
  const nominal=headers.filter(h=>meta[h].level==='Nominal').length;
  let msg=`Measurement levels: <b>${scale} Scale</b>, <b>${ordinal} Ordinal</b>, <b>${nominal} Nominal</b>. `;
  if(scale>validScale) msg+=`<b>${scale-validScale}</b> Scale variable(s) are stored as text and cannot be used in numeric analyses until corrected. `;
  if(validScale>=2) msg+='You can explore correlation between numeric Scale variables. ';
  if(validScale>=1 && (nominal+ordinal)>=1) msg+='To compare a numeric Scale outcome across groups, t-test or ANOVA may be appropriate depending on the number of groups and assumptions. ';
  if(validScale===0) msg+='No numeric Scale variable is currently available for mean-based analyses.';
  $('advisor').innerHTML=msg;
}

function usePaste(){try{parseDelimited($('paste').value)}catch(e){alert(e.message)}}
function demo(){
  $('paste').value='Group,Score,Age,Satisfaction\nA,72,21,High\nA,81,22,High\nA,77,24,Medium\nB,88,20,High\nB,91,22,High\nB,79,25,Medium\nC,68,21,Low\nC,74,23,Medium\nC,77,26,High';
  usePaste();
}
function clearAll(){
  data=[];headers=[];types={};meta={};workbook=null;
  $('paste').value='';$('preview').innerHTML='<div class="empty">Import data to preview it here.</div>';
  $('variableTable').innerHTML='<div class="empty">Import data first.</div>';
  ['rows','cols','nums','miss'].forEach(id=>$(id).textContent='—');
  $('status').textContent='No dataset loaded';$('var').innerHTML='<option>No scale variables</option>';
  $('stats').innerHTML='<div class="empty">Select a scale variable.</div>';$('sheetRow').classList.add('hidden');clearCanvas();advisor();
}

async function handleFile(file){
  if(!file)return;
  const name=file.name.toLowerCase();
  if(name.endsWith('.xlsx')||name.endsWith('.xls')){
    if(typeof XLSX==='undefined'){alert('Excel reader library could not be loaded. Please check your internet connection.');return}
    const buf=await file.arrayBuffer();
    workbook=XLSX.read(buf,{type:'array'});
    $('sheetSelect').innerHTML=workbook.SheetNames.map(s=>`<option>${esc(s)}</option>`).join('');
    $('sheetRow').classList.toggle('hidden',workbook.SheetNames.length<=1);
    loadSelectedSheet();
  }else{
    const text=await file.text();
    parseDelimited(text);
    $('sheetRow').classList.add('hidden');
  }
}
function loadSelectedSheet(){
  if(!workbook)return;
  const name=$('sheetSelect').value || workbook.SheetNames[0];
  const rows=XLSX.utils.sheet_to_json(workbook.Sheets[name],{header:1,defval:''});
  loadAOA(rows);
  $('status').textContent += ` · sheet: ${name}`;
}

$('file').addEventListener('change',e=>handleFile(e.target.files[0]).catch(err=>alert(err.message)));
['dragover','drop'].forEach(ev=>$('drop').addEventListener(ev,e=>e.preventDefault()));
$('drop').addEventListener('drop',e=>handleFile(e.dataTransfer.files[0]).catch(err=>alert(err.message)));
clearCanvas();

window.addEventListener('load',()=>{
  const h=document.createElement('script');h.src='src/hotfix-v051.js';
  h.onload=()=>{const i=document.createElement('script');i.src='src/i18n.js';document.body.appendChild(i)};
  document.body.appendChild(h);
});