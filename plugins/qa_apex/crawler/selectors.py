from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse, urlencode


FRIENDLY_RE = re.compile(
    r"/ords/r/(?P<workspace>[^/]+)/(?P<app>[^/]+)/(?P<page>[^/?#]+)",
    re.I,
)


@dataclass
class ParsedApexUrl:
    workspace: str | None = None
    app_alias: str | None = None
    page_alias: str | None = None
    session: str | None = None
    host: str | None = None
    path: str = ""
    raw: str = ""


def parse_apex_url(url: str) -> ParsedApexUrl:
    p = urlparse(url)
    out = ParsedApexUrl(host=p.hostname, path=p.path, raw=url)
    m = FRIENDLY_RE.search(p.path or "")
    if m:
        out.workspace = m.group("workspace")
        out.app_alias = m.group("app")
        out.page_alias = m.group("page")
    qs = parse_qs(p.query or "")
    sess = qs.get("session") or qs.get("p_session")
    if sess:
        out.session = sess[0]
    return out


def with_session(url: str, session: str | None) -> str:
    if not session:
        return url
    p = urlparse(url)
    qs = parse_qs(p.query or "", keep_blank_values=True)
    qs["session"] = [session]
    # flatten
    flat = []
    for k, vals in qs.items():
        for v in vals:
            flat.append((k, v))
    return urlunparse((p.scheme, p.netloc, p.path, p.params, urlencode(flat), p.fragment))


def same_host(a: str, b: str) -> bool:
    return (urlparse(a).hostname or "").lower() == (urlparse(b).hostname or "").lower()


def normalize_page_key(url: str) -> str:
    """Strip session/cs so same page is visited once."""
    p = urlparse(url)
    parsed = parse_apex_url(url)
    if parsed.app_alias and parsed.page_alias:
        return f"{parsed.app_alias}/{parsed.page_alias}".lower()
    # drop volatile query keys
    qs = parse_qs(p.query or "")
    for volatile in ("session", "cs", "dialogCs", "p_session", "clear", "request"):
        qs.pop(volatile, None)
    flat = [(k, v) for k, vals in sorted(qs.items()) for v in vals]
    return f"{p.path.lower()}?{urlencode(flat)}" if flat else p.path.lower()


def is_skippable_path(path: str) -> bool:
    low = path.lower()
    if "/ords/" not in low and "ords" not in low:
        # still allow relative app paths under same host when crawler resolves
        pass
    skip_tokens = (
        "logout",
        "javascript:",
        "mailto:",
        "#",
    )
    return any(tok in low for tok in skip_tokens)


PREFERRED_ITEM_SELECTORS = (
    # Prefer APEX static item ids
    "#{name}",
    "[name='{name}']",
    "[id$='_{name}']",
    "input[id*='{name}']",
)


@dataclass
class LocatorHint:
    name: str
    strategies: list[str] = field(default_factory=list)


def item_locator_hints(item_name: str) -> LocatorHint:
    strategies = [s.format(name=item_name) for s in PREFERRED_ITEM_SELECTORS]
    return LocatorHint(name=item_name, strategies=strategies)


def absolutize(base: str, href: str) -> str | None:
    if not href or href.startswith("javascript:") or href.startswith("mailto:"):
        return None
    return urljoin(base, href)
