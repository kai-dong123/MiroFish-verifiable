"""两个 camel 静默失效的运行时守卫（最小版）。

用法：在驱动脚本 `import oasis` 之后调用一次 `install()`。不改 `site-packages`，
只替换 `ChatAgent.update_memory`，`uninstall()` 可完整还原。

两个失效各有一条最小复现，见随附 issue：

1. 记忆切片：残余预算被 `// 10` 与 `- prefix_token_len` 两刀砍到 1，
   一条放得下的消息被切成一块一 token。这里改成「只有消息自己超上限才切」，
   其余交给 `ScoreBasedContextCreator` 按分数驱逐旧记录。
2. 同拍碰撞：`_record_tool_calling` 只读一次钟，用 `+1e-6` 排回执；这个偏移
   比时钟一拍还细，两次并排的 tool 调用会撞进同一拍，四条记录交错。
   这里给每个 agent 一条严格递增的逻辑时钟，步长取整整一拍（1e-3）。
"""
from __future__ import annotations

import time

#: 逻辑时钟步长：比 camel 的 `1e-6` 大得多，保证「后写的一定有更大的时间戳」。
STEP = 1e-3

_state = {"patched": False, "original": None, "target": None}


def _next_timestamp(agent, timestamp):
    last = getattr(agent, "_ts_guard_last", None)
    value = timestamp if timestamp is not None else time.time_ns() / 1e9
    if last is not None and value < last + STEP:
        value = last + STEP
    agent._ts_guard_last = value
    return value


def _hand_back_timestamp(agent, timestamp, own_tokens=None, content=None):
    """回退支也要把时间戳推过游标，并把游标抬到这条消息可能用到的最后一块之外。

    原方法会把一条消息切成若干块、每块再各自 `+ i * 1e-6`。块数上界：
    自己超上限那条支用 `own_tokens`；算不出 token 那条支用 UTF-8 字节数
    （byte-level BPE 每 token 至少吃 1 字节）。都拿不到才退回 1e-2。
    """
    base = timestamp if timestamp is not None else time.time_ns() / 1e9
    last = getattr(agent, "_ts_guard_last", None)
    value = max(base, last + STEP) if last is not None else base

    if own_tokens is not None:
        span = own_tokens * 1e-6
    elif isinstance(content, str):
        span = len(content.encode("utf-8")) * 1e-6
    else:
        span = 1e-2

    agent._ts_guard_last = value + span + STEP
    return value


def _dispatch(self, message, role, timestamp=None):
    original = _state["original"]

    try:
        creator = self.memory.get_context_creator()
        limit = creator.token_limit
        own_tokens = creator.token_counter.count_tokens_from_messages(
            [message.to_openai_message(role)])
    except Exception:  # noqa: BLE001
        return original(self, message, role,
                        _hand_back_timestamp(
                            self, timestamp,
                            content=getattr(message, "content", None)))

    if own_tokens > limit:
        return original(self, message, role,
                        _hand_back_timestamp(self, timestamp,
                                             own_tokens=own_tokens))

    from camel.memories.records import MemoryRecord

    base_ts = _next_timestamp(self, timestamp)
    self.memory.write_record(MemoryRecord(
        message=message, role_at_backend=role,
        timestamp=base_ts, agent_id=self.agent_id))
    return None


def install(target=None):
    """装上守卫；幂等。`target` 只给测试用。"""
    if _state["patched"]:
        return _state
    if target is None:
        from camel.agents.chat_agent import ChatAgent
        target = ChatAgent
    _state["target"] = target
    _state["original"] = target.update_memory
    target.update_memory = _dispatch
    _state["patched"] = True
    return _state


def uninstall():
    if not _state["patched"]:
        return
    _state["target"].update_memory = _state["original"]
    _state["patched"] = False
