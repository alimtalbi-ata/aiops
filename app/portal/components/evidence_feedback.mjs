/** Read-only, CSP-safe feedback for an authorized evidence request. No operational data. */
const messages=Object.freeze({
  LOADING:'Chargement des preuves…',
  EMPTY:'Aucune preuve disponible.',
  ERROR:'Impossible de consulter les preuves.',
  UNKNOWN:'État des preuves non vérifiable.'
});
export function evidenceFeedback(state){
  return Object.hasOwn(messages,state) ? {state,message:messages[state]} :
    {state:'UNKNOWN',message:messages.UNKNOWN};
}
/** Avoid duplicate live-region announcements when polling repeats the same state. */
const mountedFeedback=new WeakMap();
/** Mount a single accessible feedback message, replacing stale announcements. */
export function mountEvidenceFeedback(root,state){
  if(!root?.ownerDocument || typeof root.replaceChildren!=='function')
    throw new TypeError('DOM root required');
  const feedback=evidenceFeedback(state);
  const previous=mountedFeedback.get(root);
  const busy=feedback.state==='LOADING'?'true':'false';
  // External renderers can alter the region while preserving its first child.
  // Reuse only intact announcements; an external mutation must not mislead assistive technology.
  if(previous?.state===feedback.state && root.childNodes?.length===1 &&
     root.firstChild===previous.node &&
     previous.node.textContent===feedback.message &&
     // Nested markup can change the accessible tree without changing textContent.
     previous.node.childNodes?.length===0 &&
     previous.node.getAttribute('role')===(feedback.state==='ERROR'?'alert':'status') &&
     previous.node.getAttribute('aria-live')===(feedback.state==='ERROR'?'assertive':'polite') &&
     previous.node.getAttribute('aria-atomic')==='true' &&
     previous.node.getAttribute('aria-busy')===(feedback.state==='LOADING'?'true':null)){
    if(root.getAttribute('aria-busy')!==busy) root.setAttribute('aria-busy',busy);
    return previous.node;
  }
  const node=root.ownerDocument.createElement('p');
  node.textContent=feedback.message;
  node.setAttribute('role',feedback.state==='ERROR'?'alert':'status');
  node.setAttribute('aria-live',feedback.state==='ERROR'?'assertive':'polite');
  node.setAttribute('aria-atomic','true');
  if(feedback.state==='LOADING') node.setAttribute('aria-busy','true');
  // Keep the stable region's busy state in sync across node replacement.
  // Explicit false avoids a stale loading flag after ERROR/EMPTY/UNKNOWN.
  root.setAttribute('aria-busy',busy);
  root.replaceChildren(node);
  mountedFeedback.set(root,{state:feedback.state,node});
  return node;
}
