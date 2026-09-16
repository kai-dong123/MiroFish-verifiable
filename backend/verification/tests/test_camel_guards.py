"""守卫自己的测试：**两个方向都测** —— 该拦的拦、该切的不切。

跑法（在 `backend/` 下，两种都行）：

    python -m pytest verification/tests -q
    pytest verification/tests -q

**不依赖 flask / zep**，只要装了 camel 就能跑。（上游 `tests/` 里那些要完整后端
才收集得动 —— 本目录刻意不掺进去，装置自己的门要自己能开。）

替身类（`stand_in()`）只提供 `memory` / `agent_id` 两个属性，所以这些测试
**不去改真的 `ChatAgent`**、不发 LLM、不花钱。唯一用到的 camel 东西是
`BaseMessage` / `MemoryRecord` / `OpenAIBackendRole` 三个**普通数据类**。

## 为什么替身类必须每次新造一个

`install(target=…)` 是在**类**上打补丁（`target.update_memory = _dispatch`）。
共用一个替身类，前一个测试装的补丁就会漏进后一个 —— 而且漏得静默。所以
`stand_in()` 每次 `type(...)` 造一个新类。

## 「该切的不切」为什么也要测

只测「该拦的拦」会漏掉最坏的一种改法：**把守卫写成「一律不切」**。
那样切片事故的测试全绿，而一条自己就超上限的消息会被整条塞进记忆 ——
换个方向坏掉。所以两个方向都得钉住。
"""

from __future__ import annotations

import argparse
import time

import pytest

from verification import camel_guards as G

from camel.memories.records import MemoryRecord
from camel.messages import BaseMessage
from camel.types import OpenAIBackendRole


# --------------------------------------------------------------------------
# 替身：只提供守卫真正会读到的东西
# --------------------------------------------------------------------------


class _Counter:
    """把消息内容**当整数读成 token 数** —— 让测试完全控制「放不放得下」。

    不估、不近似：`content="7"` 就是 7 token。守卫的判据是
    `own_tokens > token_limit`，边界要能精确地踩。
    """

    def count_tokens_from_messages(self, messages):
        return sum(int(str(m.get("content") or "0")) for m in messages)


class _Creator:
    def __init__(self, token_limit):
        self.token_limit = token_limit
        self.token_counter = _Counter()


class _Memory:
    def __init__(self, token_limit, *, explode=False):
        self.records = []
        self._creator = _Creator(token_limit)
        self._explode = explode       # 模拟「算不出 token」那条兜底路径

    def get_context_creator(self):
        if self._explode:
            raise RuntimeError("模拟取不到 context creator")
        return self._creator

    def write_record(self, record):
        self.records.append(record)


def stand_in(token_limit: int = 100, *, explode: bool = False):
    """造一个**全新的**替身类（理由见模块 docstring）。返回那个类。

    它的 `update_memory` 记下每次收到的 `(message, role, timestamp)` —— 于是
    「原方法被调了几次、拿到的时间戳是什么」在测试里是可读的，不用去猜。
    """

    class _StandIn:
        def __init__(self):
            self.memory = _Memory(token_limit, explode=explode)
            self.agent_id = "stand-in"
            self.seen = []

        def update_memory(self, message, role, timestamp=None):
            self.seen.append((message, role, timestamp))
            # 照 camel 的样子补默认读数（`chat_agent.py:859`：`timestamp` 为 None 时
            # 自己读钟）。**不能把 None 直接塞进 MemoryRecord** —— 那个字段是 float。
            base_ts = (timestamp if timestamp is not None
                       else time.time_ns() / 1e9)
            self.memory.write_record(
                MemoryRecord(message=message, role_at_backend=role,
                             timestamp=base_ts, agent_id=self.agent_id))

    return _StandIn


def msg(tokens: int, text: str = "x") -> BaseMessage:
    """一条**内容可当 token 数读**的消息：`msg(7)` 就是 7 token。"""
    return BaseMessage.make_user_message(role_name="User", content=str(tokens))


USER = OpenAIBackendRole.USER


# --------------------------------------------------------------------------
# 装卸：幂等、可还原、不留痕
# --------------------------------------------------------------------------


