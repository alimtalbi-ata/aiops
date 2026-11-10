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
export function createLatestReader(read,publish,{now=()=>Date.now(),timeoutMs=15000,maxAgeMs=180000}={}){
 if(!Number.isSafeInteger(timeoutMs)||timeoutMs<1||timeoutMs>120000)throw new RangeError('timeoutMs must be 1..120000');
 if(!Number.isSafeInteger(maxAgeMs)||maxAgeMs<1||maxAgeMs>86400000)throw new RangeError('maxAgeMs must be 1..86400000');
 if(typeof read!=='function'||typeof publish!=='function')throw new TypeError('read/publish required');
 const timeoutMarker=Symbol('operational-timeout');
 let generation=0,controller=null,active=false;
 return {
  async load(query){
   const id=++generation;
   active=true;
   if(controller)controller.abort();
   controller=new AbortController();
   const signal=controller.signal;
   publish({state:'LOADING'});
   let timer;
   try{
    const result=await Promise.race([
     Promise.resolve(read(query,{signal})),
     new Promise((_,reject)=>{timer=setTimeout(()=>reject(timeoutMarker),timeoutMs);})
    ]);
    if(id!==generation||signal.aborted)return;
    // A transport success is not an evidence success. The server must have
    // already enforced actor/tenant scope; this UI only refuses to display
    // an unqualified projection as READY. Never authorize in the browser.
    const scoped=result && typeof result==='object' &&
     Object.hasOwn(result,'scope_verified') && result.scope_verified===true &&
     Object.hasOwn(result,'authorization_source') && result.authorization_source==='server' &&
     Object.hasOwn(result,'records') && Object.hasOwn(result,'observed_at');
    const state=scoped ? deriveOperationalState({records:result.records,observedAt:result.observed_at,now:now(),maxAgeMs}) : 'UNKNOWN';
    active=false;
    publish({state,result:state==='READY'||state==='EMPTY'?result:null});
   }catch(error){
    if(id!==generation||signal.aborted)return;
    // Never publish raw transport errors: messages, URLs and headers may carry secrets.
    active=false;
    if(error===timeoutMarker){
     controller.abort();
     publish({state:'UNKNOWN',reason:'TIMEOUT',result:null});
    }else publish({state:'ERROR',error_code:'READ_FAILED',result:null});
   }finally{
    clearTimeout(timer);
   }
  },
  cancel(){
   generation++;if(controller)controller.abort();controller=null;
   // A cancelled in-flight read must terminate without stale data.
   if(active){active=false;publish({state:'UNKNOWN',result:null});}
  }
 };
}
