"""非交互演示：复现题目里的两个窗口场景，并打印每步 trace。

  窗口 1：查天气 + 记待办
  窗口 2：写周报 + 记待办
  然后回到窗口 1 做两次追问（纯对话追问 / 带工具追问），验证 session 隔离与记忆。
"""
import os
import sys

# 让 `python examples/demo.py` 也能从项目根目录导入 agent 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")  # Windows 下避免中文乱码
sys.stderr.reconfigure(encoding="utf-8")

from agent import AgentRuntime, LLMClient, SessionManager
from agent.config import load_settings
from agent.logger import setup_logging
from agent.prompts import SYSTEM_PROMPT
from agent.tools import build_default_registry


def main() -> None:
    setup_logging()
    settings = load_settings()
    if not settings.llm_api_key:
        print("缺少 AGENT_LLM_API_KEY。请在项目根目录建 .env 或设置环境变量，例如：")
        print("  AGENT_LLM_API_KEY=sk-你的令牌")
        sys.exit(1)

    llm = LLMClient(settings.llm_base_url, settings.llm_api_key,
                    settings.llm_model, temperature=settings.temperature)
    sessions = SessionManager(SYSTEM_PROMPT, settings.max_turns,
                              settings.max_tokens, settings.keep_turns)
    runtime = AgentRuntime(llm, build_default_registry(), sessions, settings)

    def say(sid, text):
        print("\n" + "=" * 60)
        print(f"[{sid}] 你> {text}")
        print(f"[{sid}] Agent> {runtime.run(sid, text)}")

    say("window-1", "帮我查一下北京的天气，并把“明天下午三点开会”记到待办里。")
    say("window-2", "帮我写一份本周工作周报，并把“周五前提交周报”记到待办里。")

    # 切回窗口 1：纯对话追问（验证记忆）
    say("window-1", "我刚才让你记了什么待办？")
    # 切回窗口 1：带工具追问
    say("window-1", "再帮我算一下 1+2*3 等于多少？")
    # 窗口 2 确认自己的待办（应只有“提交周报”，没有窗口 1 的“开会”）
    say("window-2", "我有哪些待办？")

    print("\n" + "=" * 60)
    print("Trace 总览：")
    for sid in sessions.list_ids():
        print(f"--- {sid} ---")
        for e in sessions.get(sid).trace:
            print(f"  [{e['type']}] {_brief(e)}")


def _brief(e) -> str:
    t = e["type"]
    if t == "user":
        return e["text"]
    if t == "final_answer":
        return e["text"]
    if t == "reasoning":
        return e["text"][:60]
    if t == "tool_call":
        return f"{e['name']}({e['arguments']})"
    if t == "tool_result":
        return e["output"][:80]
    return str(e)[:80]


if __name__ == "__main__":
    main()
