import os, time, requests

INTERNAL_TOKEN = os.getenv('AIOPS_INTERNAL_TOKEN', os.getenv('AIOPS_ADMIN_TOKEN', 'Newaiops26$'))

def _headers(token=None):
    return {'X-AIOPS-Request': 'internal', 'Authorization': f'Bearer {token or INTERNAL_TOKEN}'}

def _request(method, base, path, payload=None, timeout=8, retries=2, token=None):
    url=base.rstrip('/')+path
    last=None
    for n in range(retries+1):
        try:
            r=requests.request(method,url,json=payload,timeout=timeout,headers=_headers(token))
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last=e
            if n<retries: time.sleep(0.25*(n+1))
    raise last

def get_json(base,path,timeout=8,token=None): return _request('GET',base,path,timeout=timeout,token=token)
def post_json(base,path,payload,timeout=8,token=None): return _request('POST',base,path,payload,timeout=timeout,token=token)
