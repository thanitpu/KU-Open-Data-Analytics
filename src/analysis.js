function validScaleVars(){
  return headers.filter(h=>meta[h]?.level==='Scale' && types[h]==='numeric');
}
function groupVars(){
  return headers.filter(h=>meta[h]?.level!=='Scale' || types[h]!=='numeric');
}
function setOptions(id,vars){
  const el=$(id); if(!el)return;
  el.innerHTML=vars.length?vars.map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join(''):'<option value="">No suitable variables</option>';
}
function refreshAnalysisSelectors(){
  if(!headers.length)return;
  const scales=validScaleVars(), groups=groupVars();
  setOptions('freqVar',headers);
  setOptions('anovaY',scales); setOptions('anovaGroup',groups);
  setOptions('corrX',scales); setOptions('corrY',scales);
  refreshTTestControls();
}
function rowsFor(h){ return data.map(r=>r[h]).filter(v=>v!=='' && v!=null); }
function numRowsFor(h){ return data.map(r=>Number(r[h])).filter(Number.isFinite); }
function sampleSD(a){if(a.length<2)return NaN;const m=mean(a);return Math.sqrt(a.reduce((s,x)=>s+(x-m)**2,0)/(a.length-1))}
function p2FromT(t,df){if(typeof jStat==='undefined')return NaN;return 2*(1-jStat.studentt.cdf(Math.abs(t),df))}
function pFromF(F,df1,df2){if(typeof jStat==='undefined')return NaN;return 1-jStat.centralF.cdf(F,df1,df2)}
function pFmt(p){return Number.isFinite(p)?(p<0.001?'&lt; .001':p.toFixed(3)):'—'}
function conclusion(p){
  if(!Number.isFinite(p))return 'p-value unavailable.';
  return p<0.05?'Statistically significant at α = .05.':'Not statistically significant at α = .05.';
}
function resultNote(text){return `<div class="advisor" style="margin-top:12px">${text}</div>`}

function runFrequency(){
  const h=$('freqVar').value;if(!h)return;
  const vals=data.map(r=>r[h]);
  const valid=vals.filter(v=>v!==''); const missing=vals.length-valid.length;
  const counts={}; valid.forEach(v=>counts[v]=(counts[v]||0)+1);
  const entries=Object.entries(counts).sort((a,b)=>b[1]-a[1]);
  let cum=0, out='<div class="table"><table><thead><tr><th>Value</th><th>Count</th><th>Percent</th><th>Cumulative %</th></tr></thead><tbody>';
  entries.forEach(([v,n])=>{cum+=n;out+=`<tr><td>${esc(v)}</td><td>${n}</td><td>${(100*n/valid.length).toFixed(1)}%</td><td>${(100*cum/valid.length).toFixed(1)}%</td></tr>`});
  out+='</tbody></table></div>';
  out+=resultNote(`<b>N valid = ${valid.length}</b>; missing = ${missing}; unique values = ${entries.length}.`);
  $('freqResult').innerHTML=out;
}

