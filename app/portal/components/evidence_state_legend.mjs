/** Read-only legend for canonical evidence states; no operational data is inferred. */
const labels=Object.freeze({
  READY:'Disponible',
  EMPTY:'Vide',
  ERROR:'Erreur',
  UNKNOWN:'Non vérifiable'
});
const descriptions=Object.freeze({
  READY:'Une preuve a été fournie, sans présumer de sa fraîcheur.',
  EMPTY:'La source confirme une absence de preuve.',
  ERROR:'La consultation a échoué.',
  UNKNOWN:'La preuve ne peut pas être vérifiée.'
});
export function evidenceStateDescription(state){
  return Object.hasOwn(labels,state) ? {label:labels[state],description:descriptions[state]} :
    {label:labels.UNKNOWN,description:descriptions.UNKNOWN};
}
/** Static native details/summary is keyboard accessible without JavaScript event handlers. */
export function mountEvidenceStateLegend(root){
  if(!root?.ownerDocument || typeof root.replaceChildren!=='function') throw new TypeError('DOM root required');
  const doc=root.ownerDocument;
  // Preserve a user's expanded explanation when a read-only view is refreshed.
  const previous=root.firstElementChild;
  const isPriorLegend=previous?.tagName?.toLowerCase()==='details';
  const wasOpen=isPriorLegend && previous.open===true;
  // Remounting an active summary otherwise drops keyboard focus into the document.
  const restoreSummaryFocus=isPriorLegend && doc.activeElement===previous.firstElementChild;
  const details=doc.createElement('details');
  details.open=wasOpen;
  const summary=doc.createElement('summary');
  summary.textContent='Comprendre les états des preuves';
  const list=doc.createElement('dl');
  for(const state of ['READY','EMPTY','ERROR','UNKNOWN']){
    const term=doc.createElement('dt');term.textContent=labels[state];
    const definition=doc.createElement('dd');definition.textContent=descriptions[state];
    list.append(term,definition);
  }
  details.append(summary,list);
  root.replaceChildren(details);
  if(restoreSummaryFocus && typeof summary.focus==='function') summary.focus();
  return details;
}
