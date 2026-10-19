import os
import time
import requests

INTERNAL_TOKEN = os.getenv('AIOPS_INTERNAL_TOKEN') or os.getenv('AIOPS_ADMIN_TOKEN')
if not INTERNAL_TOKEN:
    raise RuntimeError('AIOPS_INTERNAL_TOKEN or AIOPS_ADMIN_TOKEN must be configured')


def _headers(token=None):
    return {
        'X-AIOPS-Request': 'internal',
        'Authorization': f'Bearer {token or INTERNAL_TOKEN}',
    }


def _request(method, base, path, payload=None, timeout=8, retries=None, token=None):
    method = method.upper()
    # Retrying a side-effecting request after a timeout can duplicate an incident,
    # run or action when the server committed it but the response was lost.
    # Only GET is retried automatically. POST requires an explicit idempotency
    # contract and must be retried by the caller only when that contract is known.
    max_retries = (2 if method == 'GET' else 0) if retries is None else max(0, int(retries))
    url = base.rstrip('/') + path
    last = None
    for attempt in range(max_retries + 1):
        try:
            response = requests.request(
                method, url, json=payload, timeout=timeout, headers=_headers(token)
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last = exc
            if attempt < max_retries:
                time.sleep(0.25 * (attempt + 1))
    raise last


def get_json(base, path, timeout=8, token=None, retries=None):
    return _request('GET', base, path, timeout=timeout, token=token, retries=retries)


def post_json(base, path, payload, timeout=8, token=None, retries=None):
    return _request('POST', base, path, payload, timeout=timeout, token=token, retries=retries)
