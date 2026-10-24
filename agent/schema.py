"""核心数据结构：Agent 循环里流转的“协议对象”。

每个模块之间靠这些 dataclass 通信，而不是散落的 dict，
这样各层职责清楚，也方便在测试里构造假数据。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    """一次待执行的工具调用（参数已经解析成 dict）。"""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class RawToolCall:
    """LLM 返回的原始 tool_call，arguments 仍是 JSON 字符串，交给 parser 解析。"""
    id: str
    name: str
    arguments: str


@dataclass
class ToolResult:
    """工具执行结果，会被转成 role=tool 的消息喂回给 LLM。"""
    call_id: str
    name: str
    arguments: dict[str, Any]
    output: str
    ok: bool
    error: str | None = None


@dataclass
class LLMResponse:
    """LLM 原始返回的规范化结构。arguments 保留 JSON 字符串，由 parser 负责解析。"""
    content: str
    reasoning: str
    finish_reason: str
    tool_calls: list[RawToolCall] = field(default_factory=list)


@dataclass
class AgentStep:
    """一轮 LLM 决策：思考过程 + 可选工具调用，或最终答案。"""
    reasoning: str
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"

    @property
    def wants_tool(self) -> bool:
        return bool(self.tool_calls)
