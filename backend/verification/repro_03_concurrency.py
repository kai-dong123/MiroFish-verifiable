"""复现三 · 并发次序：**这一层钉不住，而且说得出为什么**。

    python -m verification.repro_03_concurrency      # 在 backend/ 下

不发 LLM、不联网、不要 API key。

## 与前两个不同：这一条**不修**

前两个是可以修的缺陷：切片是判据写错，时间戳是偏移比时钟刻度还细。这一个不是
缺陷，是**设计取舍** —— 要说清它为什么修不了，以及装置拿它怎么办。

## 症状

上游 MiroFish 的两个 issue（#751 / #759）：**同一份输入跑两次，跑出不同的人群**
（弃权率 9.5% vs 60.0%），温度全设 0 仍然不同，API 层面没有任何提示。

## 成因（源码，脚本本体会现场核实）

`oasis/environment/env.py`：

    55   semaphore: int = 128                        # 默认并发上限
    70   self.llm_semaphore = asyncio.Semaphore(semaphore)
    127  async with self.llm_semaphore:              # _perform_llm_action
    193  await asyncio.gather(*tasks)                # 所有 agent 的动作并发执行

MiroFish 的驱动脚本把并发数设成 **30**（`scripts/run_parallel_simulation.py` 等
四处 `semaphore=30`）。于是同一轮里，**谁的 LLM 先返回、谁的动作就先落库** ——
而落库次序决定 `post_id` 的分配，进而决定后续交互指向哪条帖子。

**次序取决于 LLM 与网络的返回快慢，那是程序管不到的量。**

## 为什么不能靠"排个序"修掉

要让这一层逐字可复现，就得让 agent 的动作**串行执行**（或者按固定次序回放）。
而并发正是这个仿真的前提 —— 27 个 agent × 15 轮，串行意味着把墙钟时间乘上并发数。
**换来的确定性和花掉的时间，是个取舍，不是个对错。**

所以本装置的立场是：**这一层不承诺可复现，只承诺可检出。**

## 本脚本做两件事

1. **核实**：在真实的 oasis 源码里核对我们引的那几行确实存在、且是这样写的。
   引错了就报"没测到"，不报"通过"。
2. **量灵敏度**：造一个最小同类场景（`gather` + `Semaphore`），量出**多小的
   耗时差就能让次序变样**（实测 1 微秒）。量出来的数如果小得离谱，就说明
   「这只是边缘情况」这句话站不住 —— 而站不住的结论我们要自己先说。

   顺带量到一件更准的事：**次序是「耗时」的确定函数**（耗时全相同，跑两遍
   逐位相同），**不确定的是「耗时」本身**。所以问题不在事件循环，在喂给它的
   那个量由网络决定。

**这个脚本不证明 MiroFish 端到端不可复现。** 那需要真跑、需要 API key、
而且"跑两次不一样"本身也不是证明。它只说明**这一层的次序由什么决定**，
以及**为什么它钉不住**。
"""

from __future__ import annotations

import asyncio
import sys

from . import _probe as P

#: 与 MiroFish 驱动脚本里一致的并发上限（四处 `semaphore=30`）。
MIROFISH_SEMAPHORE = 30

#: 要核实的源码事实：(oasis 里的行号, 该行应包含的片段, 说明)
_ENV_FACTS = (
    (55, "semaphore: int = 128", "并发上限的默认值"),
    (70, "asyncio.Semaphore(semaphore)", "把它造成信号量"),
    (127, "async with self.llm_semaphore", "`_perform_llm_action` 在这里排队"),
    (193, "await asyncio.gather(*tasks)", "所有 agent 的动作并发执行"),
)


