"""替身模型：不发一个字节的网，把一整局 OASIS 仿真在**真路径**上跑起来。

## 为什么要有这个文件

本装置的四块里，「运行时守卫」一直缺一格证据：README 写着「**接上了，但端到端
跑过** —— 那要 API key」。这一格是本文件来推的。

推之前先纠正那句话：**「那要 API key」是错的。** `camel-ai==0.2.78` 自带
`StubModel`（`camel.models.stub_model`，`ModelType.STUB`），无 key 即可构造。
但 camel 那个替身**驱动不了守卫**，原因有两条，都是实测的：

1. 它返回的 `ChatCompletion` **不带 `tool_calls`** —— 而 OASIS 的动作环
   （`oasis/social_agent/agent.py:140`）就是读 `response.info['tool_calls']`
   来选动作的；没有 tool_call = 这一轮该 agent **静默什么都不做**。
2. 它的 `StubTokenCounter` **恒返 10**，于是「这条消息超没超上限」这个判断
   永远为假 —— 守卫读的正是这个数（`camel_guards.py:129-137`）。

所以本文件另写一个：**吐合法的 tool_call**、**用真分词器计数**。两个守卫的
判据分支才有可能被真实流量走到。

## 它和 camel 那个同名类不是一回事

名字里的 `Tool` 就是要区分开：`stub_model.ToolStubModel` ≠
`camel.models.stub_model.StubModel`。后者是「有个模型对象在那儿」，前者是
「有个会做动作的模型在那儿」。

## 它**无状态**，这是硬要求

`env.step()` 并发跑所有 agent，而 `chat_agent.py:468-471` 给**每个** agent 各包
一个 `ModelManager`、包的却是**同一个后端实例**；那个 `async with self.lock`
是每个 `ModelManager` 各自的，**不跨 agent 互斥**。所以行为只能由「构造参数 +
收到的消息」决定，**不许**用一个可变游标记「这次该吐第几个动作」。

## 边界（照实说）

替身换掉的是**模型的决策**，不是管线。`SocialAgent`、`AgentGraph`、OASIS 平台、
SQLite、记忆、工具调用环、写入路径**全是真的**。它**不**提供任何关于「仿真跑得
像不像真的」的证据 —— 那需要真模型，本装置不声称。
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional, Type

from camel.models.base_model import BaseModelBackend
from camel.types import (ChatCompletion, ChatCompletionMessage, Choice,
                         ModelType, UnifiedModelType)
from camel.utils import OpenAITokenCounter

#: 旋钮的环境变量名。端到端那条命令靠它们把三档臂喂进来 —— 替身活在一个
#: **子进程**里（跑的是真入口脚本），没法用函数参数传。
ENV_N_CALLS = "E2E_STUB_N_CALLS"
ENV_CONTENT_LEN = "E2E_STUB_CONTENT_LEN"
ENV_TEXT_LEN = "E2E_STUB_TEXT_LEN"
ENV_MAX_TOKENS = "E2E_STUB_MAX_TOKENS"

#: 上下文上限（= `max_tokens`）。**这个数不能乱调小**：它同时是
#: `ScoreBasedContextCreator` 的上限，收得太紧会让 `get_context()` 抛
#: `RuntimeError`，`chat_agent.py:2004-2007` 接住之后直接把这一轮终止掉 ——
#: agent 在能写任何东西之前就没了动作，看起来像「跑通了」，其实什么都没发生。
#: 实测 `max_tokens=150` 时一个动作都不发生、平台库里 0 条帖子。
DEFAULT_MAX_TOKENS = 4000

#: 动作名必须落在 agent 的 `_internal_tools` 里，否则 `chat_agent.py:2657` 的
#: `self._internal_tools[func_name]` 在 try **之前**抛 KeyError，一路冒到
#: `oasis/social_agent/agent.py:153-155` 被 `except Exception` 吞掉，只留一行
#: `Agent N error` —— 该 agent 这一轮的动作**静默消失**。
ACTION = "create_post"

#: 一次响应里放两个动作会连写 4 条记录（`T, T+1e-6, T, T+1e-6`，
#: `chat_agent.py:2739-2751`）—— 这正是时间戳守卫要治的同拍碰撞，
#: 所以「一次几个动作」是本装置要用的旋钮之一。
DEFAULT_N_CALLS = 1


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _tool_call(name: str, args: Dict[str, Any], cid: str) -> Dict[str, Any]:
    """OpenAI 那条 tool_call 的形状 —— `chat_agent.py:2549-2555` 逐字照着读：
    `.id` / `.function.name` / `.function.arguments`（**JSON 字符串**，不是 dict）。"""
    return {"id": cid, "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)}}


class ToolStubModel(BaseModelBackend):
    """会做动作的替身。见模块头。"""

    def __init__(self, *, n_calls: int = DEFAULT_N_CALLS,
                 content_len: int = 40, text_len: int = 0,
                 max_tokens: int = DEFAULT_MAX_TOKENS,
                 model_type: Any = ModelType.GPT_4O_MINI) -> None:
        self.n_calls = max(1, int(n_calls))
        self.content_len = max(0, int(content_len))
        #: 助手消息的**文本**长度。放大它才能逼出守卫的「放不下」分支 ——
        #: **放大 tool_call 的参数没用**：实测 content_len 取 40/3000/30000
        #: 三档，`written_whole` 都是 8，因为参数不进被记录的那条消息。
        self.text_len = max(0, int(text_len))
        super().__init__(
            model_type=model_type,
            model_config_dict={"max_tokens": int(max_tokens)},
            # 真分词器。用 `StubTokenCounter`（恒返 10）守卫就等于没装。
            token_counter=OpenAITokenCounter(UnifiedModelType("gpt-4o-mini")),
        )

    @property
    def token_counter(self):
        return self._token_counter

    def _mk(self) -> ChatCompletion:
        calls = [_tool_call(ACTION, {"content": "x" * self.content_len},
                            f"call_{i}") for i in range(self.n_calls)]
        return ChatCompletion(
            id="e2e-stub", object="chat.completion",
            created=int(time.time()), model="stub",
            choices=[Choice(
                index=0, finish_reason="tool_calls",
                message=ChatCompletionMessage(
                    role="assistant", content="y" * self.text_len,
                    tool_calls=calls))],
        )

    def _run(self, messages: List[Dict[str, Any]],
             response_format: Optional[Type] = None,
             tools: Optional[List[Dict[str, Any]]] = None) -> ChatCompletion:
        return self._mk()

    async def _arun(self, messages: List[Dict[str, Any]],
                    response_format: Optional[Type] = None,
                    tools: Optional[List[Dict[str, Any]]] = None
                    ) -> ChatCompletion:
        return self._mk()


def from_env() -> ToolStubModel:
    """按环境变量造一个。三档臂之间的差别全在这四个数上。"""
    return ToolStubModel(
        n_calls=_env_int(ENV_N_CALLS, DEFAULT_N_CALLS),
        content_len=_env_int(ENV_CONTENT_LEN, 40),
        text_len=_env_int(ENV_TEXT_LEN, 0),
        max_tokens=_env_int(ENV_MAX_TOKENS, DEFAULT_MAX_TOKENS),
    )
