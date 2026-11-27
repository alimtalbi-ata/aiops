"""Server-owned adapter for the existing synthetic measured admission.

No route is installed here. Caller owns private authority DB, scope, graph,
Core/Evidence publisher and authenticated transport. A restore lock outside
this DB remains mandatory before service activation after authority restore.
"""
import re
from copy import deepcopy
from authority_guard_operations_candidate import AdmissionIdentity, publish_once, lookup_receipt
from collector_admission_fence import authenticated, claim, complete, reconcile, archived_receipt, require, transaction
from collector_receipt import digest
from collector_persisted_receipt import verify_persisted_receipt
from ingestion_demo import ingest
from incident_admission import admit


def bearer(authorization):
    require(isinstance(authorization, str) and re.fullmatch(r'Bearer [a-f0-9]{64}', authorization))
    return authorization[7:]


def _prepare(rows, scope, graph):
    """Validate the existing continuous collector contract before a claim."""
    require(isinstance(rows, list) and len(rows) == 3 and all(isinstance(r, dict) for r in rows))
    ids = {r.get('id') for r in rows}
    first = rows[0].get('id')
    require(isinstance(first, str) and re.fullmatch(r'[a-f0-9]{32}-(baseline|incident|log)', first))
    episode = first[:32]
    require(ids == {episode + '-' + phase for phase in ('baseline', 'incident', 'log')})
    for row in rows:
        phase = row['id'][33:]
        require(row.get('tenant') == scope[0] and row.get('resource') == scope[1]
                and row.get('synthetic') is True and row.get('source') == 'continuous-lab-http')
        if phase == 'log':
            require(row.get('kind') == 'log' and 'observation' not in row)
        else:
            require(row.get('kind') == 'metric' and row.get('observation', {}).get('phase') == phase)
    correlation = ingest(rows)
    decision = admit(rows, graph)
    require(decision['admitted'] is True and decision['operational_decision'] == 'DENY'
            and decision['production_authorized'] is False)
    batch = digest(correlation['incidents'][0])
    require(batch == decision['batch_sha256'])
    return episode, batch, correlation, decision


def publish(db, *, scope, authorization, generation, rows, graph, publish_records, read_context):
    """Publish once; on any exception after claim, leave PENDING, never retry.

    Scope is server configuration, not a request assertion. publish_records
    must be bound to the existing create_and_persist with server credentials.
    read_context must independently read persisted Core/Evidence, never the response.
    """
    token = bearer(authorization)
    with transaction(db):
        authenticated(db, scope, token, generation)
    episode, batch, correlation, decision = _prepare(rows, scope, graph)
    claim(db, scope, token, generation, episode, batch)
    response = {'admission': decision, 'publication': publish_records(rows), 'production_authorized': False}
    run = verify_persisted_receipt(correlation, response, read_context=read_context)
    complete(db, scope, token, generation, episode, batch, run, digest(response))
    return response


def lookup(db, *, scope, authorization, generation, episode, batch):
    """Read reference only; never start publication or infer recovery."""
    token = bearer(authorization)
    with transaction(db):
        key = '/'.join(scope)
        row = db.execute('SELECT generation FROM collector_fence WHERE scope=?', (key,)).fetchone()
        require(row is not None and type(generation) is int)
        current = row[0]
    reader = archived_receipt if generation < current else reconcile
    return reader(db, scope, token, generation, episode, batch)


def publish_guarded(db, witness, *, scope, authorization, generation, rows, graph, publish_records, read_context):
    """Publish with a mandatory witness; never delegate to the legacy path.

    The caller must supply existing private databases and independent readback.
    No runtime provisioning, automatic unlock, or retry is performed here.
    """
    token = bearer(authorization)
    with transaction(db):
        authenticated(db, scope, token, generation)
    rows = deepcopy(rows)
    episode, batch, correlation, decision = _prepare(rows, scope, graph)
    identity = AdmissionIdentity(scope, token, generation, episode, batch)
    response = None

    def publish_verified(bound_scope, bound_generation, bound_episode, bound_batch):
        nonlocal response
        require((bound_scope, bound_generation, bound_episode, bound_batch)
                == (scope, generation, episode, batch))
        response = deepcopy({'admission': decision, 'publication': publish_records(rows),
                             'production_authorized': False})
        run = verify_persisted_receipt(correlation, response, read_context=read_context)
        return run, digest(response)

    publish_once(db, witness, identity, publish_verified)
    return response


def lookup_guarded(db, witness, *, scope, authorization, generation, episode, batch):
    """Read only a guarded receipt reference; BUSY or mismatch fails closed."""
    identity = AdmissionIdentity(scope, bearer(authorization), generation, episode, batch)
    return lookup_receipt(db, witness, identity)