function refreshTTestControls(){
  const box=$('ttestControls'); if(!box||!headers.length)return;
  const type=$('ttestType')?.value||'one', scales=validScaleVars(), groups=groupVars();
  if(type==='one'){
    box.innerHTML=`<div class="row"><span class="note">Variable</span><select id="ttOneVar">${scales.map(v=>`<option>${esc(v)}</option>`).join('')}</select><span class="note">Test value</span><input id="ttMu" type="number" value="0" step="any"></div>`;
  }else if(type==='independent'){
    box.innerHTML=`<div class="row"><span class="note">Outcome</span><select id="ttIndY">${scales.map(v=>`<option>${esc(v)}</option>`).join('')}</select><span class="note">Group</span><select id="ttIndG">${groups.map(v=>`<option>${esc(v)}</option>`).join('')}</select></div><div class="note" style="margin-top:7px">The selected grouping variable must contain exactly two non-missing groups.</div>`;
  }else{
    box.innerHTML=`<div class="row"><span class="note">Variable 1</span><select id="ttPairA">${scales.map(v=>`<option>${esc(v)}</option>`).join('')}</select><span class="note">Variable 2</span><select id="ttPairB">${scales.map(v=>`<option>${esc(v)}</option>`).join('')}</select></div>`;
  }
}
function runTTest(){
  if(typeof jStat==='undefined'){$('ttestResult').innerHTML=resultNote('Statistical library could not be loaded.');return}
  const type=$('ttestType').value;
  if(type==='one'){
    const h=$('ttOneVar').value,mu=Number($('ttMu').value),a=numRowsFor(h);
    if(a.length<2)return $('ttestResult').innerHTML=resultNote('At least 2 valid observations are required.');
    const m=mean(a),sd=sampleSD(a),se=sd/Math.sqrt(a.length);
    if(!Number.isFinite(se) || se===0)return $('ttestResult').innerHTML=resultNote('The variable has zero or undefined variance, so a t-test cannot be computed.');
    const t=(m-mu)/se,df=a.length-1,p=p2FromT(t,df);
    $('ttestResult').innerHTML=`<div class="table"><table><tr><th>N</th><td>${a.length}</td><th>Mean</th><td>${f(m)}</td></tr><tr><th>SD</th><td>${f(sd)}</td><th>Test value</th><td>${f(mu)}</td></tr><tr><th>t</th><td>${f(t)}</td><th>df</th><td>${df}</td></tr><tr><th>p (two-sided)</th><td colspan="3">${pFmt(p)}</td></tr></table></div>`+resultNote(conclusion(p));
  }else if(type==='independent'){
    const y=$('ttIndY').value,g=$('ttIndG').value;
    const levels=[...new Set(data.map(r=>r[g]).filter(v=>v!==''))];
    if(levels.length!==2)return $('ttestResult').innerHTML=resultNote(`Grouping variable has ${levels.length} groups; exactly 2 are required.`);
    const a=data.filter(r=>r[g]===levels[0]).map(r=>Number(r[y])).filter(Number.isFinite);
    const b=data.filter(r=>r[g]===levels[1]).map(r=>Number(r[y])).filter(Number.isFinite);
    if(a.length<2||b.length<2)return $('ttestResult').innerHTML=resultNote('Each group needs at least 2 valid observations.');
    const m1=mean(a),m2=mean(b),s1=sampleSD(a),s2=sampleSD(b);
    const v1=s1*s1/a.length,v2=s2*s2/b.length,se=Math.sqrt(v1+v2);
    if(!Number.isFinite(se) || se===0)return $('ttestResult').innerHTML=resultNote('Both groups have zero or undefined variance, so Welch’s t-test cannot be computed.');
    const t=(m1-m2)/se;
    const denom=((v1*v1)/(a.length-1)+(v2*v2)/(b.length-1));
    if(!Number.isFinite(denom) || denom===0)return $('ttestResult').innerHTML=resultNote('Welch degrees of freedom cannot be computed for these data.');
    const df=(v1+v2)**2/denom,p=p2FromT(t,df);
    $('ttestResult').innerHTML=`<div class="table"><table><thead><tr><th>Group</th><th>N</th><th>Mean</th><th>SD</th></tr></thead><tbody><tr><td>${esc(levels[0])}</td><td>${a.length}</td><td>${f(m1)}</td><td>${f(s1)}</td></tr><tr><td>${esc(levels[1])}</td><td>${b.length}</td><td>${f(m2)}</td><td>${f(s2)}</td></tr></tbody></table></div><div class="table" style="margin-top:10px"><table><tr><th>Welch t</th><td>${f(t)}</td><th>df</th><td>${f(df)}</td><th>p</th><td>${pFmt(p)}</td></tr></table></div>`+resultNote(conclusion(p)+' Welch’s test does not assume equal variances.');
  }else{
    const A=$('ttPairA').value,B=$('ttPairB').value;
    const pairs=data.map(r=>[Number(r[A]),Number(r[B])]).filter(x=>Number.isFinite(x[0])&&Number.isFinite(x[1]));
    if(pairs.length<2)return $('ttestResult').innerHTML=resultNote('At least 2 complete pairs are required.');
    const d=pairs.map(x=>x[0]-x[1]),md=mean(d),sd=sampleSD(d),se=sd/Math.sqrt(d.length);
    if(!Number.isFinite(se) || se===0)return $('ttestResult').innerHTML=resultNote('Paired differences have zero or undefined variance, so a paired t-test cannot be computed.');
    const t=md/se,df=d.length-1,p=p2FromT(t,df);
    $('ttestResult').innerHTML=`<div class="table"><table><tr><th>Complete pairs</th><td>${d.length}</td><th>Mean difference</th><td>${f(md)}</td></tr><tr><th>SD difference</th><td>${f(sd)}</td><th>t</th><td>${f(t)}</td></tr><tr><th>df</th><td>${df}</td><th>p</th><td>${pFmt(p)}</td></tr></table></div>`+resultNote(conclusion(p));
  }
}

