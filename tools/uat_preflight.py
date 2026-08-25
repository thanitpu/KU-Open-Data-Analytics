import json
import sys
import time
import urllib.request

BASE='http://127.0.0.1:8001'
ORIGIN='http://127.0.0.1:8000'

def get_json(path, attempts=20, delay=0.5):
    last=None
    for _ in range(attempts):
        try:
            req=urllib.request.Request(BASE+path, headers={'Origin':ORIGIN,'Cache-Control':'no-cache'})
            with urllib.request.urlopen(req, timeout=3) as r:
                body=r.read().decode('utf-8')
                cors=r.headers.get('Access-Control-Allow-Origin')
                return json.loads(body), cors
        except Exception as ex:
            last=ex
            time.sleep(delay)
    raise RuntimeError(f'{path} unavailable after retries: {last}')

try:
    health, health_cors=get_json('/health')
    if health.get('status')!='ok':
        raise RuntimeError(f'/health returned unexpected payload: {health}')
    caps, caps_cors=get_json('/capabilities')
    if not isinstance(caps, dict) or 'routes' not in caps:
        raise RuntimeError('/capabilities payload does not contain routes')
    if caps_cors!=ORIGIN:
        raise RuntimeError(f'CORS mismatch for /capabilities: expected {ORIGIN}, got {caps_cors!r}')
    print('[KU Open DA UAT] Backend preflight PASS')
    print(f'[KU Open DA UAT] /health       : {health}')
    print(f'[KU Open DA UAT] /capabilities : {len(caps.get("routes",{}))} route(s)')
    print(f'[KU Open DA UAT] CORS           : {caps_cors}')
except Exception as ex:
    print(f'[KU Open DA UAT] Backend preflight FAIL: {ex}')
    sys.exit(1)
