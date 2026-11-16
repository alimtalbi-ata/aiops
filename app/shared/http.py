import os, time, requests

INTERNAL_TOKEN = os.getenv('AIOPS_INTERNAL_TOKEN') or os.getenv('AIOPS_ADMIN_TOKEN')
if not INTERNAL_TOKEN:
    raise RuntimeError('AIOPS_INTERNAL_TOKEN or AIOPS_ADMIN_TOKEN must be configured')

def _headers(token=None):
    return {'X-AIOPS-Request': 'internal', 'Authorization': f'Bearer {token or INTERNAL_TOKEN}'}

def _request(method, base, path, payload=None, timeout=8, retries=0, token=None):
    url=base.rstrip('/')+path
    last=None
    for attempt in range(retries+1):
        try:
            response=requests.request(method,url,json=payload,timeout=timeout,headers=_headers(token))
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as exc:
            # Client errors are deterministic contract/auth failures; retrying them only adds load.
            code=exc.response.status_code if exc.response is not None else None
            if code is not None and code < 500 and code != 429:
                raise
            last=exc
        except (requests.Timeout, requests.ConnectionError) as exc:
            last=exc
        except Exception:
            # JSON decode/programming errors are not transient transport failures.
            raise
        if attempt < retries:
            time.sleep(min(0.25*(attempt+1),1.0))
    raise last

def get_json(base,path,timeout=8,token=None,retries=2):
    return _request('GET',base,path,timeout=timeout,retries=retries,token=token)

def post_json(base,path,payload,timeout=8,token=None,retries=0):
    # POST is not retried at this layer by default: the caller/Temporal activity must
    # own idempotency and retry policy, since a timeout may happen after the server commits.
    return _request('POST',base,path,payload,timeout=timeout,retries=retries,token=token)
