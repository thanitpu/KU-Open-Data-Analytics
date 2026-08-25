/* KU Open Data Analytics — Advanced categorical analysis & linear regression */
(function(){
  const style=document.createElement('style');
  style.textContent='select[multiple]{padding:6px;min-height:115px}.model-equation{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;background:#f7f9f5;border:1px solid var(--line);border-radius:9px;padding:10px;overflow-x:auto}';
  document.head.appendChild(style);

  const compareLabel=[...document.querySelectorAll('aside .label')].find(x=>x.textContent.trim()==='COMPARE');
  const relLabel=[...document.querySelectorAll('aside .label')].find(x=>x.textContent.trim()==='RELATIONSHIPS');
  if(relLabel){
    const chi=document.createElement('div');chi.className='nav';chi.textContent='Chi-square';chi.onclick=()=>showAnalysisView('chisquare');relLabel.parentNode.insertBefore(chi,relLabel);
    const reg=document.createElement('div');reg.className='nav';reg.textContent='Linear Regression';reg.onclick=()=>showAnalysisView('regression');
    const learn=[...document.querySelectorAll('aside .label')].find(x=>x.textContent.trim()==='LEARN');
    relLabel.parentNode.insertBefore(reg,learn||null);
  }

  const analysisView=$('analysisView');
  if(analysisView){
    analysisView.insertAdjacentHTML('beforeend',`
<section id="chisquarePanel" class="analysis-panel hidden">
  <h1>Chi-square Test of Independence</h1>
  <p class="lead">Examine association between two categorical variables using a contingency table.</p>
  <section class="card"><div class="head">Variables</div><div class="body"><div class="row"><span class="note">Row variable</span><select id="chiRow"></select><span class="note">Column variable</span><select id="chiCol"></select><button class="btn primary" onclick="runChiSquare()">Run Chi-square</button></div></div></section>
  <section class="card"><div class="head">Results</div><div class="body" id="chiResult"><div class="empty">Select two categorical variables and run the test.</div></div></section>
</section>
<section id="regressionPanel" class="analysis-panel hidden">
  <h1>Linear Regression</h1>
  <p class="lead">Model a numeric Scale outcome using one or more numeric Scale predictors.</p>
  <section class="card"><div class="head">Model setup</div><div class="body"><div class="row"><span class="note">Outcome</span><select id="regY"></select><span class="note">Predictors</span><select id="regX" multiple size="5" style="min-width:220px"></select><button class="btn primary" onclick="runRegression()">Run Regression</button></div><div class="note" style="margin-top:8px">Use Ctrl/Cmd-click to select multiple predictors.</div></div></section>
  <section class="card"><div class="head">Model results</div><div class="body" id="regResult"><div class="empty">Choose an outcome and at least one predictor.</div></div></section>
  <section class="card"><div class="head">Residual diagnostics</div><div class="body"><canvas id="regResidualPlot" width="760" height="320"></canvas><div class="note" id="regResidualNote" style="margin-top:8px">Run regression to inspect residuals versus fitted values.</div><div style="height:12px"></div><canvas id="regQQ" width="760" height="300"></canvas><div class="note" id="regQQNote" style="margin-top:8px">Q–Q diagnostic of model residuals.</div></div></section>
</section>`);
  }

  const oldRefresh=window.refreshAnalysisSelectors;
  window.categoricalVars=function(){return headers.filter(h=>meta[h]?.level==='Nominal'||meta[h]?.level==='Ordinal')};
  window.refreshAnalysisSelectors=function(){
    if(typeof oldRefresh==='function')oldRefresh();
    if(!headers.length)return;
    const scales=validScaleVars(),cats=categoricalVars();
    setOptions('chiRow',cats);setOptions('chiCol',cats);setOptions('regY',scales);setOptions('regX',scales);
  };

  window.runChiSquare=function(){
    if(typeof jStat==='undefined')return $('chiResult').innerHTML=resultNote('Statistical library could not be loaded.');
    const rowVar=$('chiRow').value,colVar=$('chiCol').value;
    if(!rowVar||!colVar)return $('chiResult').innerHTML=resultNote('Choose two categorical variables.');
    if(rowVar===colVar)return $('chiResult').innerHTML=resultNote('Choose two different variables.');
    const complete=data.filter(r=>r[rowVar]!==''&&r[colVar]!=='');
    if(!complete.length)return $('chiResult').innerHTML=resultNote('No complete observations are available.');
    const rows=[...new Set(complete.map(r=>r[rowVar]))],cols=[...new Set(complete.map(r=>r[colVar]))];
    if(rows.length<2||cols.length<2)return $('chiResult').innerHTML=resultNote('Each variable must contain at least two categories among complete observations.');
    const observed=rows.map(()=>Array(cols.length).fill(0));
    complete.forEach(r=>observed[rows.indexOf(r[rowVar])][cols.indexOf(r[colVar])]++);
    const n=complete.length,rowTotals=observed.map(r=>r.reduce((a,b)=>a+b,0)),colTotals=cols.map((_,j)=>observed.reduce((s,r)=>s+r[j],0));
    const expected=observed.map((r,i)=>r.map((_,j)=>rowTotals[i]*colTotals[j]/n));
    let chi=0,small=0,minExp=Infinity;
    for(let i=0;i<rows.length;i++)for(let j=0;j<cols.length;j++){const e=expected[i][j],o=observed[i][j];minExp=Math.min(minExp,e);if(e<5)small++;if(e>0)chi+=(o-e)**2/e}
    const df=(rows.length-1)*(cols.length-1),p=1-jStat.chisquare.cdf(chi,df),denom=Math.min(rows.length-1,cols.length-1),v=Math.sqrt((chi/n)/denom),smallPct=100*small/(rows.length*cols.length);
    let table='<div class="subhead">Observed counts</div><div class="table"><table><thead><tr><th>'+esc(rowVar)+' / '+esc(colVar)+'</th>';cols.forEach(c=>table+='<th>'+esc(c)+'</th>');table+='<th>Total</th></tr></thead><tbody>';
    rows.forEach((r,i)=>{table+='<tr><th>'+esc(r)+'</th>';observed[i].forEach(x=>table+='<td>'+x+'</td>');table+='<td>'+rowTotals[i]+'</td></tr>'});table+='<tr><th>Total</th>';colTotals.forEach(x=>table+='<td>'+x+'</td>');table+='<td>'+n+'</td></tr></tbody></table></div>';
    let exp='<div class="subhead">Expected counts</div><div class="table"><table><thead><tr><th>'+esc(rowVar)+' / '+esc(colVar)+'</th>';cols.forEach(c=>exp+='<th>'+esc(c)+'</th>');exp+='</tr></thead><tbody>';rows.forEach((r,i)=>{exp+='<tr><th>'+esc(r)+'</th>';expected[i].forEach(x=>exp+='<td>'+f(x)+'</td>');exp+='</tr>'});exp+='</tbody></table></div>';
    const warn=smallPct>20||minExp<1?`<span class="status-warn">Assumption warning:</span> ${smallPct.toFixed(1)}% of expected cells are below 5; minimum expected count = ${f(minExp)}. Consider combining sparse categories or an exact method where appropriate.`:`<span class="status-ok">Expected-count diagnostic:</span> ${smallPct.toFixed(1)}% of cells are below 5; minimum expected count = ${f(minExp)}.`;
    $('chiResult').innerHTML=`<div class="analysis-summary"><div class="metric"><small>χ²</small><b>${f(chi)}</b></div><div class="metric"><small>df</small><b>${df}</b></div><div class="metric"><small>Cramér's V</small><b>${f(v)}</b></div></div><div class="table"><table><tr><th>N</th><td>${n}</td><th>p</th><td>${pFmt(p)}</td><th>Cramér's V</th><td>${f(v)}</td></tr></table></div>`+table+exp+resultNote(`${conclusion(p)} ${warn}`);
  };

  function transpose(A){return A[0].map((_,j)=>A.map(r=>r[j]))}
  function multiply(A,B){const out=Array.from({length:A.length},()=>Array(B[0].length).fill(0));for(let i=0;i<A.length;i++)for(let k=0;k<B.length;k++)for(let j=0;j<B[0].length;j++)out[i][j]+=A[i][k]*B[k][j];return out}
  function inverse(A){const n=A.length,M=A.map((r,i)=>[...r,...Array.from({length:n},(_,j)=>i===j?1:0)]);for(let i=0;i<n;i++){let pivot=i;for(let r=i+1;r<n;r++)if(Math.abs(M[r][i])>Math.abs(M[pivot][i]))pivot=r;if(Math.abs(M[pivot][i])<1e-12)return null;[M[i],M[pivot]]=[M[pivot],M[i]];const d=M[i][i];for(let j=0;j<2*n;j++)M[i][j]/=d;for(let r=0;r<n;r++)if(r!==i){const z=M[r][i];for(let j=0;j<2*n;j++)M[r][j]-=z*M[i][j]}}return M.map(r=>r.slice(n))}
  function selected(id){return [...$(id).selectedOptions].map(o=>o.value).filter(Boolean)}

  window.runRegression=function(){
    if(typeof jStat==='undefined')return $('regResult').innerHTML=resultNote('Statistical library could not be loaded.');
    const yVar=$('regY').value,xVars=selected('regX').filter(v=>v!==yVar);
    if(!yVar||!xVars.length)return $('regResult').innerHTML=resultNote('Choose one outcome and at least one predictor different from the outcome.');
    const complete=data.map(r=>({y:Number(r[yVar]),xs:xVars.map(v=>Number(r[v]))})).filter(z=>Number.isFinite(z.y)&&z.xs.every(Number.isFinite));
    const n=complete.length,k=xVars.length;if(n<=k+1)return $('regResult').innerHTML=resultNote(`At least ${k+2} complete observations are needed for a model with ${k} predictor(s).`);
    const yVals=complete.map(z=>z.y);if(sampleSD(yVals)===0)return $('regResult').innerHTML=resultNote('The outcome has zero variance, so linear regression cannot be estimated.');
    const X=complete.map(z=>[1,...z.xs]),Y=complete.map(z=>[z.y]),Xt=transpose(X),inv=inverse(multiply(Xt,X));
    if(!inv)return $('regResult').innerHTML=resultNote('The predictor matrix is singular. Remove redundant or perfectly collinear predictors.');
    const beta=multiply(multiply(inv,Xt),Y).map(r=>r[0]),fitted=X.map(row=>row.reduce((s,v,i)=>s+v*beta[i],0)),residuals=complete.map((z,i)=>z.y-fitted[i]);
    const yMean=mean(yVals),sse=residuals.reduce((s,e)=>s+e*e,0),sst=yVals.reduce((s,y)=>s+(y-yMean)**2,0),ssr=sst-sse,dfModel=k,dfResid=n-k-1,mse=sse/dfResid,rmse=Math.sqrt(mse),r2=1-sse/sst,adjR2=1-(1-r2)*(n-1)/dfResid,F=(ssr/dfModel)/mse,pF=1-jStat.centralF.cdf(F,dfModel,dfResid);
    const se=inv.map((r,i)=>Math.sqrt(Math.max(0,mse*r[i]))),tvals=beta.map((b,i)=>b/se[i]),pvals=tvals.map(t=>p2FromT(t,dfResid)),crit=tCritical95(dfResid),ci=beta.map((b,i)=>[b-crit*se[i],b+crit*se[i]]);
    let colWarning='';if(xVars.length>1){let maxR=0,pair='';for(let i=0;i<xVars.length;i++)for(let j=i+1;j<xVars.length;j++){const rr=pearson(complete.map(z=>z.xs[i]),complete.map(z=>z.xs[j]));if(Number.isFinite(rr)&&Math.abs(rr)>maxR){maxR=Math.abs(rr);pair=xVars[i]+' & '+xVars[j]}}if(maxR>=.995)colWarning=`<span class="status-warn">Near-collinearity warning:</span> ${esc(pair)} have |r| = ${f(maxR)}. Coefficients may be unstable.`;else if(maxR>=.9)colWarning=`<span class="status-warn">High predictor correlation:</span> ${esc(pair)} have |r| = ${f(maxR)}. Interpret individual coefficients cautiously.`}
    const names=['Intercept',...xVars];let coef='<div class="subhead">Coefficients</div><div class="table"><table><thead><tr><th>Term</th><th>B</th><th>SE</th><th>t</th><th>p</th><th>95% CI</th></tr></thead><tbody>';names.forEach((name,i)=>coef+=`<tr><td>${esc(name)}</td><td>${f(beta[i])}</td><td>${f(se[i])}</td><td>${f(tvals[i])}</td><td>${pFmt(pvals[i])}</td><td>${ciText(ci[i][0],ci[i][1])}</td></tr>`);coef+='</tbody></table></div>';
    let equation=`${yVar} = ${f(beta[0])}`;xVars.forEach((v,i)=>equation+=` ${beta[i+1]>=0?'+':'−'} ${f(Math.abs(beta[i+1]))}·${v}`);
    $('regResult').innerHTML=`<div class="analysis-summary"><div class="metric"><small>R²</small><b>${f(r2)}</b></div><div class="metric"><small>Adjusted R²</small><b>${f(adjR2)}</b></div><div class="metric"><small>RMSE</small><b>${f(rmse)}</b></div></div><div class="model-equation">${esc(equation)}</div><div class="table" style="margin-top:10px"><table><tr><th>N</th><td>${n}</td><th>F</th><td>${f(F)}</td><th>df</th><td>${dfModel}, ${dfResid}</td><th>p</th><td>${pFmt(pF)}</td></tr></table></div>`+coef+resultNote(`${conclusion(pF)} Coefficients describe conditional linear associations; they do not by themselves establish causality. ${colWarning}`);
    drawResidualPlot(fitted,residuals,'regResidualPlot');$('regResidualNote').textContent=`Residual mean = ${f(mean(residuals))}; residual SD = ${f(sampleSD(residuals))}. Inspect for curvature, unequal spread, and influential observations.`;drawQQ(residuals,'regQQ');$('regQQNote').textContent=normalitySummary(residuals);
  };

  window.drawResidualPlot=function(fitted,residuals,id){const c=$(id);if(!c)return;const ctx=c.getContext('2d');ctx.clearRect(0,0,c.width,c.height);const xmin=Math.min(...fitted),xmax=Math.max(...fitted),ymin=Math.min(...residuals),ymax=Math.max(...residuals),P={l:50,r:18,t:24,b:46},W=c.width-P.l-P.r,H=c.height-P.t-P.b,sx=v=>P.l+(v-xmin)/(xmax-xmin||1)*W,sy=v=>P.t+H-(v-ymin)/(ymax-ymin||1)*H;ctx.strokeStyle='#bcc7b3';ctx.strokeRect(P.l,P.t,W,H);ctx.strokeStyle='#879080';ctx.beginPath();ctx.moveTo(P.l,sy(0));ctx.lineTo(P.l+W,sy(0));ctx.stroke();ctx.fillStyle='#425d13';fitted.forEach((v,i)=>{ctx.beginPath();ctx.arc(sx(v),sy(residuals[i]),3.2,0,Math.PI*2);ctx.fill()});ctx.fillStyle='#364033';ctx.font='11px system-ui';ctx.textAlign='center';ctx.fillText('Fitted values',P.l+W/2,c.height-10);ctx.save();ctx.translate(12,P.t+H/2);ctx.rotate(-Math.PI/2);ctx.fillText('Residuals',0,0);ctx.restore()};
})();