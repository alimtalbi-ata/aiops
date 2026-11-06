import {buildFsRealProjection} from './fs-real-server-projection.mjs';

/**
 * Adapter for an EXISTING authenticated Portal backend route.
 * The host MUST run its session/OIDC and tenant/actor ACL middleware first.
 * No new listener, public route, token, or bypass is created here.
 */
export function createFsRealReadHandler({authorize, readCore, readTemporal, readPolicy, readQuestions}) {
  return async function fsRealRead(req, res) {
    const send = (status, payload) => {
      res.statusCode = status;
      res.setHeader('Content-Type', 'application/json; charset=utf-8');
      res.setHeader('Cache-Control', 'no-store, private');
      res.setHeader('X-Content-Type-Options', 'nosniff');
      res.end(JSON.stringify(payload));
    };
    if (req.method !== 'GET') return send(405, {error:'METHOD_NOT_ALLOWED'});
    let url;
    try { url = new URL(req.url, 'http://portal.internal'); }
    catch { return send(400, {error:'INVALID_REQUEST'}); }
    if (url.pathname !== '/api/portal/fs-real/projection' ||
        [...url.searchParams.keys()].some(k => !['mode','ticket_id'].includes(k)) ||
        url.searchParams.getAll('mode').length !== 1 ||
        url.searchParams.getAll('ticket_id').length !== 1 ||
        url.searchParams.get('ticket_id') !== '147' ||
        !['lab147','insufficient'].includes(url.searchParams.get('mode')))
      return send(400, {error:'INVALID_REQUEST'});
    // Principal must be supplied by the host's authenticated middleware.
    // Never accept an actor, tenant, or authorization from query parameters.
    if (!req.principal) return send(401, {error:'UNAUTHENTICATED'});
    try {
      const projection = await buildFsRealProjection({
        mode:url.searchParams.get('mode'), ticketId:147, principal:req.principal,
        authorize, readCore, readTemporal, readPolicy, readQuestions
      });
      return send(200, projection);
    } catch (error) {
      if (error?.message === 'FORBIDDEN') return send(403, {error:'FORBIDDEN'});
      if (error?.message === 'INVALID_REQUEST') return send(400, {error:'INVALID_REQUEST'});
      return send(503, {error:'UNAVAILABLE'});
    }
  };
}
