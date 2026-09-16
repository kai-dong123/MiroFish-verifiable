"""一条命令跑完三个复现，**再对一次账**，并落下一份**可验证性报告**。

    python -m verification.run_all                     # 在 backend/ 下
    python -m verification.run_all --out /tmp/rep       # 换个落点
    python -m verification.run_all --no-report          # 只看屏幕，不落文件

不发 LLM 请求、不要 API key、不要 Zep、不花钱。本机约 38 秒跑完
（三次计时 37.1 / 37.8 / 37.8 秒；其中约十来秒是最后那步对账）。
（首次运行要下一次分词器的编码表，约 3.6 MB —— 那不是 LLM 调用，但要用到网。）

## 退出码（**三种，不是两种**）

    0   三条都达到预期、且对账一致
    1   有任意一条**没达到预期**，或者**两份材料对不上** —— 这是真的要看的东西
    2   有任意一条**没测到**（缺依赖、取不到源码、前提造不出来……），
        或者对账有一边**抽不出数**

`2` 和 `1` 分开是刻意的：**「没测到」不等于「通过」，也不等于「失败」**。
一个装置如果把「没跑起来」报成绿色，它后面所有的绿色都不值钱了。

## 最后那步「对账」在管什么（**它不是第四个复现**）

装置本体那三条复现，和 `upstream/` 里**准备发出去的**两份最小复现，报的是
同一组数（记录数 / 实增 token / 同拍违反数）。这两份**输入本来就不一样** ——
两条完全不同的探针消息，在这个分词器下都恰好数出 277 token，于是数字撞在了
一起。**这个「一致」是当下的巧合，不是结构保证**：换分词器、或者谁改了一边
的探针消息，两边就会各走各的，而不会有任何东西响。

所以它单独跑一遍、单独列在汇总里，**不并进那个 `x/3`** —— 三条复现回答的是
「仿真会不会坏」，对账回答的是「我们的材料有没有走岔」，两件事不该混成一个比率。
它**不重跑**装置那三条（那三条的正文刚跑出来还热着），只跑两份草稿，多花十来秒。

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

#: 上游草稿里那两份**自包含最小复现**。它们是另写的紧凑版（为了贴进 issue），
#: 数字必须和装置本体报的一致 —— 不一致就是有一边错了。
#: `(模块名, 显示名, 正文键 —— 要和 `_SHARED_NUMBERS` 里那个对上)`
DRAFTS = (
    ("verification.upstream.repro_min_01_slicing", "草稿①（最小复现）", "草稿①"),
    ("verification.upstream.repro_min_02_timestamp", "草稿②（最小复现）", "草稿②"),
)

#: **两份材料共用的那组数**，以及它各自在**人类输出**里长什么样。
#:
#: 每项是 `(叫法, 装置侧正文键, 装置侧正则, 草稿侧正文键, 草稿侧正则)`，
#: 每个正则里恰好一个捕获组。锚的是两边输出里**稳定出现的那几个短语**，不是整行。
#:
#: 为什么要有这一步（不是强迫症）：这两份的**输入根本就不一样** —— 装置那条探针
#: 消息是「【记录开始】…数据 数据…【记录结束】」（763 字），草稿那条是
#: 「记录0，记录1，…记录89，」（440 字）。两条完全不同的消息，在这个分词器下
#: **都恰好数出 277 token**，于是记录数与实增 token 撞在了一起。
#: **这个「一致」是当下的巧合，不是结构保证** —— 换分词器、或者谁改了一边的探针
#: 消息，两边就会各走各的，而不会有任何东西响。所以这里把它变成会响的。
_SHARED_NUMBERS = (
    ("① 新增记录数",
     "装置①", r"被切成 \*\*([\d,]+) 条\*\*",
     "草稿①", r"→ 一条消息变成 ([\d,]+) 条记录"),
    ("① 实增 token",
     "装置①", r"实增 ([\d,]+) token",
     "草稿①", r"token 实增 ([\d,]+)（"),
    ("② 同拍违反数",
     "装置②", r"两次调用同拍：\*\*([\d,]+) 处违反\*\*",
     "草稿②", r"违反「tool_calls 后必须紧跟它的回执」： ([\d,]+) 处"),
)


def _reconcile(transcripts: dict) -> tuple:
    """把两份材料的共有数字对一遍。返回 `(退出码, 正文行列表)`。

    退出码沿用同一套三态：`0` 对得上、`1` **对不上**（真要看的东西）、
    `2` 有一边**抽不出来**（改过输出格式、或那条没跑到 —— 没测到，不是通过）。
    **抽不出来时报 `2` 不报 `0`**：一个抽不到数的对账，说「通过」是假的。
    """
    import re as _re

    from . import _probe as P

    lines, rc, missing, rows = [], 0, [], []
    for what, dev_key, pat_dev, draft_key, pat_draft in _SHARED_NUMBERS:
        got = {}
        for side, key, pat in (("装置", dev_key, pat_dev),
                               ("草稿", draft_key, pat_draft)):
            m = _re.search(pat, transcripts.get(key, ""))
            got[side] = m.group(1).replace(",", "") if m else None
        if not (got["装置"] and got["草稿"]):
            verdict = "○ 没测到"
            missing.append(f"{what}（{'装置' if not got['装置'] else '草稿'}）")
        elif got["装置"] == got["草稿"]:
            verdict = "√ 一致"
        else:
            verdict = "× **不一致**"
            rc = 1
        rows.append([what, got["装置"] or "○ 抽不到", got["草稿"] or "○ 抽不到",
                     verdict])
    if missing and rc == 0:
        rc = 2

    w = max(P._w(r[0]) for r in rows)
    lines.append("  " + "  ".join([P._pad("", w), P._pad("装置", 8),
                                   P._pad("草稿", 8), "对账"]).rstrip())
    lines.append("  " + "  ".join(["-" * w, "-" * 8, "-" * 8, "-" * 9]))
    for r in rows:
        lines.append("  " + "  ".join([P._pad(r[0], w), P._pad(r[1], 8),
                                       P._pad(r[2], 8), r[3]]).rstrip())
    lines.append("")
    if rc == 0:
        lines.append("  √ 两份材料报的是同一组数 —— 改过任何一边都要重跑这一步。")
    elif rc == 2:
        lines.append(f"  ○ 这几项有一边抽不出来：{'、'.join(missing)} —— "
                     "**这不是「一致」，是没测到**。多半是输出格式改过了。")
    else:
        lines.append("  × **两份材料对不上** —— 草稿是准备发出去的，先查清哪边对。")
    return rc, lines


def _environment() -> dict:
    """**这批数字是用什么跑的。** 拿不到的项如实写「未知」，不猜。"""
    env = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "cwd": os.getcwd(),
        "clock_step_ns": None,
        "camel_ai": None,
        "camel_oasis": None,
        "tokenizer": None,
        "tokenizer_cache": None,
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
    # 分词器：切片那一节的数字**全依赖它**（270 条 / 5130 token 是它数出来的），
    # 而它首次使用要下的一份静态数据文件。所以这里把编码名和缓存状态一并记下 ——
    # 将来有人质疑某个数字，先看得到它是哪个分词器、在哪台机器上数的。
    try:
        import tiktoken

        enc = tiktoken.get_encoding("o200k_base")
        env["tokenizer"] = f"tiktoken o200k_base (n_vocab={enc.n_vocab})"
        env["tokenizer_cache"] = os.environ.get("TIKTOKEN_CACHE_DIR") or "默认临时目录"
    except Exception as exc:  # noqa: BLE001
        env["tokenizer"] = f"取不到（{exc.__class__.__name__}）"
    return env


def _run_one(mod: str, echo: bool = True) -> tuple:
    """跑一条，**边跑边显示、同时逐字留下**。返回 `(退出码, 正文)`。

    子进程强制 UTF-8：管道读写不该受控制台代码页影响。屏幕那一路仍是原生
    编码（见 `verification/__init__.py`），两件事互不干扰。

    `echo=False` 时**只收不显** —— 对账那一步跑的是两份草稿，它们的正文只用来
    抽几个数，整段铺在屏幕上会把上面三条复现的结论淹掉。**收还是要收全的**，
    只是不显示。
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
        if not echo:
            continue
        try:
            print(text)
        except UnicodeEncodeError:      # 控制台编不出，就降级显示
            print(text.encode(sys.stdout.encoding or "utf-8",
                              "replace").decode(sys.stdout.encoding or "utf-8",
                                                "replace"))
    return proc.wait(), "\n".join(lines)


