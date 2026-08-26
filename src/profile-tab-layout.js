// KU Open DA — keep Data Profile tabs anchored to the same viewport position.
(function(){
'use strict';
function alignProfileTop(){
  const view=document.getElementById('variablesView');
  if(!view||view.classList.contains('hidden'))return;
  const header=document.querySelector('body > header');
  const top=view.getBoundingClientRect().top+window.scrollY-(header?.offsetHeight||0)-8;
  window.scrollTo({top:Math.max(0,top),behavior:'auto'});
}
document.addEventListener('click',event=>{
  if(!event.target.closest?.('.profile-tab'))return;
  requestAnimationFrame(()=>requestAnimationFrame(alignProfileTop));
});
window.KUAlignProfileTop=alignProfileTop;
})();
