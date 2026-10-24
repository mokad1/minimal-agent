"""配置：从环境变量 / .env 读取，附带合理默认值。"""
from __future__ import annotations

import os
from dataclasses import dataclass


_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_dotenv() -> None:
    """极简 .env 加载：只补环境变量里不存在的键，不依赖第三方库。

    先找当前工作目录，再找项目根目录。这样在 PyCharm 里直接运行
    examples/demo.py（工作目录是 examples/）也能读到根目录的 .env。
    """
    for path in (".env", os.path.join(_PROJECT_ROOT, ".env")):
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            return
        except FileNotFoundError:
            continue


@dataclass
class Settings:
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    temperature: float
    max_turns: int
    max_tokens: int
    keep_turns: int
    max_iterations: int


def load_settings() -> Settings:
    _load_dotenv()
    return Settings(
        llm_base_url=os.environ.get("AGENT_LLM_BASE_URL", "https://api.deepseek.com/v1"),
        llm_api_key=os.environ.get("AGENT_LLM_API_KEY", ""),
        llm_model=os.environ.get("AGENT_LLM_MODEL", "deepseek-v4-pro"),
        temperature=float(os.environ.get("AGENT_TEMPERATURE", "0.7")),
        max_turns=int(os.environ.get("AGENT_MAX_TURNS", "20")),
        max_tokens=int(os.environ.get("AGENT_MAX_TOKENS", "8000")),
        keep_turns=int(os.environ.get("AGENT_KEEP_TURNS", "4")),
        max_iterations=int(os.environ.get("AGENT_MAX_ITERATIONS", "8")),
    )
