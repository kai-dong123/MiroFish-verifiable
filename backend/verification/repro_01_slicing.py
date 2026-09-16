"""复现一 · 切片正反馈环：**一条放得下的消息，被切成几百块写进记忆**。

    python -m verification.repro_01_slicing        # 在 backend/ 下

不发 LLM、不联网、不要 API key、不要 Zep。跑完几秒钟，数字每次一样。

## 症状

记忆一装满、截断一启动，`camel/agents/chat_agent.py` 的 `update_memory` 就把
**一条完全放得下的消息**切碎（源码 884 / 933 / 948 行）：

    remaining_budget = max(0, token_limit - ctx_tokens)     # 884：ctx_tokens 是**截断后**的
    base_chunk_size  = max(1, remaining_budget) // 10       # 933：先除以 10
    chunk_body_limit = max(1, base_chunk_size - 12)         # 948：再减掉前缀的 12+ token

两件事叠在一起把每块压到 1 个 token：

* **残余预算天然很小。** 884 行读的是**截断之后**的上下文大小 —— 而截断干的事
  正是把上下文填到贴着上限。所以 `remaining_budget` 是「上限减去一个几乎满了的
  上下文」，**按构造就远小于待写的这条消息**。本次跑出来是 `4000 - 3867 = 133`。
* **133 还要再被砍两刀**：`//10` → 13，再减掉前缀长度 12 → **1**。
  那个前缀是 `"[chunk 3/412 of a long message]\\n"`，本身就要十几个 token，
  源码 942~948 行专门为它留了扣减 —— 于是扣完只剩 1。

结果：每条记录 1 个 token 正文 + 一个十几 token 的前缀，**一次写入的 token 量
膨胀一个数量级**，记录条数从 1 条变成几百条。

关键在于这是个**正反馈环**：记忆满 → 残余预算小 → 切片 → 膨胀 → 记忆更满。
所以它不会自己停下来，只会越跑越快。

（残余预算有多大，取决于上限与截断策略；上限越大、消息相对越小，碎片就越粗。
**这不是「一定会切到 1」，是「一定会按残余预算切」** —— 而残余预算由构造
就注定对不上待写的消息。本探针打印出它实际取到的值，不做推测。）

## 判据

**「只有这条消息自己就超上限才该切」。**「预算只是紧」本该交给
`ScoreBasedContextCreator` —— 它的职责就是按分数驱逐旧记录，camel 却把
两种情形合并进了同一个条件。所以这里的判据是机检的、不看叙述：

    这条消息自己的 token 数  <=  上下文上限     且     它仍然被切了
    ────────────────────────────────────────────────────────────────
    → 这不是「必要的切分」，是缺陷

## 单点扰动

两组**除一个开关外完全相同**：同一份代码、同一个进程、同样的先灌满再写一条。
唯一的差别是切片守卫开不开。同时 unguarded 那组**跑两遍**，两遍数字必须逐位
相同 —— 否则连「复现」都谈不上，只是碰巧看到一次。

## 修法

见 `verification/camel_guards.py`：判据换成「这条消息自己超没超上限」，
放得下就整条写入，旧记录交给 `ScoreBasedContextCreator` 按分数驱逐。
**这条修复的全部目的就是把写入变快 —— 而它同时是复现二的成因。**
"""

from __future__ import annotations

import sys

from . import _probe as P

#: 探针消息：一份**又长又完整**的记录。头尾各有一个标记，用来验它有没有被撕碎。
_HEAD = "【记录开始】字段 A=1 字段 B=2 字段 C=3"
_TAIL = "【记录结束】请据此继续下一步。"
_BODY = "数据 " * 240


def _probe_message():
    """一条**远小于上限**的消息。上限 4000，它只有几百 token。"""
    P_pieces = P.pieces()
    if P_pieces is None:
        return None
    return P_pieces.BaseMessage.make_user_message(
        role_name="Observer", content=f"{_HEAD} {_BODY} {_TAIL}")


def _measure(agent, creator, msg):
    """写一条消息，量四件事。**只看数字，不看叙述。**"""
    P_pieces = P.pieces()
    role = P_pieces.OpenAIBackendRole.USER

    own = P.count_tokens(creator, msg, role)
    residual = P.residual_budget(agent, creator)
    n0 = len(agent.memory.retrieve())
    t0 = P.raw_memory_tokens(agent, creator)

    agent.update_memory(msg, role)

    n1 = len(agent.memory.retrieve())
    t1 = P.raw_memory_tokens(agent, creator)
    stored = "".join(str(r.memory_record.message.content or "")
                     for r in agent.memory.retrieve())

    return {
        "own": own,
        "residual": residual,
        "records_added": n1 - n0,
        "tokens_added": t1 - t0,
        "expansion": (t1 - t0) / own if own else 0.0,
        "head_intact": _HEAD in stored,
        "tail_intact": _TAIL in stored,
    }


def _fresh_filled(token_limit: int, filler_tokens: int):
    """造一个**记忆已满、截断已启动**的 agent。前提不成立时返回 None。"""
    agent, creator = P.bare_agent(token_limit)
    if agent is None:
        return None
    n, per, raw = P.fill_until_truncating(agent, creator, filler_tokens)
    if raw <= creator.token_limit:
        return None
    return agent, creator, {"writes": n, "per": per, "raw": raw}


