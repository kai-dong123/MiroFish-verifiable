"""复现二 · 同拍碰撞：**同一拍里的两次 tool 调用，会把回执和请求拆散**。

    python -m verification.repro_02_timestamp     # 在 backend/ 下

不发 LLM、不要 API key。跑完几秒钟。
> **首次运行要联网一次**：装置用的分词器（tiktoken）要下一张几 MB 的静态表，
> 之后走本地缓存。这只是编码表，不是 LLM 调用 —— 但冷缓存的机器上确实要用到网。


## 症状

`camel/agents/chat_agent.py` 的 `_record_tool_calling`（2739~2751 行）**只读一次
时钟**，然后用 `+1e-6` 把回执排在请求之后（源码注释写着「纳秒精度，避免碰撞」）：

    current_time_ns = time.time_ns()                      # 2739：只读这一次
    base_timestamp  = current_time_ns / 1_000_000_000     # 2740
    self.update_memory(assist_msg, ASSISTANT, timestamp=base_timestamp)         # 2742
    self.update_memory(func_msg,  FUNCTION,  timestamp=base_timestamp + 1e-6)   # 2747

**在写这句的那台机器上（Windows），那个 `1e-6` 比时钟自己的分辨率还细两三个
数量级。** 第一节会**现场量出**本机 `time.time_ns()` 的最小步长（本机零点几毫秒；
换平台会变 —— Linux 实测 100 纳秒，那时这个比值方向就反过来）并把比值打出来 ——
不引用外部数字，因为这台机器上的数才是这份复现的依据。
**这个比值是观测量，不是常数**：上面那句只在写它的那台机器上成立，真正被这份
复现引用的是第一节量出来的那个比值。所以它分得开**一对**请求/回执
（那是加在显式值上的算术，不看钟），却分不开**两次调用**：一次模型响应里并排的
两个 tool 调用前后脚读钟，**读到同一个 `T`**。

四条记录于是是 `T、T+1e-6、T、T+1e-6`。排序键 `(timestamp, -score)`
（`memories/context_creators/score_based.py` 的 `_conversation_sort_key`）在时间戳
相等时按**分数高的在前**决胜负 —— 也就是**后写的那条排到前面**：

    assistant_B(T) · assistant_A(T) · func_B(T+1e-6) · func_A(T+1e-6)
       ↑ 带 tool_calls        ↑ 紧随其后的却是另一个 assistant，不是它的回执

端点回 400 `insufficient tool messages following tool_calls message`，
而上层只记一行 `Agent ... error` 就继续跑 —— **该 agent 这一轮的动作整条消失**。

## 判据（直接对**发给 API 的那串消息**做 API 的同一条校验）

`memory.get_context()` 返回的就是即将发出的 `List[OpenAIMessage]`
（`memories/base.py:143`）。于是判据不用绕：**凡带 `tool_calls` 的消息，
紧随其后的必须是回应它的 `role="tool"` 消息。** 违反了几处，就报几处。

## 单点扰动

冻住时钟，同一条序列跑四遍，只切「两次调用相隔多远」与「时间戳守卫」这两个旋钮：

    守卫关 · 同拍（相隔 0）        → 应当**违反**
    守卫关 · 跨拍但小于那个偏移     → 应当**违反**（成因是「挨得太近」，不是「同一拍」）
    守卫关 · 跨拍且大于那个偏移     → 应当合法
    守卫开 · 同拍（相隔 0）        → 应当合法（守卫把三条以上的写入串成了严格递增）

**第二、三行是这一节的关键，也是这份脚本改过一次的地方。**
原先这里只有「隔一拍」一臂，间隔取的是**当场量到的那一拍** —— 那在时钟刻度
比 `1e-6` 粗的机器上（比如 Windows，实测 0.3~0.6 ms）恰好等价于「跨过了那个偏移」，
于是看起来像「跨拍就免疫」。**换到刻度比 `1e-6` 细的机器上（Linux/WSL 实测 102 ns），
同一臂照样违反** —— 因为真正的分界从来不是时钟刻度，是 **camel 那个 `1e-6` 的偏移**：
两次调用落点相差小于它，四条记录就会交错；大过它就不交错。同拍（相差 0）只是这个
条件在真实机器上最常见的取值，不是它的全部。

所以现在这一臂的间隔**按那个偏移来定义**（半个偏移 / 两倍偏移），不按拍来定义 ——
输入不再依赖宿主机时钟，两处判定在哪个平台上都一样。

第四行才是重点：**碰撞这件事本身没被消灭，被消灭的是「碰撞能造成破坏」。**

## 为什么这是修①的代价

见本脚本第三节：在**同样的满记忆**上量两次调用之间的真实间隔。切片没修时，
写一次回执要落几百条记录、要花上百毫秒 —— 两次调用**必然跨出上百拍**，误打误撞免疫；
切片修好之后写入变快，间隔掉回**拍的量级**，才碰得上。**所以②不是独立缺陷，
是①的代价。**

（注意第三节量的是**趋势**，不是逐次保证：修好之后多数运行同拍，但也会跨到十来拍。
「同拍就一定被拆散」那条由第二节的**冻钟**定死 —— 那一条才是逐位可复核的。）
"""

