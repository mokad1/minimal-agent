"""内置工具集合：calculator / search / todo / weather。"""
from .calculator import calc, register_calculator
from .search import register_search, search
from .todo import register_todo, todo
from .weather import register_weather, weather

__all__ = [
    "calc", "search", "todo", "weather",
    "register_calculator", "register_search", "register_todo", "register_weather",
    "build_default_registry",
]


def build_default_registry():
    """构造一个注册好四个内置工具的 ToolRegistry。"""
    from ..registry import ToolRegistry
    reg = ToolRegistry()
    register_calculator(reg)
    register_search(reg)
    register_todo(reg)
    register_weather(reg)
    return reg
