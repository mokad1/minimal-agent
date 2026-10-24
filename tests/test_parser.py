from agent.parser import parse_response
from agent.schema import LLMResponse, RawToolCall


def test_final_answer():
    step = parse_response(LLMResponse("你好", "", "stop", []))
    assert step.text == "你好" and not step.wants_tool


def test_tool_call_arguments_parsed():
    resp = LLMResponse("", "", "tool_calls",
                       [RawToolCall("c1", "calculator", '{"expr": "1+2"}')])
    step = parse_response(resp)
    assert step.wants_tool
    assert step.tool_calls[0].arguments == {"expr": "1+2"}
    assert step.finish_reason == "tool_calls"


def test_malformed_arguments_does_not_crash():
    resp = LLMResponse("", "", "tool_calls",
                       [RawToolCall("c1", "calculator", "{bad json")])
    step = parse_response(resp)
    assert step.wants_tool
    assert "_parse_error" in step.tool_calls[0].arguments


def test_reasoning_extracted():
    resp = LLMResponse("", "让我想想", "tool_calls",
                       [RawToolCall("c1", "weather", '{"city": "北京"}')])
    step = parse_response(resp)
    assert step.reasoning == "让我想想"


def test_content_before_toolcall_becomes_reasoning():
    resp = LLMResponse("我先查一下天气", "", "tool_calls",
                       [RawToolCall("c1", "weather", '{"city": "北京"}')])
    step = parse_response(resp)
    assert "我先查一下天气" in step.reasoning and step.text == ""