from __future__ import annotations

import time

from . import _probe as P

#: camel 用来分开请求/回执的那个偏移（源码 2750 行）。
CAMEL_BUMP = 1e-6

#: 第二节那四臂用的冻钟起点（秒）。
#:
#: **它必须是常量，不能在两处各写一个 1000.0**：第二节跑臂时传 `freeze=` 用一次，
#: 稍后往读数里写 `"frozen_clock"` 那一格时又用一次。两边分开写的话，
#: 「这条读数取自冻钟」就成了一句**没人验的声明** —— 而它正是第二节全部判据的前提
#: （冻钟把它们变成逐位可复核的，不读物理时钟）。
SEC2_FREEZE = 1000.0


def _role_type():
    from camel.types import RoleType

    return RoleType.ASSISTANT


def _record_tool_call(agent, cid: str, ts: float) -> None:
    """**照着 camel `_record_tool_calling` 的形状**写一对记录（2742~2751 行）。

    这里把时间戳显式传进去，是为了让「同拍」成为**受控条件**而不是碰运气 ——
    camel 自己也是显式传 `base_timestamp` / `base_timestamp + 1e-6`。
    """
    Pw = P.pieces()
    common = dict(role_name="Actor", role_type=_role_type(), meta_dict=None,
                  content="", func_name="act", tool_call_id=cid)
    request = Pw.FunctionCallingMessage(args={"call": cid}, **common)
    response = Pw.FunctionCallingMessage(result=f"{cid} 的结果", **common)
    agent.update_memory(request, Pw.OpenAIBackendRole.ASSISTANT, timestamp=ts)
    agent.update_memory(response, Pw.OpenAIBackendRole.FUNCTION,
                        timestamp=ts + CAMEL_BUMP)


def _violations(ctx) -> list:
    """**API 的同一条校验**：带 tool_calls 的消息，后面必须紧跟它的回执。"""
    out = []
    for i, m in enumerate(ctx):
        if m.get("tool_calls"):
            nxt = ctx[i + 1] if i + 1 < len(ctx) else None
            if not nxt or nxt.get("role") != "tool":
                out.append((i, (nxt or {}).get("role")))
    return out


def _shape(ctx) -> str:
    return " → ".join(
        ("assistant+tool_calls" if m.get("tool_calls") else m.get("role", "?"))
        for m in ctx)


def _run_two_calls(gap: float, freeze: float):
    """冻钟跑一次「两次 tool 调用」，返回（发给 API 的消息串，违反列表）。"""
    agent, _ = P.bare_agent(8000)
    if agent is None:
        return None, None
    with P.frozen_clock(freeze) as clock:
        _record_tool_call(agent, "call_1", freeze)
        clock["t"] = freeze + gap          # 第二次调用的读钟落点
        _record_tool_call(agent, "call_2", freeze + gap)
    ctx = agent.memory.get_context()[0]
    return ctx, _violations(ctx)


