"""一条命令跑完三个复现，并落下一份**可验证性报告**。

    python -m verification.run_all                     # 在 backend/ 下
    python -m verification.run_all --out /tmp/rep       # 换个落点
    python -m verification.run_all --no-report          # 只看屏幕，不落文件

不发 LLM、不联网、不要 API key、不要 Zep、不花钱。几十秒跑完。

## 退出码（**三种，不是两种**）

    0   三条都达到预期
    1   有任意一条**没达到预期** —— 这是真的要看的东西
    2   有任意一条**没测到**（缺依赖、取不到源码、前提造不出来……）

`2` 和 `1` 分开是刻意的：**「没测到」不等于「通过」，也不等于「失败」**。
一个装置如果把「没跑起来」报成绿色，它后面所有的绿色都不值钱了。

## 报告为什么是「原样转录 + 汇总」，而不是解析出结构化数字

报告里每一条的正文，就是那条命令**当时打在屏幕上的原话**，逐字转录。
它上面只有一层汇总（模块名 / 退出码 / 判定）。

**不解析数字**是故意的：一旦报告里的数字是"再算一遍"来的，它和产生它的那次
运行就可能对不上，而这份报告的全部意义就是"我看到的和它说的是同一件事"。
要结构化数字的话，那些数字在每条的正文里，抄得走。

报告另附一节**环境**：Python 版本、平台、camel/oasis 版本、现场量到的时钟步长、
工作目录。这是"这批数字是用什么跑的"的凭据 —— 换了环境结论应当一样，
但那样的话**得能看出是换了环境**。

## 三条各自在说什么

| # | 复现 | 结论 |
|---|---|---|
| 1 | 切片正反馈环 | 一条放得下的消息被撕成几百片、膨胀一个数量级；守卫装上后 1 条 |
| 2 | 同拍碰撞 | 时钟一拍里两次 tool 调用会把请求和回执拆散 → 端点 400、整轮消失；守卫装上后合法 |
| 3 | 并发次序 | **不修**（是设计取舍）。核实成因、量出灵敏度、明说这一层钉不住 |

第 3 条和第 1、2 条同等重要，它不是"没做的东西"，是**划出来的边界**。
所以汇总里**不出现「通过率」**：三条回答的是三个不同性质的问题，
把它们并成一个比例，就把边界这条信息抹掉了。
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time

#: (模块名, 一句话说它验证什么, 这一条的性质)
CASES = (
    ("verification.repro_01_slicing",
     "切片正反馈环：放得下的消息被撕成几百片", "可修"),
    ("verification.repro_02_timestamp",
     "同拍碰撞：一拍内的两次 tool 调用把请求和回执拆散", "可修"),
    ("verification.repro_03_concurrency",
     "并发次序：核实成因、量灵敏度、明说这一层钉不住", "边界·不修"),
)

#: 退出码 → 汇总里的记号。`2` 单列，不折进任何一边。
_MARK = {0: "√ 达到预期", 1: "× 没达到预期", 2: "○ 没测到"}


def _environment() -> dict:
    """**这批数字是用什么跑的。** 拿不到的项如实写「未知」，不猜。"""
    env = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "cwd": os.getcwd(),
        "clock_step_ns": None,
        "camel_ai": None,
        "camel_oasis": None,
    }
    try:
        from . import _probe as P

        step = P.real_clock_step()
        env["clock_step_ns"] = round(step * 1e9) if step else None
    except Exception:  # noqa: BLE001
        pass
    for key, mod in (("camel_ai", "camel"), ("camel_oasis", "oasis")):
        try:
            env[key] = getattr(__import__(mod), "__version__", "未知")
        except Exception:  # noqa: BLE001
            pass
    return env


def _run_one(mod: str) -> tuple:
    """跑一条，**边跑边显示、同时逐字留下**。返回 `(退出码, 正文)`。

    子进程强制 UTF-8：管道读写不该受控制台代码页影响。屏幕那一路仍是原生
    编码（见 `verification/__init__.py`），两件事互不干扰。
    """
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.Popen(
        [sys.executable, "-m", mod],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env=env, cwd=os.getcwd(),
    )
    lines: list = []
    assert proc.stdout is not None
    for raw in proc.stdout:
        text = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        lines.append(text)
        try:
            print(text)
        except UnicodeEncodeError:      # 控制台编不出，就降级显示
            print(text.encode(sys.stdout.encoding or "utf-8",
                              "replace").decode(sys.stdout.encoding or "utf-8",
                                                "replace"))
    return proc.wait(), "\n".join(lines)


def _write_report(prefix: str, results: list, env: dict) -> tuple:
    """落盘 `.md` 与 `.json`。返回两个路径。

    `.json` 里**只有汇总与环境**，外加每条的原文 —— 同样不做二次解析。
    """
    worst = max((rc for _, _, rc, _ in results), default=0)
    n_ok = sum(1 for _, _, rc, _ in results if rc == 0)
    verdicts = {0: "达到预期", 1: "没达到预期", 2: "没测到"}

    md = ["# 可验证性报告", "",
          f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}", "",
          "> 这份报告**不是通过率**。三条回答的是三个不同性质的问题：两条是"
          "已复现并可修的具体失效，一条是**说得出为什么钉不住**的边界。",
          "> 把它们并成一个比例，就把第三条那条信息抹掉了。", "",
          "## 汇总", "",
          "| # | 复现 | 性质 | 判定 |", "|---|---|---|---|"]
    for i, (mod, what, rc, _) in enumerate(results, 1):
        md.append(f"| {i} | {what} | {CASES[i - 1][2]} | {verdicts.get(rc, rc)} |")
    md += ["", f"{n_ok}/{len(results)} 条达到预期。"
           + ("" if n_ok == len(results) else " **先看下面没通过的那条。**"), "",
           "## 环境（这批数字是用什么跑的）", "",
           "| 项 | 值 |", "|---|---|"]
    for key in ("python", "platform", "camel_ai", "camel_oasis",
                "clock_step_ns", "cwd"):
        val = env.get(key)
        label = {"python": "Python", "platform": "平台",
                 "camel_ai": "camel-ai", "camel_oasis": "camel-oasis",
                 "clock_step_ns": "时钟最小步长 (ns)", "cwd": "工作目录"}[key]
        md.append(f"| {label} | {val if val is not None else '未知'} |")
    md += ["", "时钟步长是**量出来的**，每次运行会有出入；结论只用到它比 camel 那个",
           "`1e-6` 的排序偏移大两三个数量级这一点。", "",
           "---", "", "## 各条原样转录", "",
           "> 下面每一条的正文，就是那条命令当时打在屏幕上的原话，逐字转录。",
           "> **不做二次解析** —— 报告里的数字如果是「再算一遍」来的，就可能和产生它的",
           "> 那次运行对不上，而这份报告的全部意义就是「我看到的和它说的是同一件事」。", ""]
    for i, (mod, what, rc, body) in enumerate(results, 1):
        md += [f"### {i}. {what}", "",
               f"- 命令：`python -m {mod}`",
               f"- 判定：**{verdicts.get(rc, rc)}**（退出码 `{rc}`）", "",
               "```text", body, "```", ""]

    md_text = "\n".join(md) + "\n"
    json_doc = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "not_a_pass_rate": True,
        "environment": env,
        "results": [
            {"n": i, "module": mod, "what": what, "nature": CASES[i - 1][2],
             "returncode": rc, "verdict": verdicts.get(rc, str(rc)),
             "transcript": body}
            for i, (mod, what, rc, body) in enumerate(results, 1)
        ],
        "summary": {"reached_expectation": n_ok, "total": len(results),
                    "worst_returncode": worst},
    }
    md_path, js_path = f"{prefix}.md", f"{prefix}.json"
    with open(md_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(md_text)
    with open(js_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(json_doc, f, ensure_ascii=False, indent=2)
    return md_path, js_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="跑完三个复现并落一份可验证性报告")
    parser.add_argument("--out", default="verification_report",
                        help="报告落点前缀，会生成 <前缀>.md 与 <前缀>.json"
                             "（默认 ./verification_report）")
    parser.add_argument("--no-report", action="store_true",
                        help="只在屏幕上打印，不落文件")
    args = parser.parse_args()

    print("=" * 66)
    print("装置自检：三个复现，一条命令")
    print("=" * 66)
    print("这三条**不是**「通过率」—— 它们是三个已经查实并复现过的具体问题，")
    print("以及装置对它们的处置：前两条修，第三条明说修不了、只说得出为什么。")

    results = []
    for mod, what, _nature in CASES:
        print()
        print("-" * 66)
        print(f"· {what}")
        print("-" * 66)
        rc, body = _run_one(mod)
        results.append((mod, what, rc, body))

    print()
    print("=" * 66)
    print("汇总")
    print("=" * 66)
    for mod, what, rc, _ in results:
        print(f"  {_MARK.get(rc, f'? {rc}'):<12} {mod.split('.')[-1]}")
    n_ok = sum(1 for _, _, rc, _ in results if rc == 0)
    print()
    print(f"  {n_ok}/{len(results)} 条达到预期"
          + ("" if n_ok == len(results) else " —— **先看上面没通过的那条**"))
    print()
    print("  第 3 条「没达到预期」不适用：它验的是**边界**，不是修法。")
    print("  三条都是离线、确定、无 API key —— 换台机器结论应当一样。")

    if not args.no_report:
        env = _environment()
        md_path, js_path = _write_report(args.out, results, env)
        print()
        print(f"  报告已落盘：{os.path.abspath(md_path)}")
        print(f"              {os.path.abspath(js_path)}")
        print("  （不是通过率：两条是可修的具体失效，一条是划出来的边界。）")

    return max((rc for _, _, rc, _ in results), default=0)


if __name__ == "__main__":
    sys.exit(main())
