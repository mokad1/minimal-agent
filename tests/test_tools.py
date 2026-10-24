from agent.registry import ToolContext
from agent.tools import calc, search, todo, weather

from helpers import FakeSession


def ctx():
    return ToolContext(FakeSession())


def test_calculator_basic():
    assert calc({"expr": "(1+2)*3"}, ctx()) == "9"


def test_calculator_rejects_code_injection():
    out = calc({"expr": "__import__('os').system('dir')"}, ctx())
    assert out.startswith("错误")


def test_todo_add_list_toggle_remove():
    c = ctx()
    assert "开会" in todo({"operation": "add", "task": "开会"}, c)
    assert "开会" in todo({"operation": "list"}, c)
    todo({"operation": "toggle", "id": 1}, c)
    assert "[x]" in todo({"operation": "list"}, c)
    todo({"operation": "remove", "id": 1}, c)
    assert "没有待办" in todo({"operation": "list"}, c)


def test_todo_isolated_per_session():
    a, b = ctx(), ctx()  # 两个独立 session
    todo({"operation": "add", "task": "A的待办"}, a)
    assert "A的待办" in todo({"operation": "list"}, a)
    assert "没有待办" in todo({"operation": "list"}, b)


def test_search_mock():
    assert "Agent" in search({"query": "什么是 agent"}, ctx())
    assert "没有找到" in search({"query": "zzz不存在"}, ctx())


def test_weather_deterministic():
    assert weather({"city": "北京"}, ctx()) == weather({"city": "北京"}, ctx())
    assert "北京" in weather({"city": "北京"}, ctx())
