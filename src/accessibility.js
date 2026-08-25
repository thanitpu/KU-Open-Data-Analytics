// KU Open DA — accessibility semantics and user UI preferences.
(function(root){
'use strict';
const TEXT_SIZE_KEY='ku-open-da-text-size';
const TEXT_SIZES=['standard','comfortable','large'];
let stickyHeaderObserver=null;
function ensurePreferenceStyles(){
  if(document.querySelector('link[data-ku-ui-preferences]'))return;
  const link=document.createElement('link');link.rel='stylesheet';link.href='src/ui-preferences.css';link.dataset.kuUiPreferences='true';document.head.appendChild(link);
}
function syncStickyShellOffset(){
  const header=document.querySelector('header');if(!header)return;
  const height=Math.max(0,Math.ceil(header.getBoundingClientRect().height));
  document.documentElement.style.setProperty('--ku-product-header-height',`${height}px`);
}
function installStickyShellSync(){
  syncStickyShellOffset();
  const header=document.querySelector('header');
  if(header&&typeof ResizeObserver!=='undefined'){
    stickyHeaderObserver?.disconnect?.();stickyHeaderObserver=new ResizeObserver(()=>syncStickyShellOffset());stickyHeaderObserver.observe(header);
  }
  root.addEventListener?.('resize',()=>root.requestAnimationFrame?root.requestAnimationFrame(syncStickyShellOffset):syncStickyShellOffset(),{passive:true});
}
function normalizeTextSize(value){return TEXT_SIZES.includes(value)?value:'comfortable'}
function applyTextSize(value,{persist=true}={}){
  const size=normalizeTextSize(value);document.documentElement.dataset.kuTextSize=size;
  if(persist){try{localStorage.setItem(TEXT_SIZE_KEY,size)}catch(_){}}
  document.querySelectorAll('[data-ku-text-size]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.kuTextSize===size)));
  if(root.requestAnimationFrame)root.requestAnimationFrame(syncStickyShellOffset);else syncStickyShellOffset();
  return size;
}
function installTextSizeControl(){
  const actions=document.querySelector('header .actions');if(!actions||actions.querySelector('.text-size-control'))return;
  const control=document.createElement('div');control.className='text-size-control';control.setAttribute('role','group');control.setAttribute('aria-label','Text size');
  control.innerHTML='<span>Text size</span><button type="button" data-ku-text-size="standard" title="Standard text size">A</button><button type="button" data-ku-text-size="comfortable" title="Comfortable text size">A+</button><button type="button" data-ku-text-size="large" title="Large text size">A++</button>';
  actions.prepend(control);control.addEventListener('click',event=>{const button=event.target.closest?.('[data-ku-text-size]');if(button)applyTextSize(button.dataset.kuTextSize)});
  let saved='comfortable';try{saved=localStorage.getItem(TEXT_SIZE_KEY)||saved}catch(_){}
  applyTextSize(saved,{persist:false});
}
function syncProfileTabs(){
  const tabs=[...document.querySelectorAll('.profile-tab')];
  tabs.forEach((tab,index)=>{
    const name=tab.dataset.profileTab||String(index),pane=document.querySelector(`[data-profile-pane="${name}"]`),active=tab.classList.contains('active');
    const tabId=`profile-tab-${name}`,paneId=`profile-pane-${name}`;
    tab.id=tabId;tab.setAttribute('role','tab');tab.setAttribute('aria-selected',String(active));tab.tabIndex=active?0:-1;
    if(pane){pane.id=paneId;pane.setAttribute('role','tabpanel');pane.setAttribute('aria-labelledby',tabId);pane.hidden=!active;tab.setAttribute('aria-controls',paneId)}
  });
}
function syncDynamicRegions(){
  document.querySelectorAll('[data-current-analysis]').forEach(node=>{node.setAttribute('role','status');node.setAttribute('aria-live','polite');node.setAttribute('aria-atomic','true')});
  const status=document.getElementById('status');if(status){status.setAttribute('role','status');status.setAttribute('aria-live','polite')}
  const pending=document.getElementById('journeyPendingView');if(pending){pending.setAttribute('aria-label','Analysis workflow step');pending.setAttribute('aria-live','polite')}
}
function onTabKey(event){
  const tab=event.target.closest?.('.profile-tab');if(!tab||!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
  const tabs=[...document.querySelectorAll('.profile-tab')];if(!tabs.length)return;event.preventDefault();let index=tabs.indexOf(tab);
  if(event.key==='Home')index=0;else if(event.key==='End')index=tabs.length-1;else index=(index+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;
  const next=tabs[index],name=next.dataset.profileTab;if(typeof root.setProfileTab==='function')root.setProfileTab(name);else next.click();next.focus();setTimeout(syncProfileTabs,0);
}
function init(){ensurePreferenceStyles();installTextSizeControl();installStickyShellSync();syncProfileTabs();syncDynamicRegions();document.addEventListener('keydown',onTabKey);document.addEventListener('click',event=>{if(event.target.closest?.('.profile-tab'))setTimeout(syncProfileTabs,0)});document.addEventListener('ku:render-current-analysis',syncDynamicRegions);document.addEventListener('ku:statechange',()=>setTimeout(syncDynamicRegions,0))}
root.KUAccessibility=Object.freeze({syncProfileTabs,syncDynamicRegions,applyTextSize,syncStickyShellOffset});
ensurePreferenceStyles();
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})(window);
