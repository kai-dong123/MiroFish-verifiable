"""两个运行时守卫：让 camel 的记忆写入行为变得**可观察、可开关**。

这一层补的是上游一个结构性缺口：**camel 的两个失效都是静默的，而它们没有开关。**
没有开关就没有前后对照，没有前后对照就只能靠叙述 —— 所以这个模块的第一目的不是
「修」，是**让每一处改动都能被单独打开和关掉**，从而能被单独量到。

两个守卫各自对应一个已复现的失效：

**其一 · 切片**（`camel/agents/chat_agent.py` 的 `update_memory`）
记忆一装满、截断一启动，`remaining_budget = max(0, token_limit - ctx_tokens)`
（884 行）里的 `ctx_tokens` 是**截断之后**的上下文大小 —— 而截断干的事正是把
上下文填到贴着上限，所以这个残余预算**按构造就远小于待写的消息**。它还要再被
砍两刀：`base_chunk_size = max(1, remaining_budget) // 10`（933 行），
`chunk_body_limit = max(1, base_chunk_size - prefix_token_len)`（948 行，
`prefix_token_len` 是那个块前缀 `"[chunk 1/1000 of a long message]\\n"` 的
实测 token 数（943 行），在 `gpt-4o-mini` 的编码下是 **12**——但那是量出来的，
换个分词器就不是 12，所以这里不写死）。
这两刀之后，正文容量落到下界 `max(1, …)` 上 —— **只要残余预算不到 140 token，
`chunk_body_limit` 就恒为 1**，每块还各带一个十几 token 的前缀。于是**一次写入
膨胀一个数量级**，记录条数 1 条变几百条。这是个反馈环：记忆满 → 残余预算小 →
切片 → 膨胀 → 记忆更满。

收严后的判据是「**只有这条消息自己就超上限才该切**」。「预算只是紧」本该交给
`ScoreBasedContextCreator` —— 它的职责就是按分数驱逐旧记录。camel 把两种情形
用同一个条件合并了。

**其二 · 时间戳**（`ChatAgent._record_tool_calling`）
camel 写一次 tool 调用时**只读一次时钟**，用 `+1e-6` 把回执排在请求之后
（源码注释称「纳秒精度，避免碰撞」）。问题是这个 `1e-6` **比时钟自己的分辨率
还细两三个数量级**：`time.time_ns()` 在本机的最小步长约半毫秒
（`repro_02_timestamp.py` 第一节现场量，不引用外部数字）。

所以它分得开**一对**请求/回执（那是加在显式值上的算术，不看钟），却分不开
**两次调用**：一次模型响应里并排的两个 tool 调用，记录时前后脚读钟，**读到的是
同一个 `T`**。于是四条记录的时间戳是 `T、T+1e-6、T、T+1e-6`，而排序键
`(timestamp, -score)`（`score_based.py:_conversation_sort_key`）在时间戳相等时
按**分数高的在前**决胜负 —— 也就是**后写的那条排到前面**：

    assistant_B(T) · assistant_A(T) · func_B(T+1e-6) · func_A(T+1e-6)

第一个 assistant 带着 `tool_calls`，紧随其后的却是另一个 assistant，**不是它的
回执**。端点回 400 `insufficient tool messages following tool_calls message`，
而上层只记一行 `Agent ... error` 就继续跑 —— **该 agent 这一轮的动作整条消失**。

关键在于：**这个失效是第一个守卫的代价。** 切片没修时，写一次回执要落几百条记录、
要花好几毫秒，两次 tool 调用**必然跨拍**，于是误打误撞地免疫；而切片的修复
**全部目的就是让写入变快** —— 快进同一拍，碰撞才开始发生。两个守卫因此必须
能分开开关，否则分不清是谁动了什么。修法是让每个 agent 有一条严格递增的逻辑
时钟，「后写的一定有更大的时间戳」成为不变式；步长取**整整一拍**（1e-3），
取小了跨不出去。

**这两个守卫改的是第三方库的运行时行为。** 因此：默认不装，`install()` 显式调用，
被替换的原方法留在 `_state["original"]` 里、`uninstall()` 可完整还原，计数落进调用方
的产物。安装点在上游驱动脚本里（`backend/scripts/run_parallel_simulation.py`）。

**守卫是幂等的**：重复 `install()` 不会套第二层。
"""

from __future__ import annotations

import time

#: 逻辑时钟步长：每条记录与上一条之间**至少**推进这么多秒。
#:
#: 硬要求只有一条：**比 camel 那个 `1e-6` 的排序偏移大得多**（否则回执会被推得
#: 跟请求挤在一起，等于没修）。取 1e-3 是因为它正好落在**本机时钟一拍的量级**上
#: （半毫秒到一毫秒）—— 让逻辑时钟的刻度跟物理时钟同量级，读日志时两种数字
#: 不会混得没法分辨。**步长取任何大于 1e-6 的值都成立**，这里取的是好读的那个。
STEP = 1e-3

_state: dict = {
    "patched": False,
    "original": None,
    "target": None,
    "slicing": False,
    "timestamp": False,
    "written_whole": 0,
    "still_sliced": 0,
    "timestamp_pushed": 0,
}


