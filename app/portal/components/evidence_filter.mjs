/** Read-only task filter for an already server-authorized evidence projection. */
export function filterEvidence(records, {query='', status='ALL'}={}) {
  if (!Array.isArray(records)) return {state:'UNKNOWN',records:[]};
  if (typeof query!=='string' || typeof status!=='string') return {state:'UNKNOWN',records:[]};
  const allowed = new Set(['ALL','READY','UNKNOWN','ERROR','EMPTY']);
  if (!allowed.has(status) || query.length>256) return {state:'UNKNOWN',records:[]};
  const needle=query.trim().toLocaleLowerCase();
  const valid=records.every(r=>r && typeof r==='object' && typeof r.id==='string' && typeof r.label==='string' && allowed.has(r.status) && r.status!=='ALL');
  if (!valid) return {state:'UNKNOWN',records:[]};
  // A repeated evidence ID with divergent content is ambiguous, never silently first-wins.
  const seen=new Map();
  for(const r of records){
    const prior=seen.get(r.id);
    if(prior && (prior.label!==r.label || prior.status!==r.status)) return {state:'UNKNOWN',records:[]};
    seen.set(r.id,r);
  }
  const emitted=new Set();
  const filtered=records.filter(r=>{
    if(emitted.has(r.id))return false;
    emitted.add(r.id);
    return (status==='ALL'||r.status===status) && (!needle||r.label.toLocaleLowerCase().includes(needle)||r.id.toLocaleLowerCase().includes(needle));
  });
  return {state:filtered.length?'READY':'EMPTY',records:filtered};
}
/** Native controls; no inline handlers or HTML injection (strict CSP compatible). */
export function mountEvidenceFilter(root,{records=[],onChange=()=>{}}={}){
  if(!root?.ownerDocument || typeof root.replaceChildren!=='function')throw new TypeError('DOM root required');
  const doc=root.ownerDocument;
  const form=doc.createElement('form');form.setAttribute('role','search');
  const label=doc.createElement('label');label.textContent='Rechercher une preuve';
  const input=doc.createElement('input');input.type='search';input.setAttribute('aria-label','Rechercher une preuve');input.setAttribute('maxlength','256');
  const status=doc.createElement('select');status.setAttribute('aria-label','Filtrer par état');
  for(const value of ['ALL','READY','UNKNOWN','ERROR','EMPTY']){
    const option=doc.createElement('option');option.value=value;option.textContent=value==='ALL'?'Tous les états':value;status.append(option);
  }
  const count=doc.createElement('output');count.setAttribute('role','status');count.setAttribute('aria-live','polite');
  // When filters hide every authorized record, offer an explicit keyboard action to recover.
  const reset=doc.createElement('button');reset.type='button';reset.textContent='Effacer les filtres';
  reset.addEventListener('click',()=>{input.value='';status.value='ALL';update();input.focus();});
  const list=doc.createElement('ul');list.setAttribute('aria-label','Preuves filtrées');
  function update(){
    const result=filterEvidence(records,{query:input.value,status:status.value||'ALL'});
    list.replaceChildren();
    for(const record of result.records){const li=doc.createElement('li');li.textContent=record.label+' — '+record.status;list.append(li);}
    reset.hidden=!(result.state==='EMPTY' && Array.isArray(records) && records.length>0);
    count.textContent=result.state==='UNKNOWN'?'Preuves non vérifiables':result.state==='EMPTY'?(Array.isArray(records)&&records.length===0?'Aucune preuve disponible':'Aucune preuve ne correspond aux filtres'):`${result.records.length} preuve(s) — ${result.state}`;
    onChange(result);
  }
  input.addEventListener('input',update);status.addEventListener('change',update);
  form.addEventListener('submit',event=>event.preventDefault());
  label.append(input);form.append(label,status,count,reset,list);root.replaceChildren(form);update();
  return {setRecords(next){records=next;update();},refresh:update};
}
