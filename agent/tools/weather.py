"""weather：mock 实现的天气查询，按城市名做确定性哈希，同城结果稳定（便于测试）。"""
from __future__ import annotations

import hashlib

_COND = ["晴", "多云", "阴", "小雨", "雷阵雨", "雾"]


def weather(args: dict, ctx) -> str:
    city = str(args.get("city", "")).strip()
    if not city:
        return "错误：weather 需要 city 参数"
    h = int(hashlib.md5(city.encode("utf-8")).hexdigest(), 16)
    cond = _COND[h % len(_COND)]
    low = h % 15 + 5          # 5~19 度
    high = low + h % 12 + 3   # 比低温高 3~14 度
    return f"{city} 今天{cond}，气温 {low}~{high}°C（mock 数据，仅供演示）"


def register_weather(registry) -> None:
    registry.tool(
        name="weather",
        description="查询某个城市的天气（mock 数据，确定性结果）。",
        parameters={
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名，例如 '北京'"},
            },
            "required": ["city"],
        },
    )(weather)
