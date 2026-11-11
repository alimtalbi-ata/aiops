/**
 * Pure, failure-only settlement guard for trusted server-side read transport.
 * Generation counters MUST be issued by the server adapter, never parsed from
 * client payloads. This helper does not authenticate, authorize or return data.
 */
const diagnostic = reason => Object.freeze({state:'UNKNOWN',reason,result:null});
const failure = () => Object.freeze({state:'ERROR',error_code:'READ_FAILED',result:null});
function own(obj,key) {
  const d=Object.getOwnPropertyDescriptor(obj,key);
  if (!d || !Object.hasOwn(d,'value')) throw new TypeError('missing trusted field');
  return d.value;
}
export function projectReadSettlement(input) {
  try {
    if (input===null || typeof input!=='object' || Array.isArray(input)) return failure();
    const generation=own(input,'generation');
    const activeGeneration=own(input,'activeGeneration');
    const cancelled=own(input,'cancelled');
    const timedOut=own(input,'timedOut');
    if (!Number.isSafeInteger(generation) || generation<0 ||
        !Number.isSafeInteger(activeGeneration) || activeGeneration<0 ||
        typeof cancelled!=='boolean' || typeof timedOut!=='boolean') return failure();
    if (generation!==activeGeneration) return diagnostic('STALE_RESPONSE');
    if (cancelled) return diagnostic('CANCELLED');
    if (timedOut) return diagnostic('TIMEOUT');
    return diagnostic('NOT_QUALIFIED');
  } catch {
    return failure();
  }
}
