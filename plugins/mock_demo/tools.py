from __future__ import annotations

from typing import Any

from base_agent.contracts.enums import ExecutionMode
from base_agent.tools.registry import ExecutionContext, RawToolResult, ToolDefinition


class _BaseMock:
    def validate_input(self, payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    def validate_output(self, raw: Any) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise ValueError("output must be object")
        return raw


class EchoTool(_BaseMock):
    definition = ToolDefinition(
        name="mock.demo.echo",
        description="Return the provided text unchanged",
        plugin_id="mock.demo",
        capability="demo.echo",
        input_schema={"type": "object", "required": ["text"], "properties": {"text": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"text": {"type": "string"}}},
        permissions=["tool.execute:mock.demo.*"],
        timeout_ms=1000,
        execution_mode=ExecutionMode.DETERMINISTIC,
        tags=["mock"],
    )

    def validate_input(self, payload: dict[str, Any]) -> dict[str, Any]:
        if "text" not in payload:
            raise ValueError("text required")
        return {"text": str(payload["text"])}

    def execute(self, payload: dict[str, Any], ctx: ExecutionContext) -> RawToolResult:
        return RawToolResult(ok=True, data={"text": payload["text"]})


class AddTool(_BaseMock):
    definition = ToolDefinition(
        name="mock.demo.add",
        description="Add two integers",
        plugin_id="mock.demo",
        capability="demo.add",
        input_schema={"type": "object", "required": ["a", "b"]},
        permissions=["tool.execute:mock.demo.*"],
        tags=["mock"],
    )

    def validate_input(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"a": int(payload["a"]), "b": int(payload["b"])}

    def execute(self, payload: dict[str, Any], ctx: ExecutionContext) -> RawToolResult:
        return RawToolResult(ok=True, data={"sum": payload["a"] + payload["b"]})


class BannerObserveTool(_BaseMock):
    """Mock observation for GT banner visibility tests."""

    definition = ToolDefinition(
        name="mock.demo.banner_observe",
        description="Observe promo banner visibility",
        plugin_id="mock.demo",
        capability="demo.banner",
        permissions=["tool.execute:mock.demo.*"],
        tags=["mock", "gt"],
    )

    def execute(self, payload: dict[str, Any], ctx: ExecutionContext) -> RawToolResult:
        visible = bool(payload.get("visible", False))
        return RawToolResult(ok=True, data={"visible": visible, "subject": "promo.banner.visibility"})


def register_mock_demo(registry) -> None:
    for tool in (EchoTool(), AddTool(), BannerObserveTool()):
        registry.register(tool)