def _real_gap_with_full_memory(slicing: bool):
    """**第三节**：在满记忆上量两次调用之间真实的、由物理时钟给出的间隔。

    返回 `(间隔秒, 一拍秒)`；前提不成立时返回 `None`。
    """
    from . import camel_guards as G

    tick = P.real_clock_step()
    G.set_flags(slicing=False, timestamp=False)   # 灌入一律在守卫关着时做
    fresh = None
    try:
        from .repro_01_slicing import _fresh_filled

        fresh = _fresh_filled(4000, 400)
    except Exception:  # noqa: BLE001
        return None
    if fresh is None:
        return None
    agent, creator, _ = fresh

    G.set_flags(slicing=slicing, timestamp=False)
    _record_tool_call(agent, "call_1", time.time_ns() / 1e9)
    _record_tool_call(agent, "call_2", time.time_ns() / 1e9)

    stamps = {r.memory_record.message.tool_call_id: r.memory_record.timestamp
              for r in agent.memory.retrieve()
              if getattr(r.memory_record.message, "tool_call_id", None)
              in ("call_1", "call_2")
              and r.memory_record.role_at_backend.value == "assistant"}
    if len(stamps) != 2:
        return None
    return abs(stamps["call_2"] - stamps["call_1"]), tick


def _tick_verdict(gap: float, tick: float, want_same: bool) -> str:
    """由**读数**算出「后果」那一列 —— 不许把结论摆在读数旁边。

    `gap` 是两次调用的真实间隔，`tick` 是当场量的一拍，`want_same` 是这一行的
    预期（缺陷那行预期跨拍，修好那行预期同拍）。判定只有一条：
    `gap < tick` 就是同拍。

    **这一格曾经是写死的**，于是有过一次它一边打出「3.35 ms / 9.66 拍」、
    一边宣称「同拍 → 碰撞才发生」—— 同一张表里读数和结论互相打脸。这类错
    不会自己报错，只会顺着报告流出去，所以判定必须由读数算，且与预期不符时
    **直书「与预期相反」**、不许悄悄折回预期那一侧。

    单独拎成函数是为了能被测（见 `tests/test_repro_verdicts.py`）：
    写死的字面量测不出来，算出来的才测得出。
    """
    same = (gap / tick) < 1.0 if tick > 0 else False
    if same == want_same:
        return "同拍 → 碰撞才发生" if same else "跨拍 → 误打误撞免疫"
    n = gap / tick if tick > 0 else float("nan")
    return ("**同一拍**（与预期相反）" if same
            else f"**跨到 {n:,.0f} 拍**（与预期相反）")


