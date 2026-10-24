"""LLM 客户端：直接打 OpenAI 兼容的 /chat/completions，不依赖任何 agent 框架。

只做三件事：拼请求、发请求、把响应收敛成 LLMResponse。
不保存任何 agent 逻辑，纯“模型调用 + 异常处理”。
"""
from __future__ import annotations

import time

import requests

from .schema import LLMResponse, RawToolCall


class LLMError(Exception):
    """LLM 调用失败（网络/HTTP/结构异常）时抛出。"""


class LLMClient:
    def __init__(self, base_url: str, api_key: str, model: str,
                 temperature: float = 0.7, timeout: float = 60.0,
                 max_retries: int = 3) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.timeout = timeout
        self.max_retries = max_retries

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> LLMResponse:
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_err: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = requests.post(url, json=payload, headers=headers,
                                     timeout=self.timeout)
                if resp.status_code >= 400:
                    # 429/5xx 属于可重试的临时错误；4xx 直接报错，重试无意义。
                    if resp.status_code in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                        last_err = LLMError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                        time.sleep(2 ** attempt)
                        continue
                    raise LLMError(f"HTTP {resp.status_code}: {resp.text[:300]}")
                try:
                    data = resp.json()
                except ValueError as exc:
                    raise LLMError(f"响应不是合法 JSON: {resp.text[:200]}") from exc
                return self._parse(data)
            except requests.RequestException as exc:
                last_err = exc
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
                    continue
                raise LLMError(f"网络请求失败（重试 {self.max_retries} 次后）: {exc}") from exc

        raise LLMError(str(last_err))

    def _parse(self, data: dict) -> LLMResponse:
        try:
            choice = data["choices"][0]
            msg = choice["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"响应结构异常: {str(data)[:300]}") from exc

        tool_calls = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function", {})
            tool_calls.append(RawToolCall(
                id=tc.get("id", ""),
                name=fn.get("name", ""),
                arguments=fn.get("arguments") or "{}",
            ))

        return LLMResponse(
            content=msg.get("content") or "",
            reasoning=msg.get("reasoning_content") or msg.get("reasoning") or "",
            finish_reason=choice.get("finish_reason", "stop"),
            tool_calls=tool_calls,
        )
