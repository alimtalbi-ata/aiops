"""Token-free, REJECT-only Core terminal recovery for the production Worker.

No claim, ACK, Temporal signal, GLPI write, approval or executor path. Core is
sole authority for eighth-lease expiry, canonical Incident/Run, DEAD and 014/015.
"""
import re
from datetime import datetime

CORE_SCHEMA = 'aiops.core-hitl-reject-delivery.v1'
RECEIPT_SCHEMA = 'aiops.core-hitl-reject-terminal-receipt.v1'
_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{1,127}\Z', re.ASCII)
_HASH = re.compile(r'[0-9a-f]{64}\Z', re.ASCII)
_INPUT = frozenset(('tenant_id', 'event_id', 'run_id', 'incident_id',
                    'proposal_id', 'proposal_hash', 'proposal_revision',
                    'decision', 'execution_allowed', 'effect_allowed'))


class UnqualifiedTerminal(ValueError):
    """Non-enumerating denial; never include Core response or credentials."""


def _valid_id(value):
    return type(value) is str and _ID.fullmatch(value) is not None


def validate_request(args, owner):
    if (type(args) is not dict or frozenset(args) != _INPUT
            or not all(_valid_id(args.get(k)) for k in
                       ('tenant_id', 'event_id', 'run_id', 'incident_id', 'proposal_id'))
            or not _valid_id(owner)
            or type(args.get('proposal_hash')) is not str
            or _HASH.fullmatch(args['proposal_hash']) is None
            or type(args.get('proposal_revision')) is not int
            or args['proposal_revision'] < 1
            or args.get('decision') != 'REJECT'
            or args.get('execution_allowed') is not False
            or args.get('effect_allowed') is not False):
        raise UnqualifiedTerminal('terminal_request_unqualified')
    return {
        'owner': owner, 'run_id': args['run_id'],
        'incident_id': args['incident_id'], 'proposal_id': args['proposal_id'],
        'proposal_hash': args['proposal_hash'],
        'proposal_revision': args['proposal_revision'],
        'execution_allowed': False, 'effect_allowed': False,
    }


def _validate_receipt(response, args, owner):
    if (type(response) is not dict
            or response.get('schema') != CORE_SCHEMA
            or response.get('receipt_schema') != RECEIPT_SCHEMA
            or response.get('status') != 'DEAD'
            or response.get('execution_allowed') is not False
            or response.get('effect_allowed') is not False
            or response.get('attempts') != 8
            or type(response.get('attempts')) is not int
            or type(response.get('idempotent')) is not bool
            or response.get('actor_id') != owner
            or any(response.get(k) != args[k] for k in
                   ('tenant_id', 'event_id', 'run_id', 'incident_id', 'proposal_id',
                    'proposal_hash', 'proposal_revision'))
            or type(response.get('receipt_sha256')) is not str
            or _HASH.fullmatch(response['receipt_sha256']) is None
            or type(response.get('dead_at')) is not str
            or any(k in response for k in
                   ('lease_token', 'lease_token_sha256', 'human_approved',
                    'authorization', 'approval_allowed'))):
        raise UnqualifiedTerminal('terminal_receipt_unqualified')
    try:
        when = datetime.fromisoformat(response['dead_at'])
    except ValueError:
        raise UnqualifiedTerminal('terminal_time_unqualified') from None
    if when.tzinfo is None:
        raise UnqualifiedTerminal('terminal_time_unqualified')
    return response


async def recover_terminal_once(args, *, owner, post):
    """Core terminal-recover then independently read back DEAD, without signals.

    post(path, body) is a trusted authenticated async transport returning JSON.
    Core must enforce service bearer, tenant, source freshness, eighth expired
    lease, actor, immutable receipt and canonical Incident/Run ownership.
    HTTP 401/403/503, UNKNOWN, transport errors and inconsistent receipts fail
    closed; never echo response, raw token or transport exception in logs.
    """
    body = validate_request(args, owner)
    root = f"/api/tenants/{args['tenant_id']}/hitl/reject-delivery/{args['event_id']}"
    try:
        recovered = _validate_receipt(await post(root + '/terminal-recover', body), args, owner)
        readback = _validate_receipt(await post(root + '/terminal-receipt', body), args, owner)
    except Exception as exc:
        if isinstance(exc, UnqualifiedTerminal):
            raise
        raise UnqualifiedTerminal('terminal_core_unavailable_or_denied') from None
    if (recovered['receipt_sha256'] != readback['receipt_sha256']
            or recovered['dead_at'] != readback['dead_at']):
        raise UnqualifiedTerminal('terminal_readback_mismatch')
    return {
        'status': 'DEAD', 'tenant_id': args['tenant_id'],
        'event_id': args['event_id'], 'run_id': args['run_id'],
        'incident_id': args['incident_id'],
        'receipt_sha256': readback['receipt_sha256'],
        'idempotent': recovered['idempotent'],
        'execution_allowed': False, 'effect_allowed': False,
        'temporal_signal_sent': False, 'ack_sent': False,
        'human_glpi_authorization': 'UNKNOWN',
    }