def _write_report(prefix: str, results: list, env: dict,
                  recon_rc: int = 0, recon_lines: tuple = ()) -> tuple:
    """落盘 `.md` 与 `.json`。返回两个路径。

    `.json` 里**只有汇总与环境**，外加每条的原文 —— 同样不做二次解析。
    """
    worst = max([rc for _, _, rc, _ in results] + [recon_rc], default=0)
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
           "### 另：对账（**不并进上面那个 x/3**）", "",
           "> 上面那三条是**三个复现**；对账不是第四个 —— 它管的是另一件事："
           "装置本体报的数字，和准备发出去的**上游草稿**里那份最小复现报的，"
           "是不是同一组。两份的输入本来就不一样（两条不同的探针消息），"
           "所以「一致」不是结构保证，是一条要守的断言。", "",
           f"- 判定：**{verdicts.get(recon_rc, recon_rc)}**（退出码 `{recon_rc}`）", "",
           "```text", "\n".join(recon_lines), "```", "",
           "## 环境（这批数字是用什么跑的）", "",
           "| 项 | 值 |", "|---|---|"]
    for key in ("python", "platform", "camel_ai", "camel_oasis",
                "tokenizer", "tokenizer_cache", "clock_step_ns", "cwd"):
        val = env.get(key)
        label = {"python": "Python", "platform": "平台",
                 "camel_ai": "camel-ai", "camel_oasis": "camel-oasis",
                 "tokenizer": "分词器", "tokenizer_cache": "分词器缓存目录",
                 "clock_step_ns": "时钟最小步长 (ns)", "cwd": "工作目录"}[key]
        md.append(f"| {label} | {val if val is not None else '未知'} |")
    md += ["", "时钟步长是**量出来的**，每次运行会有出入；结论只用到它比 camel 那个",
           "`1e-6` 的排序偏移大两三个数量级这一点。",
           "",
           "分词器那一行不是装饰：切片那一节的数字（270 条 / 5130 token）**是它数出来的**，",
           "换个分词器就不是这些数。它首次使用要下的一份静态数据文件（约 3.6 MB，之后走缓存）——",
           "所以「不发 LLM 请求」是准确的，「这台机器上不需要任何网络」不是。", "",
           "---", "", "## 各条原样转录", "",
           "> 下面每一条的正文，就是那条命令当时打在屏幕上的原话，逐字转录。",
           "> **不做二次解析** —— 报告里的数字如果是「再算一遍」来的，就可能和产生它的",
           "> 那次运行对不上，而这份报告的全部意义就是「我看到的和它说的是同一件事」。",
           "",
           "> 唯一的例外是读数块（`.json` 里的 `readings`）：那是**复现自己按锚定",
           "> 分隔符打出来的一段结构化读数**，报告只是把它原样取出来，并记下它在正文",
           "> 里的 `readings_sha256`。这不是「从散文里抠数字」，取不到就记",
           "> `readings_missing: true`，**不猜**。", ""]
    for i, (mod, what, rc, body) in enumerate(results, 1):
        md += [f"### {i}. {what}", "",
               f"- 命令：`python -m {mod}`",
               f"- 判定：**{verdicts.get(rc, rc)}**（退出码 `{rc}`）", "",
               "```text", body, "```", ""]

    md_text = "\n".join(md) + "\n"

    def _repro_entry(i, mod, what, rc, body):
        """一条复现的机读条目。

        读数块由复现**自己按锚定分隔符吐出**，这里只把它取出来 —— 不是从散文里
        猜数字，所以「不做二次解析」这条纪律没有破。取不到就记 `readings_missing`：
        **「没测到」和「读数是空的」必须分开**，前者不许被读成后者。
        """
        from . import _probe as P

        block = P.parse_readings(body)

        entry = {"n": i, "module": mod, "what": what, "nature": CASES[i - 1][2],
                 "returncode": rc, "verdict": verdicts.get(rc, str(rc)),
                 "transcript": body}
        if block is None:
            entry["readings_missing"] = True
            entry["readings"] = None
            entry["readings_sha256"] = None
        else:
            entry["readings_missing"] = False
            entry["readings"] = block
            entry["readings_sha256"] = P.readings_sha256(body)
        return entry

    json_doc = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "not_a_pass_rate": True,
        "environment": env,
        "results": [_repro_entry(i, mod, what, rc, body)
                    for i, (mod, what, rc, body) in enumerate(results, 1)],
        "reconciliation": {"returncode": recon_rc,
                           "verdict": verdicts.get(recon_rc, str(recon_rc)),
                           "not_a_fourth_reproduction": True,
                           "transcript": "\n".join(recon_lines)},
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
    transcripts = {}
    for mod, what, _nature in CASES:
        print()
        print("-" * 66)
        print(f"· {what}")
        print("-" * 66)
        rc, body = _run_one(mod)
        results.append((mod, what, rc, body))
        # 正文按**复现号**收着，给下面那步对账用（键要和 `_SHARED_NUMBERS` 对上）
        if mod.endswith("repro_01_slicing"):
            transcripts["装置①"] = body
        elif mod.endswith("repro_02_timestamp"):
            transcripts["装置②"] = body

    # -- 对账：两份材料报的必须是同一组数 -----------------------------------
    #
    # **它不重复跑装置那两条** —— 那两条的正文上面刚跑出来、还热着。只跑两份草稿，
    # 拿它们的数字去比。这样这一步只多花十来秒，而不是把整套再跑一遍。
    print()
    print("-" * 66)
    print("· 对账：装置本体与上游草稿的「最小复现」，报的是不是同一组数")
    print("-" * 66)
    print("  这两份的输入**本来就不一样**（两条不同的探针消息），所以「数字一致」"
          "不是结构保证，是一条要守的断言。")
    for mod, label, key in DRAFTS:
        rc, body = _run_one(mod, echo=False)
        transcripts[key] = body
        print(f"  {'√' if rc == 0 else '○'} {label} 跑完"
              + ("" if rc == 0 else f"（退出码 {rc} —— 它自己那条没跑成，"
                                    f"对账只能是「没测到」）"))
    recon_rc, recon_lines = _reconcile(transcripts)
    for line in recon_lines:
        print(line)

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
    print(f"  {_MARK.get(recon_rc, f'? {recon_rc}'):<12} 对账（两份材料报的是不是同一组数）")
    print()
    print("  第 3 条「没达到预期」不适用：它验的是**边界**，不是修法。")
    print("  以上都是无 LLM 调用、无 API key、结果确定 —— 换台机器结论应当一样。")
    print("  （首次运行要下一次分词器的编码表，约 3.6 MB；之后走缓存。）")
    print("  对账单独列在汇总里，**不并进那个 x/3** —— 它不是第四个复现，")
    print("  它管的是「装置和准备发出去的草稿有没有走岔」。")

    if not args.no_report:
        env = _environment()
        md_path, js_path = _write_report(args.out, results, env,
                                         recon_rc, recon_lines)
        print()
        print(f"  报告已落盘：{os.path.abspath(md_path)}")
        print(f"              {os.path.abspath(js_path)}")
        print("  （不是通过率：两条是可修的具体失效，一条是划出来的边界。）")

    return max([rc for _, _, rc, _ in results] + [recon_rc], default=0)


if __name__ == "__main__":
    sys.exit(main())
