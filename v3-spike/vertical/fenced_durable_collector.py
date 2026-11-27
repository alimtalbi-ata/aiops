"""Opt-in durable collector transport; no automatic recovery or rearm.

The authority must be outside this restorable journal. Credentials are supplied
by the caller and never persisted here. HTTP is confined loopback, not mutual
TLS. Routes require server-side installation before use. A reference-only
lookup is not a verified full receipt and never clears UNKNOWN_BLOCKED.
"""
import json
import re
from urllib.request import build_opener, ProxyHandler, Request

from continuous_collector import NoRedirect, ROOT, require
from durable_collector import DurableCollector
from collector_receipt import digest, validate_receipt
from collector_admission_fence import scope_key, token_hash


class FencedDurableCollector(DurableCollector):
    def __init__(self, target_port, gamma_port, root, *, scope, token, generation, initialize=False):
        scope_key(scope)
        token_hash(token)
        require(scope[1] == ROOT and type(generation) is int and generation >= 0,
                'invalid fenced collector configuration')
        self.scope = scope
        self._token = token
        self.generation = generation
        self.pending = None
        self.receipt_sha256 = None
        super().__init__(target_port, gamma_port, root, initialize=initialize)

    def snapshot(self):
        return super().snapshot() | {'version': 2, 'fence': {'scope': list(self.scope), 'generation': self.generation,
                                               'pending': self.pending, 'receipt_sha256': self.receipt_sha256}}

    def restore(self, payload):
        require(isinstance(payload, dict) and payload.get('version') == 2 and 'fence' in payload, 'fenced journal required')
        fence = payload['fence']
        require(isinstance(fence, dict) and set(fence) == {'scope', 'generation', 'pending', 'receipt_sha256'}
                and fence['scope'] == list(self.scope) and type(fence['generation']) is int
                and fence['generation'] == self.generation, 'fenced journal scope/generation mismatch')
        pending, receipt = fence['pending'], fence['receipt_sha256']
        if pending is not None:
            require(isinstance(pending, dict) and set(pending) == {'episode', 'batch'}
                    and isinstance(pending['episode'], str) and re.fullmatch(r'[a-f0-9]{32}', pending['episode'])
                    and isinstance(pending['batch'], str) and re.fullmatch(r'[a-f0-9]{64}', pending['batch']),
                    'invalid pending publication identity')
        super().restore({k: v for k, v in payload.items() if k != 'fence'} | {'version': 1})
        require((self.state in ('UNKNOWN_BLOCKED', 'LATCHED') or pending is None)
                and (self.state != 'LATCHED' or pending is not None)
                and ((self.state == 'LATCHED' and isinstance(receipt, str) and re.fullmatch(r'[a-f0-9]{64}', receipt))
                     or (self.state != 'LATCHED' and receipt is None)), 'invalid fenced journal state')
        self.pending, self.receipt_sha256 = pending, receipt

    def _post(self, path, body):
        origin = 'http://127.0.0.1:' + str(self.gamma_port)
        raw = json.dumps(body, separators=(',', ':'), allow_nan=False).encode()
        require(len(raw) <= 4096, 'oversized collector request')
        req = Request(origin + path, data=raw, headers={'Origin': origin, 'Content-Type': 'application/json',
                      'Authorization': 'Bearer ' + self._token})
        with build_opener(ProxyHandler({}), NoRedirect()).open(req, timeout=15) as response:
            raw = response.read(65537)
            require(response.status == 200 and len(raw) <= 65536
                    and response.headers.get('Cache-Control') == 'no-store', 'unverified collector response')
            return json.loads(raw)

    def publish(self, rows, correlation):
        require(self.state == 'UNKNOWN_BLOCKED' and self.pending is None, 'publication already pending')
        self.pending = {'episode': rows[0]['id'][:32], 'batch': digest(correlation['incidents'][0])}
        self.checkpoint()  # identity survives process crash before any network I/O
        response = self._post('/api/v1/collector/admit', {'generation': self.generation, 'rows': rows})
        validate_receipt(correlation, response)
        self.receipt_sha256 = digest(response)
        return response

    def allow_local_rearm(self):
        return False  # only server Verify can advance authority generation

    def reconcile_reference(self):
        require(self.pending is not None and self.state in ('UNKNOWN_BLOCKED', 'LATCHED'), 'no pending publication')
        result = self._post('/api/v1/collector/receipt', {'generation': self.generation, **self.pending})
        if result == {'state': 'UNKNOWN_BLOCKED'}:
            return result
        require(result.get('state') == 'COMMITTED' and isinstance(result.get('run_id'), str)
                and re.fullmatch(r'RUN-[A-F0-9]{16}', result['run_id'])
                and isinstance(result.get('receipt_sha256'), str)
                and re.fullmatch(r'[a-f0-9]{64}', result['receipt_sha256']), 'invalid receipt reference')
        if self.state == 'LATCHED':
            require(result['run_id'] == self.run_id and result['receipt_sha256'] == self.receipt_sha256,
                    'receipt reference differs from verified publication')
        return {'state': 'COMMITTED', 'run_id': result['run_id'], 'receipt_sha256': result['receipt_sha256']}
