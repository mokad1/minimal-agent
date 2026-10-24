"""日志 / trace：把每次决策、每个工具调用都留痕，方便排查和演示。

trace 直接写进 session.trace（结构化 list[dict]），
同时打一条可读日志到 stderr，两条路都有。
"""
from __future__ import annotations

import logging
import time

logger = logging.getLogger("agent")


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] agent: %(message)s"))
    root = logging.getLogger("agent")
    if not root.handlers:
        root.addHandler(handler)
    root.setLevel(level)


def trace(session, event_type: str, payload: dict) -> None:
    """往 session.trace 追加一条结构化事件，并打日志。"""
    entry = {"type": event_type, "ts": time.time(), **payload}
    session.trace.append(entry)
    logger.info("%s | %s | %s", session.id, event_type, _short(payload))


def _short(payload: dict) -> str:
    s = str(payload)
    return s if len(s) <= 300 else s[:300] + "..."
