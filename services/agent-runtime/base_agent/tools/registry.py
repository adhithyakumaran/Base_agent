from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field

from base_agent.contracts.enums import ExecutionMode
from base_agent.contracts.models import RunBudget


class RetryPolicy(BaseModel):
    max_attempts: int = 0
    backoff_ms: int = 200
    backoff_multiplier: float = 2.0
    retry_on: list[str] = Field(default_factory=list)


class ToolDefinition(BaseModel):
    name: str
    version: str = "1.0.0"
    description: str
    plugin_id: str
    capability: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    permissions: list[str] = Field(default_factory=list)
    timeout_ms: int = 10_000
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    execution_mode: ExecutionMode = ExecutionMode.DETERMINISTIC
    llm_visible: bool = False
    parallel_safe: bool = False
    idempotent: bool = True
    cost_class: str = "cheap"
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RawToolResult(BaseModel):
    ok: bool = True
    data: dict[str, Any] = Field(default_factory=dict)
    error_class: str | None = None
    error_message: str | None = None
    latency_ms: float = 0.0


class ExecutionContext(BaseModel):
    run_id: str
    permissions: list[str] = Field(default_factory=list)
    deadline_ms: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"arbitrary_types_allowed": True}


class Tool(Protocol):
    definition: ToolDefinition

    def validate_input(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def execute(self, payload: dict[str, Any], ctx: ExecutionContext) -> RawToolResult: ...

    def validate_output(self, raw: Any) -> dict[str, Any]: ...


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        name = tool.definition.name
        if name in self._tools:
            raise ValueError(f"duplicate tool: {name}")
        if not tool.definition.capability:
            raise ValueError(f"tool missing capability: {name}")
        self._tools[name] = tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(name)
        return self._tools[name]

    def list(self) -> list[ToolDefinition]:
        return [t.definition for t in self._tools.values()]

    def by_capability(self, capability: str) -> list[Tool]:
        return [t for t in self._tools.values() if t.definition.capability == capability]

    def filter(self, *, permissions: list[str] | None = None, llm_visible: bool | None = None,
               tags: list[str] | None = None) -> list[ToolDefinition]:
        out: list[ToolDefinition] = []
        for t in self._tools.values():
            d = t.definition
            if llm_visible is not None and d.llm_visible != llm_visible:
                continue
            if permissions is not None and not set(d.permissions).issubset(set(permissions)):
                # tool may require subset of granted perms
                if d.permissions and not set(d.permissions).issubset(set(permissions)):
                    continue
            if tags is not None and not set(tags).intersection(set(d.tags)):
                continue
            out.append(d)
        return out

    def llm_export(self, names: list[str]) -> list[dict[str, Any]]:
        export = []
        for name in names:
            d = self.get(name).definition
            export.append(
                {
                    "name": d.name,
                    "description": d.description,
                    "capability": d.capability,
                    "input_schema": d.input_schema,
                }
            )
        return export


class ToolExecutor:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def execute(self, name: str, payload: dict[str, Any], ctx: ExecutionContext) -> RawToolResult:
        import time

        tool = self.registry.get(name)
        # permission gate
        needed = set(tool.definition.permissions)
        granted = set(ctx.permissions)
        if needed and not needed.issubset(granted):
            return RawToolResult(
                ok=False,
                error_class="authorization_failure",
                error_message=f"missing permissions: {sorted(needed - granted)}",
            )
        try:
            validated = tool.validate_input(payload)
        except Exception as exc:  # noqa: BLE001
            return RawToolResult(ok=False, error_class="invalid_input", error_message=str(exc))

        start = time.perf_counter()
        try:
            raw = tool.execute(validated, ctx)
        except Exception as exc:  # noqa: BLE001
            from base_agent.errors.taxonomy import classify_exception

            return RawToolResult(
                ok=False,
                error_class=classify_exception(exc).value,
                error_message=str(exc),
                latency_ms=(time.perf_counter() - start) * 1000,
            )
        raw.latency_ms = (time.perf_counter() - start) * 1000
        if raw.ok:
            try:
                raw.data = tool.validate_output(raw.data)
            except Exception as exc:  # noqa: BLE001
                return RawToolResult(
                    ok=False,
                    error_class="validation_failure",
                    error_message=str(exc),
                    latency_ms=raw.latency_ms,
                )
        return raw


# silence unused import warning helpers
_ = RunBudget