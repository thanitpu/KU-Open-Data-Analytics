// KU Open Data Analytics — FastAPI analytics client v0.6
// Set window.KU_ANALYTICS_API_BASE to the deployed API origin, e.g.
// window.KU_ANALYTICS_API_BASE = 'https://ku-open-data-analytics-api.onrender.com';

const KU_ANALYTICS_API_BASE = (window.KU_ANALYTICS_API_BASE || '').replace(/\/$/, '');

function analyticsRowsToCsv(){
  if(!Array.isArray(headers) || !Array.isArray(data) || !headers.length || !data.length){
    throw new Error('Import a dataset first.');
  }
  const quote = value => {
    const s = String(value ?? '');
    return /[",\n\r]/.test(s) ? `"${s.replace(/"/g,'""')}"` : s;
  };
  return [headers.map(quote).join(','), ...data.map(row => headers.map(h => quote(row[h])).join(','))].join('\n');
}

function refreshAIAnalyticsTargets(){
  const select = document.getElementById('aiTarget');
  if(!select) return;
  const current = select.value;
  select.innerHTML = '<option value="">No target</option>' + headers.map(h => `<option value="${esc(h)}">${esc(h)}</option>`).join('');
  if(headers.includes(current)) select.value = current;
}

function refreshAIAnalyticsControls(){
  const intent = document.getElementById('aiIntent')?.value || '';
  const targetWrap = document.getElementById('aiTargetWrap');
  const needsTarget = ['Regression','Binary Classification','Multiclass Classification'].includes(intent);
  if(targetWrap) targetWrap.classList.toggle('hidden', !needsTarget);
  refreshAIAnalyticsTargets();
}

function showAIAnalyticsView(){
  if(!headers.length){ alert('Import a dataset first.'); return; }
  document.getElementById('workspaceView').classList.add('hidden');
  document.getElementById('variablesView').classList.add('hidden');
  document.getElementById('analysisView').classList.add('hidden');
  document.getElementById('aiAnalyticsView').classList.remove('hidden');
  document.querySelectorAll('.nav').forEach(n => n.classList.remove('active'));
  refreshAIAnalyticsControls();
}

async function runAIAnalytics(){
  const intent = document.getElementById('aiIntent').value;
  const target = document.getElementById('aiTarget').value;
  const needsTarget = ['Regression','Binary Classification','Multiclass Classification'].includes(intent);
  const resultEl = document.getElementById('aiAnalyticsResult');
  const reportEl = document.getElementById('aiAnalyticsReport');
  if(needsTarget && !target){ alert('Please select a target variable.'); return; }
  if(!KU_ANALYTICS_API_BASE){
    resultEl.innerHTML = '<div class="advisor"><b>Analytics API is not configured yet.</b><br>Set <code>window.KU_ANALYTICS_API_BASE</code> to the deployed FastAPI origin.</div>';
    return;
  }
  resultEl.innerHTML = '<div class="empty">Running validated analytics engine…</div>';
  reportEl.textContent = '';
  try{
    const csv = analyticsRowsToCsv();
    const form = new FormData();
    form.append('file', new Blob([csv], {type:'text/csv'}), 'dataset.csv');
    form.append('intent', intent);
    form.append('mode', 'fast');
    if(needsTarget) form.append('target', target);
    const response = await fetch(`${KU_ANALYTICS_API_BASE}/analyze`, {method:'POST', body:form});
    let payload;
    try { payload = await response.json(); } catch (_) { payload = null; }
    if(!response.ok){
      const detail = payload?.detail || payload?.error || `HTTP ${response.status}`;
      throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
    }
    const r = payload?.result || {};
    const method = r.method || {};
    const evidence = r.evidence || {};
    const rows = [
      ['Route', r.route], ['Analysis type', r.analysis_type], ['Status', r.status], ['Readiness', r.readiness],
      ...Object.entries(method).map(([k,v]) => [k, v]),
      ...Object.entries(evidence).filter(([,v]) => ['string','number','boolean'].includes(typeof v)).map(([k,v]) => [k, typeof v === 'number' ? Number(v).toFixed(4) : v])
    ];
    resultEl.innerHTML = `<div class="table"><table><tbody>${rows.map(([k,v]) => `<tr><th>${esc(k)}</th><td>${esc(v ?? '—')}</td></tr>`).join('')}</tbody></table></div>`;
    reportEl.textContent = payload?.report?.text || 'No executive report returned.';
  }catch(err){
    resultEl.innerHTML = `<div class="advisor"><b>API request failed.</b><br>${esc(err.message)}<br><br>Check that the FastAPI backend is deployed and reachable.</div>`;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const intent = document.getElementById('aiIntent');
  if(intent) intent.addEventListener('change', refreshAIAnalyticsControls);
});
