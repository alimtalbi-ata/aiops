/**
 * Read-only Portal transport diagnostic projection.
 * Status MUST originate from a trusted fetch adapter's Response.status, not
 * response JSON, exception messages, or browser-supplied actor/tenant claims.
 * No authorization is granted by this function. No payload is returned.
 */
const failed=()=>Object.freeze({state:'ERROR',error_code:'READ_FAILED',result:null});
const unknown=reason=>Object.freeze({state:'UNKNOWN',reason,result:null});
function ownData(input,key,fallback){
  const descriptor=Object.getOwnPropertyDescriptor(input,key);
  if (!descriptor) return fallback;
  if (!Object.hasOwn(descriptor,'value')) throw new TypeError('accessor rejected');
  return descriptor.value;
}
export function projectReadTransportFailure(input={}) {
  // Proxy traps can throw; never evaluate inherited values or accessors.
  try {
    if (input===null || typeof input!=='object' || Array.isArray(input)) return failed();
    const aborted=ownData(input,'aborted',false);
    const timedOut=ownData(input,'timedOut',false);
    const status=ownData(input,'status',null);
    if (aborted===true) return unknown('CANCELLED');
    if (timedOut===true) return unknown('TIMEOUT');
    if (!Number.isInteger(status) || status<100 || status>599) return failed();
    if (status===401) return unknown('AUTH_REQUIRED');
    if (status===403) return unknown('TENANT_ACL_NOT_QUALIFIED');
    if (status===404) return unknown('NOT_FOUND');
    if (status===429) return Object.freeze({state:'ERROR',error_code:'RATE_LIMITED',result:null});
    return failed();
  } catch {
    return failed();
  }
}
