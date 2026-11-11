/**
 * Read-only Portal transport diagnostic projection.
 * Input status MUST be supplied by the trusted fetch adapter from Response.status,
 * never from an exception, response JSON, query string, or browser actor claims.
 * No tenant/actor authorization is granted by this function.
 */
export function projectReadTransportFailure({status=null, aborted=false, timedOut=false}={}) {
  if (aborted === true) return Object.freeze({state:'UNKNOWN',reason:'CANCELLED',result:null});
  if (timedOut === true) return Object.freeze({state:'UNKNOWN',reason:'TIMEOUT',result:null});
  if (!Number.isInteger(status) || status < 100 || status > 599)
    return Object.freeze({state:'ERROR',error_code:'READ_FAILED',result:null});
  if (status === 401) return Object.freeze({state:'UNKNOWN',reason:'AUTH_REQUIRED',result:null});
  if (status === 403) return Object.freeze({state:'UNKNOWN',reason:'TENANT_ACL_NOT_QUALIFIED',result:null});
  if (status === 404) return Object.freeze({state:'UNKNOWN',reason:'NOT_FOUND',result:null});
  if (status === 429) return Object.freeze({state:'ERROR',error_code:'RATE_LIMITED',result:null});
  return Object.freeze({state:'ERROR',error_code:'READ_FAILED',result:null});
}
