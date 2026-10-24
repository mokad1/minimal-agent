# minimal-agent —— 从零实现的最小可用 Agent

不依赖任何 Agent 框架（langgraph / openhands / openclaw），用 Python 手写核心 Agent Runtime，
实现「接收输入 → 判断(回复/调工具) → 调工具 → 根据结果决定继续或返回」的主循环，
并配套工具注册、Session 隔离、Context 管理与基础压缩、异常处理与执行 trace。

---

## 一、功能清单（对照题目要求）

| 要求 | 实现 |
| --- | --- |
| 从零完成，不依赖 agent 框架 | 主循环 `agent/runtime.py` 手写，仅用 `requests` 直接打 OpenAI 兼容接口 |
| 基本循环 Step1~Step4 | `AgentRuntime.run()` 完整实现 |
| 至少三个工具，todo 必须 | `calculator` / `search`(mock) / `todo` / `weather`(mock)，共 4 个 |
| 工具注册机制（名称/描述/Schema） | `ToolRegistry` + `@registry.tool(...)` 装饰器 |
| LLM 输出解析（思考/工具调用/最终答案） | `agent/parser.py` |
| Session 管理（多窗口隔离） | `SessionManager`，每个 session 独立 Context + 工具态 + trace |
| Context 有效管理（轮次上限/记忆/追问/压缩） | `agent/context.py` |
| 异常处理 | LLM 重试、工具异常回传、坏 JSON 降级、循环次数兜底 |
| 工具调用 trace / 执行日志 | `agent/logger.py`，写 `session.trace` + 打日志 |
| 测试用例 | `tests/`，30 个用例，覆盖上述全部 |
| 真实 LLM API | OpenAI 兼容接口，已用 DeepSeek 官方接口实测（`deepseek-v4-pro`），任意 OpenAI 兼容网关可换 |

---

## 二、运行方式（快速开始）

### 1. 环境
- Python 3.10+
- `pip install -r requirements.txt`（只有 `requests` 和 `pytest`）

### 2. 配置真实 LLM
项目根目录建 `.env`（已提供 `.env.example` 可复制改）：

```bash
AGENT_LLM_BASE_URL=https://api.deepseek.com/v1   # 或任意 OpenAI 兼容网关，如 https://nodlink.cn/v1
AGENT_LLM_API_KEY=sk-你的令牌                     # 必填，不写死、不提交
AGENT_LLM_MODEL=deepseek-v4-pro                  # 诺联可用 gpt-5.5 等
```

也支持直接设环境变量（Windows：`set AGENT_LLM_API_KEY=sk-xxx`；Linux/Mac：`export ...`）。

### 3. 跑演示（复现题目里的两个窗口场景）

```bash
python examples/demo.py
```

它会用真实 LLM 依次执行：
- 窗口 1：查北京天气 + 记待办「明天下午三点开会」
- 窗口 2：写周报 + 记待办「周五前提交周报」
- 切回窗口 1：纯对话追问「我刚才记了什么待办？」（验证记忆）
- 窗口 1：带工具追问「算 1+2*3」（验证带工具追问）
- 窗口 2：确认自己的待办（验证隔离，应看不到窗口 1 的「开会」）

最后打印每个 session 的完整 trace。

### 4. 交互式 CLI

```bash
python examples/cli.py
# 直接输入=发消息；/new 新窗口；/switch <id> 切换；/sessions 列表；/trace 看日志；/quit 退出
```

### 5. 跑测试

```bash
python -m pytest -q
# 30 passed
```

测试用 `FakeLLM`（脚本式假模型）模拟 LLM 返回，**不依赖网络**，确定性可复现。

---

## 三、系统设计

### 目录结构

```
minimal-agent/
├── agent/
│   ├── runtime.py      # 核心主循环（AgentRuntime）
│   ├── llm.py          # OpenAI 兼容客户端（requests，含重试/异常）
│   ├── parser.py       # LLM 输出解析：思考/工具调用/最终答案
│   ├── registry.py     # 工具注册与执行（Tool / ToolRegistry / ToolContext）
│   ├── context.py      # 上下文：消息组装、轮次上限、基础压缩
│   ├── session.py      # Session / SessionManager（多窗口隔离）
│   ├── schema.py       # 数据类：ToolCall / ToolResult / AgentStep 等
│   ├── logger.py       # trace + 日志
│   ├── prompts.py      # 系统提示词
│   ├── config.py       # 环境变量配置
│   └── tools/          # 内置工具
│       ├── calculator.py   # 安全算术（ast 白名单）
│       ├── search.py       # mock 搜索
│       ├── todo.py         # 待办（按 session 隔离）
│       └── weather.py      # mock 天气（确定性）
├── examples/
│   ├── cli.py          # 交互式多窗口
│   └── demo.py         # 非交互演示
└── tests/              # 30 个用例
```

### Agent 主循环（核心）

`AgentRuntime.run(session_id, user_input)`：

```
Step 1  接收用户输入            -> 写入当前 session 的 Context（role=user）
Step 2  判断回复还是调工具        -> 拼好 context + 工具 Schema 调 LLM，parse_response 得到 AgentStep
Step 3  调用工具                -> 有 tool_calls：逐个 ToolRegistry.call，结果写回（role=tool）
Step 4  根据结果决定继续或返回    -> 还有 tool_calls 就 continue 回到 Step 2；否则返回最终答案给用户
```

关键点：
- **单轮内最多 `max_iterations` 次工具调用**（默认 8），防止模型无限要求调工具。
- 工具调用与结果以标准 OpenAI 消息协议回填：`assistant(tool_calls)` → `tool(tool_call_id, content)`，
  这样模型能看到「我调了什么、结果是什么」，是循环能闭环的基础。