def _next_timestamp(agent, timestamp):
    """这次写入该用哪个时间戳：每个 agent 一条**严格递增**的逻辑时钟。

    `timestamp_pushed` 只数我们自己取读数、却被推后的那些。camel 显式给的那对
    （请求 / 回执）**几乎总会被推**（它的 1e-6 小于一个步长），那是把门撑开、
    不是撞上门，所以不计数 —— **这个计数不是「撞窗口的次数」，别那样读它。**
    """
    last = getattr(agent, "_ts_guard_last", None)
    if timestamp is not None:
        value = timestamp
    else:
        value = time.time_ns() / 1e9
        if last is not None and value < last + STEP:
            _state["timestamp_pushed"] += 1
    if last is not None and value < last + STEP:
        value = last + STEP
    agent._ts_guard_last = value
    return value


def _note_timestamp(agent, timestamp):
    """交给原方法去写时，把游标推到**它可能用到的时间戳之外**。

    原方法自己那次读数我们看不到，而且它还会把一条消息切成若干块、每块再各自
    `+ i * 1e-6`。用一个步长当前缀，覆盖到 1000 块为止 —— 再多就说明这条消息
    被切成了一 token 一块，那是另一个守卫管的另一个事故。
    """
    value = timestamp if timestamp is not None else time.time_ns() / 1e9
    last = getattr(agent, "_ts_guard_last", None)
    agent._ts_guard_last = (value + STEP if last is None
                            else max(last, value) + STEP)


def _dispatch(self, message, role, timestamp=None):
    """替换 `ChatAgent.update_memory` 的那个函数。两个开关在这里读。"""
    original = _state["original"]

    if not _state["slicing"]:
        # 切片守卫没开：把时间戳换掉（若开了），其余原样交回。
        if _state["timestamp"]:
            return original(self, message, role,
                            _next_timestamp(self, timestamp))
        return original(self, message, role, timestamp)

    # -- 切片守卫开着：先判这条消息自己超没超上限 -------------------------
    try:
        creator = self.memory.get_context_creator()
        limit = creator.token_limit
        own_tokens = creator.token_counter.count_tokens_from_messages(
            [message.to_openai_message(role)])
    except Exception:  # noqa: BLE001
        # 算不出来就别自作聪明 —— 交回原方法。
        if _state["timestamp"]:
            _note_timestamp(self, timestamp)
        return original(self, message, role, timestamp)

    if own_tokens > limit:
        # 自己就超上限：切是必要的（不切谁也装不进去），交回原方法。
        _state["still_sliced"] += 1
        if _state["timestamp"]:
            _note_timestamp(self, timestamp)
        return original(self, message, role, timestamp)

    # 放得下：原样写。旧记录由 ScoreBasedContextCreator 按分数去驱逐。
    # 下面几行与 camel 自己的 `_write_single_record` 等价（那是闭包，取不到）。
    from camel.memories.records import MemoryRecord

    base_ts = (_next_timestamp(self, timestamp) if _state["timestamp"]
               else (timestamp if timestamp is not None
                     else time.time_ns() / 1e9))
    self.memory.write_record(MemoryRecord(
        message=message, role_at_backend=role,
        timestamp=base_ts, agent_id=self.agent_id))
    _state["written_whole"] += 1
    return None


def install(target=None, *, slicing: bool = True, timestamp: bool = True):
    """装上守卫。**幂等** —— 重复调用只改开关，不套第二层。

    Args:
        target: 带 `update_memory` 的类，默认 camel 的 `ChatAgent`。
            **这是给测试用的注入口**：传一个替身类就能在**不改真的 `ChatAgent`**、
            不发 LLM 的前提下把「该拦的拦、该切的不切」两个方向都测到。替身只需
            提供 `memory` / `agent_id` 两个属性（写入用的 `MemoryRecord` 是 camel
            的普通数据类，不需要模型）。见 `tests/test_camel_guards.py`。
        slicing: 切片守卫。
        timestamp: 时间戳守卫。**两个开关独立** —— 这是本模块存在的主要理由：
            第二个失效是第一个的代价，不拆开就分不清是谁动了什么。

    **顺序要求**：本模块 import camel，所以要放在 `import oasis` 之后调用
    （上游驱动脚本里就是那么放的）。
    """
    if _state["patched"]:
        _state["slicing"] = slicing
        _state["timestamp"] = timestamp
        return _state

    if target is None:
        from camel.agents.chat_agent import ChatAgent
        target = ChatAgent

    _state["target"] = target
    _state["original"] = target.update_memory
    _state["slicing"] = slicing
    _state["timestamp"] = timestamp
    target.update_memory = _dispatch
    _state["patched"] = True
    return _state


def set_flags(*, slicing=None, timestamp=None) -> dict:
    """只改开关、不重装。**量前后对照时用这个** —— 同一份代码、同一个进程。"""
    if slicing is not None:
        _state["slicing"] = slicing
    if timestamp is not None:
        _state["timestamp"] = timestamp
    return _state


def uninstall() -> None:
    """还原原方法并清零计数。"""
    if not _state["patched"]:
        return
    _state["target"].update_memory = _state["original"]
    _state["patched"] = False
    _state["target"] = None
    _state["original"] = None
    _state["slicing"] = False
    _state["timestamp"] = False
    _state["written_whole"] = 0
    _state["still_sliced"] = 0
    _state["timestamp_pushed"] = 0


def counters() -> dict:
    """给产物用的计数。**中性措辞** —— 见 `_next_timestamp` 的说明。"""
    return {"slicing": _state["slicing"], "timestamp": _state["timestamp"],
            "written_whole": _state["written_whole"],
            "still_sliced": _state["still_sliced"],
            "timestamp_pushed": _state["timestamp_pushed"]}
