"""交互式命令行：一个进程里可开多个窗口（session），随时切换继续聊，互不影响。

用法：
    python examples/cli.py

命令：
    直接输入       -> 向当前窗口发消息
    /new           -> 新开一个窗口并切过去
    /switch <id>   -> 切换到指定窗口
    /sessions      -> 列出所有窗口
    /trace         -> 打印当前窗口的执行 trace
    /quit          -> 退出
"""
import os
import sys

# 让 `python examples/cli.py` 也能从项目根目录导入 agent 包
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

    cur = "window-1"
    sessions.get_or_create(cur)
    print("已就绪。直接输入开始对话；/new 新窗口；/switch <id> 切换；"
          "/sessions 列表；/trace 看执行日志；/quit 退出")

    while True:
        try:
            raw = input(f"[{cur}] 你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not raw:
            continue
        if raw == "/quit":
            break
        if raw == "/sessions":
            print("窗口:", ", ".join(sessions.list_ids()) or "(无)")
            continue
        if raw.startswith("/switch "):
            target = raw.split(None, 1)[1].strip()
            if sessions.get(target) is None:
                print(f"窗口 {target} 不存在")
            else:
                cur = target
                print(f"已切换到 {cur}")
            continue
        if raw == "/new":
            n = len(sessions.list_ids()) + 1
            cur = f"window-{n}"
            sessions.get_or_create(cur)
            print(f"已新建并切换到 {cur}")
            continue
        if raw == "/trace":
            sess = sessions.get(cur)
            for e in (sess.trace if sess else []):
                print(f"  [{e['type']}] {_brief(e)}")
            continue

        answer = runtime.run(cur, raw)
        print(f"[{cur}] Agent> {answer}")


def _brief(e) -> str:
    t = e["type"]
    if t in ("user", "final_answer", "reasoning"):
        return e.get("text", "")
    if t == "tool_call":
        return f"{e['name']}{e['arguments']}"
    if t == "tool_result":
        return e.get("output", "")
    return str(e)


if __name__ == "__main__":
    main()
