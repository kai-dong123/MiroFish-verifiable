"""一条命令跑完三个复现。

    python -m verification.run_all            # 在 backend/ 下

不发 LLM、不联网、不要 API key、不要 Zep、不花钱。几十秒跑完。

## 退出码（**三种，不是两种**）

    0   三条都达到预期
    1   有任意一条**没达到预期** —— 这是真的要看的东西
    2   有任意一条**没测到**（缺依赖、源码对不上……）

`2` 和 `1` 分开是刻意的：**「没测到」不等于「通过」，也不等于「失败」**。
一个装置如果把"没跑起来"报成绿色，它后面所有的绿色都不值钱了。

## 三条各自在说什么

| # | 复现 | 结论 |
|---|---|---|
| 1 | 切片正反馈环 | 一条放得下的消息被撕成几百片、膨胀一个数量级；守卫装上后 1 条 |
| 2 | 同拍碰撞 | 时钟一拍里两次 tool 调用会把请求和回执拆散 → 端点 400、整轮消失；守卫装上后合法 |
| 3 | 并发次序 | **不修**（是设计取舍）。核实成因、量出灵敏度、明说这一层钉不住 |

第 3 条和第 1、2 条同等重要，它不是"没做的东西"，是**划出来的边界**。
"""

from __future__ import annotations

import subprocess
import sys

#: (模块名, 一句话说它验证什么)
CASES = (
    ("verification.repro_01_slicing",
     "切片正反馈环：放得下的消息被撕成几百片"),
    ("verification.repro_02_timestamp",
     "同拍碰撞：一拍内的两次 tool 调用把请求和回执拆散"),
    ("verification.repro_03_concurrency",
     "并发次序：核实成因、量灵敏度、明说这一层钉不住"),
)

#: 三个复现各自 main() 的返回 → 退出码。`None` 一律是「没测到」。
_RC = {None: 2, False: 1, True: 0}


def main() -> int:
    print("=" * 66)
    print("装置自检：三个复现，一条命令")
    print("=" * 66)
    print("这三条**不是**「通过率」—— 它们是三个已经查实并复现过的具体问题，")
    print("以及装置对它们的处置：前两条修，第三条明说修不了、只说得出为什么。")

    results = []
    for mod, what in CASES:
        print()
        print("-" * 66)
        print(f"· {what}")
        print("-" * 66)
        proc = subprocess.run([sys.executable, "-m", mod],
                              capture_output=False)
        results.append((mod, what, proc.returncode))

    print()
    print("=" * 66)
    print("汇总")
    print("=" * 66)
    worst = 0
    for mod, what, rc in results:
        mark = {0: "√ 达到预期", 1: "× 没达到预期", 2: "○ 没测到"}.get(rc, f"? {rc}")
        print(f"  {mark:<12} {mod.split('.')[-1]}")
        worst = max(worst, rc)
    print()
    n_ok = sum(1 for _, _, rc in results if rc == 0)
    print(f"  {n_ok}/{len(results)} 条达到预期"
          + ("" if n_ok == len(results) else " —— **先看上面没通过的那条**"))
    print()
    print("  第 3 条「没达到预期」不适用：它验的是**边界**，不是修法。")
    print("  三条都是离线、确定、无 API key —— 换台机器结论应当一样。")
    return worst


if __name__ == "__main__":
    sys.exit(main())
