"""Session 管理：每个窗口一条独立会话，互不影响。

一条 Session 拥有：自己的 Context、自己的工具态（store，例如 todo 列表）、
自己的 trace 日志、以及活跃时间。

用户 A 的窗口 1 和窗口 2 是两条 Session，靠 session_id 区分；
用户随时可以切回任意窗口继续聊，彼此不串数据。
"""
from __future__ import annotations

import time

from .context import Context


class Session:
    def __init__(self, session_id: str, system_prompt: str,
                 max_turns: int, max_tokens: int, keep_turns: int) -> None:
        self.id = session_id
        self.context = Context(system_prompt, max_turns, max_tokens, keep_turns)
        self.store: dict = {}       # 会话级工具态（todo 等）
        self.trace: list[dict] = []  # 执行 / 工具调用日志
        self.created_at = time.time()
        self.last_active = time.time()

    def touch(self) -> None:
        self.last_active = time.time()


class SessionManager:
    def __init__(self, system_prompt: str, max_turns: int = 20,
                 max_tokens: int = 8000, keep_turns: int = 4) -> None:
        self.system_prompt = system_prompt
        self.max_turns = max_turns
        self.max_tokens = max_tokens
        self.keep_turns = keep_turns
        self._sessions: dict[str, Session] = {}

    def get_or_create(self, session_id: str) -> Session:
        if session_id not in self._sessions:
            self._sessions[session_id] = Session(
                session_id, self.system_prompt, self.max_turns,
                self.max_tokens, self.keep_turns)
        return self._sessions[session_id]

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def list_ids(self) -> list[str]:
        return list(self._sessions.keys())

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
