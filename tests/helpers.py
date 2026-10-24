"""测试共用的小工具：假 LLM、构造响应、构造配置、假 session。"""
from __future__ import annotations

from agent.config import Settings
from agent.schema import LLMResponse, RawToolCall


def make_settings(**overrides) -> Settings:
    base = dict(
        llm_base_url="https://example.invalid/v1",
        llm_api_key="test-key",
        llm_model="test-model",
        temperature=0.0,
        max_turns=20,
        max_tokens=8000,
        keep_turns=4,
        max_iterations=8,
    )
    base.update(overrides)
    return Settings(**base)


class FakeLLM:
    """按脚本出牌：每次 .chat 依次弹出预设响应，并记录每次收到的 messages/tools。"""

    def __init__(self, script):
        self.script = list(script)
        self.calls: list[dict] = []

    def chat(self, messages, tools=None):
        self.calls.append({"messages": messages, "tools": tools})
        if not self.script:
            raise AssertionError("FakeLLM 脚本已用完")
        return self.script.pop(0)


def resp(content="", tool_calls=None, finish="stop", reasoning=""):
    """便捷构造 LLMResponse。tool_calls 传 [(id, name, args_json), ...]。"""
    tcs = []
    for (cid, name, args_json) in (tool_calls or []):
        tcs.append(RawToolCall(id=cid, name=name, arguments=args_json))
    return LLMResponse(content=content, reasoning=reasoning,
                       finish_reason=finish, tool_calls=tcs)


class FakeSession:
    """只有 id 和 store 的最小会话，用于 ToolContext 的测试。"""

    def __init__(self, sid="s1"):
        self.id = sid
        self.store: dict = {}
