// KU Open DA — answer-first rendering for Explain relationships / drivers.
(function(root){
'use strict';
const safe=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
function renderDriverAnswer(){
  const state=root.KUAppState?.getState();
  if(state?.currentStep!=='results'||state.analysisPlan?.questionType!=='explain-drivers')return;
  const payload=state.result?.payload||{},r=payload.result,findings=Array.isArray(r?.findings)?r.findings.filter(x=>Number.isFinite(Number(x?.importance??x?.effect))):[];
  if(!findings.length)return;
  const top=findings.slice(0,5),target=state.analysisPlan.target||r.target||'the outcome',names=top.slice(0,3).map(x=>x.relationship).filter(Boolean),multiMethod=Array.isArray(payload.methods)&&payload.methods.length>0;
  const headline=document.querySelector('.result-answer h2');
  if(headline&&!multiMethod)headline.textContent=`The strongest predictive signals for ${target} were ${names.join(', ')}.`;
  const answer=document.querySelector('.result-answer');if(!answer||document.getElementById('predictiveDrivers'))return;
  const section=document.createElement('section');section.id='predictiveDrivers';section.className='card';section.style.marginTop='14px';
  section.innerHTML=`<div class="head">Predictive drivers${multiMethod?' · primary validated model':''}</div><div class="body"><div class="table"><table><thead><tr><th>Feature</th><th>Model importance</th></tr></thead><tbody>${top.map(x=>`<tr><td>${safe(x.relationship||'Feature')}</td><td>${Number(x.importance??x.effect).toFixed(4)}</td></tr>`).join('')}</tbody></table></div><div class="note" style="margin-top:10px">These are model-derived predictive importance signals from the fitted validated model. They do not establish causal effects.${multiMethod?' Other selected methods are reported separately in the combined Results sections.':''}</div></div>`;
  answer.insertAdjacentElement('afterend',section);
}
document.addEventListener('ku:render-current-analysis',renderDriverAnswer);
root.KURenderDriverAnswer=renderDriverAnswer;
})(window);
