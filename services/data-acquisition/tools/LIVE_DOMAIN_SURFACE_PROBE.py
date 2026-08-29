from __future__ import annotations

import argparse
import json
import re
import socket
import ssl
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / 'config'
UA = 'Mozilla/5.0 (compatible; KU2D-Acquisition-Research/1.0; public-read-only)'


def load_json(path: Path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def candidates(domains: set[str]) -> list[dict]:
    out = []
    dc = load_json(CFG / 'domain_source_candidates.json', {'domains': {}})
    if 'ota' in domains:
        for x in (dc.get('domains') or {}).get('ota', []):
            out.append({'domain': 'ota', **x})
    if 'coffee' in domains:
        reg = load_json(CFG / 'source_registry.json', {'sources': []})
        for x in reg.get('sources') or []:
            if str(x.get('sector') or '').strip().lower() != 'cafe':
                continue
            out.append({
                'domain': 'coffee', 'candidate_id': x.get('source_id'), 'name': x.get('business'),
                'url': x.get('url'), 'source_type': 'official-public-web', 'status': 'existing-source',
                'purpose': 'retail_market_intelligence',
            })
    if 'q_diving' in domains:
        reg = load_json(CFG / 'q_diving_source_registry.json', {'sources': []})
        for x in reg.get('sources') or []:
            out.append({
                'domain': 'q_diving', 'candidate_id': x.get('source_id'), 'name': x.get('name'),
                'url': x.get('url'), 'source_type': x.get('source_type') or 'official-public-web',
                'status': 'existing-source', 'purpose': 'knowledge_learning',
            })
    return out


def title_of(html: str) -> str:
    m = re.search(r'<title[^>]*>(.*?)</title>', html or '', re.I | re.S)
    if not m:
        return ''
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', m.group(1))).strip()[:240]


def clue_flags(html: str, headers: dict) -> list[str]:
    h = html or ''
    lo = h.lower()
    flags = []
    checks = [
        ('json_ld', r'application/ld\+json'), ('next_data', r'__next_data__'),
        ('graphql', r'graphql'), ('apollo', r'apollo'), ('hydration_state', r'(?:hydration|initial_state|initialstate)'),
        ('rss', r'(?:application/rss\+xml|rss\.xml|/feed[\"\'])'), ('atom', r'application/atom\+xml'),
        ('price_label', r'(?:฿|thb|price|ราคา)'), ('availability', r'(?:availability|available|check.?in|check.?out|เข้าพัก|เช็กอิน)'),
        ('promotion', r'(?:promotion|promo|deal|coupon|ส่วนลด|โปรโมชั่น)'),
        ('product_cards', r'(?:product-card|productcard|product_item|product-item)'),
        ('menu', r'(?:menu|เมนู)'), ('article', r'(?:article|blog|บทความ)'),
        ('video', r'(?:youtube|video)'), ('sitemap_hint', r'(?:sitemap\.xml|sitemapindex)'),
    ]
    for key, pat in checks:
        if re.search(pat, lo, re.I):
            flags.append(key)
    ct = str(headers.get('content-type') or '').lower()
    if 'application/json' in ct:
        flags.append('json_response')
    if 'cloudflare' in str(headers.get('server') or '').lower() or 'cf-ray' in headers:
        flags.append('cloudflare')
    return sorted(set(flags))


def access_class(status: int | None, html: str, error: str | None) -> str:
    lo = (html or '').lower()
    if status and 200 <= status < 400:
        if any(x in lo for x in ('access denied', 'captcha', 'verify you are human', 'just a moment...')):
            return 'challenge-or-block'
        return 'public-readable'
    if status in (401, 403, 429):
        return 'restricted-or-throttled'
    if error:
        return 'network-error'
    return 'unavailable'


def probe(item: dict, timeout: int = 12) -> dict:
    url = item.get('url') or ''
    started = time.monotonic()
    status = None; final_url = url; body = b''; headers = {}; err = None
    req = Request(url, headers={
        'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.5',
        'Accept-Language': 'en-US,en;q=0.8,th;q=0.6', 'Cache-Control': 'no-cache',
    })
    try:
        ctx = ssl.create_default_context()
        with urlopen(req, timeout=timeout, context=ctx) as r:
            status = getattr(r, 'status', None) or r.getcode()
            final_url = r.geturl() or url
            headers = {str(k).lower(): str(v) for k, v in r.headers.items()}
            body = r.read(1_500_000)
    except HTTPError as e:
        status = e.code; final_url = e.geturl() or url
        headers = {str(k).lower(): str(v) for k, v in (e.headers.items() if e.headers else [])}
        try: body = e.read(200_000)
        except Exception: body = b''
        err = f'HTTPError: {e.code}'
    except (URLError, socket.timeout, TimeoutError, ssl.SSLError) as e:
        err = f'{type(e).__name__}: {e}'
    except Exception as e:
        err = f'{type(e).__name__}: {e}'
    enc = 'utf-8'
    m = re.search(r'charset=([\w.-]+)', headers.get('content-type', ''), re.I)
    if m: enc = m.group(1)
    try: html = body.decode(enc, errors='replace')
    except Exception: html = body.decode('utf-8', errors='replace')
    return {
        **item, 'tested_at': datetime.now(timezone.utc).isoformat(), 'http_status': status,
        'final_url': final_url, 'final_host': urlparse(final_url).netloc.lower(),
        'bytes_read': len(body), 'title': title_of(html), 'access_class': access_class(status, html, err),
        'content_type': headers.get('content-type'), 'server': headers.get('server'),
        'clues': clue_flags(html, headers), 'error': err, 'elapsed_seconds': round(time.monotonic()-started, 3),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--domains', default='ota,coffee,q_diving')
    ap.add_argument('--output', default='validation/domain-live-probe.json')
    ap.add_argument('--timeout', type=int, default=12)
    args = ap.parse_args()
    domains = {x.strip().lower().replace('-', '_') for x in args.domains.split(',') if x.strip()}
    rows = [probe(x, timeout=args.timeout) for x in candidates(domains)]
    summary = {}
    for domain in sorted(domains):
        rr = [x for x in rows if x.get('domain') == domain]
        summary[domain] = {
            'sources': len(rr), 'public_readable': sum(x['access_class']=='public-readable' for x in rr),
            'restricted_or_throttled': sum(x['access_class']=='restricted-or-throttled' for x in rr),
            'challenge_or_block': sum(x['access_class']=='challenge-or-block' for x in rr),
            'network_error': sum(x['access_class']=='network-error' for x in rr),
        }
    payload = {
        'schema': 'ku2d.domain-live-surface-probe.v1', 'generated_at': datetime.now(timezone.utc).isoformat(),
        'execution_environment': 'cloud-hosted-public-read-only',
        'policy': 'No login, CAPTCHA solving, proxy rotation or access-control bypass. Probe discovers public-readable surfaces only.',
        'summary': summary, 'results': rows,
    }
    out = ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))
    print(f'Wrote {out}')


if __name__ == '__main__':
    main()
