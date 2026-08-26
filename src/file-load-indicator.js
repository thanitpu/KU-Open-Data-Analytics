// KU Open DA — visible loading feedback for file import / browser parsing.
(function(root){
'use strict';
let overlay=null,hideTimer=null,safetyTimer=null,active=false;
const formatBytes=bytes=>{const n=Number(bytes)||0;if(n>=1024**3)return`${(n/1024**3).toFixed(2)} GB`;if(n>=1024**2)return`${(n/1024**2).toFixed(1)} MB`;if(n>=1024)return`${(n/1024).toFixed(1)} KB`;return`${n} B`};
function ensure(){
  if(overlay)return overlay;
  const style=document.createElement('style');style.id='kuFileLoadIndicatorStyle';style.textContent=`
    body.ku-file-loading,body.ku-file-loading *{cursor:wait!important}
    .ku-file-load-overlay{position:fixed;inset:0;z-index:99999;background:rgba(22,38,31,.28);backdrop-filter:blur(2px);display:grid;place-items:center;padding:20px}
    .ku-file-load-overlay[hidden]{display:none}
    .ku-file-load-card{width:min(430px,calc(100vw - 40px));background:#fff;border:1px solid #d8e3dc;border-radius:16px;box-shadow:0 18px 50px rgba(16,38,29,.18);padding:20px 22px}
    .ku-file-load-card b{display:block;color:var(--ku-green,#2f5d50);font-size:15px;margin-bottom:6px}
    .ku-file-load-card span{display:block;color:var(--ku-muted,#66736c);font-size:12px;line-height:1.5}
    .ku-file-load-meta{margin-top:6px;font-size:11px!important;color:#7a857f!important;overflow-wrap:anywhere}
    .ku-file-load-track{height:6px;border-radius:999px;background:#e9efeb;overflow:hidden;margin:15px 0 12px}
    .ku-file-load-bar{height:100%;width:38%;border-radius:999px;background:var(--ku-green,#2f5d50);animation:kuFileLoadMove 1.15s ease-in-out infinite}
    .ku-file-load-note{font-size:10.5px!important;color:#7b847f!important}
    @keyframes kuFileLoadMove{0%{transform:translateX(-110%)}50%{transform:translateX(115%)}100%{transform:translateX(285%)}}
    @media(prefers-reduced-motion:reduce){.ku-file-load-bar{animation:none;width:100%;opacity:.65}}
  `;document.head.appendChild(style);
  overlay=document.createElement('div');overlay.className='ku-file-load-overlay';overlay.hidden=true;overlay.setAttribute('role','status');overlay.setAttribute('aria-live','polite');overlay.innerHTML='<div class="ku-file-load-card"><b>Loading dataset…</b><span id="kuFileLoadStage">Reading and preparing the file in your browser.</span><span class="ku-file-load-meta" id="kuFileLoadMeta"></span><div class="ku-file-load-track" aria-hidden="true"><div class="ku-file-load-bar"></div></div><span class="ku-file-load-note">Large files may take several seconds to parse, inspect, and profile. Please keep this tab open.</span></div>';document.body.appendChild(overlay);return overlay;
}
function show(file){
  ensure();active=true;clearTimeout(hideTimer);clearTimeout(safetyTimer);document.body.classList.add('ku-file-loading');overlay.hidden=false;
  const name=file?.name||'Dataset',size=file?.size?` · ${formatBytes(file.size)}`:'';document.getElementById('kuFileLoadMeta').textContent=`${name}${size}`;
  document.getElementById('kuFileLoadStage').textContent='Reading and preparing the file in your browser.';
  safetyTimer=setTimeout(()=>hide(),90000);
}
function setStage(text){if(!active)return;const node=document.getElementById('kuFileLoadStage');if(node)node.textContent=text}
function hide(){if(!active)return;active=false;clearTimeout(hideTimer);clearTimeout(safetyTimer);document.body.classList.remove('ku-file-loading');if(overlay)overlay.hidden=true}
function finishSoon(){if(!active)return;setStage('Dataset loaded. Finishing profile updates…');clearTimeout(hideTimer);hideTimer=setTimeout(()=>requestAnimationFrame(()=>requestAnimationFrame(hide)),180)}
function fileFromEvent(event){return event?.target?.files?.[0]||event?.dataTransfer?.files?.[0]||null}
function install(){
  ensure();const input=document.getElementById('file'),drop=document.getElementById('drop'),status=document.getElementById('status');
  input?.addEventListener('change',event=>{const file=fileFromEvent(event);if(file)show(file)},true);
  drop?.addEventListener('drop',event=>{const file=fileFromEvent(event);if(file)show(file)},true);
  if(status&&typeof MutationObserver!=='undefined')new MutationObserver(()=>{const text=status.textContent||'';if(active&&/rows\s*[×x]\s*\d+\s*variables loaded/i.test(text))finishSoon()}).observe(status,{childList:true,subtree:true,characterData:true});
  window.addEventListener('unhandledrejection',()=>{if(active)hide()});window.addEventListener('error',()=>{if(active)hide()});
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install);else install();
root.KUFileLoadIndicator={show,hide,setStage,finishSoon};
})(window);
