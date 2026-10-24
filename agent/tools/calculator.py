"""calculator：安全地计算算术表达式。

不直接 eval（会执行任意代码），而是用 ast 解析后只放行算术节点，
从而既支持 + - * / // % ** 和括号，又杜绝 __import__、os.system 之类注入。
"""
from __future__ import annotations

import ast
import math
import operator

_BINOPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCS = {"sqrt": math.sqrt, "abs": abs, "round": round}


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        return _BINOPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS:
        return _FUNCS[node.func.id](*[_eval(a) for a in node.args])
    raise ValueError(f"不支持的表达式节点: {type(node).__name__}")


def calc(args: dict, ctx) -> str:
    expr = str(args.get("expr", "")).strip()
    if not expr:
        return "错误：表达式为空"
    try:
        return str(_eval(ast.parse(expr, mode="eval")))
    except Exception as exc:  # noqa: BLE001 —— 计算错误也要变成可读文本回传
        return f"错误：无法计算「{expr}」：{exc}"


def register_calculator(registry) -> None:
    registry.tool(
        name="calculator",
        description="计算一个算术表达式，返回数值结果。支持 + - * / // % ** 和括号，以及 sqrt()/abs()/round()。",
        parameters={
            "type": "object",
            "properties": {
                "expr": {"type": "string",
                         "description": "要计算的算术表达式，例如 '(1+2)*3' 或 'sqrt(16)+2'"},
            },
            "required": ["expr"],
        },
    )(calc)
