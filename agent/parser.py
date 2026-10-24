"""LLM 输出解析：把一条 LLM 响应归类成三种信息之一——
思考过程 / 工具调用 / 最终答案。

这是 agent 循环里最关键、也最容易出 bug 的一步：不同模型对
content / reasoning_content / tool_calls 的返回习惯不同，这里统一收敛。
"""
from __future__ import annotations

import json

from .schema import AgentStep, LLMResponse, ToolCall


def parse_response(resp: LLMResponse) -> AgentStep:
    reasoning = (resp.reasoning or "").strip()
    text = (resp.content or "").strip()

    # 有些模型在“调用工具前”会先在 content 里写一段说明，把它归入思考过程。
    if resp.tool_calls and text:
        reasoning = "\n".join(x for x in (reasoning, text) if x)
        text = ""

    step = AgentStep(reasoning=reasoning, text=text)

    for raw in resp.tool_calls:
        args: dict = {}
        try:
            parsed = json.loads(raw.arguments) if raw.arguments else {}
            args = parsed if isinstance(parsed, dict) else {"_raw": parsed}
        except (json.JSONDecodeError, TypeError) as exc:
            # 参数 JSON 坏了：不要把整个循环搞崩，降级成空参数并带上错误信息，
            # 工具侧会因此返回“参数错误”，进而让模型重试。
            args = {"_parse_error": str(exc), "_raw": raw.arguments}
        step.tool_calls.append(ToolCall(id=raw.id, name=raw.name, arguments=args))

    # 归一化 finish_reason：有工具调用就是 tool_calls，否则视为结束。
    step.finish_reason = "tool_calls" if step.tool_calls else (resp.finish_reason or "stop")
    return step
