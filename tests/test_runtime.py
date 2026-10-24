from agent.runtime import AgentRuntime
from agent.session import SessionManager
from agent.tools import build_default_registry

from helpers import FakeLLM, make_settings, resp


def build_runtime(script, settings=None):
    settings = settings or make_settings()
    sessions = SessionManager("SYS", settings.max_turns,
                              settings.max_tokens, settings.keep_turns)
    llm = FakeLLM(script)
    rt = AgentRuntime(llm, build_default_registry(), sessions, settings,
                      summarizer=lambda msgs: "SUMMARY")
    return rt, sessions, llm


def test_direct_reply():
    rt, _, _ = build_runtime([resp(content="你好，有什么可以帮你？")])
    assert rt.run("s1", "你好") == "你好，有什么可以帮你？"


def test_tool_loop_calculator():
    script = [
        resp(tool_calls=[("c1", "calculator", '{"expr": "1+2*3"}')], finish="tool_calls"),
        resp(content="结果是 7"),
    ]
    rt, _, llm = build_runtime(script)
    assert rt.run("s1", "1+2*3 等于多少") == "结果是 7"
    # 第二轮 LLM 确实收到了工具执行结果
    second_messages = llm.calls[1]["messages"]
    tool_msgs = [m for m in second_messages if m["role"] == "tool"]
    assert tool_msgs and tool_msgs[0]["content"] == "7"


def test_todo_multiturn_followup():
    script = [
        resp(tool_calls=[("c1", "todo", '{"operation":"add","task":"开会"}')], finish="tool_calls"),
        resp(content="已帮你记下待办：开会"),
        resp(tool_calls=[("c2", "todo", '{"operation":"list"}')], finish="tool_calls"),
        resp(content="你当前有一个待办：开会"),
    ]
    rt, _, _ = build_runtime(script)
    assert "已帮你记下" in rt.run("w1", "记一个待办：开会")
    assert "开会" in rt.run("w1", "我刚才记了什么待办？")


def test_sessions_isolated_via_runtime():
    script = [
        resp(tool_calls=[("c1", "todo", '{"operation":"add","task":"A待办"}')], finish="tool_calls"),
        resp(content="记好了"),
        resp(tool_calls=[("c2", "todo", '{"operation":"list"}')], finish="tool_calls"),
        resp(content="没有待办"),
    ]
    rt, _, _ = build_runtime(script)
    rt.run("w1", "记待办 A待办")
    assert "没有待办" in rt.run("w2", "我有哪些待办？")


def test_tool_error_fed_back_and_recovers():
    script = [
        resp(tool_calls=[("c1", "calculator", '{"expr": "1/0"}')], finish="tool_calls"),
        resp(content="这个表达式除数为零，无法计算。"),
    ]
    rt, _, llm = build_runtime(script)
    assert "无法计算" in rt.run("s1", "算 1/0")
    tool_msgs = [m for m in llm.calls[1]["messages"] if m["role"] == "tool"]
    assert any("错误" in m["content"] for m in tool_msgs)


def test_max_iterations_exceeded_is_reported():
    script = [resp(tool_calls=[(f"c{i}", "calculator", '{"expr":"1+1"}')], finish="tool_calls")
              for i in range(20)]
    rt, _, _ = build_runtime(script, settings=make_settings(max_iterations=3))
    assert "运行出错" in rt.run("s1", "算")


def test_trace_recorded():
    script = [
        resp(tool_calls=[("c1", "calculator", '{"expr":"1+1"}')], finish="tool_calls"),
        resp(content="=2"),
    ]
    rt, sessions, _ = build_runtime(script)
    rt.run("s1", "算 1+1")
    events = [e["type"] for e in sessions.get("s1").trace]
    assert "tool_call" in events
    assert "tool_result" in events
    assert "final_answer" in events


def test_compression_triggered_in_runtime():
    # 第 3 轮超过 max_turns=2，主循环应触发压缩（调用注入的 summarizer）
    settings = make_settings(max_turns=2, keep_turns=1)
    script = [resp(content="ok1"), resp(content="ok2"), resp(content="ok3")]
    rt, sessions, llm = build_runtime(script, settings=settings)
    rt.run("s1", "q1")
    rt.run("s1", "q2")
    rt.run("s1", "q3")

    s = sessions.get("s1")
    assert s.context.turn_count == 1  # 压缩后只保留最近 keep_turns 轮
    third = llm.calls[2]["messages"]
    assert any(m["role"] == "system" and "SUMMARY" in m["content"] for m in third)
    assert any(e["type"] == "compress" for e in s.trace)
