"""Canonical Playwright npm command builder — single source of truth."""

from __future__ import annotations

import re
from typing import Literal

FlowPolarity = Literal["positive", "negative"]

_FLOW_ID = re.compile(r"^BF-[A-Z0-9-]+$")


def _normalize_flow_id(flow_id: str) -> str:
    fid = flow_id.strip().lstrip("@")
    if not _FLOW_ID.fullmatch(fid):
        raise ValueError(f"invalid flow id: {flow_id!r}")
    return fid


def build_sanity_command(*, positive_only: bool = True) -> str:
    return "npm run test:sanity:positive" if positive_only else "npm run test:sanity"


def build_regression_command() -> str:
    return "npm run test:regression"


def build_flow_command(flow_id: str, *, polarity: FlowPolarity = "positive") -> str:
    fid = _normalize_flow_id(flow_id)
    if polarity == "positive":
        return f"npm run test:flow:positive -- {fid}"
    if polarity == "negative":
        return f"npm run test:flow:negative -- {fid}"
    raise ValueError(f"unknown flow polarity: {polarity!r}")


def build_negative_flow_commands(flow_ids: list[str]) -> list[str]:
    return [build_flow_command(fid, polarity="negative") for fid in flow_ids]


def build_positive_flow_commands(flow_ids: list[str]) -> list[str]:
    return [build_flow_command(fid, polarity="positive") for fid in flow_ids]
