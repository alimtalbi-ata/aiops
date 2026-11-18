"""Offline injected readback adapter; no transport, authentication or positive authority."""
from copy import deepcopy

from .acme_runtime_context import qualify_context, digest, AUTHORITIES


def collect_prepared(expected, intent, readers, policies, *, as_of_utc, source_registry=None):
    """Read Core twice around Twin/Policy; preserve the existing refusal contract."""
    def qualify(rows):
        return qualify_context(expected, intent, rows, policies, as_of_utc=as_of_utc,
                               source_registry=source_registry)

    def refuse(reason, reject=False):
        return dict(qualify({}), qualification='REJECT' if reject else 'BLOCK',
                    reason=reason, context=None, evidence=[])

    if not isinstance(readers, dict) or set(readers) != set(AUTHORITIES) or any(
            not callable(v) for v in readers.values()):
        return refuse('READERS_INVALID', True)
    rows = {}
    for authority in AUTHORITIES:
        try:
            rows[authority] = deepcopy(readers[authority]())
        except (OSError, TimeoutError, ConnectionError):
            return refuse('AUTHORITY_MISSING:' + authority)
    result = qualify(rows)
    if result['reason'] != 'INJECTED_READBACKS_NOT_ATTESTED':
        return result
    core = rows['core']['content']
    if core.get('run_status') != 'PREPARED' or core.get('incident_status') != 'PREPARED':
        return refuse('CORE_NOT_PREPARED', True)
    if type(core.get('version')) is not int or core['version'] < 0:
        return refuse('CORE_VERSION_INVALID', True)
    # Proposed offline manifest binds the entire normalized Twin/Policy envelopes.
    try:
        manifest = {a: digest(rows[a]) for a in ('twin', 'policy')}
        if core.get('authority_manifest') != manifest:
            return refuse('MANIFEST_MISMATCH', True)
        second = deepcopy(readers['core']())
        if second is None:
            return refuse('AUTHORITY_MISSING:core')
        if digest(second) != digest(rows['core']):
            return refuse('CORE_CHANGED', True)
    except (OSError, TimeoutError, ConnectionError):
        return refuse('AUTHORITY_MISSING:core')
    except (ValueError, TypeError, RecursionError, OverflowError):
        return refuse('READBACK_INVALID', True)
    return result
