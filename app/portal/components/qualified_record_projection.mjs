/** Optional read-only field projection for qualified Portal records.
 * This is defense-in-depth, NOT actor/tenant authorization. The server must
 * derive identity, tenant scope and record permissions before this boundary.
 */
export function projectQualifiedRecords(envelope, allowedFields) {
 const unknown={state:'UNKNOWN',result:null};
 try {
  // Read array lengths as own data descriptors: Proxy get traps must never run.
  const safeLength=array=>{
   if(!Array.isArray(array))return null;
   const descriptor=Object.getOwnPropertyDescriptor(array,'length');
   const length=descriptor&&Object.hasOwn(descriptor,'value')?descriptor.value:null;
   return Number.isSafeInteger(length)&&length>=0&&length<=10000?length:null;
  };
  const fieldCount=safeLength(allowedFields);
  if(fieldCount===null||fieldCount===0)return unknown;
  const fields=[];
  for(let i=0;i<fieldCount;i++){
   const descriptor=Object.getOwnPropertyDescriptor(allowedFields,String(i));
   if(!descriptor||!Object.hasOwn(descriptor,'value'))return unknown;
   const key=descriptor.value;
   if(typeof key!=='string'||!/^[a-zA-Z][a-zA-Z0-9_]*$/.test(key))return unknown;
   fields.push(key);
  }
  if(new Set(fields).size!==fields.length)return unknown;
  if(envelope===null||typeof envelope!=='object')return unknown;
  const own=(obj,key)=>{
   const d=Object.getOwnPropertyDescriptor(obj,key);
   return d&&Object.hasOwn(d,'value')?d.value:undefined;
  };
  if(own(envelope,'scope_verified')!==true||own(envelope,'authorization_source')!=='server')return unknown;
  const records=own(envelope,'records'),observedAt=own(envelope,'observed_at');
  const recordCount=safeLength(records);
  // Bound string payload size as well as cell count; no oversized UI projection.
  if(typeof observedAt==='string'&&observedAt.length>64)return unknown;
  let stringUnits=0;
  if(recordCount===null||typeof observedAt!=='string')return unknown;
  // Bound total projection work, not only each input dimension. Fail closed before reading records.
  if(recordCount>Math.floor(100000/fieldCount))return unknown;
  const projected=[];
  for(let i=0;i<recordCount;i++){
   const entry=Object.getOwnPropertyDescriptor(records,String(i));
   if(!entry||!Object.hasOwn(entry,'value'))return unknown;
   const record=entry.value;
   if(record===null||typeof record!=='object'||Array.isArray(record))return unknown;
   const safe=Object.create(null);
   for(const key of fields){
    const descriptor=Object.getOwnPropertyDescriptor(record,key);
    if(!descriptor||!Object.hasOwn(descriptor,'value'))return unknown;
    const value=descriptor.value;
    if(value!==null&&typeof value!=='string'&&typeof value!=='boolean'&&
       !(typeof value==='number'&&Number.isFinite(value)))return unknown;
    if(typeof value==='string'){
     if(value.length>4096)return unknown;
     stringUnits+=value.length;
     if(stringUnits>1000000)return unknown;
    }
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
