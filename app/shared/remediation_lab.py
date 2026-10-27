"""Fail-closed remediation proposal simulator. Never executes scripts, APIs or commands.

Approval is an offline fixture, NOT an authenticated LIVE authorization.
"""
from __future__ import annotations
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CATALOG_PATH = Path(__file__).resolve().parents[2] / 'config/remediation/recipes.v1.json'
SAFE_ID = re.compile(r'^[A-Za-z0-9_.:-]{1,64}$')
MODES = frozenset({'DEMO', 'REPLAY', 'STORY', 'LIVE'})
DECISIONS = frozenset({'APPROVED', 'REJECTED', 'CLARIFY', 'EXPIRED'})

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError('timezone_required')
    return value.astimezone(timezone.utc).isoformat()

def load_catalog() -> dict[str, Any]:
    doc = json.loads(CATALOG_PATH.read_text(encoding='utf-8'))
    if doc.get('schema_version') != 1:
        raise ValueError('unsupported_catalog_schema')
    entries = doc['recipes']
    if len({(r['id'], r['version']) for r in entries}) != len(entries):
        raise ValueError('duplicate_recipe_version')
    return {(r['id'], r['version']): r for r in entries}

def canonical_digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()

def validate_proposal(proposal: dict[str, Any], catalog: dict | None = None) -> tuple[dict, str]:
    """Strict allowlist and typed validation; never interpolate into a command."""
    catalog = load_catalog() if catalog is None else catalog
    if set(proposal) != {'proposal_id', 'recipe_id', 'recipe_version', 'target_ci', 'parameters', 'mode', 'requested_by'}:
        raise ValueError('proposal_fields_invalid')
    if proposal['mode'] not in MODES:
        raise ValueError('mode_invalid')
    for key in ('proposal_id', 'target_ci', 'requested_by'):
        if not isinstance(proposal[key], str) or not SAFE_ID.fullmatch(proposal[key]):
            raise ValueError(f'{key}_invalid')
    recipe = catalog.get((proposal['recipe_id'], proposal['recipe_version']))
    if recipe is None or recipe.get('implementation') != 'SIMULATOR_ONLY':
        raise ValueError('recipe_not_allowlisted')
    if not proposal['target_ci'].startswith(recipe['target_prefix']):
        raise ValueError('target_out_of_scope')
    params = proposal['parameters']
    spec = recipe['parameters']
    if not isinstance(params, dict) or set(params) != set(spec):
        raise ValueError('parameter_keys_invalid')
    for key, meta in spec.items():
        value = params[key]
        kind = meta['type']
        if kind == 'identifier':
            if not isinstance(value, str) or not SAFE_ID.fullmatch(value):
                raise ValueError(f'parameter_{key}_invalid')
        elif kind == 'integer':
            if type(value) is not int or not meta['min'] <= value <= meta['max']:
                raise ValueError(f'parameter_{key}_invalid')
        elif kind == 'secret_ref':
            if not isinstance(value, str) or not re.fullmatch(r'vault://[A-Za-z0-9/_-]{1,120}', value):
                raise ValueError(f'parameter_{key}_invalid')
        elif kind == 'enum':
            if not isinstance(value, str) or value not in meta['values']:
                raise ValueError(f'parameter_{key}_invalid')
        else:
            raise ValueError('unknown_parameter_type')
    return recipe, canonical_digest(proposal)

def redacted_parameters(params: dict, recipe: dict) -> dict:
    return {k: ('[REDACTED]' if recipe['parameters'][k]['type'] == 'secret_ref' else v) for k, v in params.items()}

def evaluate_simulation(proposal: dict[str, Any], decision: dict[str, Any], preconditions: dict[str, bool], *, now: datetime | None = None) -> dict[str, Any]:
    """Generate an audit fixture only. No effects, no network, no subprocess."""
    now = utc_now() if now is None else now
    timestamp = iso(now)
    recipe, digest = validate_proposal(proposal)
    base = {
        'timestamp': timestamp, 'proposal_id': proposal['proposal_id'],
        'proposal_digest': digest, 'recipe_id': recipe['id'],
        'recipe_version': recipe['version'], 'target_ci': proposal['target_ci'],
        'parameters': redacted_parameters(proposal['parameters'], recipe),
        'mode': proposal['mode'], 'executor': 'NO_EFFECT_SIMULATOR',
        'effect_applied': False, 'postchecks': 'NOT_RUN',
        'rollback': 'NOT_REQUIRED', 'timeout_seconds': recipe['timeout_seconds'],
        'idempotency_key': canonical_digest({'proposal_digest': digest, 'executor': 'NO_EFFECT_SIMULATOR'}),
    }
    def blocked(reason: str) -> dict:
        return {**base, 'status': 'BLOCKED', 'reason': reason}
    if proposal['mode'] == 'LIVE':
        return blocked('LIVE_NOT_QUALIFIED')
    if set(decision) != {'state', 'proposal_digest', 'actor_id', 'actor_role', 'authenticated', 'expires_at', 'requested_by'}:
        return blocked('DECISION_FIELDS_INVALID')
    if decision['state'] not in DECISIONS or decision['state'] != 'APPROVED':
        return blocked('HUMAN_DECISION_NOT_APPROVED')
    if decision['proposal_digest'] != digest:
        return blocked('APPROVAL_BINDING_MISMATCH')
    if decision['authenticated'] is not True or decision['actor_role'] != 'approver':
        return blocked('APPROVER_NOT_VERIFIED')
    if not isinstance(decision['actor_id'], str) or not SAFE_ID.fullmatch(decision['actor_id']):
        return blocked('APPROVER_ID_INVALID')
    if decision['requested_by'] != proposal['requested_by'] or decision['actor_id'] == proposal['requested_by']:
        return blocked('SEPARATION_OF_DUTIES_FAILED')
    try:
        expiry = datetime.fromisoformat(decision['expires_at'].replace('Z', '+00:00'))
        if expiry.tzinfo is None or expiry.astimezone(timezone.utc) <= now.astimezone(timezone.utc):
            return blocked('APPROVAL_EXPIRED')
    except (ValueError, TypeError, AttributeError):
        return blocked('APPROVAL_EXPIRY_INVALID')
    if not isinstance(preconditions, dict) or set(preconditions) != set(recipe['preconditions']):
        return blocked('PRECONDITIONS_MISSING')
    if any(preconditions[k] is not True for k in recipe['preconditions']):
        return blocked('PRECONDITIONS_FAILED')
    return {
        **base, 'status': 'SIMULATED', 'reason': 'NO_SIDE_EFFECTS',
        'approval_actor': decision['actor_id'],
        'preconditions': 'FIXTURE_ASSERTED_NOT_RUNTIME_VERIFIED',
        'planned_postchecks': recipe['postchecks'],
        'compensation': recipe['compensation'],
        'dry_run': True,
    }
