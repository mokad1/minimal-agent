"""工具注册机制。

每个工具由三要素组成：名称、描述、参数 JSON Schema。
LLM 只能看到 as_openai_schema() 生成的“描述 + Schema”，
并据此自主决定调用谁、传什么参数——这正是 agent 与普通脚本的区别。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .schema import ToolCall, ToolResult


class ToolContext:
    """传给工具函数的执行上下文，让工具能拿到会话级状态。

    典型用途：todo 工具把待办存在 ctx.store 里，按 session 隔离。
    """

    def __init__(self, session: Any):
        self.session = session

    @property
    def session_id(self) -> str:
        return self.session.id

    @property
    def store(self) -> dict:
        return self.session.store


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict  # 只描述 arguments 部分的 JSON Schema
    fn: Callable[[dict, ToolContext], Any]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> Tool:
        if tool.name in self._tools:
            raise ValueError(f"工具重复注册: {tool.name}")
        self._tools[tool.name] = tool
        return tool

    def tool(self, name: str, description: str, parameters: dict):
        """装饰器式注册：@registry.tool(name=..., description=..., parameters=...)。"""
        def deco(fn):
            self.register(Tool(name, description, parameters, fn))
            return fn
        return deco

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def as_openai_schema(self) -> list[dict]:
        """转成 OpenAI chat/completions 的 tools 参数格式。"""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self._tools.values()
        ]

    def call(self, call: ToolCall, ctx: ToolContext) -> ToolResult:
        """执行一次工具调用。

        工具抛出的任何异常都不向外崩，而是包成 ToolResult(ok=False) 喂回给 LLM，
        让模型有机会换参数重试或向用户解释。
        """
        tool = self.get(call.name)
        if tool is None:
            return ToolResult(
                call.id, call.name, call.arguments,
                output=f"错误：不存在工具 {call.name}",
                ok=False, error=f"unknown tool: {call.name}",
            )
        try:
            value = tool.fn(call.arguments, ctx)
            return ToolResult(call.id, call.name, call.arguments,
                              output=str(value), ok=True)
        except Exception as exc:  # noqa: BLE001 —— 工具层异常必须转成结果回传
            return ToolResult(
                call.id, call.name, call.arguments,
                output=f"工具执行出错：{exc}",
                ok=False, error=str(exc),
            )