def _verify_source() -> bool | None:
    """**在真实源码里**核对那几行。核不上就返回 None（没测到），不是 False。"""
    try:
        import oasis.environment.env as env_mod
    except Exception as exc:  # noqa: BLE001
        P.skip(f"取不到 oasis 源码（{exc.__class__.__name__}: {exc}）—— 没测到。")
        return None

    path = env_mod.__file__
    P.note(f"源码：{path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError as exc:
        P.skip(f"读不了源码（{exc}）—— 没测到。")
        return None

    all_ok = True
    for lineno, fragment, why in _ENV_FACTS:
        actual = lines[lineno - 1] if 0 < lineno <= len(lines) else ""
        hit = fragment in actual
        all_ok = all_ok and hit
        P.ok(f"{lineno:>4} 行 {why}：`{actual.strip()}`") if hit else \
            P.bad(f"{lineno:>4} 行 **对不上** —— 期望含 `{fragment}`，实为 "
                  f"`{actual.strip()}`")
    if not all_ok:
        return None
    return True


def _driver_semaphore() -> int | None:
    """从 MiroFish 自己的驱动脚本里**读出**并发数，不用我们记的数。"""
    from pathlib import Path

    script = (Path(__file__).resolve().parent.parent
              / "scripts" / "run_parallel_simulation.py")
    if not script.is_file():
        return None
    for line in script.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("semaphore="):
            try:
                return int(line.split("=", 1)[1].split(",")[0].strip())
            except ValueError:
                return None
    return None


# --------------------------------------------------------------------------
# 灵敏度：多小的耗时差能把次序翻过来
# --------------------------------------------------------------------------


async def _round(delays, log) -> None:
    """一轮：所有 agent 抢一个信号量，谁先做完谁先落库。"""
    sem = asyncio.Semaphore(MIROFISH_SEMAPHORE)

    async def one(i, d):
        async with sem:
            await asyncio.sleep(d)
            log.append(i)          # 落库次序 = 完成次序

    await asyncio.gather(*[one(i, d) for i, d in enumerate(delays)])


def _order(delays):
    log: list = []
    asyncio.run(_round(delays, log))
    return log


def _flip_threshold(n: int = 8, probe_deltas=(1e-6, 1e-4, 1e-2)) -> list:
    """把 0 号 agent 依次拖慢几个量级，量出**多小的差就能让落库次序变样**。

    基准是「所有人耗时相同」那一轮的次序，**不是提交次序** —— 事件循环的唤醒序
    本来就不是提交序（实测：相同耗时的次序稳定但就是 `[0,2,6,5,7,4,1,3]`，
    不是 `0..7`）。这反而是更准的切入口：

        **次序是「耗时」的一个确定函数；不确定的是「耗时」本身。**

    返回 `[(δ 秒, 次序是否变了)]`。
    """
    out = []
    base = 0.02
    baseline = _order([base] * n)
    for d in probe_deltas:
        delays = [base] * n
        delays[0] = base + d
        out.append((d, _order(delays) != baseline))
    return out


def main() -> bool | None:
    P.title("复现三 · 并发次序：钉不住，且说得出为什么（离线、不要 API key）")
    P.quiet_logging()

    # -- 一、核实源码 ------------------------------------------------------
    P.step("一、在真实源码里核实成因 —— 引错了就该报「没测到」")
    if _verify_source() is None:
        return None
    sem = _driver_semaphore()
    if sem is None:
        P.skip("读不出 MiroFish 驱动脚本里的并发数 —— 没测到。")
        return None
    P.ok(f"MiroFish 驱动脚本里设的并发上限 = {sem}"
         + ("（与驱动脚本一致）" if sem == MIROFISH_SEMAPHORE else ""))

    # -- 二、量灵敏度 ------------------------------------------------------
    P.step("二、量灵敏度：多小的耗时差能让落库次序变样")
    rows = _flip_threshold()
    P.table([[f"{d * 1e6:,.0f} µs" if d < 1e-3 else f"{d * 1e3:,.1f} ms",
              "变了" if flip else "没变"]
             for d, flip in rows],
            header=["把一个 agent 拖慢", "落库次序"])
    smallest = min((d for d, flip in rows if flip), default=None)

    # -- 三、次序是确定的，不确定的是它的输入 ------------------------------
    P.step("三、次序是「耗时」的确定函数 —— 不确定的是「耗时」")
    a1, a2 = _order([0.02] * 8), _order([0.02] * 8)
    b = _order([0.02 + 1e-6] + [0.02] * 7)
    P.note(f"耗时全相同，跑两遍：{a1}")
    P.note(f"                     {a2}"
           + ("   ← 逐位相同" if a1 == a2 else "   ← **不一样**"))
    P.note(f"但它不是提交次序 0..7 —— 事件循环的唤醒序本来就不是提交序")
    P.note(f"只把 0 号拖慢 1µs：{b}")
    flipped = a1 != b

    # -- 判据 --------------------------------------------------------------
    P.step("判据")
    ok = True
    if a1 == a2:
        P.ok("耗时全相同时，两遍次序逐位相同 —— **这一层是确定的**，"
             "乱的不是事件循环，是喂给它的耗时")
    else:
        P.note("耗时全相同时两遍次序也不同 —— 那连「确定函数」这个说法都要收紧，"
               "如实记下")
    if flipped:
        P.ok(f"**1 微秒**的耗时差就让落库次序变了 —— 而这个次序决定 `post_id`，"
             f"`post_id` 决定后续交互指向谁")
    else:
        P.bad("1µs 都没变 —— 那「这只是边缘情况」这句话本身就需要重新量")
        ok = False
    if smallest is not None:
        P.ok(f"实测变样的最小耗时差 ≈ {smallest * 1e6:,.0f} µs")
    P.ok("而两次真实 LLM 调用之间的耗时差是**毫秒到秒**量级 —— "
         "比这个阈值大好几个数量级，**根本没有安全余量**")
    P.note("（上面「1 微秒」是脚本**自己设的输入**，不是量出来的 —— 量出来的那个"
           "阈值在上一行。而「真实 LLM 调用的耗时差是毫秒到秒」是**外部前提**："
           "这个脚本离线、不发请求，量不到它，这里按常识写下来。"
           "它要是错的，本节结论要重写。）")

    # -- 边界 --------------------------------------------------------------
    P.step("边界（**这一节和上面同等重要**）")
    print("  · 这个脚本**没有**证明 MiroFish 端到端不可复现。那要真跑、要 API key，")
    print("    而且「跑两次不一样」本身也不构成证明。")
    print("  · 它证明的是：**这一层的次序由 LLM 与网络的返回快慢决定**，")
    print("    而那个量不在程序手里 —— 所以它原理上钉不住，不是没修好。")
    print("  · 要让这一层逐字可复现，就得把 agent 的动作串行化；")
    print("    而并发正是这个仿真跑得动的前提。**这是取舍，不是对错。**")
    print("  · 本装置对此的立场：**这一层不承诺可复现，只承诺可检出。**")
    print("  · 装置在能钉住的层上钉死（见 `repro_01` / `repro_02`，")
    print("    那两条每次运行数字逐位相同），在钉不住的层上**明说钉不住**。")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
