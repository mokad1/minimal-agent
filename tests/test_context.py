from agent.context import Context, estimate_tokens
from agent.schema import AgentStep, ToolCall, ToolResult


def make_ctx(**kw):
    kw.setdefault("system_prompt", "SYS")
    kw.setdefault("max_turns", 100)
    kw.setdefault("max_tokens", 10 ** 9)
    return Context(**kw)


def test_build_messages_starts_with_system():
    ctx = make_ctx()
    ctx.add_user("hi")
    assert ctx.build_messages()[0]["role"] == "system"


def test_history_preserved_across_turns():
    ctx = make_ctx()
    ctx.add_user("a")
    ctx.add_user("b")
    roles = [m["role"] for m in ctx.build_messages()]
    assert roles.count("user") == 2


def test_tool_roundtrip_in_messages():
    ctx = make_ctx()
    ctx.add_user("算 1+1")
    step = AgentStep(
        reasoning="", text="",
        tool_calls=[ToolCall("c1", "calculator", {"expr": "1+1"})],
        finish_reason="tool_calls",
    )
    ctx.add_assistant(step)
    ctx.add_tool_result(ToolResult("c1", "calculator", {"expr": "1+1"}, "2", True))
    msgs = ctx.build_messages()
    assert msgs[-1]["role"] == "tool" and msgs[-1]["tool_call_id"] == "c1"
    assert msgs[-2]["role"] == "assistant" and msgs[-2]["tool_calls"]


def test_compress_replaces_old_with_summary():
    ctx = make_ctx(max_turns=2, keep_turns=2)
    for i in range(5):
        ctx.add_user(f"u{i}")
    assert ctx.needs_compression()
    ctx.compress("SUMMARY")
    msgs = ctx.build_messages()
    # 摘要作为一条 system 消息紧跟系统提示词之后
    assert "SUMMARY" in msgs[1]["content"]
    assert ctx.turn_count == 2
    all_text = " ".join(str(m.get("content")) for m in msgs)
    assert "u0" not in all_text and "u4" in all_text


def test_estimate_tokens():
    assert estimate_tokens("你好") == 2    # 中文 1 字 1 token
    assert estimate_tokens("abcd") == 1    # 英文 4 字符 1 token