def main() -> bool | None:
    P.title("复现二 · 同拍碰撞（确定性、不调 LLM、不要 API key）")
    P.quiet_logging()

    if P.pieces() is None:
        return None

    # -- 第一节：先量清楚「一拍有多宽」 ---------------------------------
    P.step("第一节：先量清楚时钟一拍有多宽 —— 这是全篇的根据")
    tick = P.real_clock_step()
    if tick <= 0:
        P.skip("量不到时钟步长 —— 没测到。")
        return None
    P.ok(f"本机 `time.time_ns()` 最小正步长 = {tick * 1e9:,.0f} ns "
         f"（{tick * 1e3:.3f} ms）")
    # 这一行**必须分两种情况写**：`tick / CAMEL_BUMP` 在刻度比 1µs 细的机器上
    # 小于 1，写成 `1/{比值:,.0f}` 会印出「1/0」—— 一个看着像除零、
    # 其实只是四舍五入的假象。判定不受影响，但读的人会当场卡住。
    ratio = tick / CAMEL_BUMP
    if ratio >= 1:
        P.ok(f"camel 用来排次序的偏移 = {CAMEL_BUMP * 1e9:,.0f} ns "
             f"—— 只有一拍的 **1/{ratio:,.0f}**")
    else:
        P.ok(f"camel 用来排次序的偏移 = {CAMEL_BUMP * 1e9:,.0f} ns "
             f"—— **比本机时钟的一拍还粗 {1 / ratio:,.1f} 倍**")
    P.note("那个偏移细到能分开加在显式值上的那一对（那是算术）；")
    if ratio >= 1:
        P.note("而两次各自读钟的调用会读到**同一个**数 —— 于是也撞得上。")
    else:
        P.note("却分不开两次挨得太近的调用 —— 哪怕它们**读到了不同的数**，")
        P.note("相差只要小于这个偏移，四条记录照样交错。**分界是那个偏移，不是一拍。**")

    # -- 第二节：单点扰动 -------------------------------------------------
    P.step("第二节：同一条序列，只切「时间戳守卫」这一个开关")
    try:
        from . import camel_guards as G

        G.uninstall()
        G.install(slicing=True, timestamp=False)
    except Exception as exc:  # noqa: BLE001
        P.bad(f"守卫装不上（{exc.__class__.__name__}: {exc}）—— 没测到。")
        return None

    rows, results = [], {}
    for label, gap, flag in (("守卫关 · 同拍", 0.0, False),
                             ("守卫关 · 跨拍·小于偏移", CAMEL_BUMP / 2, False),
                             ("守卫关 · 跨拍·大于偏移", CAMEL_BUMP * 2, False),
                             ("守卫开 · 同拍", 0.0, True)):
        G.set_flags(slicing=True, timestamp=flag)
        ctx, bad = _run_two_calls(gap, freeze=SEC2_FREEZE)
        if ctx is None:
            P.bad(f"{label}：跑不出来")
            return None
        results[label] = bad
        rows.append([label, f"{gap * 1e9:,.0f}",
                     f"{len(bad)} 处" if bad else "无",
                     "合法" if not bad else "**违反**"])
    P.table(rows, header=["", "两次相隔(ns)", "违反", "发给 API 的消息串合法吗"])
    P.note("（第二、三行的间隔是**按那个 `1e-6` 的偏移定的**：半个偏移、两倍偏移 ——"
           "不是按本机的时钟刻度定的。所以这两行在哪个平台上都是同一件事。）")

    G.set_flags(slicing=True, timestamp=False)
    ctx_off, bad_off = _run_two_calls(0.0, freeze=SEC2_FREEZE)
    G.set_flags(slicing=True, timestamp=True)
    ctx_on, bad_on = _run_two_calls(0.0, freeze=SEC2_FREEZE)
    P.note(f"守卫关：{_shape(ctx_off)}")
    P.note(f"守卫开：{_shape(ctx_on)}")

    # -- 第三节：为什么这是修①的代价 --------------------------------------
    P.step("第三节：为什么这是「修①」的代价 —— 在同样的满记忆上量真实间隔")
    gap_defect = _real_gap_with_full_memory(slicing=False)
    gap_fixed = _real_gap_with_full_memory(slicing=True)
    if gap_defect and gap_fixed:
        rows = []
        for label, (gap, tick), want_same in (
                ("切片没修（缺陷在）", gap_defect, False),
                ("切片修了（守卫开）", gap_fixed, True)):
            n = gap / tick if tick > 0 else float("nan")
            verdict = _tick_verdict(gap, tick, want_same)
            rows.append([label, f"{gap*1e3:.2f} ms", f"{n:,.2f} 拍", verdict])
        P.table(rows, header=["", "两次调用的真实间隔", "合多少拍", "后果"])
        P.note("（间隔由物理时钟给出，不是我们设的：camel 自己读钟，"
               "我们从记忆里把落下的时间戳读回来。）")
        # 「合多少拍」这一列的分母是**这一节另量一次**的读数，不是第一节那次 ——
        # 两次都是独立测量，本来就不会相同。把分母打出来，免得读者拿它跟第一节的
        # 数字对，对不上就以为有一处错了。**麻烦的是这一列，不是间隔那一列**：
        # 间隔由实际工作量决定，很稳；分母本身是个随机量。
        P.note(f"（上面「合多少拍」的分母是本节当场另量的一拍 = "
               f"{gap_defect[1]*1e3:.3f} / {gap_fixed[1]*1e3:.3f} ms —— "
               f"它和第一节那个数**不是同一个**，两次都是独立测量。"
               f"所以这一列抖得比左边那列厉害，别拿它当精确值。）")
        # 这一节量的是**趋势**，不是保证 —— 必须说清楚，否则上面那两行会被读成
        # 「修了①就一定同拍」。真实的观测是：缺陷下稳定跨上百拍（多次运行都在
        # 10² ms 量级），修掉之后落进「拍的量级」，多数运行直接同拍、少数跨到几拍。
        P.note("（这一节量的是**趋势**，不是逐次保证：缺陷那一行稳定在 10² ms / "
               "上百拍；修掉之后掉进「拍的量级」—— 多数运行直接同拍，但也有运行"
               "跨到几拍。**「同拍就一定拆散」这条是由第二节的冻钟定死的**，"
               "这一节只负责说明「修①把间隔拉到了碰得上的范围」。）")
        P.note("（本节的两个数**不进判据** —— 判据用的是第二节那组冻钟读数，"
               "逐位可复核。物理时钟量出来的东西不该有否决权。）")
    else:
        P.skip("满记忆那组没量到 —— 这一节不作数。")

    # -- 判据 --------------------------------------------------------------
    P.step("判据")
    ok = True
    if results["守卫关 · 同拍"]:
        P.ok(f"守卫关着、两次调用同拍：**{len(results['守卫关 · 同拍'])} 处违反** —— "
             f"带 tool_calls 的消息后面跟着的不是它的回执")
    else:
        P.bad("守卫关着、两次调用同拍，却没排出违反的形状 —— 缺陷没复现")
        ok = False
    if results["守卫关 · 跨拍·小于偏移"]:
        P.ok("守卫关着、两次调用**跨了拍但相差不到那个偏移**：照样违反 —— "
             "所以成因是「两次落点挨得太近」，**不是「同一拍」**")
    else:
        P.bad("跨拍且小于那个偏移时不违反了 —— 那分界就不是那个偏移，"
              "上面的解释要重写")
        ok = False
    if not results["守卫关 · 跨拍·大于偏移"]:
        P.ok("守卫关着、两次调用相差**大过**那个偏移：合法 —— "
             "这才是它的免疫条件（与时钟刻度无关）")
    else:
        P.bad("相差大过那个偏移也违反 —— 那免疫条件不是那个偏移，"
              "上面的解释要重写")
        ok = False
    if not results["守卫开 · 同拍"]:
        P.ok("守卫开着、同样是同拍：合法 —— 碰撞还在，但**破坏不了**了")
    else:
        P.bad("守卫开着仍然违反 —— 守卫没起作用")
        ok = False

    P.step("结论")
    if ok:
        print("  两次 tool 调用的落点相差小于 camel 那个 1 微秒偏移时，")
        print("  四条记录的时间戳就交错在一起；排序键按分数把「后写的」排到前面，")
        print("  于是请求和它的回执被拆散。同拍（相差 0）是最常见的那种情形，")
        print("  但不是唯一的一种 —— **分界是那个偏移，不是时钟刻度。**")
        print("  端点回 400，上层只记一行错误继续跑 —— 这一轮的动作整条消失。")
        print("  守卫让每条记录的时间戳严格递增，碰撞再也造不成破坏。")
        print("  **而它们之所以会撞上，是因为切片那条修复把写入从「上百拍」"
              "拉回到「那个偏移的量级」。**")
    else:
        print("  上面有没通过的项，这条不能作数。")

    # 第二节那四臂的裸数（`rows` 里是格式化串，这里要裸数）。
    _sec2 = (("guard_off_same", "守卫关 · 同拍", 0.0,
              results["守卫关 · 同拍"]),
             ("guard_off_sub_bump", "守卫关 · 跨拍·小于偏移", CAMEL_BUMP / 2,
              results["守卫关 · 跨拍·小于偏移"]),
             ("guard_off_above_bump", "守卫关 · 跨拍·大于偏移", CAMEL_BUMP * 2,
              results["守卫关 · 跨拍·大于偏移"]),
             ("guard_on_same", "守卫开 · 同拍", 0.0,
              results["守卫开 · 同拍"]))
    readings = {"clock": {"tick_ns": tick * 1e9,
                          "camel_bump_ns": CAMEL_BUMP * 1e9,
                          "ticks_per_bump": tick / CAMEL_BUMP}}
    arms = {"clock": "第一节 · 时钟刻度（前提读数，不是实验臂）"}
    for key, label, gap, bad in _sec2:
        arms[key] = label
        readings[key] = {"gap_ns": gap * 1e9, "violations": len(bad),
                         # 这一格能被写成常量 `True`，靠的是**结构**而不是这句话：
                         # `_run_two_calls` 的 `freeze` 参数**没有默认值**，所以
                         # 任何产出读数的臂都必然是从冻钟里跑出来的。那条签名由
                         # `tests/test_repro_verdicts.py::
                         # test_the_frozen_clock_is_structural_not_a_written_flag`
                         # 钉住 —— 谁哪天给它加个默认值，读数就不会再是冻钟的了，
                         # 而这一格会继续印 `True`。
                         "frozen_clock": True}

    boundaries = [
        ("clock", "tick_ns",
         "取样窗口内的**最小值**，受时钟分辨率限制 —— 它量不出比一拍更细的东西"),
        ("clock", "ticks_per_bump", "分母是上面那个下限受制的量，比值跟着它走"),
        ("guard_off_sub_bump", "gap_ns",
         "**这一臂的间隔取的是那个偏移的一半（500 ns）**，为的是让它在"
         "**任何**时钟刻度下都落在「跨拍、但相差小于偏移」这一侧 —— "
         "刻度比 500 ns 粗的机器上它跨了好几拍，比它细的机器上它跨了一拍，"
         "而两种机器上它都该违反。**这一臂是取消掉「隔一拍」那一臂换来的**："
         "旧的写法按「拍」取间隔，判定就跟着宿主机时钟走了（Linux 实测翻面）"),
    ]

    # 第三节的两个臂：**各自带各自的分母**。共用一个 tick 会歪曲这张表 ——
    # 那一列的分母是本节当场另量的一拍，和第一节那个数不是同一个。
    if gap_defect and gap_fixed:
        for key, label, got, want_same in (
                ("slicing_unfixed", "切片没修（缺陷在）", gap_defect, False),
                ("slicing_fixed", "切片修了（守卫开）", gap_fixed, True)):
            gap, tick_here = got
            arms[key] = label
            readings[key] = {"gap_s": gap,
                             "tick_s": tick_here,
                             # 分母量成 `0` 时**不写 `NaN`**：`json.dumps` 默认
                             # `allow_nan=True`，会把裸 `NaN` 落进产物 —— 那是一份
                             # **非严格 JSON**。Python 读得回来，`jq` 之类的严格
                             # 解析器当场失败。用本仓统一的哨兵 `None`（= 没测到），
                             # 与 `_probe.residual_budget` 同一套口径；消费方必须
                             # 按下标取值，别直接拿去算。
                             "ticks_ratio": (gap / tick_here if tick_here > 0
                                             else None)}
            boundaries.append(
                (key, "ticks_ratio",
                 "分母是**本节当场另量的一拍**，与第一节那个数不是同一个；"
                 "间隔由实际工作量决定、很稳，分母本身是随机量 —— "
                 "**这一列抖得比间隔那一列厉害**，不该当精确值用；"
                 "分母量成 `0` 时这一格是 `null`（没测到），不是无穷大"))
            boundaries.append(
                (key, "gap_s",
                 "满记忆这个前提沿用了复现一的**严格不等式**关（写入后 token "
                 "超过上限才算启动截断），所以这一臂同样坐在边界上"))

    P.emit_readings(
        "repro_02_timestamp", arms=arms, readings=readings,
        units={"tick_ns": "ns", "camel_bump_ns": "ns", "ticks_per_bump": "拍",
               "gap_ns": "ns", "violations": "处", "frozen_clock": "是/否",
               "gap_s": "秒", "tick_s": "秒", "ticks_ratio": "拍"},
        boundaries=tuple(boundaries),
        note=f"第二节三臂用的是**冻钟**（同一个数被读到），逐位可复核；"
             f"第三节两臂是物理时钟量出来的**趋势**，不进判据。"
             f"`ticks_ratio` 的分母逐臂不同："
             + ("、".join(f"{k}={readings[k]['tick_s']*1e3:.3f} ms"
                          for k in ("slicing_unfixed", "slicing_fixed")
                          if k in readings) or "（第三节没量到）"),
    )
    return ok


if __name__ == "__main__":
    P.exit_with(main())