function runAnova(){
  if(typeof jStat==='undefined')return $('anovaResult').innerHTML=resultNote('Statistical library could not be loaded.');
  const y=$('anovaY').value,g=$('anovaGroup').value;
  const groups={};
  data.forEach(r=>{const gv=r[g],yv=Number(r[y]);if(gv!==''&&Number.isFinite(yv)){(groups[gv]??=[]).push(yv)}});
  const entries=Object.entries(groups).filter(([_,a])=>a.length>0),k=entries.length;
  if(k<2)return $('anovaResult').innerHTML=resultNote('At least 2 groups with valid observations are required.');
  const all=entries.flatMap(x=>x[1]),grand=mean(all),N=all.length;
  let ssb=0,ssw=0;
  entries.forEach(([_,a])=>{const m=mean(a);ssb+=a.length*(m-grand)**2;ssw+=a.reduce((s,x)=>s+(x-m)**2,0)});
  const dfb=k-1,dfw=N-k;
  if(dfw<=0)return $('anovaResult').innerHTML=resultNote('ANOVA requires residual degrees of freedom. Add more observations within groups.');
  const msb=ssb/dfb,msw=ssw/dfw;
  if(!Number.isFinite(msw) || msw===0)return $('anovaResult').innerHTML=resultNote('Within-group variance is zero or undefined, so the ANOVA F statistic cannot be computed.');
  const F=msb/msw,p=pFromF(F,dfb,dfw);
  let desc='<div class="table"><table><thead><tr><th>Group</th><th>N</th><th>Mean</th><th>SD</th></tr></thead><tbody>';
  entries.forEach(([name,a])=>desc+=`<tr><td>${esc(name)}</td><td>${a.length}</td><td>${f(mean(a))}</td><td>${f(sampleSD(a))}</td></tr>`);
  desc+='</tbody></table></div>';
  const eta=ssb/(ssb+ssw);
  const an=`<div class="table" style="margin-top:10px"><table><thead><tr><th>Source</th><th>SS</th><th>df</th><th>MS</th><th>F</th><th>p</th></tr></thead><tbody><tr><td>Between</td><td>${f(ssb)}</td><td>${dfb}</td><td>${f(msb)}</td><td>${f(F)}</td><td>${pFmt(p)}</td></tr><tr><td>Within</td><td>${f(ssw)}</td><td>${dfw}</td><td>${f(msw)}</td><td></td><td></td></tr></tbody></table></div>`;
  $('anovaResult').innerHTML=desc+an+resultNote(`${conclusion(p)} Effect size η² = ${f(eta)}. A significant omnibus ANOVA does not identify which groups differ; post-hoc tests will be added later.`);
}

function ranks(a){
  const indexed=a.map((v,i)=>[v,i]).sort((x,y)=>x[0]-y[0]),out=Array(a.length);
  for(let i=0;i<indexed.length;){
    let j=i;while(j+1<indexed.length&&indexed[j+1][0]===indexed[i][0])j++;
    const r=(i+j+2)/2;for(let k=i;k<=j;k++)out[indexed[k][1]]=r;i=j+1;
  }
  return out;
}
function pearson(a,b){
  const ma=mean(a),mb=mean(b);
  let num=0,da=0,db=0;
  for(let i=0;i<a.length;i++){const x=a[i]-ma,y=b[i]-mb;num+=x*y;da+=x*x;db+=y*y}
  return num/Math.sqrt(da*db);
}
function runCorrelation(){
  if(typeof jStat==='undefined')return $('corrResult').innerHTML=resultNote('Statistical library could not be loaded.');
  const x=$('corrX').value,y=$('corrY').value,type=$('corrType').value;
  if(x===y)return $('corrResult').innerHTML=resultNote('Choose two different variables.');
  const pairs=data.map(r=>[Number(r[x]),Number(r[y])]).filter(z=>Number.isFinite(z[0])&&Number.isFinite(z[1]));
  if(pairs.length<3)return $('corrResult').innerHTML=resultNote('At least 3 complete pairs are required.');
  let a=pairs.map(z=>z[0]),b=pairs.map(z=>z[1]);
  if(type==='spearman'){a=ranks(a);b=ranks(b)}
  const r=pearson(a,b);
  if(!Number.isFinite(r))return $('corrResult').innerHTML=resultNote('Correlation cannot be computed because at least one variable has zero variance.');
  const df=pairs.length-2;
  const denom=1-r*r;
  const t=denom<=0?(r>0?Infinity:-Infinity):r*Math.sqrt(df/denom);
  const p=denom<=0?0:p2FromT(t,df);
  const strength=Math.abs(r)<.1?'negligible':Math.abs(r)<.3?'weak':Math.abs(r)<.5?'moderate':Math.abs(r)<.7?'strong':'very strong';
  $('corrResult').innerHTML=`<div class="table"><table><tr><th>Method</th><td>${type==='pearson'?'Pearson':'Spearman'}</td><th>N</th><td>${pairs.length}</td></tr><tr><th>Coefficient</th><td>${f(r)}</td><th>p (two-sided)</th><td>${pFmt(p)}</td></tr></table></div>`+resultNote(`${conclusion(p)} The observed association is ${strength} and ${r>=0?'positive':'negative'}. Correlation does not by itself establish causation.`);
}