### 工具注册机制

每个工具 = 名称 + 描述 + 参数 JSON Schema。LLM 只能看到 `as_openai_schema()` 生成的描述与 Schema，
据此**自主决策**调谁、传什么参数：

```python
registry.tool(
    name="calculator",
    description="计算一个算术表达式，返回数值结果。...",
    parameters={"type": "object", "properties": {"expr": {"type": "string", ...}},
                "required": ["expr"]},
)(calc)
```

`ToolContext` 会把 `session` 传给工具，于是 `todo` 能把待办存在 `session.store["todos"]` 里，
天然做到**按 session 隔离**。

新增一个工具只需三步：写一个 `fn(args, ctx)` 函数 → 用装饰器注册 → 完成。

### LLM 输出解析

`parse_response(LLMResponse) -> AgentStep` 把一条模型响应归一化成三种信息：
- **思考过程**：取 `reasoning_content`（DeepSeek 风格）；若模型在调工具前于 `content` 里写说明，也归入思考。
- **工具调用**：解析 `tool_calls[].function.arguments`（JSON 字符串 → dict）；坏 JSON 不崩，降级为带 `_parse_error` 的空参数，让工具报错后模型重试。
- **最终答案**：无 tool_calls 时 `text` 即答案。

### Session 管理

`SessionManager` 以 `session_id` 为键维护多条 `Session`。每条 Session 持有：
- 自己的 `Context`（消息历史）
- 自己的 `store`（工具态，如 todo 列表）
- 自己的 `trace`（执行日志）
- `created_at / last_active`

窗口 1 与窗口 2 是完全独立的两条 Session，随时可切回继续聊、互不串数据。

---

## 四、Memory：召回时机与放置方式

本版本没有向量检索，**Context 即内存**。策略如下：

### 放置方式（什么东西放哪）

| 位置 | 内容 | 说明 |
| --- | --- | --- |
| `system` #0 | 系统提示词 | 稳定不变的「角色 + 工具规则」，始终在第一位 |
| `system` #1 | 压缩摘要 | 仅在发生压缩后出现，紧跟系统提示词之后，作为被遗忘早期对话的替代 |
| `user` | 用户输入 | 每轮一条 |
| `assistant` | 叙述 + tool_calls | 记录「模型决定调哪个工具、传什么参数」 |
| `tool` | 工具执行结果 | 用 `tool_call_id` 挂回对应的 assistant 消息，模型据此判断下一步 |

**塞入 context 的信息**：用户输入、工具调用参数、工具执行结果、最终答案。
**不塞入 context 的信息**：思考过程（reasoning）。它只在 `session.trace` 里留痕，用于排查，不回填——
因为思考是模型内部推理，回填既多耗 token，又可能引入幻觉；这是本项目的一个显式取舍。
（若换用 DeepSeek-Reasoner 这类强依赖推理链的模型，可改成把 reasoning 也回填，改动点集中在 `Context.add_assistant`。）

### 召回时机

1. **每次调 LLM 前全量召回**：`Context.build_messages()` 把「系统提示词 + 摘要 + 全部历史消息」一次性拼给模型。
   「最小可用」版本不做过期的按需检索，靠**轮次/长度上限**来控制体积。
2. **压缩时机**：`Context.needs_compression()` 在每轮循环里检查，满足其一即触发：
   - 轮次数 > `max_turns`（默认 20）
   - 估算 token > `max_tokens`（默认 8000，用「中文 1 字≈1 token、英文 4 字符≈1 token」粗略估算）
3. **压缩动作**：`Context.compress(summary)` 保留最近 `keep_turns`（默认 4）个用户轮次，
   把更早的完整轮次交给 LLM 总结成一段摘要，塞回 system 之后；旧消息删除。
   摘要生成函数可注入（测试里注入假函数，避免真实调用）。

---

## 五、异常处理

| 场景 | 处理 |
| --- | --- |
| 网络/5xx/429 | `LLMClient` 指数退避重试 3 次，仍失败抛 `LLMError` |
| HTTP 4xx | 不重试，直接抛 `LLMError`（带上响应片段） |
| 响应不是合法 JSON / 结构异常 | 抛 `LLMError` |
| 工具抛异常 | `ToolRegistry.call` 捕获，包成 `ToolResult(ok=False)` 喂回给 LLM，模型可换参数重试或向用户解释 |
| 工具参数是坏 JSON | parser 降级为带 `_parse_error` 的参数，不崩 |
| 单轮工具调用次数用尽 | 抛 `LLMError`，返回「运行出错」文本 |
| 任何未预期异常 | `AgentRuntime.run` 兜底，转成可读文本返回，进程不崩 |

## 六、trace / 执行日志

每个 session 维护 `trace: list[dict]`，事件类型：`user / reasoning / tool_call / tool_result /
final_answer / compress / error`，同时打结构化日志到 stderr。
`examples/demo.py` 末尾会打印完整 trace，直观展示每一轮「模型想了什么、调了什么、得到什么」。

---

## 七、扩展：加一个自己的工具

```python
from agent.registry import ToolRegistry

def my_tool(args, ctx):
    return f"收到参数 {args}"

reg = ToolRegistry()
reg.tool(
    name="my_tool",
    description="一句话说明这个工具干什么",
    parameters={"type": "object", "properties": {...}, "required": [...]},
)(my_tool)
```

然后把 `reg` 传给 `AgentRuntime` 即可，LLM 会自动按 Schema 决定何时调用它。
