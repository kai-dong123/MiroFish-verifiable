"""离线探针的共享底座：**不发 LLM、不联网、不要 API key、不花钱、结果确定**。

三个复现脚本都靠这里的四件东西。它们能被离线跑，是因为 camel 里出问题的那些
路径**只碰记忆对象和时钟**，不碰模型：

1. **裸 agent**（`bare_agent`）—— 用 `ChatAgent.__new__` 绕过 `__init__`。
   真造一个 `ChatAgent` 要一个模型后端；而这里要测的是**写入决策**，与模型无关。
   `update_memory` 用到的属性只有 `memory`、`agent_id`、`_system_message` 三个。

2. **把记忆灌到截断启动**（`fill_until_truncating`）—— 切片那条路径的**前提状态**
   是「记忆已满、驱逐已开始」。不把这个状态造出来，切片分支根本不会被走到，
   探针会静静地测了个空气。

3. **可冻结的时钟**（`frozen_clock`）—— 时间戳那条路径的窗口只有一微秒宽，
   真实时钟下是**概率性**触发的。要把它做成**每次都复现**，就得自己当钟表。
   同时 `real_clock_step()` 量出真实时钟的一拍有多宽 —— 那是这个窗口在现实中
   够不够得着的证据，不是我们编的。

4. **同一口径的打印**（`title` / `step` / `ok` / `bad` / `note`）。

**判据的可信度取决于前提是否成立**，所以每个探针都**先证明前提成立、再报结论**；
前提不成立时一律报「没测到」，绝不报「通过」。
"""

from __future__ import annotations

import contextlib
import time
from types import SimpleNamespace

# --------------------------------------------------------------------------
# 1. camel 部件
# --------------------------------------------------------------------------


def pieces():
    """把要用的 camel 部件一次取出。**取不到返回 None**（环境没装，不是失败）。"""
    try:
        from camel.agents.chat_agent import ChatAgent
        from camel.memories.agent_memories import ChatHistoryMemory
        from camel.memories.context_creators.score_based import (
            ScoreBasedContextCreator,
        )
        from camel.memories.records import MemoryRecord
        from camel.utils import OpenAITokenCounter
        from camel.types import OpenAIBackendRole, UnifiedModelType
        from camel.messages import BaseMessage, FunctionCallingMessage
    except Exception as exc:  # noqa: BLE001
        print(f"  ○ camel 取不到（{exc.__class__.__name__}: {exc}）"
              " —— **这不是「通过」，是没测到**。")
        return None

    return SimpleNamespace(
        ChatAgent=ChatAgent,
        ChatHistoryMemory=ChatHistoryMemory,
        ScoreBasedContextCreator=ScoreBasedContextCreator,
        MemoryRecord=MemoryRecord,
        OpenAITokenCounter=OpenAITokenCounter,
        OpenAIBackendRole=OpenAIBackendRole,
        UnifiedModelType=UnifiedModelType,
        BaseMessage=BaseMessage,
        FunctionCallingMessage=FunctionCallingMessage,
    )


def bare_agent(token_limit: int):
    """造一个**只带记忆、不带模型**的 ChatAgent。

    返回 `(agent, creator)`，取不到 camel 时返回 `(None, None)`。
    """
    P = pieces()
    if P is None:
        return None, None

    creator = P.ScoreBasedContextCreator(
        P.OpenAITokenCounter(P.UnifiedModelType("gpt-4o-mini")),
        token_limit=token_limit,
    )
    agent = P.ChatAgent.__new__(P.ChatAgent)
    agent.agent_id = "probe"
    # `memory` 是个 setter，赋值时会调 `init_messages()`，而它要读
    # `_system_message` —— `__new__` 绕过了 `__init__`，这个属性还不存在。
    agent._system_message = None
    agent.memory = P.ChatHistoryMemory(context_creator=creator)
    return agent, creator


def count_tokens(creator, message, role=None) -> int:
    """这条消息在 camel 那边值多少 token —— 用**它自己的**计数器，不用我们估的。"""
    msgs = ([message.to_openai_message(role)] if role is not None
            else [message.to_openai_message()])
    return creator.token_counter.count_tokens_from_messages(msgs)


def raw_memory_tokens(agent, creator) -> int:
    """记忆里**实际躺着**的 token 总量（含各类前缀），不是模型看到的那部分。"""
    return sum(
        count_tokens(creator, r.memory_record)
        for r in agent.memory.retrieve()
    )


def residual_budget(agent, creator) -> int:
    """**截断之后**上下文还剩多少额度 —— 就是 camel 884 行拿去做判断的那个数。

    这个数是理解切片缺陷的关键：截断把上下文填到贴着上限，所以残余额度按构造
    远小于待写的消息。把**实测值**打出来，读者不必相信我们的推测。
    """
    import warnings as _w

    try:
        with _w.catch_warnings():
            _w.simplefilter("ignore")
            _, ctx_tokens = agent.memory.get_context()
    except Exception:  # noqa: BLE001
        return -1
    return creator.token_limit - ctx_tokens


def quiet_logging() -> None:
    """把 camel 自己的 logger 提到 ERROR —— 探针要印的是**结论**，不是它的告警。

    camel 在切片那条路径上每次写入都 `logger.warning` 一行（884 行附近），
    几百行告警会把真正的结论淹掉。只动 camel 的 logger，不动别人的。
    """
    import logging as _log

    for name in ("camel",):
        _log.getLogger(name).setLevel(_log.ERROR)