def test_install_is_idempotent():
    """重复 `install()` 只改开关，**不套第二层**。"""
    T = stand_in()
    original = T.update_memory

    G.install(T, slicing=True, timestamp=True)
    assert G._state["original"] is original
    G.install(T, slicing=False, timestamp=True)      # 第二次

    assert G._state["patched"] is True
    # 原方法仍是**最初那个**，不是第一层的 `_dispatch`
    assert G._state["original"] is original
    assert T.update_memory is G._dispatch, "被套了两层：补丁成了补丁的‘原方法’"

    # 套两层的话，写一条消息会经过两条 `_dispatch`，计数会翻倍
    G.set_flags(slicing=True, timestamp=False)
    agent = T()
    agent.update_memory(msg(5), USER)
    assert G.counters()["written_whole"] == 1


def test_uninstall_restores_original_and_clears_counters():
    T = stand_in()
    original = T.update_memory

    G.install(T, slicing=True, timestamp=True)
    agent = T()
    agent.update_memory(msg(5), USER)
    assert G.counters()["written_whole"] == 1

    G.uninstall()

    assert T.update_memory is original, "没还原回原方法"
    assert G._state["patched"] is False
    assert G._state["original"] is None
    assert G.counters() == {"slicing": False, "timestamp": False,
                            "written_whole": 0, "still_sliced": 0,
                            "timestamp_pushed": 0}


def test_uninstall_without_install_is_noop():
    """没装就卸 —— 不该炸，也不该把状态搞乱。"""
    G.uninstall()
    assert G._state["patched"] is False

    T = stand_in()
    original = T.update_memory
    G.uninstall()
    assert T.update_memory is original


# --------------------------------------------------------------------------
# 方向一：该拦的拦
# --------------------------------------------------------------------------


def test_whole_write_when_message_fits():
    """消息自己放得下 → **整条写入**，不交给原方法去切。"""
    T = stand_in(token_limit=100)
    G.install(T, slicing=True, timestamp=False)
    agent = T()

    agent.update_memory(msg(7), USER)

    c = G.counters()
    assert c["written_whole"] == 1
    assert c["still_sliced"] == 0
    assert agent.seen == [], "原方法被调了 —— 那就没拦住"
    assert len(agent.memory.records) == 1, "应该只有一条记录"
    assert agent.memory.records[0].message.content == "7"


def test_write_uses_the_agents_own_identity():
    """写进去的记录要带上这个 agent 的 id —— 否则记忆会串味。"""
    T = stand_in()
    G.install(T, slicing=True, timestamp=False)
    agent = T()

    agent.update_memory(msg(3), USER)

    rec = agent.memory.records[0]
    assert rec.agent_id == "stand-in"
    assert rec.role_at_backend is USER


# --------------------------------------------------------------------------
# 方向二：该切的不切（**这一个方向和上一个同等重要**）
# --------------------------------------------------------------------------


def test_hands_back_when_message_itself_exceeds_limit():
    """消息**自己就超上限** → 切片是必要的，原样交回原方法。"""
    T = stand_in(token_limit=100)
    G.install(T, slicing=True, timestamp=False)
    agent = T()

    agent.update_memory(msg(101), USER)

    c = G.counters()
    assert c["still_sliced"] == 1
    assert c["written_whole"] == 0, "把一条自己就超上限的消息整条塞进去了"
    assert len(agent.seen) == 1, "应该交回原方法"


def test_boundary_is_strict_greater_not_greater_equal():
    """边界：`own == limit` 时**放得下**，走整条写入。

    守卫里是 `if own_tokens > limit`。写成 `>=` 的后果是每条正好顶格的消息
    都被交回去切 —— 而顶格恰恰是最常见的情形之一。所以这一格单独钉。
    """
    T = stand_in(token_limit=100)
    G.install(T, slicing=True, timestamp=False)

    agent = T()
    agent.update_memory(msg(100), USER)              # 正好顶格
    assert G.counters()["written_whole"] == 1
    assert G.counters()["still_sliced"] == 0

    agent.update_memory(msg(101), USER)              # 越界一格
    assert G.counters()["still_sliced"] == 1


