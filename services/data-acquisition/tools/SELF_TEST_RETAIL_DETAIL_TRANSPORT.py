from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "acquisition"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import retail_detail_catalog as core
import retail_detail_transport as transport

unicode_url = "https://www.jib.co.th/web/product/readProduct/32021/556/SPEAKER--ลำโพง--CREATIVE-PEBBLE-2-0--WHITE-"
encoded = transport.ascii_transport_url(unicode_url)
assert encoded.startswith("https://www.jib.co.th/web/product/readProduct/32021/556/")
assert "%E0%B8%A5%E0%B8%B3%E0%B9%82%E0%B8%9E%E0%B8%87" in encoded
assert "ลำโพง" not in encoded
assert transport.ascii_transport_url(encoded) == encoded

calls = []
original_catalog = core.generic_retail_detail_catalog


def fake_catalog(seed_url, max_pages=6, candidate_urls=None):
    # Exercise the patched core.get binding installed by the wrapper.
    result = core.get(unicode_url, timeout=7)
    return {"technique": "generic_retail_detail_catalog", "potential": {}, "transport_result": result}


def fake_get(url, *args, **kwargs):
    calls.append(url)
    return {"ok": True, "url": url}

original_get = core.get
core.generic_retail_detail_catalog = fake_catalog
core.get = fake_get
try:
    out = transport.generic_retail_detail_catalog("https://www.jib.co.th/web/index.php", max_pages=2)
finally:
    core.generic_retail_detail_catalog = original_catalog
    core.get = original_get

assert calls and calls[0] == encoded, calls
assert out["potential"]["unicode_safe_transport"] is True
assert out["transport_result"]["ok"] is True

print("Unicode-safe retail detail transport: PASS")
