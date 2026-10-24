"""核心 Agent Runtime：自己实现的主循环，不依赖任何 agent 框架。

循环步骤（对应题目要求）：
  Step 1  接收用户输入            -> run(session_id, user_input)
  Step 2  判断直接回复还是调用工具  -> LLM 输出后 parse_response 得到 AgentStep
  Step 3  调用工具                -> registry.call(...)
  Step 4  根据工具结果决定继续 loop 还是返回结果 -> 有 tool_calls 就继续，否则返回最终答案
"""
from __future__ import annotations

from .config import Settings
from .context import Context
from .llm import LLMClient, LLMError
from .logger import trace
from .parser import parse_response
from .registry import ToolContext, ToolRegistry
from .schema import LLMResponse
from .session import SessionManager


class AgentRuntime:
    def __init__(self, llm: LLMClient, registry: ToolRegistry,
                 sessions: SessionManager, settings: Settings,
                 summarizer=None) -> None:
        self.llm = llm
        self.registry = registry
        self.sessions = sessions
        self.settings = settings
        # 摘要函数可注入，测试时换成假函数，避免真实调用。
        self.summarizer = summarizer

    def run(self, session_id: str, user_input: str) -> str:
        """处理一条用户输入，返回最终答案（任何异常都转成可读文本，不向外崩）。"""
        session = self.sessions.get_or_create(session_id)
        session.touch()
        ctx: Context = session.context
        ctx.add_user(user_input)
        trace(session, "user", {"text": user_input})

        try:
            for _ in range(self.settings.max_iterations):
                if ctx.needs_compression():
                    summary = self._summarize(ctx)
                    ctx.compress(summary)
                    trace(session, "compress", {"note": "已压缩较早对话为摘要"})

                step = parse_response(self._call_llm(ctx))

                if step.reasoning:
                    trace(session, "reasoning", {"text": step.reasoning})

                if step.wants_tool:
                    # Step 3/4：有工具调用 -> 记录 assistant 消息，逐个执行，然后继续 loop
                    ctx.add_assistant(step)
                    for tc in step.tool_calls:
                        result = self.registry.call(tc, ToolContext(session))
                        ctx.add_tool_result(result)
                        trace(session, "tool_call",
                              {"name": tc.name, "arguments": tc.arguments})
                        trace(session, "tool_result",
                              {"name": result.name, "ok": result.ok,
                               "output": result.output})
                    continue

                # 没有工具调用 -> 最终答案，返回给用户
                ctx.add_assistant(step)
                trace(session, "final_answer", {"text": step.text})
                return step.text

            # 单轮内工具调用次数用尽（模型一直要调工具不给结论）
            raise LLMError(f"超过单轮最大工具调用次数 {self.settings.max_iterations}")
        except Exception as exc:  # noqa: BLE001 —— 兜底，任何异常都不崩
            trace(session, "error", {"error": str(exc)})
            return f"[运行出错] {exc}"

    def _call_llm(self, ctx: Context) -> LLMResponse:
        return self.llm.chat(ctx.build_messages(), self.registry.as_openai_schema())

    def _summarize(self, ctx: Context) -> str:
        """基础压缩：把较早的完整轮次总结成一段话。"""
        if self.summarizer is not None:
            return self.summarizer(ctx.build_messages())
        messages = ctx.build_messages()
        messages.append({
            "role": "user",
            "content": "请把以上对话要点压缩成一段简短摘要，保留关键事实和待办状态。",
        })
        resp = self.llm.chat(messages, tools=None)  # 不带工具，避免套娃
        return resp.content or ""
