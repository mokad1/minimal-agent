"""todo：题目要求必须实现的工具，按 session 隔离存储。

数据放在 ToolContext.session.store["todos"] 里，所以窗口 1 和窗口 2
各自的待办互不可见——这是 session 隔离最直观的体现。
"""
from __future__ import annotations

import time

_TODOS_KEY = "todos"


def _load(store: dict) -> list:
    return store.setdefault(_TODOS_KEY, [])


def _fmt(todos: list) -> str:
    if not todos:
        return "（当前没有待办）"
    lines = []
    for t in todos:
        mark = "[x]" if t["done"] else "[ ]"
        lines.append(f"{t['id']}. {mark} {t['text']}")
    return "\n".join(lines)


def todo(args: dict, ctx) -> str:
    op = args.get("operation", "list")
    todos = _load(ctx.store)

    if op == "add":
        text = str(args.get("task", "")).strip()
        if not text:
            return "错误：add 操作需要 task 参数"
        new_id = (todos[-1]["id"] + 1) if todos else 1
        todos.append({"id": new_id, "text": text, "done": False,
                      "created_at": time.time()})
        return f"已添加待办 #{new_id}：{text}\n当前列表：\n{_fmt(todos)}"

    if op == "list":
        return "当前待办列表：\n" + _fmt(todos)

    if op in ("toggle", "done"):
        tid = int(args.get("id", -1))
        for t in todos:
            if t["id"] == tid:
                t["done"] = not t["done"]
                state = "完成" if t["done"] else "未完成"
                return f"已标记待办 #{tid} 为{state}\n当前列表：\n{_fmt(todos)}"
        return f"错误：没有 id={tid} 的待办"

    if op == "remove":
        tid = int(args.get("id", -1))
        for i, t in enumerate(todos):
            if t["id"] == tid:
                removed = todos.pop(i)
                return f"已删除待办 #{tid}：{removed['text']}\n当前列表：\n{_fmt(todos)}"
        return f"错误：没有 id={tid} 的待办"

    if op == "clear":
        todos.clear()
        return "已清空所有待办"

    return f"错误：不支持的 operation「{op}」，可选 add/list/toggle/remove/clear"


def register_todo(registry) -> None:
    registry.tool(
        name="todo",
        description="管理用户的待办事项列表。operation 可选：add(新增，需 task)、list(列出)、toggle(切换完成状态，需 id)、remove(删除，需 id)、clear(清空)。",
        parameters={
            "type": "object",
            "properties": {
                "operation": {"type": "string",
                              "enum": ["add", "list", "toggle", "remove", "clear"]},
                "task": {"type": "string", "description": "待办内容，仅 add 需要"},
                "id": {"type": "integer", "description": "待办编号，仅 toggle/remove 需要"},
            },
            "required": ["operation"],
        },
    )(todo)