def main() -> bool | None:
    P.title("复现一 · 切片正反馈环（离线、确定性、不要 API key）")
    P.quiet_logging()

    if P.pieces() is None:
        return None
    msg = _probe_message()
    if msg is None:
        return None

    # -- 前提 --------------------------------------------------------------
    limit, filler = 4000, 400
    P.step(f"前提：把记忆灌到截断启动（上限 {limit} token）")
    try:
        from . import camel_guards as G

        G.uninstall()
        G.install(slicing=False, timestamp=False)
    except Exception as exc:  # noqa: BLE001
        P.bad(f"守卫装不上（{exc.__class__.__name__}: {exc}）—— 没测到。")
        return None

    # **三组的灌入一律在守卫关着时做。** 否则第三组的记忆是在守卫开着时灌出来的，
    # 前提状态就跟前两组不一样了 —— 那就不是单点扰动，是两个变量一起动。
    G.set_flags(slicing=False)
    filled = [_fresh_filled(limit, filler) for _ in range(3)]
    if any(f is None for f in filled):
        P.skip("灌不进「截断已启动」那个状态 —— "
               "**这不是「没有缺陷」，是没测到**。")
        return None
    creator = filled[0][1]
    info = filled[0][2]
    P.ok(f"{info['writes']} 次灌入后，记忆里实际躺着 {info['raw']} token "
         f"> 上限 {limit} —— 截断已启动")

    own = P.count_tokens(creator, msg, P.pieces().OpenAIBackendRole.USER)
    P.ok(f"待写的这条消息自己只占 {own} token ≤ {limit} —— "
         f"**它完全放得下**，切它没有道理")
    if own > limit:
        P.bad("探针消息自己就超上限，前提不成立")
        return None

    # -- 单点扰动 ----------------------------------------------------------
    P.step("单点扰动：同一条消息、同样的满记忆，只切「切片守卫」这一个开关")

    pre = [(len(a.memory.retrieve()), P.raw_memory_tokens(a, c),
            P.residual_budget(a, c)) for a, c, _ in filled]
    if len(set(pre)) != 1:
        P.bad(f"三组的**前提状态**不一致 {pre} —— 那这就不是单点扰动，"
              f"下面的对照不能作数")
        return None
    P.ok(f"三组前提逐位相同：记忆 {pre[0][0]} 条 / {pre[0][1]} token、"
         f"残余预算 {pre[0][2]} —— **唯一的差别只有那个开关**")

    runs = {}
    for label, flags in (("守卫关（第 1 遍）", False),
                         ("守卫关（第 2 遍）", False),
                         ("守卫开", True)):
        a, c, _ = filled[len(runs)]
        G.set_flags(slicing=flags)          # 只有**写入这一下**换开关
        runs[label] = _measure(a, c, msg)

    off1, off2, on = (runs["守卫关（第 1 遍）"], runs["守卫关（第 2 遍）"],
                      runs["守卫开"])

    P.table(
        [["守卫关（1）", f"{off1['residual']}", off1["records_added"],
          off1["tokens_added"], f"{off1['expansion']:.1f}×",
          "连续" if off1["head_intact"] else "**撕碎**"],
         ["守卫关（2）", f"{off2['residual']}", off2["records_added"],
          off2["tokens_added"], f"{off2['expansion']:.1f}×",
          "连续" if off2["head_intact"] else "**撕碎**"],
         ["守卫开", f"{on['residual']}", on["records_added"],
          on["tokens_added"], f"{on['expansion']:.1f}×",
          "连续" if on["head_intact"] else "**撕碎**"]],
        header=["", "残余预算", "新增记录", "实增 token", "膨胀", "原文可寻回"])

    P.note(f"（残余预算 = 上限 {limit} 减去**截断之后**的上下文大小；"
           f"待写消息自身 {own} token）")
    if off1["residual"] >= 0:
        P.note(f"（守卫关着时，camel 拿 {off1['residual']} 这个数去做 "
               f"//10 再减 12 的前缀扣减 → 每块正文容量 "
               f"{max(1, max(1, off1['residual']) // 10 - 12)} token）")

    # -- 判据 --------------------------------------------------------------
    P.step("判据")
    ok = True

    if off1["records_added"] == off2["records_added"] and \
            off1["tokens_added"] == off2["tokens_added"]:
        P.ok(f"守卫关那两遍数字逐位相同（{off1['records_added']} 条 / "
             f"{off1['tokens_added']} token）—— 这是**确定性的复现**，不是碰巧")
    else:
        P.bad("守卫关那两遍数字不一致，这个复现不可信 —— 先说清这件事")
        ok = False

    if off1["records_added"] > 1:
        P.ok(f"一条占 {own} token 的消息，被切成 **{off1['records_added']} 条**"
             f"记录写进记忆，实增 {off1['tokens_added']} token"
             f"（{off1['expansion']:.1f} 倍）")
    else:
        P.bad("守卫关着时它没被切 —— 这个缺陷在本环境里没复现出来")
        ok = False

    if not off1["head_intact"]:
        P.ok("原文在记忆里**已经找不回连续的『记录开始』** —— "
             "它被逐 token 撕开，每片之间还插了块前缀")
    else:
        P.note("原文仍可连续寻回（前缀没切断它）—— 这一项不成立，如实记下")

    if on["records_added"] == 1 and on["head_intact"]:
        P.ok(f"装上守卫后：**1 条记录**、实增 {on['tokens_added']} token"
             f"（{on['expansion']:.2f} 倍）、原文完整可寻回")
    else:
        P.bad(f"装上守卫后仍不正常：{on['records_added']} 条 / "
              f"{on['tokens_added']} token")
        ok = False

    P.step("结论")
    if ok:
        print("  记忆一满，一条放得下的消息就被撕成几百片、膨胀一个数量级；")
        print("  而这是个正反馈环 —— 越满越碎，越碎越满。守卫装上后一次写入一条。")
    else:
        print("  上面有没通过的项，这条不能作数。")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
