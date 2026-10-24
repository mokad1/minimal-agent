"""上下文管理：决定“把什么塞进 context、什么时候塞、放在哪个位置”。

塞进 context 的内容（按角色）：
  - system   : 系统提示词（位置 0）+ 压缩后产生的历史摘要（紧跟其后）
  - user     : 用户输入
  - assistant: 思考/叙述 + 工具调用（tool_calls）
  - tool     : 工具执行结果（用 tool_call_id 挂回对应调用）

管理策略：
  - 轮次上限 max_turns：超过后把最早的一批“完整轮次”压缩成一段摘要，
    塞回 system 之后、最近对话之前，旧消息删除 → 既保记忆又控长度。
  - 长度上限 max_tokens：用“中文 1 字≈1 token、英文 4 字符≈1 token”的简单启发式估算，
    够用即可，不追求精确。
"""
from __future__ import annotations

import json

from .schema import AgentStep, ToolResult


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数：中文按 1 字 1 token，其余按 4 字符 1 token。"""
    cjk = sum(1 for ch in text if "一" <= ch <= "鿿")
    other = len(text) - cjk
    return cjk + other // 4


def _dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


class Context:
    def __init__(self, system_prompt: str, max_turns: int = 20,
                 max_tokens: int = 8000, keep_turns: int = 4) -> None:
        self.system_prompt = system_prompt
        self.max_turns = max_turns
        self.max_tokens = max_tokens
        self.keep_turns = keep_turns
        self.messages: list[dict] = []   # 不含 system，正文消息列表
        self._turn_count = 0
        self._summary: str | None = None  # 压缩后的历史摘要

    @property
    def turn_count(self) -> int:
        return self._turn_count

    def add_user(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})
        self._turn_count += 1

    def add_assistant(self, step: AgentStep) -> None:
        msg: dict = {"role": "assistant",
                     "content": step.text if step.text else None}
        if step.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": _dumps(tc.arguments)},
                }
                for tc in step.tool_calls
            ]
        self.messages.append(msg)

    def add_tool_result(self, result: ToolResult) -> None:
        self.messages.append(
            {"role": "tool", "tool_call_id": result.call_id,
             "content": result.output}
        )

    def needs_compression(self) -> bool:
        if self._turn_count > self.max_turns:
            return True
        return self.estimate_total_tokens() > self.max_tokens

    def estimate_total_tokens(self) -> int:
        n = estimate_tokens(self.system_prompt)
        if self._summary:
            n += estimate_tokens(self._summary)
        for m in self.messages:
            n += estimate_tokens(m.get("content") or "")
            for tc in m.get("tool_calls") or []:
                n += estimate_tokens(str(tc.get("function", {}).get("arguments", "")))
        return n

    def compress(self, summary: str) -> None:
        """把最早的一批轮次替换成一段摘要，只保留最近 keep_turns 个用户轮次。

        传入的 summary 由调用方（runtime）用 LLM 生成。
        """
        if self._turn_count <= self.keep_turns:
            return
        user_idxs = [i for i, m in enumerate(self.messages) if m["role"] == "user"]
        if len(user_idxs) <= self.keep_turns:
            return
        cut = user_idxs[-self.keep_turns]
        self._summary = summary
        self.messages = self.messages[cut:]
        self._turn_count = self.keep_turns

    def build_messages(self) -> list[dict]:
        """每次调用 LLM 前用这个拼出完整 context：system(含摘要) + 正文。"""
        head = [{"role": "system", "content": self.system_prompt}]
        if self._summary:
            head.append({
                "role": "system",
                "content": "[以下是更早对话的摘要，请据此理解上下文]\n" + self._summary,
            })
        return head + self.messages
