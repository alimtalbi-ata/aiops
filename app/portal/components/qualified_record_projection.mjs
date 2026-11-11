/** Optional read-only field projection for qualified Portal records.
 * This is defense-in-depth, NOT actor/tenant authorization. The server must
 * derive identity, tenant scope and record permissions before this boundary.
 */
export function projectQualifiedRecords(envelope, allowedFields) {
 const unknown={state:'UNKNOWN',result:null};
 if(!Array.isArray(allowedFields)||allowedFields.length===0||
    allowedFields.some(k=>typeof k!=='string'||!/^[a-zA-Z][a-zA-Z0-9_]*$/.test(k))||
    new Set(allowedFields).size!==allowedFields.length)return unknown;
 try {
  if(envelope===null||typeof envelope!=='object')return unknown;
  const own=(obj,key)=>{
   const d=Object.getOwnPropertyDescriptor(obj,key);
   return d&&Object.hasOwn(d,'value')?d.value:undefined;
  };
  if(own(envelope,'scope_verified')!==true||own(envelope,'authorization_source')!=='server')return unknown;
  const records=own(envelope,'records'),observedAt=own(envelope,'observed_at');
  if(!Array.isArray(records)||typeof observedAt!=='string')return unknown;
  const projected=[];
  for(const record of records){
   if(record===null||typeof record!=='object'||Array.isArray(record))return unknown;
   const safe=Object.create(null);
   for(const key of allowedFields){
    const descriptor=Object.getOwnPropertyDescriptor(record,key);
    if(!descriptor||!Object.hasOwn(descriptor,'value'))return unknown;
    const value=descriptor.value;
    if(value!==null&&typeof value!=='string'&&typeof value!=='boolean'&&
       !(typeof value==='number'&&Number.isFinite(value)))return unknown;
    safe[key]=value;
   }
   projected.push(safe);
  }
  // Freshness is deliberately NOT asserted here: createLatestReader validates
  // observed_at against now/maxAgeMs before READY or EMPTY may be displayed.
  return {state:'UNVERIFIED_FRESHNESS',result:{
   records:projected,observed_at:observedAt,scope_verified:true,authorization_source:'server'
  }};
 }catch{return unknown;} // Proxy traps and hostile descriptors fail closed.
}