def test_hands_back_when_tokens_cannot_be_counted():
    """算不出 token 时**别自作聪明** —— 交回原方法，不崩。"""
    T = stand_in(explode=True)
    G.install(T, slicing=True, timestamp=False)
    agent = T()

    agent.update_memory(msg(7), USER)               # 不该抛

    c = G.counters()
    assert c["written_whole"] == 0
    assert len(agent.seen) == 1, "算不出来时应该原样交回"


# --------------------------------------------------------------------------
# 不装 == 上游行为（这是「默认 off」的判据）
# --------------------------------------------------------------------------


def test_slicing_off_is_transparent():
    """切片开关关掉时，每一次写入都原样落到原方法，**一个计数都不动**。"""
    T = stand_in()
    G.install(T, slicing=False, timestamp=False)
    agent = T()

    agent.update_memory(msg(7), USER)
    agent.update_memory(msg(500), USER)

    assert len(agent.seen) == 2
    c = G.counters()
    assert (c["written_whole"], c["still_sliced"], c["timestamp_pushed"]) == (0, 0, 0)
    # 显式传的 timestamp 也没被动过
    assert agent.seen[0][2] is None


# --------------------------------------------------------------------------
# 两个开关**独立** —— 这是本模块存在的主要理由
# --------------------------------------------------------------------------


def test_slicing_on_timestamp_off_leaves_timestamps_untouched():
    T = stand_in()
    G.install(T, slicing=True, timestamp=False)
    agent = T()

    agent.update_memory(msg(5), USER, timestamp=1234.0)

    assert G.counters()["written_whole"] == 1
    assert agent.memory.records[0].timestamp == 1234.0, "时间戳不该被切片开关碰"


def test_timestamp_on_slicing_off_only_moves_the_clock():
    """切片关、时间戳开：其余仍原样交回，但时钟被排成**严格递增**。

    注意守卫是**往后推**、不是**替换**：第一条没有更早的记录可比，**不该被动**；
    第二条才会被推开来。把这一格写下来，是因为「替换」和「往后推」在
    `timestamp_pushed` 的读法上不一样（见 `_next_timestamp` 的说明）。
    """
    T = stand_in()
    G.install(T, slicing=False, timestamp=True)
    agent = T()

    agent.update_memory(msg(5), USER, timestamp=1234.0)
    agent.update_memory(msg(5), USER, timestamp=1234.0)      # 同一个 T

    assert len(agent.seen) == 2, "切片关着时应该原样交回原方法"
    c = G.counters()
    assert (c["written_whole"], c["still_sliced"]) == (0, 0)

    ts = [r.timestamp for r in agent.memory.records]
    assert ts[0] == 1234.0, "第一条不该被动 —— 它是往后推，不是替换"
    assert ts[1] >= ts[0] + G.STEP - 1e-9, "第二条没被推开 —— 同拍碰撞没被修掉"


def test_set_flags_does_not_reinstall():
    """`set_flags` 只改开关 —— 量前后对照就靠它（同一份代码、同一个进程）。"""
    T = stand_in()
    G.install(T, slicing=True, timestamp=True)
    original = G._state["original"]

    G.set_flags(slicing=False)

    assert G._state["patched"] is True
    assert G._state["original"] is original, "set_flags 重新装了"
    assert G.counters()["slicing"] is False
    assert G.counters()["timestamp"] is True


def test_set_flags_without_install_does_not_patch():
    """没装时 `set_flags` 只改标志位 —— 不该顺手把补丁装上。"""
    T = stand_in()
    original = T.update_memory

    G.set_flags(slicing=True, timestamp=True)

    assert G._state["patched"] is False
    assert T.update_memory is original


# --------------------------------------------------------------------------
# 时间戳守卫：严格递增
# --------------------------------------------------------------------------


def test_timestamp_is_strictly_increasing_across_calls():
    """连续写入必须**严格递增**，且至少差一个逻辑步长。"""
    T = stand_in()
    G.install(T, slicing=True, timestamp=True)
    agent = T()

    for _ in range(5):
        agent.update_memory(msg(5), USER)

    ts = [r.timestamp for r in agent.memory.records]
    assert len(ts) == 5
    for a, b in zip(ts, ts[1:]):
        assert b >= a + G.STEP, f"{a} → {b} 没拉开一个步长"


