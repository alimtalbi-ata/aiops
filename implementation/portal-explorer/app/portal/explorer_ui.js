'use strict';
const page=location.pathname.split('/').pop();
const $=id=>document.getElementById(id);
const status=(message,bad=false)=>{ $('status').textContent=message; $('status').className=bad?'status error':'status'; };
const clear=node=>node.replaceChildren();
const el=(tag,text,attrs={})=>{const x=document.createElement(tag);if(text!==null)x.textContent=String(text);for(const [k,v] of Object.entries(attrs))x.setAttribute(k,v);return x;};
const button=(text,fn)=>{const x=el('button',text);x.addEventListener('click',fn);return x;};
const field=(type,placeholder,value='')=>{const x=el('input');x.type=type;x.placeholder=placeholder;x.value=value;return x;};
const select=(values)=>{const s=el('select');values.forEach(([v,label])=>{const o=el('option',label);o.value=v;s.append(o)});return s;};
const api=async(path,options)=>{const r=await fetch('/api/explorer'+path,{cache:'no-store',...options});let body;try{body=await r.json()}catch{throw Error('Réponse non JSON : HTTP '+r.status)}if(!r.ok)throw Error(body.detail||('HTTP '+r.status));return body;};
const show=async(fn)=>{status('Chargement…');try{await fn();status('Données chargées · lecture seule')}catch(e){status(e.message,true)}};
function table(columns,rows){
  const box=$('results');clear(box);const scroll=el('div',null,{class:'scroll'});const t=el('table');
  const thead=el('thead'),tr=el('tr');columns.forEach(c=>tr.append(el('th',c)));thead.append(tr);t.append(thead);
  const body=el('tbody');rows.forEach(row=>{const r=el('tr');columns.forEach(c=>{const v=row[c];r.append(el('td',v===null?'NULL':typeof v==='object'?JSON.stringify(v):v??''))});body.append(r)});
  t.append(body);scroll.append(t);box.append(el('p',rows.length+' ligne(s)',{class:'muted'}),scroll);
}
function raw(data){const box=$('results');clear(box);box.append(el('pre',JSON.stringify(data,null,2)));}
function draw(series){
 const panel=$('chart-panel');panel.hidden=!series.length;if(!series.length)return;
 const canvas=$('chart'),ctx=canvas.getContext('2d');const w=canvas.width,h=canvas.height;
 ctx.clearRect(0,0,w,h);ctx.fillStyle='#102336';ctx.fillRect(0,0,w,h);
 const pts=series.flatMap(s=>s.values.map(([t,v])=>[Number(t),Number(v)]).filter(([t,v])=>Number.isFinite(t)&&Number.isFinite(v)));
 if(!pts.length){panel.hidden=true;return;}
 const xmin=Math.min(...pts.map(p=>p[0])),xmax=Math.max(...pts.map(p=>p[0]));
 let ymin=Math.min(...pts.map(p=>p[1])),ymax=Math.max(...pts.map(p=>p[1]));
 if(ymin===ymax){ymin-=1;ymax+=1;}
 const x=t=>48+(t-xmin)/Math.max(1,xmax-xmin)*(w-72),y=v=>h-38-(v-ymin)/(ymax-ymin)*(h-64);
 ctx.strokeStyle='#4b6880';ctx.beginPath();ctx.moveTo(48,12);ctx.lineTo(48,h-38);ctx.lineTo(w-18,h-38);ctx.stroke();
 ctx.fillStyle='#a6bacd';ctx.font='14px sans-serif';ctx.fillText(ymax.toPrecision(4),4,20);ctx.fillText(ymin.toPrecision(4),4,h-38);
 const colors=['#5dc6ed','#f8c565','#9fe28c','#ef91bc','#baadff','#ff9b77'];
 series.slice(0,6).forEach((s,i)=>{ctx.strokeStyle=colors[i];ctx.lineWidth=2;ctx.beginPath();let started=false;
 s.values.forEach(([t,v])=>{t=Number(t);v=Number(v);if(!Number.isFinite(t)||!Number.isFinite(v))return;
 if(!started){ctx.moveTo(x(t),y(v));started=true}else ctx.lineTo(x(t),y(v))});ctx.stroke();
 ctx.fillStyle=colors[i];ctx.fillText(JSON.stringify(s.metric||{}).slice(0,95),60,20+i*19);
 });
}
const titles={databases:'SQL Explorer',prometheus:'Prometheus Explorer',alerts:'Alertes et règles',cmdb:'Inventaire CMDB',logs:'Logs Loki',traces:'Traces Tempo',orchestration:'Temporal et n8n',core:'Core AIOps'};
$('heading').textContent=titles[page]||'Explorateur';
document.querySelectorAll('nav a').forEach(a=>{if(a.dataset.page===page)a.setAttribute('aria-current','page')});
const controls=$('controls');
async function databases(){
 $('intro').textContent='Bases configurées uniquement · comptes SQL en lecture seule · 200 lignes maximum.';
 const catalog=await api('/catalog');const options=catalog.databases.map(d=>[d.id,d.id+' ('+d.engine+')'+(d.configured?'':' — non configuré')]);
 const source=select(options),sql=el('textarea');sql.value='SELECT 1 AS valeur';
 const limit=select([[25,'25 lignes'],[100,'100 lignes'],[200,'200 lignes']]);
 const run=button('Exécuter SELECT',()=>show(async()=>{const data=await api('/databases/'+source.value+'/query',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sql:sql.value,limit:Number(limit.value)})});table(data.columns,data.rows);}));
 const browse=button('Lister les tables',()=>show(async()=>{const d=await api('/databases/'+source.value+'/tables');table(d.columns,d.rows)}));
 const schema=field('text','Schéma','public'),name=field('text','Table'),offset=field('number','Décalage','0');
 const inspect=button('Colonnes',()=>show(async()=>{const d=await api('/databases/'+source.value+'/columns?'+new URLSearchParams({schema:schema.value,table:name.value}));table(d.columns,d.rows)}));
 const preview=button('Afficher les lignes',()=>show(async()=>{const d=await api('/databases/'+source.value+'/preview?'+new URLSearchParams({schema:schema.value,table:name.value,limit:limit.value,offset:offset.value}));table(d.columns,d.rows)}));
 source.addEventListener('change',()=>{schema.value=source.value==='glpi'?'glpi':'public'});
 controls.append(el('label','Base : '),source,el('p','Requête SQL :'),sql,limit,run,browse,
 el('p','Exploration de table :'),schema,name,offset,inspect,preview);
 raw({connections:catalog.databases,notice:'Les connexions SQL doivent être configurées avec des rôles SELECT-only.'});
}
async function prometheus(){
 $('intro').textContent='PromQL instantané et temporel, visualisation et inventaire des cibles.';
 const query=field('text','PromQL','up'),mode=select([['range','Courbe temporelle'],['instant','Valeur instantanée']]);
 const minutes=select([[15,'15 minutes'],[60,'1 heure'],[360,'6 heures'],[1440,'24 heures']]);
 controls.append(query,mode,minutes,button('Interroger',()=>show(async()=>{
 let path='/observability/prometheus/query?'+new URLSearchParams({query:query.value});
 if(mode.value==='range'){const end=Math.floor(Date.now()/1000),start=end-Number(minutes.value)*60;
 path='/observability/prometheus/query_range?'+new URLSearchParams({query:query.value,start,end,step:Math.max(15,Math.ceil((end-start)/300))});}
 const data=await api(path);const results=data.data?.result||[];
 if(mode.value==='range'){draw(results);table(['metric','samples'],results.map(s=>({metric:JSON.stringify(s.metric),samples:s.values?.length||0})))}
 else{draw([]);table(['metric','value'],results.map(s=>({metric:JSON.stringify(s.metric),value:JSON.stringify(s.value)})));}
 })));
 await show(async()=>{const d=await api('/observability/prometheus/targets');const targets=d.data?.activeTargets||[];
 table(['job','health','lastError'],targets.map(t=>({job:t.labels?.job||'',health:t.health,lastError:t.lastError||''})));});
}
async function alerts(){
 $('intro').textContent='État courant des alertes, règles et seuils publiés par Prometheus.';
 controls.append(button('Actualiser',()=>show(load)));
 async function load(){const [a,r,t]=await Promise.all([
 api('/observability/prometheus/alerts'),api('/observability/prometheus/rules'),api('/observability/prometheus/targets')]);
 const rules=(r.data?.groups||[]).flatMap(g=>(g.rules||[]).map(x=>({group:g.name,name:x.name,state:x.state,health:x.health,query:x.query||'',duration:x.duration||0})));
 const targets=t.data?.activeTargets||[];const box=$('results');clear(box);
 box.append(el('div',null,{class:'cards'}));const cards=box.firstChild;
 [['Règles',rules.length],['Alertes actives',(a.data?.alerts||[]).length],['Targets UP',targets.filter(x=>x.health==='up').length],['Targets DOWN',targets.filter(x=>x.health!=='up').length]].forEach(([k,v])=>{const c=el('div',null,{class:'stat'});c.append(el('span',k),el('strong',v));cards.append(c)});
 const pre=el('pre',JSON.stringify({rules,alerts:a.data?.alerts||[],targets:targets.map(x=>({job:x.labels?.job,health:x.health,lastError:x.lastError}))},null,2));box.append(pre);
 }
 await show(load);
}
async function logs(){
 $('intro').textContent='Loki : requêtes LogQL temporelles. Le service doit être joignable depuis le portail.';
 const q=field('text','LogQL','{job=~".+"}'),min=select([[15,'15 minutes'],[60,'1 heure']]);
 controls.append(q,min,button('Rechercher',()=>show(async()=>{const end=Date.now()*1e6,start=end-Number(min.value)*60*1e9;
 const d=await api('/observability/loki/query_range?'+new URLSearchParams({query:q.value,start:Math.floor(start),end:Math.floor(end),limit:100}));
 const rows=(d.data?.result||[]).flatMap(s=>(s.values||[]).map(v=>({time:new Date(Number(v[0])/1e6).toISOString(),labels:JSON.stringify(s.stream),message:v[1]})));
 table(['time','labels','message'],rows)})));
 raw({status:'Prêt à interroger Loki si EXPLORER_LOKI_URL est configuré.'});
}
async function traces(){
 $('intro').textContent='Recherche temporelle et consultation par identifiant de traces Tempo, en lecture seule.';
 const minutes=select([[15,'15 minutes'],[60,'1 heure'],[360,'6 heures'],[1440,'24 heures']]);
 const id=field('text','Trace ID (16 ou 32 caractères hexadécimaux)');
 controls.append(el('p','Rechercher des traces :'),minutes,button('Rechercher dans Tempo',()=>show(async()=>{
 const data=await api('/tempo/search?'+new URLSearchParams({minutes:minutes.value,limit:20}));
 const rows=(data.traces||[]).map(t=>({traceID:t.traceID||t.traceId||'',rootServiceName:t.rootServiceName||'',rootTraceName:t.rootTraceName||'',startTimeUnixNano:t.startTimeUnixNano||'',durationMs:t.durationMs??''}));
 table(['traceID','rootServiceName','rootTraceName','startTimeUnixNano','durationMs'],rows);
 if(!rows.length)status('Aucune trace trouvée sur cette période.');
 })),el('p','Consulter une trace par identifiant :'),id,
 button('Afficher la trace',()=>show(async()=>raw(await api('/observability/tempo/trace/'+encodeURIComponent(id.value))))));
 raw({notice:'La recherche peut retourner zéro trace ; aucune trace n’est créée par cet explorateur.'});
}
async function core(){
 $('intro').textContent='Core AIOps : tableau de bord, incidents, exécutions et scénarios existants. Consultation uniquement.';
 const collection=select([['dashboard','Tableau de bord'],['incidents','Incidents'],['runs','Exécutions'],['scenarios','Scénarios']]);
 controls.append(collection,button('Consulter le Core',()=>show(async()=>{
 const data=await api('/core/'+collection.value+'?limit=100');
 if(collection.value==='dashboard'){table(['indicateur','valeur'],Object.entries(data).map(([indicateur,valeur])=>({indicateur,valeur})));return;}
 const rows=data.items||[];
 if(!rows.length){table(['résultat'],[]);status('Aucun résultat Core pour cette collection.');return;}
 const columns=Object.keys(rows[0]);table(columns,rows);
 if(data.truncated)status('Résultats limités à 100 lignes ; '+data.upstream_returned+' disponibles.');
 })));
 raw({notice:'Aucune commande d’exécution ou modification n’est exposée par cette page.'});
}
async function cmdb(){
 $('intro').textContent='Inventaire GLPI en lecture seule via une session Technician dédiée. Aucune modification des équipements ou tickets.';
 const kind=select([['Computer','Ordinateurs'],['NetworkEquipment','Équipements réseau'],['Monitor','Moniteurs'],['Printer','Imprimantes'],['Software','Logiciels']]);
 const offset=field('number','Décalage','0'),id=field('number','ID équipement');
 controls.append(kind,offset,button('Lister les équipements',()=>show(async()=>{
 const d=await api('/cmdb/inventory/'+kind.value+'?'+new URLSearchParams({offset:offset.value,limit:25}));
 const rows=d.items||[];
 table(['id','name','serial','otherserial','entities_id','states_id'],rows.map(x=>({id:x.id,name:x.name,serial:x.serial,otherserial:x.otherserial,entities_id:x.entities_id,states_id:x.states_id})));
 if(d.truncated_possible)status('Page de 25 éléments : renseigner le décalage pour continuer.');
 })),id,button('Fiche équipement',()=>show(async()=>{
 if(!/^\d+$/.test(id.value)||Number(id.value)<1)throw Error('Identifiant équipement invalide');
 const d=await api('/cmdb/inventory/'+kind.value+'/'+id.value);
 table(['champ','valeur'],Object.entries(d).map(([champ,valeur])=>({champ,valeur})));
 })));
 raw({notice:'Les droits Technician sont sélectionnés uniquement dans la session GLPI de consultation. Les tickets et permissions restent inchangés.'});
}
async function orchestration(){
 $('intro').textContent='Consultation des disponibilités Temporal et n8n. Aucun déclenchement de workflow.';
 controls.append(button('Vérifier les services',()=>show(async()=>{
 const services=['temporal','n8n'];const results=[];
 for(const service of services){try{const x=await api('/observability/'+service+'/health');results.push({service,state:'accessible',response:x})}
 catch(e){results.push({service,state:'indisponible',reason:e.message})}}
 raw(results)})));
 const namespace=field('text','Namespace Temporal','default');
 controls.append(el('p','Temporal : namespaces et workflows'),namespace,
 button('Lister les namespaces Temporal',()=>show(async()=>{
 const data=await api('/observability/temporal/namespaces');raw(data);
 })),
 button('Lister les workflows Temporal',()=>show(async()=>{
 const data=await api('/temporal/namespaces/'+encodeURIComponent(namespace.value)+'/workflows?pagesize=25');
 const items=data.executions||data.workflowExecutions||data.workflows||[];
 if(!Array.isArray(items)){raw(data);return;}
 const rows=items.map(x=>({
 workflowId:x.execution?.workflowId||x.workflowId||'',
 runId:x.execution?.runId||x.runId||'',
 status:x.status||'',
 workflowType:x.type?.name||x.type||'',
 taskQueue:x.taskQueue||'',
 startTime:x.startTime||'',
 closeTime:x.closeTime||'',
 duration:x.executionDuration||'',
 historyLength:x.historyLength??''
 }));
 table(['workflowId','runId','status','workflowType','taskQueue','startTime','closeTime','duration','historyLength'],rows);
 })));
 controls.append(button('Lister les workflows n8n',()=>show(async()=>{
 const data=await api('/observability/n8n/workflows?limit=50');
 const rows=(data.data||[]).map(w=>({id:w.id,name:w.name,active:w.active,updatedAt:w.updatedAt}));
 table(['id','name','active','updatedAt'],rows);
 })),button('Historique des exécutions n8n',()=>show(async()=>{
 const data=await api('/observability/n8n/executions?limit=50');
 const rows=(data.data||[]).map(x=>({id:x.id,workflowId:x.workflowId,status:x.status,startedAt:x.startedAt,stoppedAt:x.stoppedAt}));
 table(['id','workflowId','status','startedAt','stoppedAt'],rows);
 })));
 raw({notice:'Listes n8n disponibles uniquement avec EXPLORER_N8N_API_KEY côté serveur. Temporal : namespaces et workflows en lecture seule via Temporal UI.'});
}
({databases,prometheus,alerts,logs,traces,cmdb,orchestration,core}[page]||(()=>Promise.resolve()))().catch(e=>status(e.message,true));
