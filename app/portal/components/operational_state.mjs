/** Read-only operator status, no network or action authority. */
export const STATES = Object.freeze(['LOADING','READY','EMPTY','ERROR','UNKNOWN']);
const COPY = Object.freeze({
 LOADING:['Chargement en cours','Récupération des observations…'],
 READY:['Observations disponibles','Consultez les éléments vérifiés ci-dessous.'],
 EMPTY:['Aucune observation','Aucune donnée pour les filtres sélectionnés.'],
 ERROR:['Chargement impossible','Réessayez ou consultez la source de diagnostic.'],
 UNKNOWN:['État non vérifié','Les preuves sont absentes, périmées ou incomplètes.']
});
export function deriveOperationalState({loading=false,error=null,records=null,observedAt=null,now=Date.now(),maxAgeMs=180000}={}) {
 if(loading)return 'LOADING';
 if(error)return 'ERROR';
 if(!Array.isArray(records)||typeof observedAt!=='string'||!observedAt.trim())return 'UNKNOWN';
 const time=Date.parse(observedAt);
 if(!Number.isFinite(time)||!Number.isFinite(now)||!Number.isFinite(maxAgeMs)||maxAgeMs<=0||time>now||now-time>maxAgeMs)return 'UNKNOWN';
 return records.length?'READY':'EMPTY';
}
export function renderOperationalState(root,state,{details='',retry=null}={}) {
 if(!root||typeof root.replaceChildren!=='function'||!root.ownerDocument)throw new TypeError('DOM root required');
 const safe=STATES.includes(state)?state:'UNKNOWN',doc=root.ownerDocument;
 const section=doc.createElement('section');
 section.setAttribute('data-operational-state',safe);
 section.setAttribute('aria-busy',safe==='LOADING'?'true':'false');
 section.setAttribute('role',safe==='ERROR'?'alert':'status');
 section.setAttribute('aria-live',safe==='ERROR'?'assertive':'polite');
 const heading=doc.createElement('h3');heading.textContent=COPY[safe][0];
 const message=doc.createElement('p');message.textContent=COPY[safe][1]+(details?' '+String(details):'');
 section.append(heading,message);
 if(safe==='ERROR'&&typeof retry==='function'){
  const button=doc.createElement('button');button.type='button';button.textContent='Réessayer';
  button.addEventListener('click',retry);section.append(button);
 }
 root.replaceChildren(section);return section;
}
/** Latest-only reader: also fences sources that ignore AbortSignal. */
export function createLatestReader(read,publish){
 if(typeof read!=='function'||typeof publish!=='function')throw new TypeError('read/publish required');
 let generation=0,controller=null;
 return {
  async load(query){
   const id=++generation;
   if(controller)controller.abort();
   controller=new AbortController();
   const signal=controller.signal;
   publish({state:'LOADING'});
   try{
    const result=await read(query,{signal});
    if(id!==generation||signal.aborted)return;
    publish({state:'READY',result});
   }catch(error){
    if(id!==generation||signal.aborted)return;
    publish({state:'ERROR',error});
   }
  },
  cancel(){generation++;if(controller)controller.abort();controller=null;}
 };
}
