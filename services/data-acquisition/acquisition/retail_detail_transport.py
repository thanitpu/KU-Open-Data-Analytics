from __future__ import annotations

from urllib.parse import quote, unquote, urlsplit, urlunsplit

import retail_detail_catalog as core


def ascii_transport_url(url: str) -> str:
    """Encode Unicode URL components for stdlib HTTP/Chrome command-line transport.

    Canonical product URLs remain Unicode-friendly in discovery/evidence, while the
    outbound transport receives RFC 3986 percent-encoded path/query components.
    Existing percent escapes are decoded once then re-encoded to avoid double escaping.
    """
    try:
        p = urlsplit(str(url or ""))
        path = quote(unquote(p.path or "/"), safe="/%:@!$&'()*+,;=-._~")
        query = quote(unquote(p.query or ""), safe="=&?/:@!$'()*+,;%-._~")
        fragment = quote(unquote(p.fragment or ""), safe="/?/:@!$&'()*+,;=-._~")
        return urlunsplit((p.scheme, p.netloc, path, query, fragment))
    except Exception:
        return str(url or "")


def generic_retail_detail_catalog(seed_url: str, max_pages: int = 6, candidate_urls: list[str] | None = None) -> dict:
    """Run the canonical detail technique with Unicode-safe outbound transport."""
    original_get = core.get
    original_browser = core.browser_render

    def safe_get(url, *args, **kwargs):
        return original_get(ascii_transport_url(url), *args, **kwargs)

    def safe_browser(url, *args, **kwargs):
        return original_browser(ascii_transport_url(url), *args, **kwargs)

    core.get = safe_get
    core.browser_render = safe_browser
    try:
        result = core.generic_retail_detail_catalog(seed_url, max_pages=max_pages, candidate_urls=candidate_urls)
        result.setdefault("potential", {})["unicode_safe_transport"] = True
        return result
    finally:
        core.get = original_get
        core.browser_render = original_browser
