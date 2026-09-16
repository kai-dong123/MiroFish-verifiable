"""复现一 · 切片正反馈环：**一条放得下的消息，被切成几百块写进记忆**。

    python -m verification.repro_01_slicing        # 在 backend/ 下

不发 LLM、不要 API key、不要 Zep。跑完几秒钟，数字每次一样。
> **首次运行要联网一次**：装置用的分词器（tiktoken）要下一份静态数据（约 3.6 MB，
> 之后走本地缓存）。这只是编码表，不是 LLM 调用 —— 但冷缓存的机器上确实要用到网。


## 症状

记忆一装满、截断一启动，`camel/agents/chat_agent.py` 的 `update_memory` 就把
**一条完全放得下的消息**切碎（下面四行是源码 884 / 933 / 943 / 948 行的**原文**）：

    remaining_budget = max(0, token_limit - ctx_tokens)      # 884：ctx_tokens 是**截断后**的
    base_chunk_size = max(1, remaining_budget) // 10         # 933：先除以 10
    prefix_token_len = len(token_counter.encode(sample_prefix))  # 943：前缀长度是**量出来的**
    chunk_body_limit = max(1, base_chunk_size - prefix_token_len)  # 948：再扣掉它

**注意 943 那一行 —— 那个减数不是字面量 `12`，是当场用分词器量出来的。**
在 `gpt-4o-mini` 这个分词器下它**恰好**量出 12，所以本节下面拿 12 去算数是对的；
但那是**这一台机器上、这一个分词器下的读数**，不是代码里的常数。（这里先前把减数
写成了字面量 `12`、还标注成「948 行」—— 数值对、**引文错**，已改正。
`tests/test_citations.py` 钉的就是 948 那一行的真实内容。）

两件事叠在一起把每块压到 1 个 token：

* **残余预算天然很小。** 884 行读的是**截断之后**的上下文大小 —— 而截断干的事
  正是把上下文填到贴着上限。所以 `remaining_budget` 是「上限减去一个几乎满了的
  上下文」，**按构造就远小于待写的这条消息**。本次跑出来是 `4000 - 3867 = 133`。
* **133 还要再被砍两刀**：`//10` → 13，再扣掉上面量出来的 `prefix_token_len`（这次是
  12）→ **1**。那个前缀长这样：`"[chunk 3/412 of a long message]\\n"`，本身就要十几个
  token，源码 942~948 行专门为它留了扣减 —— 于是扣完只剩 1。

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


def _chunk_body_limit(creator, residual: int) -> dict:
    """照 camel `chat_agent.py:933-948` 那条链，**每一环都由实测得出**。

    上游那几行是：

        base_chunk_size  = max(1, remaining_budget) // 10               # 933
        sample_prefix    = "[chunk 1/1000 of a long message]\\n"        # 942
        prefix_token_len = len(token_counter.encode(sample_prefix))     # 943
        chunk_body_limit = max(1, base_chunk_size - prefix_token_len)   # 948

    `residual` 是量出来的，`prefix_token_len` 这里也**当场拿 camel 自己的
    计数器量**。此前这一步写的是字面量 `12`（gpt-4o-mini 下恰好对，换个
    分词器就不是 12）—— 「每块正文容量 1 token」于是成了**再推导**出来的数。
    引文上错的那件事，`tests/test_citations.py::KNOWN_MISQUOTES` 已经记过一次，
    只是当时只扫了材料、没扫到装置自己这一步。

    `clamped` 记的是**上游那个 `max(1, ...)` 兜底有没有真的兜住**：
    `base_chunk_size - prefix_token_len <= 0` 时，容量是兜底兜出来的，
    不是算出来的 —— 贴界判定要认的正是这件事。
    """
    base_chunk_size = max(1, residual) // 10
    prefix_token_len = len(creator.token_counter.encode(
        "[chunk 1/1000 of a long message]\n"))
    return {
        "base_chunk_size": base_chunk_size,
        "prefix_token_len": prefix_token_len,
        "chunk_body_limit": max(1, base_chunk_size - prefix_token_len),
        "clamped": base_chunk_size - prefix_token_len <= 0,
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
    # 每条臂**各算各的**（不共用一个上算出来的数）：三者的残余预算实测相同，
    # 但把「谁的量」写清楚，读数才不会在人改前提时悄悄错位。
    chains = {k: _chunk_body_limit(filled[0][1], r["residual"])
              for k, r in (("guard_off_1", off1), ("guard_off_2", off2),
                           ("guard_on", on))}
    chain = chains["guard_off_1"]
    if off1["residual"] >= 0:
        P.note(f"（守卫关着时，camel 拿 {off1['residual']} 这个数去做 "
               f"//10 再减 {chain['prefix_token_len']} 的前缀扣减 → 每块正文容量 "
               f"{chain['chunk_body_limit']} token）")
        if chain["clamped"]:
            P.note(f"（注意：上面那个 {chain['chunk_body_limit']} 是上游 "
                   f"`max(1, ...)` **兜底兜出来的** —— 算出来的容量本来小于 1。"
                   f"它是个夹逼产物，不是量出来的容量）")

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

    def _cells(r, c):
        return {"residual": r["residual"],
                "records_added": r["records_added"],
                "tokens_added": r["tokens_added"],
                "expansion": round(r["expansion"], 4),
                "head_intact": r["head_intact"],
                "chunk_body_limit": c["chunk_body_limit"],
                "base_chunk_size": c["base_chunk_size"],
                "prefix_token_len": c["prefix_token_len"]}

    P.emit_readings(
        "repro_01_slicing",
        arms={"guard_off_1": "守卫关（1）", "guard_off_2": "守卫关（2）",
              "guard_on": "守卫开"},
        readings={"guard_off_1": _cells(off1, chains["guard_off_1"]),
                  "guard_off_2": _cells(off2, chains["guard_off_2"]),
                  "guard_on": _cells(on, chains["guard_on"])},
        units={"residual": "token", "records_added": "条", "tokens_added": "token",
               "expansion": "倍（实增 token ÷ 待写消息自身 token）",
               "chunk_body_limit": "token/块", "base_chunk_size": "token",
               "prefix_token_len": "token"},
        boundaries=(
            ("guard_off_1", "residual",
             "截断**之后**算出来的，按构造就贴着上限 —— 它不是一个自由的输入"),
            ("guard_off_2", "residual", "同上"),
            ("guard_off_1", "chunk_body_limit",
             "卡在机制能表达的最小正文容量上：残余预算 120–139 都会得到 1，"
             "**这一格分不出区间内的差别**"),
            ("guard_off_2", "chunk_body_limit", "同上"),
            ("guard_on", "records_added",
             "1 是这个量的最小值（写一条消息不可能产生 0 条记录），"
             "所以它只说明「没坏」，**不说明「好」**"),
            ("guard_on", "chunk_body_limit", P.BOUND_UNMEASURED,
             "**这次没量到**：守卫开着时根本没走切片那条分支，这一格算出来的是"
             "「要是切了会是多少」，即**反事实**值，不是这次运行量到的容量"),
        ),
        note=f"上限 {limit} token；待写消息自身 {own} token；"
             f"守卫关那两遍是同一份前提下的两次独立运行（确定性对照）。"
             f"chunk_body_limit 那条链每一环都是实测的：残余预算 {off1['residual']} "
             f"→ //10 得 {chain['base_chunk_size']}，减去当场量出的前缀 "
             f"{chain['prefix_token_len']} → {chain['chunk_body_limit']}"
             + ("（这个 1 是 max(1, …) 兜底兜出来的）" if chain["clamped"]
                else "（不是兜底兜出来的，是算出来的）"),
    )
    return ok


if __name__ == "__main__":
    P.exit_with(main())
