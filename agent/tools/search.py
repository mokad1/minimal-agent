"""search：mock 实现的搜索工具，返回内置知识库里的结果。"""
from __future__ import annotations

_KB = {
    "agent": "Agent 是一个能自主决定是否调用工具来完成任务的程序：它循环执行『接收输入 → 判断(回复/调工具) → 调工具 → 根据结果决定继续或返回』。",
    "todo": "待办(todo)工具用于记录和跟踪任务，支持新增、列出、切换完成、删除、清空。",
    "weather": "天气信息可通过 weather 工具按城市查询。",
    "python": "Python 是一门解释型、动态类型的编程语言，以可读性著称。",
    "context": "上下文(context)管理决定把用户输入、思考过程、工具调用与结果按角色放进消息列表，并在超长时压缩成摘要。",
    "session": "会话(session)代表一个独立对话窗口，拥有自己的上下文与工具状态，窗口之间互不影响。",
}


def search(args: dict, ctx) -> str:
    q = str(args.get("query", "")).strip().lower()
    if not q:
        return "错误：search 需要 query 参数"
    for key, text in _KB.items():
        if key in q:
            return text
    return f"没有找到与「{args.get('query', '')}」相关的资料（这是 mock 搜索，仅覆盖少量关键词）。"


def register_search(registry) -> None:
    registry.tool(
        name="search",
        description="在（mock）资料库中按关键词搜索，返回匹配的说明文字。",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
            },
            "required": ["query"],
        },
    )(search)
