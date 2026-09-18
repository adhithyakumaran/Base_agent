"""Parse failure DOM evidence into element records."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

from qa_orchestrator.models import DiscoveredElement


class _DomParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.elements: list[dict[str, str]] = []
        self._stack: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {k: (v or "") for k, v in attrs}
        node = {
            "tag": tag.lower(),
            "role": attr_map.get("role", ""),
            "name": attr_map.get("name", ""),
            "text": "",
            "aria-label": attr_map.get("aria-label", ""),
            "placeholder": attr_map.get("placeholder", ""),
            "data-testid": attr_map.get("data-testid", ""),
            "id": attr_map.get("id", ""),
            "title": attr_map.get("title", ""),
            "type": attr_map.get("type", ""),
        }
        self._stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        if not self._stack:
            return
        if self._stack[-1]["tag"] == tag.lower():
            node = self._stack.pop()
            text = node.pop("text", "").strip()
            node["text"] = text
            if tag.lower() in {"button", "input", "a", "select", "textarea"} or node.get("role"):
                self.elements.append(node)

    def handle_data(self, data: str) -> None:
        if self._stack:
            self._stack[-1]["text"] = (self._stack[-1].get("text", "") + data).strip()


def parse_dom_html(html: str) -> list[DiscoveredElement]:
    parser = _DomParser()
    try:
        parser.feed(html)
    except Exception:
        return _parse_dom_regex(html)
    out: list[DiscoveredElement] = []
    for idx, node in enumerate(parser.elements):
        attrs = {
            k: v
            for k, v in node.items()
            if k not in {"tag", "role", "text", "name"} and v
        }
        if node.get("name"):
            attrs["name"] = node["name"]
        role = node.get("role") or _implicit_role(node["tag"], node.get("type", ""))
        name = node.get("aria-label") or node.get("title") or node.get("text") or node.get("placeholder") or ""
        out.append(
            DiscoveredElement(
                element_id=f"dom-{idx}",
                role=role,
                name=name[:120],
                text=node.get("text", "")[:120],
                tag=node["tag"],
                attributes=attrs,
                interactive=node["tag"] in {"button", "input", "a", "select", "textarea"},
            )
        )
    return out


def _parse_dom_regex(html: str) -> list[DiscoveredElement]:
    elements: list[DiscoveredElement] = []
    pattern = re.compile(
        r"<(button|input|a|select|textarea)([^>]*)>(.*?)</\1>|<(input|button)([^>]*)/?>",
        re.I | re.S,
    )
    for idx, match in enumerate(pattern.finditer(html)):
        tag = (match.group(1) or match.group(4) or "input").lower()
        attr_blob = match.group(2) or match.group(5) or ""
        inner = (match.group(3) or "").strip()
        attrs = dict(re.findall(r'([\w-]+)\s*=\s*"([^"]*)"', attr_blob))
        role = attrs.get("role") or _implicit_role(tag, attrs.get("type", ""))
        name = attrs.get("aria-label") or attrs.get("title") or inner or attrs.get("placeholder") or ""
        elements.append(
            DiscoveredElement(
                element_id=f"dom-{idx}",
                role=role,
                name=name[:120],
                text=inner[:120],
                tag=tag,
                attributes=attrs,
                interactive=True,
            )
        )
    return elements


def load_dom_from_path(path: Path) -> list[DiscoveredElement]:
    if not path.exists():
        return []
    return parse_dom_html(path.read_text(encoding="utf-8", errors="ignore"))


def _implicit_role(tag: str, input_type: str) -> str:
    if tag == "button":
        return "button"
    if tag == "a":
        return "link"
    if tag == "input":
        if input_type in {"submit", "button"}:
            return "button"
        return "textbox"
    return tag
