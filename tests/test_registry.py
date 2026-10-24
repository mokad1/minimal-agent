import pytest

from agent.registry import Tool, ToolContext, ToolRegistry
from agent.schema import ToolCall

from helpers import FakeSession


def test_register_and_schema(registry):
    assert {"calculator", "search", "todo", "weather"} <= set(registry.names())
    schema = registry.as_openai_schema()
    by_name = {s["function"]["name"]: s for s in schema}
    assert by_name["calculator"]["type"] == "function"
    assert "expr" in by_name["calculator"]["function"]["parameters"]["properties"]


def test_duplicate_registration_raises():
    reg = ToolRegistry()

    def f(args, ctx):
        return "x"

    reg.register(Tool("t", "d", {"type": "object", "properties": {}}, f))
    with pytest.raises(ValueError):
        reg.register(Tool("t", "d", {"type": "object", "properties": {}}, f))


def test_call_tool(registry):
    res = registry.call(ToolCall("c1", "calculator", {"expr": "1+2"}),
                        ToolContext(FakeSession()))
    assert res.ok and res.output == "3"


def test_call_unknown_tool(registry):
    res = registry.call(ToolCall("c1", "nope", {}), ToolContext(FakeSession()))
    assert not res.ok and "不存在" in res.output


def test_call_tool_error_is_caught():
    reg = ToolRegistry()

    def boom(args, ctx):
        raise RuntimeError("boom")

    reg.register(Tool("boom", "d", {"type": "object", "properties": {}}, boom))
    res = reg.call(ToolCall("c1", "boom", {}), ToolContext(FakeSession()))
    assert not res.ok and "boom" in res.output