def fill_until_truncating(agent, creator, filler_tokens: int = 400):
    """把记忆灌到**截断已经启动**为止 —— 也就是「残余预算远小于待写消息」那个状态。

    这一步是切片探针的前提。判据是「记忆里实际躺着的 token **超过**了上限」：
    只有超过，下次写入前 `get_context()` 才会先做一次截断，而截断会把上下文填到
    贴着上限 —— 于是 `remaining_budget` 被挤得远小于待写的消息，切片分支才会被走到。
    **不把这个状态造出来，切片分支根本不会被走到，探针会静静地测了个空气。**

    返回 `(写入次数, 每条多少 token, 实际总 token)`；灌不进那种状态时
    `实际总 token <= 上限`，调用方据此判「前提不成立」。
    """
    P = pieces()
    if P is None:
        return 0, 0, 0

    msg = P.BaseMessage.make_user_message(
        role_name="User", content="填 " + "x" * (filler_tokens * 3))
    per = count_tokens(creator, msg, P.OpenAIBackendRole.USER)
    n = 0
    while True:
        agent.update_memory(msg, P.OpenAIBackendRole.USER)
        n += 1
        raw = raw_memory_tokens(agent, creator)
        # `n >= 3` 是给「上限远大于单条」的情形留出余量：一条放得下时，
        # 记忆会一直涨到超过上限，循环才停 —— 不设这个下界会提前返回。
        if raw > creator.token_limit and n >= 3:
            return n, per, raw


# --------------------------------------------------------------------------
# 2. 时钟
# --------------------------------------------------------------------------


@contextlib.contextmanager
def frozen_clock(start: float):
    """把 `time.time_ns` 换成一个**可手动推进**的表。

    camel 是 `import time` 再 `time.time_ns()`，所以换掉模块属性就够了。
    用法：`with frozen_clock(0.0) as clock:` 然后 `clock["t"] += ...`。

    为什么要当钟表：那个窗口只有一微秒宽，真实时钟下是**概率性**触发的。
    自己当钟表才能让每一次都复现 —— 复现的意义是可查证，不是碰运气。
    """
    real = time.time_ns
    clock = {"t": float(start), "reads": 0}

    def fake():
        clock["reads"] += 1
        return int(clock["t"] * 1e9)

    time.time_ns = fake
    try:
        yield clock
    finally:
        time.time_ns = real


def real_clock_step(seconds: float = 0.05) -> float:
    """量真实 `time.time_ns()` 的**最小正步长**（秒）。量不到返回 0.0。

    这是全篇的根据，所以量法本身要经得起推敲。**按时间窗采样，不按次数**：
    一次定次数的循环可能在时钟的**同一拍内**就跑完了 —— 那样每次读数都相同，
    一个正步长也采不到，函数会静静地返回 0，看上去像「时钟没有步长」。
    （这是本装置自己踩过的坑，记在这里以免重犯。）按 50ms 采样，
    在本机约能跨过 48 拍，够稳。

    采样用 `time.perf_counter()` 计时，**不能用 `time.time_ns()`** ——
    要量的就是它，用它计时会自锁。
    """
    best = None
    deadline = time.perf_counter() + seconds
    prev = time.time_ns()
    while time.perf_counter() < deadline:
        now = time.time_ns()
        d = now - prev
        # **取窗口内的最小值，不能见着第一个正数就返回**：读数是随机落在拍上的，
        # 相邻两次读数之间可能隔着好几拍，第一个正步长往往偏大。
        if d > 0 and (best is None or d < best):
            best = d
        prev = now
    return (best or 0) / 1e9


# --------------------------------------------------------------------------
# 3. 打印（三个探针同一口径）
# --------------------------------------------------------------------------

_W = 66

#: 只用 **GBK 也编得出**的记号。中文 Windows 的 cmd 默认代码页是 GBK，
#: 用 `✅`／`▸` 这类字符会在打印时直接抛 `UnicodeEncodeError` ——
#: 一个「跑一条命令就能看到结果」的装置，不该在最外层被字符集挡住。
#: 这几个都在 GBK 里：√ U+221A、× U+00D7、○ U+25CB、· U+00B7。
_MARK_OK, _MARK_BAD, _MARK_SKIP, _MARK_NOTE = "√", "×", "○", "·"


def title(text: str) -> None:
    print()
    print("=" * _W)
    print(text)
    print("=" * _W)


def step(text: str) -> None:
    print(f"\n> {text}")


def note(text: str) -> None:
    print(f"  {_MARK_NOTE} {text}")


def ok(text: str) -> None:
    print(f"  {_MARK_OK} {text}")


def bad(text: str) -> None:
    print(f"  {_MARK_BAD} {text}")


def skip(text: str) -> None:
    print(f"  {_MARK_SKIP} {text}")


def _w(text) -> int:
    """字符串的**显示宽度**：CJK 与全角标点占两格。

    `len()` 数的是字符数，中文表格用它对齐会歪 —— 而一个数字类的装置，
    表格歪掉会让人怀疑数字本身。
    """
    import unicodedata

    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1
               for c in str(text))


def _pad(text, width: int) -> str:
    return str(text) + " " * max(0, width - _w(text))


def table(rows, header=None, pad: int = 2) -> None:
    """印一张对齐的小表。`rows` 是序列的序列。"""
    all_rows = ([[str(c) for c in header]] if header else []) + \
        [[str(c) for c in r] for r in rows]
    cols = len(all_rows[0])
    widths = [max(_w(r[i]) for r in all_rows) for i in range(cols)]
    for i, row in enumerate(all_rows):
        print("  " + (" " * pad).join(_pad(c, widths[j])
                                      for j, c in enumerate(row)))
        if header and i == 0:
            print("  " + (" " * pad).join("-" * w for w in widths))