def test_explicit_pair_is_pushed_apart_but_not_counted():
    """camel 显式给的那一对（`T` 与 `T+1e-6`）会被推开，但**不进计数**。

    这就是 README 里那条 ⚠️ 说的：`timestamp_pushed` **不是「撞窗口的次数」**。
    请求/回执那一对几乎总会被推 —— 那是把次序撑开，不是撞上。
    """
    T = stand_in()
    G.install(T, slicing=True, timestamp=True)
    agent = T()

    agent.update_memory(msg(5), USER, timestamp=1000.0)         # 请求
    agent.update_memory(msg(5), USER, timestamp=1000.0 + 1e-6)  # 回执

    ts = [r.timestamp for r in agent.memory.records]
    # 用近似比较：1000.001 - 1000.0 在浮点下略小于 1e-3，直接 `>=` 会假红
    assert ts[1] - ts[0] >= G.STEP - 1e-9, "回执没被推得足够远"
    assert G.counters()["timestamp_pushed"] == 0, \
        "显式给的那一对不该进计数 —— 这个计数只数我们自己读钟读挤了的次数"


def test_timestamp_pushed_counts_only_our_own_reads():
    """我们自己取读数、却落在上一条的步长以内 → 计数 +1。"""
    T = stand_in()
    G.install(T, slicing=True, timestamp=True)
    agent = T()

    # 先把游标推到一个**未来**的值，再让守卫自己去读钟 —— 读数必然不够大
    future = time.time_ns() / 1e9 + 1000.0
    agent.update_memory(msg(5), USER, timestamp=future)
    agent.update_memory(msg(5), USER)                # timestamp=None，守卫自己读

    assert G.counters()["timestamp_pushed"] == 1
    ts = [r.timestamp for r in agent.memory.records]
    assert ts[1] >= ts[0] + G.STEP


def test_step_is_larger_than_camels_offset():
    """步长的**唯一硬要求**：比 camel 那个 `1e-6` 大得多。

    取小了会把回执推得跟请求挤在一起，等于没修。这个断言把那条要求钉住 ——
    以后有人把 `STEP` 调小，这里先红。
    """
    assert G.STEP > 1e-6 * 100


# --------------------------------------------------------------------------
# counters()
# --------------------------------------------------------------------------


def test_counters_shape():
    T = stand_in()
    G.install(T, slicing=True, timestamp=True)
    assert set(G.counters()) == {
        "slicing", "timestamp", "written_whole", "still_sliced",
        "timestamp_pushed"}
    assert G.counters()["slicing"] is True
    assert G.counters()["timestamp"] is True


# --------------------------------------------------------------------------
# 驱动脚本那一侧：--guards 四档，**默认 off**
# --------------------------------------------------------------------------


def _args(spec=None):
    parser = argparse.ArgumentParser()
    from verification.attach import add_guard_argument
    add_guard_argument(parser)
    argv = [] if spec is None else ["--guards", spec]
    return parser.parse_args(argv)


def test_attach_default_is_off():
    """**默认 off：不装。** 一个能对比「装与不装」的装置，默认必须是不装。"""
    from verification.attach import install_if_requested

    args = _args()
    assert args.guards == "off"
    assert install_if_requested(args, log=lambda *_: None) is False
    assert G._state["patched"] is False


def test_attach_choices_cover_both_and_each_alone():
    from verification.attach import install_if_requested
    for spec, want in (("slicing", (True, False)),
                       ("timestamp", (False, True)),
                       ("both", (True, True))):
        G.uninstall()
        args = _args(spec)
        assert install_if_requested(args, log=lambda *_: None) is True
        c = G.counters()
        assert (c["slicing"], c["timestamp"]) == want, f"--guards {spec} 档位不对"


def test_attach_unknown_spec_does_nothing():
    """`choices` 挡不住的取值（比如直接构造 args）不该装上半套。"""
    from verification.attach import install_if_requested

    class _A:
        guards = "slicing+both"

    assert install_if_requested(_A(), log=lambda *_: None) is False
    assert G._state["patched"] is False


def test_attach_logging_failure_does_not_block_install():
    """日志后端出问题不该拦住装守卫 —— 那是两件事。"""
    from verification.attach import install_if_requested

    def _boom(*_):
        raise RuntimeError("日志后端坏了")

    assert install_if_requested(_args("both"), log=_boom) is True
    assert G._state["patched"] is True
