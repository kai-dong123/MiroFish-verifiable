"""离线探针的共享底座：**不发 LLM 请求、不要 API key、不花钱、结果确定**。

三个复现脚本都靠这里的四件东西。它们能被离线跑，是因为 camel 里出问题的那些
路径**只碰记忆对象和时钟**，不碰模型：

1. **裸 agent**（`bare_agent`）—— 用 `ChatAgent.__new__` 绕过 `__init__`。
   真造一个 `ChatAgent` 要一个模型后端；而这里要测的是**写入决策**，与模型无关。
   `update_memory` 用到的属性只有 `memory`、`agent_id`、`_system_message` 三个。

   > **一处例外，别被「离线」这个词盖过去：分词器要一份数据文件。**
   > `bare_agent` 里那个 `OpenAITokenCounter` 走的是 tiktoken，而 tiktoken 的
   > 编码表是**首次使用时下载**的一份静态数据（o200k_base 约 3.6 MB，下完落在
   > 本地缓存里）。**缓存热的时候一次网络请求都不发**（本机实测 0.1 秒内取到）；
   > **冷缓存时要联网下这一次**（实测 3.5 秒）。
   >
   > 这条不能省掉不写：切片那一整节的数字（270 条 / 5130 token）**全都依赖这个
   > 分词器给出的真 token 数**，换一个计数方式这些数就不是这些数了。所以「离线」
   > 的意思是**不发 LLM、不调 API**，不是「这台机器上不需要任何网络」。
   > 报告的**环境**一节把这个编码名和缓存状态记下来了。

2. **把记忆灌到截断启动**（`fill_until_truncating`）—— 切片那条路径的**前提状态**
   是「记忆已满、驱逐已开始」。不把这个状态造出来，切片分支根本不会被走到，
   探针会静静地测了个空气。

3. **可冻结的时钟**（`frozen_clock`）—— 时间戳那条路径要的是「两次读钟落在
   **同一拍**」：camel 给回执加的 `+1e-6` 比时钟自己的一拍还细两三个数量级，
   所以同拍读两次就撞、跨拍读两次就没事。真实时钟下同不同拍由调度决定，
   是**概率性**的；冻住钟就让它每次都同拍，于是**每次复现**。
   同时 `real_clock_step()` 量出真实时钟的一拍有多宽 —— 那是「同拍容不容易发生」
   在现实中的依据，不是我们编的。

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
    本机一拍在 0.30 ~ 1.00 ms 之间，所以这 50ms 窗跨过**几十到一百多拍** ——
    只要跨过两拍以上，最小值就有意义。

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


# --------------------------------------------------------------------------
# 4. 读数块：给检查器读的那一段
# --------------------------------------------------------------------------
#
# `run_all` 的立场是「不做二次解析、不重算」—— 它把子进程的正文逐字抄进报告，
# 不从散文里抠数字。但有些结论只能由读数算出来，那就需要一份**机器可读**的读数。
#
# 解法是让**复现自己**按锚定的分隔符吐出结构化的一段：这不是「从散文里猜」，
# 而是「读同一个进程自己吐的结构」，抽取因此是确定的；`run_all` 另记这一段在
# 正文里的 sha256，于是「这份读数出自那次运行」是可核的。

_READINGS_BEGIN = "--- 读数 BEGIN（机器可读；由本复现自己打出，人读上面那几张表）---"
_READINGS_END = "--- 读数 END ---"


#: 贴界：这格的值被**机制**压住了（夹逼、取整、下界），失去了分辨力。
BOUND_RAILED = "贴界"
#: 未测量：这格**这次运行根本没量**（比如那条分支压根没走）。和「量到 0」不是一回事。
BOUND_UNMEASURED = "未测量"


def _boundary(spec) -> dict:
    """一条边界声明。`(臂, 量, 为什么)` 默认按**贴界**；四元组可指定类别。

    这两类必须分开，因为检查器对它们的处理不一样：
    贴界 → 结论**降级为不采信**（量还在，但分不出差别）；
    未测量 → 结论**不可判定**（量不在，判不了）。
    合成一类就会出现「拿反事实的格子当成量到的读数」这种错。
    """
    if len(spec) == 4:
        arm, metric, kind, why = spec
    else:
        arm, metric, why = spec
        kind = BOUND_RAILED
    if kind not in (BOUND_RAILED, BOUND_UNMEASURED):
        raise ValueError(f"边界类别只有 {BOUND_RAILED!r} / {BOUND_UNMEASURED!r}，"
                         f"收到 {kind!r}")
    return {"arm": arm, "metric": metric, "kind": kind, "why": why}


def non_gbk_chars(text: str) -> str:
    """挑出 GBK **编不出**的字符（去重、按出现顺序）。

    为什么值得单独一个函数：中文 Windows 的 cmd 默认代码页是 GBK，而
    `__init__._harden_streams()` 把编不出的字符**降级成 `?` 而不是崩掉**。
    于是这类字符不会报错，只会**悄悄把内容改掉** —— 读数块里一个脏字符
    就是一次无声的数据损坏。所以这里把它变成一个能断言的东西。
    """
    bad: list = []
    for ch in text:
        if ch in bad:
            continue
        try:
            ch.encode("gbk")
        except UnicodeEncodeError:
            bad.append(ch)
    return "".join(bad)


def emit_readings(repro: str, arms, readings, *,
                  units=None, boundaries=(), note=None) -> None:
    """打出机器可读的读数块。

    参数：

    * `repro` —— 复现的名字（稳定标识，别改）。
    * `arms` —— `{稳定键: 人读标签}`。**稳定键要自己定**，别复用打屏标签：
      同一批复现可能有两套标签（表里「守卫关（1）」、`runs` 里「守卫关（第 1 遍）」）。
    * `readings` —— `{稳定键: {量: 裸数}}`。**要裸数，不要格式化串** ——
      表里那个 `1.0×` 和 `{"value": 1.0, "unit": "×"}` 是两回事，
      而 `f"{x:,.0f}"` 那种带千分位的更不该进这里。
    * `units` —— `{量: 单位}`，只给人读。
    * `boundaries` —— `((稳定键, 量, 为什么), ...)` 或
      `((稳定键, 量, 类别, 为什么), ...)`。类别见 `BOUND_RAILED` /
      `BOUND_UNMEASURED`；不写类别时按**贴界**算。
      由**复现自己**声明：检查器重算不了这件事（夹逼发生在 camel 源码里）。
      只声明事实，不下结论 —— 采不采信、判不判得了，都由检查器按规则判。
    * `note` —— 一句话交代这一批读数的前提。

    **派生量要在 `boundaries` 或 `note` 里说清分母/来源**：比如「合多少拍」
    的分母是本节当场另量的一拍，和第一节那个数不是同一个 —— 只报一个
    `tick` 会歪曲那张表。
    """
    import json

    payload = {
        "repro": repro,
        "arms": dict(arms),
        "readings": {k: dict(v) for k, v in readings.items()},
        "units": dict(units or {}),
        "boundaries": [_boundary(b) for b in boundaries],
        "note": note,
    }
    print(f"\n  {_READINGS_BEGIN}")
    body = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    unsafe = non_gbk_chars(body)
    if unsafe:
        # 报警但**不崩**：一个装置不该因为一个字打印不出来就整个停下来。
        # 但也不能装作没发生 —— 脏字符会被降级成 `?`，那是无声的数据损坏。
        note(f"读数块里有 {len(unsafe)} 个字符 GBK 编不出：{unsafe!r} —— "
             f"中文 Windows 的 cmd 下它们会变成 `?`。"
             f"本目录的记号只用 GBK 编得出的字符，正是为了这件事。")
    print(body)
    print(f"  {_READINGS_END}")


def parse_readings(text: str) -> dict | None:
    """从一段正文里把读数块取出来。取不到就返回 `None` —— **不猜**。

    「抽不出来」和「读数是空的」必须分开：前者是 `None`，后者是取到了但没内容。
    `run_all` 那边据此把「没测到」和「测到了但什么都没有」分开报。
    """
    import json

    lines = text.splitlines()
    try:
        i = next(n for n, ln in enumerate(lines) if _READINGS_BEGIN in ln)
        j = next(n for n, ln in enumerate(lines[i + 1:], i + 1)
                 if _READINGS_END in ln)
    except StopIteration:
        return None
    body = "\n".join(lines[i + 1:j])
    try:
        return json.loads(body)
    except ValueError:
        return None


def readings_sha256(text: str) -> str | None:
    """读数块在**这一段正文里**的 sha256。取不到块就返回 None。

    记它是为了让「这份读数出自那次运行」可核 —— 块被换过，哈希就对不上。
    """
    import hashlib

    lines = text.splitlines()
    try:
        i = next(n for n, ln in enumerate(lines) if _READINGS_BEGIN in ln)
        j = next(n for n, ln in enumerate(lines[i + 1:], i + 1)
                 if _READINGS_END in ln)
    except StopIteration:
        return None
    body = "\n".join(lines[i:j + 1])
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def sha256_text(path) -> str:
    """一个**受版本控制的文本文件**的 sha256。读的是文本，不是字节。

    **为什么不是 `read_bytes()`** —— 这条是踩出来的，而且踩得很难看：

    `core.autocrlf` 在 Windows 上是**默认开的**，clone 下来时 git 会把仓库里
    的 LF 换成 CRLF。于是同一个文件在两个人的工作区里**字节不同、文本相同**。
    谁要是拿字节哈希去钉一个「报告有没有过期」，那条测试就会在**每一个用默认
    配置 clone 的人**那里先红一次 —— 而它报的是一个**根本不存在的问题**：
    测试集没变，只是换行符变了。

    这与本装置已经踩过两次的那个毛病同源（见 `README.md` 里「产物没过期」那一节）：
    **别去钉一个「本来就会合法地变」的东西，然后说它变了
    就是有问题。** 换行符是 git 的合法产物，不是内容的改动。

    另外三处哈希（`adjudicate` / `mutations._sha` / `reconcile_selfcheck`）本来就
    是拿文本算的 —— 这个函数把剩下的两类也归到同一条口径上，免得同一份材料里
    有两种「sha256」，读的人还得猜是哪一种。
    """
    import hashlib
    import pathlib

    text = pathlib.Path(path).read_text(encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# 5. 出口：**三种退出码，不是两种**
# --------------------------------------------------------------------------

def exit_with(verdict: bool | None) -> None:
    """`True` → `0`，`False` → `1`，`None` → `2`（**没测到**）。

    三条复现的 `main()` 签名都是 `-> bool | None`，其中 `None` 是
    「没测到／前提不成立」—— 它**既不等于通过，也不等于失败**。

    这里必须写 `is True` / `is False`：`None` 是假值，写成
    `0 if verdict else 1` 会把「没测到」折进「没达到预期」，
    而 README「退出码：**三种，不是两种**」那一节承诺的正是三态。
    **一个装置如果把「没跑起来」报成红色，它后面所有的红色也一样不值钱。**
    """
    if verdict is True:
        raise SystemExit(0)
    if verdict is False:
        raise SystemExit(1)
    raise SystemExit(2)
