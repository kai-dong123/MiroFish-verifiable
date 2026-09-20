"""一条命令跑完三个复现，**再对一次账**，并落下一份**可验证性报告**。

    python -m verification.run_all                     # 在 backend/ 下
    python -m verification.run_all --out /tmp/rep       # 换个落点
    python -m verification.run_all --no-report          # 只看屏幕，不落文件

不发 LLM 请求、不要 API key、不要 Zep、不花钱。机器闲着时本机约 38 秒跑完
（三次计时 37.1 / 37.8 / 37.8 秒；其中一部分是最后那步对账）。
**这个秒数不是刻度**：同一台机器、同一份代码，忙起来实测能到 86 秒。
（首次运行要下一次分词器的编码表 —— 一张几 MB 的静态表，不是 LLM 调用，但要用到网。）

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
的探针消息，两边就会各走各的 —— 那正是这一步要响的地方（它比的就是这三个数）。

所以它单独跑一遍、单独列在汇总里，**不并进那个 `x/3`** —— 三条复现回答的是
「仿真会不会坏」，对账回答的是「我们的材料有没有走岔」，两件事不该混成一个比率。
它**不重跑**装置那三条（那三条的正文刚跑出来还热着），只跑两份草稿，多花十来秒。

## 报告为什么是「原样转录 + 汇总」，而不是解析出结构化数字

报告里每一条的正文，就是那条命令**当时打在屏幕上的原话**，逐字转录。
它上面只有一层汇总（模块名 / 退出码 / 判定）。

**不解析数字**是故意的：一旦报告里的数字是"再算一遍"来的，它和产生它的那次
运行就可能对不上，而这份报告的全部意义就是"我看到的和它说的是同一件事"。
要结构化数字的话，那些数字在每条的正文里，抄得走。

报告另附一节**环境**：Python 版本、平台、camel/oasis 版本、分词器与它那张编码表
**在本机落盘的字节数**、现场量到的时钟步长、工作目录。
这是"这批数字是用什么跑的"的凭据 —— 换了环境结论应当一样，
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
import threading
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

#: 退出码 → 措辞。**只写一处。** 打屏那一列（`_MARK`）与产物里那一栏
#: （`_write_report` 里的 `verdicts`）都从它出来 —— 原先这两张表各写一份，
#: 同一份语义在本文件里抄了两遍：改一张不会响，打屏与产物就会分叉。形状和
#: `SELFPROOF.md` 里那次 `KeyError: '已否决'` 是同一个（那次是两张映射表
#: 分家），只是这次两张都是 `.get(rc, …)`、不会炸，只会悄悄说两种话。
VERDICTS = {0: "达到预期", 1: "没达到预期", 2: "没测到"}

#: 打屏用，前面带记号。`2` 单列，不折进任何一边。
_MARK = {rc: f"{mark} {VERDICTS[rc]}"
         for rc, mark in ((0, "√"), (1, "×"), (2, "○"))}


def _what_to_look_at(results: list, where: str = "下面") -> str:
    """汇总数字后面那句「该去看哪条」。`where` 是正文里相对位置（控制台是「上面」）。

    这句话以前是写死的「先看没通过的那条」—— 整批缺口**全是「没测到」**的时候
    它照样这么说，等于指着人去查一个不存在的失败。那正是这台装置要对着干的
    那件事（缺读数被当成结论），只不过发生在汇总层。所以按缺口**是哪一类**
    分开说：真有 `1` 才叫人去看，只有 `2` 就明说那是没量到。
    """
    n_failed = sum(1 for _, _, rc, _ in results if rc == 1)
    n_unmeasured = sum(1 for _, _, rc, _ in results if rc == 2)
    if n_failed:
        tail = f" **先看{where}没通过的那条。**"
        if n_unmeasured:
            tail += (f"（另有 {n_unmeasured} 条是「没测到」——"
                     "那是没量到读数，不是「没通过」。）")
        return tail
    if n_unmeasured:
        return (f" 余下 {n_unmeasured} 条是**「没测到」**：没量到读数，"
                "不是「没通过」，别照着失败去查。")
    return ""


def _boundary_disclaimer(results: list) -> list:
    """「边界」那条报「没达到预期」时，补一句「这不是修法没生效」。

    **只在真的发生时才返回东西。** 这句话原先无条件打印，而且是按下标说的
    「第 3 条」—— 于是那条报「达到预期」（这是**常态**：那一条量的是边界，
    本来就该达到自己声明的预期）或者报「没测到」的时候，屏幕上照样会替一个
    **没发生的「没达到预期」**开脱。一句替没发生的事作的解释，和一处假绿
    是同一类东西，只是矮了一层。它由 `CASES` 里的 `nature` 驱动，不按下标。
    """
    for (mod, what, nature), (_m, _w, rc, _b) in zip(CASES, results):
        if nature.startswith("边界") and rc == 1:
            return [f"  ↑ {what}",
                    f"    这一条报「没达到预期」**不适用**：它验的是**边界**"
                    f"（`{nature}`），不是修法 —— 这一层明说钉不住，见正文。"]
    return []


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
    if missing:
        # **「没测到」压过「不符」。** 原先写的是 `if missing and rc == 0`：一行抽
        # 不出来、另一行不一致时，`rc` 已经因为不一致变成了 `1`，这一句就不再升到
        # `2` —— 而下面正文里唯一会说「有一边抽不出来」的分支是 `elif rc == 2`。
        # 于是那句话只能从正文里**消失**：读者拿到的是「材料走岔了」，而其中一项
        # **根本没量到**。缺读数被当成了结论，正是这台装置对着干的那件事。
        rc = 2

    w = max(P._w(r[0]) for r in rows)
    lines.append("  " + "  ".join([P._pad("", w), P._pad("装置", 8),
                                   P._pad("草稿", 8), "对账"]).rstrip())
    lines.append("  " + "  ".join(["-" * w, "-" * 8, "-" * 8, "-" * 9]))
    for r in rows:
        lines.append("  " + "  ".join([P._pad(r[0], w), P._pad(r[1], 8),
                                       P._pad(r[2], 8), r[3]]).rstrip())
    lines.append("")
    # 两句**各自独立**地说：一件事是「没量到」，另一件是「量到了但对不上」。
    # 原先这里是一个 `if/elif/else`，两者同时成立时只能说出前一句（`elif`），
    # 后一句那件更硬的事实就跟着消失了。
    n_bad = sum(1 for r in rows if r[3].startswith("×"))
    if not missing and not n_bad:
        lines.append("  √ 两份材料报的是同一组数 —— 改过任何一边都要重跑这一步。")
    if missing:
        lines.append(f"  ○ 这几项有一边抽不出来：{'、'.join(missing)} —— "
                     "**这不是「一致」，是没测到**。多半是输出格式改过了。")
    if n_bad:
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
        "tokenizer_cache_bytes": None,
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
        env["tokenizer_cache_bytes"] = _tokenizer_cache_bytes()
    except Exception as exc:  # noqa: BLE001
        env["tokenizer"] = f"取不到（{exc.__class__.__name__}）"
    return env


#: 编码表那份静态数据的下载地址。tiktoken 把它按 **URL 的 sha1** 落进缓存目录，
#: 所以这个哈希就是缓存里的文件名 —— 于是不用去猜「哪个文件是它」。
_TIKTOKEN_BLOB = ("https://openaipublic.blob.core.windows.net/encodings/"
                  "o200k_base.tiktoken")


def _tokenizer_cache_bytes():
    """量一下那份编码表**在本机落盘多少字节**（拿不到就 `None`，不猜）。

    README 里写着「首次会下一张几 MB 的表」。那句话是**观测值不是常数** ——
    编码表跟着 `tiktoken` 的版本走，哪天变了，材料里那句话就悄悄过期了。
    所以把**实测**的这个数记进产物的环境块：将来谁要核，核的是它，不是散文。
    """
    import hashlib
    import tempfile

    cache = (os.environ.get("TIKTOKEN_CACHE_DIR")
             or os.environ.get("DATA_GYM_CACHE_DIR")
             or os.path.join(tempfile.gettempdir(), "data-gym-cache"))
    blob = os.path.join(cache, hashlib.sha1(_TIKTOKEN_BLOB.encode()).hexdigest())
    try:
        return os.path.getsize(blob)
    except OSError:
        return None                       # 缓存目录被别人清过／还没下完


#: 单条复现的墙钟上限（秒）。与 `e2e_stub` 的 `--timeout` 同量级：本机一条
#: 复现实测十来秒到一分钟，600 秒是「它已经不像在干活了」而不是「它有点慢」。
_ROUND_TIMEOUT_S = 600.0


def _run_one(mod: str, echo: bool = True,
             timeout: float = _ROUND_TIMEOUT_S,
             argv: list | None = None) -> tuple:
    """跑一条，**边跑边显示、同时逐字留下**。返回 `(退出码, 正文)`。

    子进程强制 UTF-8：管道读写不该受控制台代码页影响。屏幕那一路仍是原生
    编码（见 `verification/__init__.py`），两件事互不干扰。

    `echo=False` 时**只收不显** —— 对账那一步跑的是两份草稿，它们的正文只用来
    抽几个数，整段铺在屏幕上会把上面三条复现的结论淹掉。**收还是要收全的**，
    只是不显示。

    **卡死要占住 `2`，绝对不能占 `1`。** 原先这里没有上限：一条复现如果永远
    不返回（并发那条最可能），`run_all` 就一直挂着，报告一个字都不落 ——
    屏幕上既没有「达到预期」也没有「没测到」，**什么判定都没有**。

    加超时**不能只加 `proc.wait(timeout=…)` 再照返回码翻译**：本机实测，
    被 `kill()` 之后 `returncode` 是 **`1`** —— 和**合法的「没达到预期」是同一个
    码**。照码翻译的话，一条**根本没跑完**的复现会被译成「跑完了，只是没达到
    预期」，正是本装置要挡的那类假读数。所以超时**自己占住 `2`**，并把原因写进
    正文，让它和真跑完的那两条在报告里长得不一样。

    `argv` 只是给测试留的**注入口**（默认按 `mod` 拼 `-m`）：要验超时，就得有一条
    **真的会跑很久**的命令被掐掉。树里为此常驻一个只睡觉的模块，等于为了被杀死
    而交付一段死代码；让调用方递一条进来更省。
    """
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.Popen(
        argv if argv is not None else [sys.executable, "-m", mod],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env=env, cwd=os.getcwd(),
    )
    lines: list = []
    hit: list = []

    def _on_timeout():                  # 到点了：记一笔，然后掐掉它
        hit.append(True)
        try:
            proc.kill()
        except OSError:                 # 已经自己退了，那就算了
            pass

    timer = threading.Timer(timeout, _on_timeout)
    timer.start()
    try:
        assert proc.stdout is not None
        for raw in proc.stdout:
            text = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            lines.append(text)
            if not echo:
                continue
            try:
                print(text)
            except UnicodeEncodeError:  # 控制台编不出，就降级显示
                print(text.encode(sys.stdout.encoding or "utf-8",
                                  "replace").decode(sys.stdout.encoding or "utf-8",
                                                    "replace"))
        rc = proc.wait()
    finally:
        timer.cancel()
    if hit:
        note = f"○ 没测到：{timeout:.0f} 秒没跑完，已中断"
        lines.append(note)
        if echo:
            print(note)
        return 2, "\n".join(lines)
    if rc not in (0, 1, 2):
        # **三条复现的契约只有 `{0, 1, 2}`；落在外面的退出码 = 这一条没跑完。**
        # 最常来的是**被信号杀死**：POSIX 上 `wait()` 对死于信号的子进程返回
        # **负数**（`SIGKILL` -9、`SIGABRT` -6、`SIGSEGV` -11）—— 容器被
        # `stop`、OOM killer 动手、C 扩展段错误，都从这里进来。
        #
        # **不能原样放它过去**：它一旦进了 `main()` 那个 `max(...)`，`0` 比任何
        # 负数都大，汇总会从这个洞里把「一条都没跑成」读成「3/3 达到预期」，
        # 进程还退 `0` —— 那正是这台装置对着干的那件事（没量到被当成了结论），
        # 只不过发生在它自己身上。`mutations.py` 对同一件事写的是
        # `rc in (0, 1)`（见 `measured = ...`），这里同理。
        #
        # ⚠️ **Windows 上还有一半挡不住**：`proc.kill()` 在那边返回 `1`，
        # 与「跑成了但没达到预期」撞车（`_probe.py` 里已声明过这一条）。
        # 这一处只负责把**契约外的值**收进 `2`。
        note = (f"○ 没测到：进程非正常结束（退出码 {rc}）—— 它没有落回 0/1/2 里的"
                "任何一个，说明这一条**没跑完**，不是「跑成了但没达到预期」。")
        lines.append(note)
        if echo:
            print(note)
        return 2, "\n".join(lines)
    return rc, "\n".join(lines)


def _write_report(prefix: str, results: list, env: dict,
                  recon_rc: int = 0, recon_lines: tuple = ()) -> tuple:
    """落盘 `.md` 与 `.json`。返回两个路径。

    `.json` 里**只有汇总与环境**，外加每条的原文 —— 同样不做二次解析。
    """
    worst = max([rc for _, _, rc, _ in results] + [recon_rc], default=0)
    n_ok = sum(1 for _, _, rc, _ in results if rc == 0)
    # 措辞**不再在这里抄第二份** —— 用模块级那一张（见 `VERDICTS` 那里的说明）：
    # 打屏与产物必须说同一句话，而「同一句话抄两遍」正是它们分叉的唯一原因。
    verdicts = VERDICTS

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
           + ("" if n_ok == len(results) else _what_to_look_at(results)), "",
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
                "tokenizer", "tokenizer_cache", "tokenizer_cache_bytes",
                "clock_step_ns", "cwd"):
        val = env.get(key)
        label = {"python": "Python", "platform": "平台",
                 "camel_ai": "camel-ai", "camel_oasis": "camel-oasis",
                 "tokenizer": "分词器", "tokenizer_cache": "分词器缓存目录",
                 "tokenizer_cache_bytes": "编码表落盘字节数 (B)",
                 "clock_step_ns": "时钟最小步长 (ns)", "cwd": "工作目录"}[key]
        md.append(f"| {label} | {val if val is not None else '未知'} |")
    step_ns = env.get("clock_step_ns")
    if step_ns:
        # **比值现场算，不写死。** 原先这里写的是「比 camel 那个 `1e-6` 的排序偏移
        # 大两三个数量级」—— 那句话只在本机（Windows，一拍几百微秒）成立；换到
        # Linux（一拍 100 纳秒）方向就反了，而这一句正是**要印进产物**的那一句。
        # 同一件事在 `README.md` 与 `repro_03_concurrency.py` 里都带着平台限定，
        # 只有这一份没跟上 —— 又是一份没赶上修订的抄本，这次直接算出来，抄不了。
        camel_ns = 1e-6 * 1e9                      # camel 的排序偏移，1e-6 秒 = 1000 ns
        ratio = step_ns / camel_ns
        rel = (f"比它大 {ratio:,.0f} 倍" if ratio >= 1
               else f"比它**小** {1 / ratio:,.0f} 倍")
        md += ["", "时钟步长是**量出来的**，每次运行会有出入。camel 那个 `1e-6` 秒的排序",
               f"偏移折成 {camel_ns:,.0f} 纳秒；本机这一拍是 **{step_ns:,.0f} 纳秒**，{rel}。",
               "**这个比值随平台变，不是常数** —— 它在这里只作读数、不进任何判据"
               "（判据要的是与平台无关的量）。"]
    else:
        md += ["", "时钟步长这次没量到（上表记「未知」）—— 它只作读数、不进判据，"
               "所以不影响三条复现的判定。"]
    md += ["",
           "分词器那一行不是装饰：切片那一节的数字（270 条 / 5130 token）**是它数出来的**，",
           "换个分词器就不是这些数。它首次使用要下的一份静态数据文件"
           "（一张几 MB 的静态表，之后走缓存；本机实测字节数见下表）——",
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
                    "not_reached": sum(1 for _, _, rc, _ in results if rc == 1),
                    "unmeasured": sum(1 for _, _, rc, _ in results if rc == 2),
                    "worst_returncode": worst},
    }
    md_path, js_path = f"{prefix}.md", f"{prefix}.json"
    with open(md_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(md_text)
    with open(js_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(json_doc, f, ensure_ascii=False, indent=2)
    return md_path, js_path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="跑完三个复现并落一份可验证性报告")
    parser.add_argument("--out", default="verification_report",
                        help="报告落点前缀，会生成 <前缀>.md 与 <前缀>.json"
                             "（默认 ./verification_report）")
    parser.add_argument("--no-report", action="store_true",
                        help="只在屏幕上打印，不落文件")
    parser.add_argument("--timeout", type=float, default=_ROUND_TIMEOUT_S,
                        help=f"单条复现的墙钟上限（秒，默认 {_ROUND_TIMEOUT_S:.0f}）。"
                             "到点了报「没测到」（退 2），不报「没达到预期」")
    args = parser.parse_args(argv)

    # 落点先问一句（`--no-report` 时不必问）。**问在动手之前**：三个复现要跑一分
    # 来钟，等它们跑完再发现写不出去，等于把已经量到的读数连同退出码一起丢掉，
    # 而那时按契约只能退 `1` —— 读者会去找一个并不存在的失败。
    if not args.no_report:
        from . import _probe as P

        rc = P.refuse_out_path(f"{args.out}.md", f"{args.out}.json")
        if rc is not None:
            return rc

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
        rc, body = _run_one(mod, timeout=args.timeout)
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
        rc, body = _run_one(mod, echo=False, timeout=args.timeout)
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
          + ("" if n_ok == len(results) else f" ——{_what_to_look_at(results, '上面')}"))
    print(f"  {_MARK.get(recon_rc, f'? {recon_rc}'):<12} 对账（两份材料报的是不是同一组数）")
    print()
    for line in _boundary_disclaimer(results):
        print(line)
    print("  以上都是无 LLM 调用、无 API key、结果确定 —— 换台机器结论应当一样。")
    print("  （前提是分词器那份静态编码表拿得到 —— 首次使用要下一次，约几 MB，"
          "之后走缓存。）")
    print("  取不到时上面会明确写「没测到」，**不会**把没跑成的记成「没达到预期」"
          " —— 缺读数不是结论。")
    print("  对账单独列在汇总里，**不并进那个 x/3** —— 它不是第四个复现，")
    print("  它管的是「装置和准备发出去的草稿有没有走岔」。")

    if not args.no_report:
        env = _environment()
        try:
            md_path, js_path = _write_report(args.out, results, env,
                                             recon_rc, recon_lines)
        except OSError as exc:
            # 落点上面那道门已经问过一次（不存在/不可写）。这里接的是**它挡不住
            # 的那一半**：目录在、但文件建不出来（同名目录、被占用、只读盘）。
            # 同一条路：说明白、退 `2` —— 判定都算出来了，写不下去，**但绝不
            # 把这件事退成 `1`**（那是「有真的要看的东西」，会把人指去查复现）。
            print(f"\n○ 没测到：报告写不下去（{exc.__class__.__name__}: {exc}）—— "
                  "三条复现的判定都在上面，但**这一份报告没落成**。")
            return 2
        print()
        print(f"  报告已落盘：{os.path.abspath(md_path)}")
        print(f"              {os.path.abspath(js_path)}")
        print("  （不是通过率：两条是可修的具体失效，一条是划出来的边界。）")

    return max([rc for _, _, rc, _ in results] + [recon_rc], default=0)


if __name__ == "__main__":
    sys.exit(main())
