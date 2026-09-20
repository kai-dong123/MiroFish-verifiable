"""变异测试留痕 —— 把「这套测试不是恒真的」变成一份**可复核的产物**。

`README.md` 里那几句「验过它不是恒真的（七处都变红 / 红 16·3·16 条 / 五处都红）」
原先只是**断言**：仓库里既没有变异脚本，也没有结果文件。一个无法复核的断言，
和一句自夸没有区别 —— 而它恰恰是「装置可信」这个论点的唯一支撑。

这个模块把那句话变成**可以重跑的东西**：逐条改坏被测的代码，跑测试，记录红了几条、
红在哪几条、原样输出是什么，再**保证还原**。产物落盘：

    backend/verification/MUTATIONS.md          （人读）
    backend/verification/mutations_report.json （机读，另有一道「报告没过期」的测试盯着）

复跑（在 `backend/` 下）：

    python -m verification.mutations

## 这份报告是什么、不是什么

* **是**：一张「改坏了会不会红」的对照表 —— 用来证明测试不是恒真的。
* **不是**：通过率、覆盖率、质量分。这里的红色**是期望的结果**，
  一条红都没有才是坏消息。**别把这张表的红条数读成任何形式的得分。**

## 三条纪律

1. **每处变异只改一处，改的是真实的源文件**（不是替身、不是 mock）——
   改完立刻跑测试，跑完立刻按字节还原。
2. **还原失败就报错**，不留一个被改坏的工作区。还原前后都记 `sha256`。
3. **有阴性对照**：一处语义上什么都不改的编辑（只加一句注释）必须**一条都不红**。
   没有这一条，上面那些红就没法排除「测试环境本来就红」这个解释 ——
   「一个只有一种输出方式的检查，不是检查」。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import platform
import re
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent          # backend/verification
BACKEND = HERE.parent                                   # backend/
SUITE = "verification/tests"

GUARDS = HERE / "camel_guards.py"
TIMESTAMP = HERE / "repro_02_timestamp.py"
CITATIONS = HERE / "tests" / "test_citations.py"
ADJUDICATE = HERE / "adjudicate.py"
#: 另外两道入口，加上汇总驱动 —— 「落点」那一组要证明**三道门都不是摆设**。
#: 它们共用 `_probe.refuse_out_path`，所以只验一处的话，谁把另外两道删掉，
#: 账上照样一片安静。
SELFPROOF = HERE / "selfproof.py"
RUN_ALL = HERE / "run_all.py"
#: 「没测到·不许折」那一组的靶子。这两份**此前不在任何变异的靶子里** ——
#: 它们一进名单，`sources` 就多两个（见 `_touched`），材料里那个数要跟着改。
E2E_STUB = HERE / "e2e_stub.py"
RECONCILE = HERE / "reconcile_selfcheck.py"
#: 本文件**自己**也是靶子（`O7`：留痕那道门）。这是唯一一处会改到「正在跑的那个
#: 文件」的变异：进程里那一份早已 `import` 完，磁盘上被改不影响本轮判定。
#: ⚠️ 代价要说清 —— **跑到一半被 kill，就会把 `mutations.py` 自己停在改坏的状态**，
#: 而坏掉的恰恰是那台用来自查的机器，下次连「账目对不上」都说不出口。
#: 中断过先 `git diff verification/mutations.py` 看一眼再重跑。
MUTATIONS_SELF = pathlib.Path(__file__).resolve()
#: 变异的靶子不一定是代码 —— `C7` 改的是这份 README 里那段**逐字贴出来的源码**。
README_MD = HERE / "README.md"
#: 另外两个非代码靶子：依赖清单（版本钉）与仓库根那份《开源及第三方资源使用清单》
#: （第一节那张「对上游的改动」表）。后者在 `backend/` **之外** —— 正是它逼出了
#: `_rel` 那个回退分支的错（见 `_rel`）。
REQUIREMENTS = BACKEND / "requirements.txt"
DOC_CLAIMS = BACKEND.parent / "docs" / "开源及第三方资源使用清单.md"

T_GUARDS = "verification/tests/test_camel_guards.py"
T_VERDICTS = "verification/tests/test_repro_verdicts.py"
T_CITATIONS = "verification/tests/test_citations.py"
T_ADJ = "verification/tests/test_adjudicate.py"
T_ADJ_E2E = "verification/tests/test_e2e_stub.py"
T_ENV_PINS = "verification/tests/test_environment_pins.py"
T_DOC_CLAIMS = "verification/tests/test_docs_claims.py"
T_BASELINE = "verification/tests/test_upstream_baseline.py"

#: 下半那条变异要植回去的**错引写法**。
#:
#: 故意**拼出来、不写成一整行**：本文件在 `verification/` 下，会被
#: `test_no_known_misquote_survives_in_our_materials` 扫（那个扫描盖
#: `verification/` 下所有 `.py` / `.md` / `.txt`，只排除 `tests/`）。
#: 写成一整行的话，**这一行自己就会被那条测试抓红**。
#:
#: 这不是绕开检查 —— 那条检查要抓的是「材料里**留下了**这个写法」；
#: 这里要的是「**制造一次**这个写法、看它会不会被抓到」。
#: 制造它的人不该同时被它抓住，否则这个变异永远做不出来。
_MISQUOTE_WRONG = "base_chunk_size - " + "12"
_MISQUOTE_RIGHT = "base_chunk_size - prefix_token_len"

#: 人读的产物里，那个字面量不再抄第二遍（理由同上：抄一遍报告自己就红）。
_REDACTION = "＜那个被引错的字面量，本报告不抄＞"
_REDACTION_NOTE = (
    "`C6` 那条的 `+` 行被**刻意屏蔽**成上面那个占位符：那个写法一旦抄进这份报告，"
    "**报告自己就会被 `test_no_known_misquote_survives_in_our_materials` 抓红**"
    "（理由和 `README.md` 里不抄第二遍是同一条）。要看原样 —— 连同那个字面量本身 —— "
    "去 `mutations_report.json`：后缀 `.json` 不在那条扫描的范围里。")


def _rel(p) -> str:
    """产物里一律写 **backend 相对路径**。

    绝对路径会把跑这份产物时的本机目录名（用户名在内）原样写进
    `mutations_report.json` / `MUTATIONS.md` —— 这两份是要公开出去的，
    路径本身跟结论没关系，却把「在谁的机器上跑的」漏了个干净。
    `_apply` 认相对路径（见那里），所以落盘的和用的可以是同一个值。
    """
    p = pathlib.Path(p)
    try:
        return str(p.relative_to(BACKEND)).replace("\\", "/")
    except ValueError:
        # 不在 `backend/` 下的（清单在仓库根的 `docs/` 里）。**这里原先回退成
        # `p.name`，那是个错的 —— `_apply` 拿这个值去拼 `BACKEND / file` 来找文件，
        # 只留文件名就会指向一个不存在的地方，变异根本落不下去。**
        # 一直没炸，只因为当时还没有一条变异碰过 `backend/` 之外的文件。
        # 写成 `../` 相对路径：既能被 `_apply` 拼回原地，又不把绝对路径漏进产物。
        return "../" + str(p.relative_to(BACKEND.parent)).replace("\\", "/")


def _M(mid, group, what, target, edits, *, expect=None, claim=""):
    """一条变异。`expect` = **材料里声明的**红条数；None 表示只声明「至少一条红」。"""
    return {
        "id": mid,
        "group": group,
        "what": what,
        "target": target,
        "edits": [{"file": _rel(f), "old": o, "new": n} for f, o, n in edits],
        "expect_failed": expect,
        "claim": claim,
    }


#: 组名。README 的四组，加上一句阴性对照。
G_GUARD = "守卫"
G_VERDICT = "判词"
G_CITE_UP = "引文·上半"
G_CITE_DOWN = "引文·下半"
G_ADJ = "裁决"
G_ADJ_MISS = "裁决·缺读数"
G_ADJ_VAC = "裁决·恒真"
#: 后加的两组。**没有并进上面任何一组** —— 上面那几组的条数写在 README 的
#: 声明里（「守卫：七处」），并进去就会把那句话变成过期的。
G_COUNTERS = "守卫·计数落盘"
G_ADJ_E2E = "裁决·端到端"
G_CITE_VERBATIM = "引文·逐字块"
G_PINS = "环境·版本钉"
G_DIFF_TABLE = "清单·改动表"
G_BASELINE = "上游基线"
G_OUT = "落点"
G_UNMEASURED = "没测到·不许折"
G_CONTROL = "阴性对照"

CLAIM_7 = "README「守卫：两个方向都要成立」：七处变异都变红"
CLAIM_5 = "README「引文：文档里的行号不许腐烂」：上半五处变异都红"

MUTATIONS = (
    # ---- 守卫：七处 --------------------------------------------------------
    _M("G1", G_GUARD, "判据的边界写成 `>=`（顶格的消息会被误判成超限）",
       T_GUARDS, [(GUARDS, "    if own_tokens > limit:", "    if own_tokens >= limit:")],
       claim=CLAIM_7),
    _M("G2", G_GUARD, "整个守卫变成空操作（开头就把活原样交回原方法）",
       T_GUARDS, [(GUARDS,
                   '    """替换 `ChatAgent.update_memory` 的那个函数。两个开关在这里读。"""\n'
                   '    original = _state["original"]',
                   '    """替换 `ChatAgent.update_memory` 的那个函数。两个开关在这里读。"""\n'
                   '    original = _state["original"]\n'
                   '    return original(self, message, role, timestamp)  # 变异：空操作')],
       claim=CLAIM_7),
    _M("G3", G_GUARD, "变成「一律不切」（该切的那条路被永远关掉）",
       T_GUARDS, [(GUARDS, "    if own_tokens > limit:", "    if False:")],
       claim=CLAIM_7),
    _M("G4", G_GUARD, "逻辑步长调到比 camel 那个 `1e-6` 还细",
       T_GUARDS, [(GUARDS, "STEP = 1e-3", "STEP = 1e-7")],
       claim=CLAIM_7),
    _M("G5", G_GUARD, "时间戳不再往后推（拿掉严格递增那一步）",
       T_GUARDS, [(GUARDS,
                   "    if last is not None and value < last + STEP:\n"
                   "        value = last + STEP\n"
                   "    agent._ts_guard_last = value",
                   "    agent._ts_guard_last = value")],
       claim=CLAIM_7),
    _M("G6", G_GUARD, "去掉兜底（算不出 token 时不再交回原方法，直接抛）",
       T_GUARDS, [(GUARDS,
                   "    except Exception:  # noqa: BLE001\n"
                   "        # 算不出来就别自作聪明 —— 交回原方法。\n"
                   '        if _state["timestamp"]:\n'
                   "            _note_timestamp(self, timestamp)\n"
                   "        return original(self, message, role, timestamp)",
                   "    except Exception:  # noqa: BLE001\n"
                   "        raise")],
       claim=CLAIM_7),
    _M("G7", G_GUARD, "`install` 不再幂等（第二次调用会套第二层补丁）",
       T_GUARDS, [(GUARDS,
                   '    if _state["patched"]:\n'
                   '        _state["slicing"] = slicing\n'
                   '        _state["timestamp"] = timestamp\n'
                   "        return _state",
                   '    if False:\n'
                   '        _state["slicing"] = slicing\n'
                   '        _state["timestamp"] = timestamp\n'
                   "        return _state")],
       claim=CLAIM_7),

    # ---- 判词：三处 --------------------------------------------------------
    _M("V1", G_VERDICT, "判词写死（直接把结论摆在预期那一侧，不再由读数算）",
       T_VERDICTS, [(TIMESTAMP,
                     "    same = (gap / tick) < 1.0 if tick > 0 else False",
                     "    same = want_same")],
       expect=16, claim="README「判词」：判词写死 → 红 16 条"),
    _M("V2", G_VERDICT, "判据的 `<` 写成 `<=`（`gap == tick` 会被算成同一拍）",
       T_VERDICTS, [(TIMESTAMP,
                     "    same = (gap / tick) < 1.0 if tick > 0 else False",
                     "    same = (gap / tick) <= 1.0 if tick > 0 else False")],
       expect=3, claim="README「判词」：`<` 写成 `<=` → 红 3 条"),
    _M("V3", G_VERDICT, "去掉「与预期相反」那一支（与预期不符时折回预期那一侧的话术）",
       T_VERDICTS, [(TIMESTAMP,
                     '    n = gap / tick if tick > 0 else float("nan")\n'
                     '    return ("**同一拍**（与预期相反）" if same\n'
                     '            else f"**跨到 {n:,.0f} 拍**（与预期相反）")',
                     '    return ("同拍 → 碰撞才发生" if same\n'
                     '            else "跨拍 → 误打误撞免疫")')],
       expect=3, claim="README「判词」：去掉「与预期相反」那一支 → 红 3 条"),

    # ---- 引文·上半：五处 ---------------------------------------------------
    _M("C1", G_CITE_UP, "行号错开一格（933 → 934）",
       T_CITATIONS, [(CITATIONS,
                      '("camel.agents.chat_agent", 933,',
                      '("camel.agents.chat_agent", 934,')],
       claim=CLAIM_5),
    _M("C2", G_CITE_UP, "引一个越界的行号（884 → 999999）",
       T_CITATIONS, [(CITATIONS,
                      '("camel.agents.chat_agent", 884,',
                      '("camel.agents.chat_agent", 999999,')],
       claim=CLAIM_5),
    _M("C3", G_CITE_UP, "换成那一行没有的片段（`// 10` 写成 `// 100`）",
       T_CITATIONS, [(CITATIONS,
                      '"base_chunk_size = max(1, remaining_budget) // 10",',
                      '"base_chunk_size = max(1, remaining_budget) // 100",')],
       claim=CLAIM_5),
    _M("C4", G_CITE_UP, "引一个不存在的模块（`camel.memories.base` → `..._missing`）",
       T_CITATIONS, [(CITATIONS,
                      '("camel.memories.base", 143,',
                      '("camel.memories.base_missing", 143,')],
       claim=CLAIM_5),
    _M("C5", G_CITE_UP, "同一行引两遍（把 env:55 那条改成 env:193，片段也跟着改成 193 行的）",
       T_CITATIONS, [(CITATIONS,
                      '("oasis.environment.env", 55,',
                      '("oasis.environment.env", 193,'),
                     (CITATIONS,
                      '"semaphore: int = 128",',
                      '"await asyncio.gather(*tasks)",')],
       claim=CLAIM_5),

    # ---- 引文·下半：一处 ---------------------------------------------------
    _M("C6", G_CITE_DOWN, "把那个错引写法**植回 `camel_guards.py`**，看扫描抓不抓",
       T_CITATIONS, [(GUARDS, _MISQUOTE_RIGHT, _MISQUOTE_WRONG)],
       expect=1, claim="README「引文」：下半把那个写法植回 `camel_guards.py`，当场红"),

    # ---- 引文·逐字块：一处 -------------------------------------------------
    # README §① 那个块贴着上游源码、逐行标了行号。把其中一行的行号**错开一格**，
    # 那一行就指向了另一行（886 → 885 是个空行）—— 也就是「材料里贴着一行
    # 上游根本没有的代码」。这一条要证明第三半那个检查**不是恒真的**。
    _M("C7", G_CITE_VERBATIM, "逐字块里的行号错开一格（886 → 885，那一行是空行）",
       T_CITATIONS, [(README_MD,
                      "if current_tokens <= remaining_budget:                         # 886",
                      "if current_tokens <= remaining_budget:                         # 885")],
       expect=1, claim="README「引文」：标了行号的逐字块，行号错了当场红"),

    # ---- 裁决：三处 --------------------------------------------------------
    # 判据表那三条规则里，**贴界按单元格判**是最深的一条：它错成乘积式，
    # 产物照样长得像证据，而且降级得**没人看得出来**（本装置在别处真踩过）。
    _M("J1", G_ADJ, "贴界退化成「碰过这一臂或这一量的格子都算贴界」（一格贴界，整行整列降级）",
       T_ADJ, [(ADJUDICATE,
                '        hits = [f"{a}.{m}" for a, m in c["operands"] if (a, m) in railed]',
                '        _arms = {a for a, _ in railed}\n'
                '        _mets = {m for _, m in railed}\n'
                '        hits = [f"{a}.{m}" for a, m in c["operands"]\n'
                '                if (a, m) in railed or a in _arms or m in _mets]')],
       expect=1, claim="README「裁决：三种结果不是两种」：贴界按单元格判，退化成乘积当场红"),

    _M("J2", G_ADJ_MISS, "把「缺读数」折进「否决」—— 正是本装置抓别人的那件事",
       T_ADJ, [(ADJUDICATE, '"check": c["check"], "verdict": UNDECIDED,',
                '"check": c["check"], "verdict": FAIL_,  # 变异：没测到就当没通过')],
       # 期望值 3 → 4（2026-09-19）：当时「四种结果都吐得出」那条测试还不存在，所以
       # 折进去之后只有三条会红。现在多了一条守在出口的闭集检查，这一处改坏会多红一条。
       expect=4, claim="README「裁决」：缺读数判不可判定，折进「否决」当场红"),

    _M("J3", G_ADJ_VAC, "falsifier 只查在不在，**不实例化** —— 于是它永远「翻得动」",
       T_ADJ, [(ADJUDICATE,
                '            if after[cid]["verdict"] != base[cid]["verdict"]:',
                '            if True:  # 变异：声明了就算数，不去试它')],
       # 期望值 1 → 2（2026-09-20）：多出来的那条是
       # `test_a_claim_that_no_single_change_can_flip_is_not_trusted` ——
       # 「恒真 → 不采信」那条规则落地时新加的。它现造一条**翻不动的**判据，
       # 断言它必须 `trusted=False`；而这一处变异让「翻得动」变成恒真，
       # 于是那条断言跟着红。**同一处改坏现在会被两道检查夹住**：
       # 一道看「报了没报恒真」，一道看「报了恒真之后有没有真的不采信」。
       expect=2, claim="README「裁决·非空泛」：falsifier 必须实例化，只查在不在当场红"),

    _M("J4", G_ADJ_VAC, "**判据恒真也照退 0** —— 这张表开始装绿",
       T_ADJ, [(ADJUDICATE,
                '        return 1\n    return 0\n\n\nif __name__ == "__main__":',
                '        return 0  # 变异：有恒真判据也当表是好的\n'
                '    return 0\n\n\nif __name__ == "__main__":')],
       expect=1, claim="README「裁决：恒真就不许退 0」：判据恒真时退出码必须非 0"),

    _M("J5", G_ADJ_MISS, "**「没测到」退 1**（退成「没达到预期」）—— 正是本装置"
                         "抓别人的那件事，落在自己身上",
       T_ADJ, [(ADJUDICATE,
                '        print(f"\\n○ 没测到：{e}")\n        return 2',
                '        print(f"\\n○ 没测到：{e}")\n        return 1  # 变异：折成「没达到预期」')],
       expect=1, claim="README「退出码：三种不是两种」：前提不成立退 2，折成 1 当场红"),

    # ---- 守卫·计数落盘 ----------------------------------------------------
    # 这一格从前是空的：`counters()` **只有测试在调**，谁真拿 `--guards both`
    # 跑一整局也拿不到任何一个数。补上之后要有个东西守着它不被拿掉。
    _M("J6", G_COUNTERS, "**装守卫时不安排落盘** —— 计数照样烂在内存里，"
                         "一次真跑还是什么都看不见（回到补它之前那个状态）",
       T_GUARDS, [(GUARDS,
                   '    _state["patched"] = True\n    _arrange_counters_dump()',
                   '    _state["patched"] = True  # 变异：不安排落盘')],
       expect=1, claim="README「守卫端到端」：装了守卫就得安排落盘，拿掉当场红"),

    # ---- 裁决·端到端 ------------------------------------------------------
    _M("J7", G_ADJ_E2E, "端到端报告不在时**编一份读数**出来 —— 最容易写下的"
                        "那种「补全」，而且编完那张表看着更完整",
       T_ADJ_E2E, [(ADJUDICATE,
                    '    if not path.is_file():\n        return None\n    try:',
                    '    if not path.is_file():\n'
                    '        # 变异：没跑过就编一份读数 —— 于是那五条照判「通过」\n'
                    '        return {"results": [{"readings": {\n'
                    '            "readings": {\n'
                    '                "roomy_e2e": {"written_whole": 1, '
                    '"still_sliced": 0,\n'
                    '                              "timestamp_pushed": 1, '
                    '"db_posts": 1},\n'
                    '                "bigtext_e2e": {"written_whole": 1, '
                    '"still_sliced": 1,\n'
                    '                               "timestamp_pushed": 0, '
                    '"db_posts": 1},\n'
                    '                "two_e2e": {"written_whole": 2, '
                    '"still_sliced": 0,\n'
                    '                            "timestamp_pushed": 1, '
                    '"db_posts": 2}},\n'
                    '            "boundaries": []}}]}\n'
                    '    try:')],
       expect=1, claim="README「裁决：三种结果不是两种」：端到端读数缺了要判不可判定，"
                       "编一份补上当场红"),

    # ---- 环境·版本钉：一处 -------------------------------------------------
    # `tiktoken` 是装置**直接** import 的（`run_all.py` 拿它数 token），原先却
    # 一个字都没写在 `requirements.txt` 里 —— 装上了只是因为 `camel-ai` 的传递依赖
    # 把它带了进来。这一处变异就是「有人把后来补上的那个锁定放开」。
    _M("P1", G_PINS, "把 `tiktoken` 的锁定从 `==0.7.0` 放成 `>=0.1`",
       T_ENV_PINS, [(REQUIREMENTS, "tiktoken==0.7.0", "tiktoken>=0.1")],
       expect=1, claim="环境版本钉：直接依赖被放成开区间 → 当场红"),

    # ---- 清单·改动表：一处 -------------------------------------------------
    # 第一节那张表的数字此前是**纯手写**的，而且写错过三处。这一处变异就是
    # 「有人把其中一个数改歪」—— 它必须被现场 diff 当场抓住。
    _M("D1", G_DIFF_TABLE, "清单改动表里把一个数目改歪（`requirements.txt` 15 → 16）",
       T_DOC_CLAIMS, [(DOC_CLAIMS, "| 15 行插入 |", "| 16 行插入 |")],
       expect=1, claim="清单第一节：改动数目和现场 diff 对不上 → 当场红"),

    # ---- 上游基线：一处 ----------------------------------------------------
    # 「先问一句这里到底是不是 git 仓库」那道门，是踩出来的：没有 `.git` 的副本
    # （从 GitHub 下载 ZIP 就是）原会撞上一条红，而红上指控的是「历史被人重写过」。
    # 这一处变异就是「那道门被焊死」—— 门永远关着，本仓里这条检查就再也不跑了。
    _M("N1", G_BASELINE, "把「这里是不是 git 仓库」那道门焊死（`_is_repo()` 恒为假）",
       T_BASELINE, [(BACKEND / T_BASELINE,
                     '    return out.returncode == 0 and out.stdout.strip() == "true"',
                     "    return False  # 变异：门永远关着")],
       expect=1, claim="上游基线：门恒假 → 本仓里那条阴性对照当场红"
                       "（**本仓明明在仓库里，却被判成不是**）"),

    # ---- 落点：七处 --------------------------------------------------------
    # 这一组补的是一处**已经量到过**的边界：`--out` / `--json` / `--md` 指到一个
    # 不存在的目录时，落盘那一步抛 `FileNotFoundError`、没人接、进程退 `1`。
    # 按本装置自己的表，`1` 是「跑成了但没达到预期」—— 而那一刻**一个读数都没
    # 落下来**。观众会去找一个不存在的失败。
    #
    # 修法是**跑之前先问一句落点**。所以这几处要证明的是那两道出口都**不是摆设**：
    # 门（在动手之前退 `2`）和 `except OSError`（门挡不住的那一半也得退 `2`，
    # 因为门只问得出「目录在不在、可不可写」，问不出磁盘满、路径太长）。
    #
    # **六道入口各验一处**（`O1`–`O4` 三道、加上 `O5`–`O7` 补的三道）—— 它们共用
    # `_probe.refuse_out_path`，只验一处的话，谁把另外几道门删掉，这张表上什么都
    # 不会响。原先这里写的是「三道入口」并只验了三道，而当时**有门的也只有那三道**：
    # 另外三道（端到端、对账、留痕）在坏落点上照样抛 traceback 退 `1`，
    # 各自的表里 `1` 却是「没达到预期」「不符」「与声明不符」。**六道门是补出来的，
    # 所以六处都要有靶子** —— 补门那次把别的入口漏掉，就是同一个错的另一遍。
    _M("O1", G_OUT, "汇总驱动把落点那道门摘了（`--out` 不通也照跑三个复现）",
       T_VERDICTS, [(RUN_ALL,
                     '        rc = P.refuse_out_path(f"{args.out}.md", f"{args.out}.json")',
                     "        rc = None  # 变异：落点这道门形同虚设")],
       expect=1, claim="落点：门被摘掉 → 「坏落点要在动手之前退」当场红"),
    _M("O2", G_OUT, "裁决把落点那道门摘了（判定照算，算完才发现写不出去）",
       T_ADJ, [(ADJUDICATE,
                "    rc = P.refuse_out_path(args.json, args.md)",
                "    rc = None  # 变异：落点这道门形同虚设")],
       expect=1, claim="落点：裁决那道门被摘掉 → 当场红"),
    _M("O3", G_OUT, "裁决写不下去时报「没达到预期」（`2` 改成 `1`）",
       T_ADJ, [(ADJUDICATE,
                '              "表算出来了，但**这一份产物没落成**。")\n'
                "        return 2",
                '              "表算出来了，但**这一份产物没落成**。")\n'
                "        return 1  # 变异：把「没落成」报成「没达到预期」")],
       expect=1, claim="落点：写不下去时折成 `1` → 当场红（`1` 会把人指去查判据）"),
    _M("O4", G_OUT, "自证把落点那道门摘了",
       T_ADJ, [(SELFPROOF,
                "    rc = P.refuse_out_path(args.json, args.md)",
                "    rc = None  # 变异：落点这道门形同虚设")],
       expect=1, claim="落点：自证那道门被摘掉 → 当场红"),
    _M("O5", G_OUT, "端到端把落点那道门摘了（真去跑那一局，跑完才发现写不出去）",
       T_VERDICTS, [(E2E_STUB,
                     "    rc = P.refuse_out_path(args.out,\n"
                     '                           str(pathlib.Path(args.out).with_suffix(".md")))',
                     "    rc = None  # 变异：落点这道门形同虚设\n"
                     "    _ = (args.out, str(pathlib.Path(args.out).with_suffix('.md')))")],
       expect=1, claim="落点：端到端那道门被摘掉 → 当场红"),
    _M("O6", G_OUT, "对账把落点那道门摘了",
       T_VERDICTS, [(RECONCILE,
                     "    rc = P.refuse_out_path(args.json, args.md)",
                     "    rc = None  # 变异：落点这道门形同虚设")],
       expect=1, claim="落点：对账那道门被摘掉 → 当场红"),
    _M("O7", G_OUT, "留痕把落点那道门摘了（⚠️ 这条改的是本文件自己）",
       T_VERDICTS, [(MUTATIONS_SELF,
                     "        rc = P.refuse_out_path(args.json, args.md)\n"
                     "        if rc is not None:\n"
                     "            return rc",
                     "        rc = None  # 变异：落点这道门形同虚设\n"
                     "        if rc is not None:\n"
                     "            return rc")],
       expect=1, claim="落点：留痕那道门被摘掉 → 当场红"),

    # ---- 没测到·不许折：六处 ------------------------------------------------
    # 这一组是这台装置**自己的立场**在源码里的落点：`0` 达到预期、`1` 跑成了但
    # 没达到预期、`2` 没测到 —— `2` **不许**折进任何一边。它盯别人的正是这件事，
    # 而它自己在六处犯了同一个错，两个方向都有：
    #
    # * **把「没跑完」记成「跑成了」**（`X1`：契约外的退出码进 `max(...)`，
    #   `0` 比任何负数都大，于是「一条都没跑成」被读成「全部达到预期」）；
    # * **把「没跑完」记成「没达到预期」**（`X2`：端到端那一档跑的是**上游脚本**，
    #   契约里根本没有 `2`，`rc != 0` 排在前面，替一个没跑完的档位宣布了结论）；
    # * **让「没量到」被「量到了但对不上」顶掉**（`X3`/`X4`：对账的两句话）；
    # * **同一份语义抄两份表**（`X5`：打屏一列、产物一栏 —— 不炸，只说两种话）；
    # * **只接住一半的形状错**（`X6`：`JSONDecodeError` 接住了，
    #   「是 JSON、但结构不对」漏了，后者甩 traceback 退成 `1`）。
    #
    # 六处都已经修好，这一组证明的正是**那些修法不是摆设**。
    _M("X1", G_UNMEASURED, "汇总驱动把契约外的退出码原样放过去（`2` 那道判据形同虚设）",
       T_VERDICTS, [(RUN_ALL,
                     "\n    if rc not in (0, 1, 2):\n",
                     "\n    if False:  # 变异：契约外的退出码放它过去\n")],
       expect=1, claim="没测到：被信号杀死的复现不许记成「达到预期」→ 当场红"),
    _M("X2", G_UNMEASURED, "端到端把「没跑完」判成「没达到预期」（`rc != 0` 排到前面）",
       T_ADJ_E2E, [(E2E_STUB,
                    '\n    if run["rc"] not in (0, 1):\n',
                    "\n    if False:  # 变异：契约外的退出码放它过去\n")],
       expect=1, claim="没测到：负退出码 / argparse 的 `2` 不许判成「没达到预期」→ 当场红"),
    _M("X3", G_UNMEASURED, "对账时不一致就不再把「抽不出来」升到 `2`",
       T_VERDICTS, [(RUN_ALL,
                     "\n        rc = 2\n",
                     "\n        rc = 2 if not rc else rc  # 变异：不一致时不升 2\n")],
       expect=1, claim="没测到：有一边抽不出来就必须退 `2`，不许被那处不一致顶掉 → 当场红"),
    _M("X4", G_UNMEASURED, "对账的收尾退回 `elif`（两件事只能说出前一件）",
       T_VERDICTS, [(RUN_ALL,
                     "\n    if n_bad:\n",
                     "\n    elif n_bad:  # 变异：两件事只能说出前一件\n")],
       expect=1, claim="没测到：「没量到」和「对不上」必须各自说一遍 → 当场红"),
    _M("X5", G_UNMEASURED, "产物那一栏又抄了一份 `0/1/2 → 措辞`（打屏与产物分家）",
       T_VERDICTS, [(RUN_ALL,
                     "\n    verdicts = VERDICTS\n",
                     '\n    verdicts = {0: "达到预期", 1: "没达到预期",'
                     ' 2: "没达到预期"}  # 变异：又抄了一份表\n')],
       expect=1, claim="没测到：措辞表只许有一份 → 抄第二份当场红"),
    _M("X6", G_UNMEASURED, "裁决不再查形状（「是 JSON 但结构不对」重新变成 traceback）",
       T_ADJ, [(ADJUDICATE,
                "\n    why = _report_shape_problem(rep)\n",
                "\n    why = None  # 变异：形状不查了\n")],
       expect=1, claim="没测到：读得成 JSON 不等于结构对 → 当场红"),

    # ---- 阴性对照 ----------------------------------------------------------
    _M("K0", G_CONTROL, "语义上什么都不改（只在 `STEP` 那行尾加一句注释）",
       T_GUARDS, [(GUARDS, "STEP = 1e-3", "STEP = 1e-3  # 阴性对照：这行不该有行为差异")],
       expect=0, claim="本模块自己的纪律：不做任何语义改动的编辑，一条都不许红"),
)


FAILED_RE = re.compile(r"^(?:FAILED|ERROR) (\S+)", re.M)
_PYTEST_CMD = [sys.executable, "-m", "pytest", SUITE,
               "-q", "--tb=no", "-rf", "-p", "no:cacheprovider"]

#: 本模块跑 pytest 时给子进程带的标记。`tests/test_mutation_evidence.py` 见到它就
#: **跳过自己** —— 那一组问的是「报告有没有过期」，而本模块的每一轮（含基线）
#: 恰恰是在「源码就是被改坏的那个状态」下跑的，问了只会自问自答：
#:
#: * 变异轮：`sources` 的哈希当然对不上（文件正被改着）；
#: * 基线轮：报告是**上一轮**写的，它绿不绿取决于它自己 —— 一旦记下 false
#:   就再也翻不了身（测它的人正是让它红的那件事）。
#:
#: 所以「报告过期」这件事由**普通 pytest 运行**去抓（就是那个文件存在的理由），
#: 不由本模块的基线轮抓 —— 那是个自我指涉的圈，绕不出去。
_MUTATION_ENV = "MIROFISH_MUTATION_RUN"


class MutationPremiseError(RuntimeError):
    """前提不成立 —— **没测到**（退 `2`），不是「没达到预期」（退 `1`）。

    和装置另外几条线同一个契约。最典型的情形是基线那一轮没跑成：那时每一条
    变异都要拿它的 `failed` 去做减法，继续跑下去只会产出一份看着完整的废纸。
    """


def _verdict(measured: bool, in_target: int, expect) -> bool | None:
    """这一处变异实测下来**相符吗** —— 三态：`True` / `False` / **`None`（没测到）**。

    `None` 那一支是后加的，挡的是一个真的假绿：`expect_failed == 0` 的**阴性
    对照**在「这一轮根本没跑起来」时会报 `in_target == 0`，于是 `0 == 0` →
    「相符」。而 `failed` 为 0 有两种完全不同的成因 —— 「跑完了，一条都没红」
    和「压根没跑成」（收集失败、内部错、超时）。**后者不是发现，更不是通过。**

    单拎成函数是为了能被测（见 `tests/test_mutation_evidence.py`）：写死的三元
    表达式测不出来，这个测得出。
    """
    if not measured:
        return None
    return (in_target >= 1) if expect is None else (in_target == expect)


#: `_verdict` 那三态在人读的产物里怎么印。**键必须盖全** ——
#: 这里原先写的是 `'相符' if r['matched'] else '不符'`，而 `None` 是假值，
#: 于是**没跑成的那几轮被印成了「不符」**：一处不存在的发现。
#: （`SELFPROOF.md` 那个 `KeyError: '已否决'` 是同一个病：同一张表两份副本，
#: 只改了其中一份。所以这里由测试拿 `_verdict` 的值域去撞它。）
_VERDICT_MARKS = {True: "相符", False: "**不符**", None: "○ 没测到"}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _suite_fingerprint(root=None) -> str:
    """整个测试目录的指纹。

    报告里那些「红了几条、绿了几条」只对**跑的时候那套测试**成立。测试文件
    增删改一条，这些数字就全是旧的了 —— 而报告本身不会因此变红。所以把整个
    `tests/` 的指纹一起记下来：测试一动，指纹就对不上，`test_the_recorded_hashes_
    still_describe_the_files_on_disk` 会先红，逼着重新跑一遍。

    **按文本算，不按字节算** —— 见 `_probe.sha256_text`：`core.autocrlf` 会在
    clone 时把 LF 换成 CRLF，**字节哈希于是钉住了「谁的检出配置」，不是「测试
    有没有变」**。这一处原先正是 `read_bytes()`，实测在一个干净 clone 里当场
    红过（2026-09-17）—— 而它报的是一个不存在的问题。
    """
    h = hashlib.sha256()
    for path in sorted((root or HERE / "tests").rglob("*.py")):
        try:                       # 传别处的 root 时（测试用），退到文件名
            name = str(path.relative_to(BACKEND)).replace("\\", "/")
        except ValueError:
            name = path.name
        h.update(name.encode())
        h.update(path.read_text(encoding="utf-8").encode("utf-8"))
    return h.hexdigest()


#: 单轮 pytest 的上限。超了就记「没测到」。
#:
#: 挂死的后果比慢更糟：这份留痕跑的时候，工作区里那个源码正被改成**坏的**状态，
#: 卡在半路等于把工作区停在那儿（"留痕跑到一半被 kill 会把某个源码停在改坏状态"）。
_ROUND_TIMEOUT_S = 900.0


def _run_pytest(label: str) -> dict:
    t0 = time.time()
    env = {**os.environ, _MUTATION_ENV: label}
    timed_out = False
    try:
        proc = subprocess.run(_PYTEST_CMD, cwd=BACKEND, capture_output=True,
                              env=env, text=True, encoding="utf-8",
                              errors="replace", timeout=_ROUND_TIMEOUT_S)
        rc = proc.returncode
        out = (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired as exc:
        # 超时**不是**「一条都没红」，是「没测到」—— 上层据此把它单列。
        timed_out = True
        rc = None
        out = (exc.stdout or "") + (exc.stderr or "")
        if isinstance(out, bytes):
            out = out.decode("utf-8", "replace")

    ids = FAILED_RE.findall(out)
    by_file: dict = {}
    for nid in ids:
        head = nid.split("::", 1)[0]
        by_file[head] = by_file.get(head, 0) + 1

    # **只在 pytest 那行汇总上数。** 整段里搜的话，**被测测试自己打印的文字**里
    # 出现「3 errors」「5 failed」会被当成本次的数字 —— 数出来的东西根本不属于
    # 这次运行。汇总行是最后一行带计数的；pytest 不印 0 的那些词，所以「找不到」
    # 就是 0，这是对的。
    summary_line = next(
        (ln for ln in reversed(out.strip().splitlines())
         if re.search(r"\b\d+ (passed|failed|error|errors|skipped)\b", ln)), "")

    def _count(word: str) -> int:
        m = re.search(rf"(\d+) {word}\b", summary_line)
        return int(m.group(1)) if m else 0

    errors = _count("error") + _count("errors")
    # **这一轮到底测出来没有。** `rc` 不在 `(0, 1)` 里（收集失败退 2、内部错退 3、
    # 一条都没收集退 5）或出现 error，说明这一轮**没正常跑完** —— 此时 `failed`
    # 往往是 0，而 `expect_failed=0` 的阴性对照会因此**假绿**：
    # 一次收集失败看起来和一次「一条都没红」一模一样。
    measured = (not timed_out) and rc in (0, 1) and errors == 0

    return {
        "returncode": rc,
        "timed_out": timed_out,
        "measured": measured,
        "failed": _count("failed"),
        "passed": _count("passed"),
        "skipped": _count("skipped"),
        "errors": errors,
        "failed_ids": ids,
        "failed_by_file": by_file,
        "seconds": round(time.time() - t0, 2),
        "raw_tail": "\n".join(out.strip().splitlines()[-12:]),
    }


def _apply(edits, backups: dict) -> None:
    """按顺序改文件，把**改动前**的内容记进 `backups`（调用方必须用 `_revert` 还回去）。

    `backups` 由调用方持有、先建后用：这样**中途出错**时前面已经改掉的那几个文件
    也在 `backups` 里，`finally` 里照样能还原 —— 不留一个改坏一半的工作区。

    `e["file"]` 是 **backend 相对路径**（`_rel` 写下的那个），这里补回绝对路径 ——
    落盘的产物和真正动手改的必须是同一个值，不然产物记的是一份、改的是另一份。
    """
    for e in edits:
        path = pathlib.Path(e["file"])
        if not path.is_absolute():
            path = BACKEND / path
        text = path.read_text(encoding="utf-8")
        backups.setdefault(path, text)
        n = text.count(e["old"])
        if n != 1:
            raise RuntimeError(
                f"变异目标不唯一：{path.name} 里 {e['old']!r} 命中 {n} 次（要求正好 1 次）"
                " —— 源码动过了，先看那条论断还成不成立，别硬改变异脚本")
        path.write_text(text.replace(e["old"], e["new"], 1), encoding="utf-8")


def _revert(backups: dict) -> bool:
    ok = True
    for path, text in backups.items():
        path.write_text(text, encoding="utf-8")
        if path.read_text(encoding="utf-8") != text:
            ok = False
    return ok


def targets_of(mid: str) -> set:
    """这次变异**动手改了哪些文件**（backend 相对路径，`_rel` 写下的那个形状）。

    给测试用的：有些测试在变异轮里必须跳过自己 —— 因为它们量的东西
    （行数、条数）**本来就该随着源码被改坏而变**，在那一轮里问等于自问自答。
    但「该跳」是有条件的，不是「见了变异就跳」：那一轮里如果只动了一个
    **它并不量**的文件，那些检查照样该跑。**能判的判成不判，和判错一样是在放水**
    （`test_upstream_baseline.py` 的注释里记着本装置犯过的那次）。
    """
    for mut in MUTATIONS:
        if mut["id"] == mid:
            return {e["file"] for e in mut["edits"]}
    return set()


def _touched() -> set:
    """本次要动手改的**每一个**文件（绝对路径）。

    报告的 `sources` / `sources_after` 是「**碰过的都逐字节放回去了**」这句公开话
    的落点。原先只列那四个源码 `.py`，可 `C7` 早就在改 `README.md` 了 ——
    **碰了却不在名单里，那句话就没覆盖它**。所以这份名单按变异的实际靶子生成，
    不再手写。
    """
    touched = {GUARDS, TIMESTAMP, CITATIONS, ADJUDICATE}
    for mut in MUTATIONS:
        for e in mut["edits"]:
            p = pathlib.Path(e["file"])
            touched.add(p if p.is_absolute() else (BACKEND / p).resolve())
    return touched


def _delta(round_res: dict, baseline: dict, target: str) -> tuple[int, int]:
    """这一轮**相对基线多红了几条** —— 目标文件、以及整轮。

    为什么不直接数红条：**基线自己红着的时候，那些红跟这条变异毫无关系**。
    实测踩到过（2026-09-18）：基线红 2 条，两条都在 `test_docs_claims.py` 里，
    而 `D1` 的靶子恰恰是那个文件 —— 于是它**按声明红掉的那 1 条**被数成了 3 条，
    当场判成「与声明不符」，而它其实完全按声明变红了。
    **判据被污染之后照样给出判定**，正是这个装置盯着别人的那件事。

    基线全绿时，下面两个减法减的都是 0，结果与「原样数红条」逐字相同 ——
    所以这一手**不动任何正常情形下的数字**，只在基线已经红了的时候起作用。
    两个数（原样的、扣过的）都留在报告里，扣没扣由读者自己核。
    （靶子上的红**少于**基线时，结果是负数 —— 照实记，不夹到 0：
    那说明这条变异没让靶子多红，反而盖掉了基线那条红。）
    """
    in_target = (round_res["failed_by_file"].get(target, 0)
                 - baseline["failed_by_file"].get(target, 0))
    whole_round = round_res["failed"] - baseline["failed"]
    return in_target, whole_round


def run(only: set | None = None) -> dict:
    sources = _touched()
    source_before = {_rel(p): _sha(p.read_text(encoding="utf-8"))
                     for p in sorted(sources)}

    print("基线（一点没改）：", end=" ", flush=True)
    baseline = _run_pytest("baseline")
    print(f"{baseline['passed']} passed / {baseline['failed']} failed "
          f"（{baseline['seconds']}s，退出码 {baseline['returncode']}）")
    if not baseline["measured"]:
        # 基线自己都没跑成，下面每一条的减法都是在拿一个不存在的数去减 ——
        # **没测到**，不是「基线没通过」。继续跑下去只会产出一份看着完整的废纸。
        print(f"○ 没测到：基线那一轮没跑成（超时={baseline['timed_out']}、"
              f"退出码 {baseline['returncode']}、{baseline['errors']} 个 error）——"
              f"下面每一条都要拿它做减法，先把它修好再跑。")
        raise MutationPremiseError("基线没跑成")

    records = []
    for mut in MUTATIONS:
        if only and mut["id"] not in only:
            continue
        print(f"{mut['id']:<3} {mut['what']} … ", end="", flush=True)
        backups: dict = {}
        try:
            _apply(mut["edits"], backups)
            res = _run_pytest(f"mutation:{mut['id']}")
        finally:
            reverted = _revert(backups)
        if not reverted:
            raise RuntimeError("还原失败 —— 工作区被改坏在磁盘上了，先手工检查再继续")

        in_target, whole_delta = _delta(res, baseline, mut["target"])
        raw_in_target = res["failed_by_file"].get(mut["target"], 0)
        base_in_target = baseline["failed_by_file"].get(mut["target"], 0)
        matched = _verdict(res["measured"], in_target, mut["expect_failed"])
        records.append({**mut, **res, "failed_in_target": in_target,
                        "failed_in_target_raw": raw_in_target,
                        "baseline_in_target": base_in_target,
                        "failed_delta": whole_delta,
                        "matched": matched, "reverted": reverted})
        if matched is None:
            why = ("超时" if res["timed_out"]
                   else f"退出码 {res['returncode']}")
            print(f"○ **没测到**（{why}"
                  + (f"；{res['errors']} 个 error" if res["errors"] else "")
                  + "）—— 这一轮没跑成，不是「一条都没红」")
            continue
        cut = "" if (raw_in_target == in_target and res["failed"] == whole_delta) else (
            f"（原样 {raw_in_target} / 整轮 {res['failed']}；"
            f"已扣掉基线本来就红的 {base_in_target} / {baseline['failed']} 条）")
        print(f"红 {in_target} 条（目标文件）· 整轮 {whole_delta} 条"
              f" · {'相符' if matched else '**与声明不符**'}{cut}")

    # 再确认一遍：全跑完，上面那 `sources` 里每个源文件都必须逐字节回到原样
    source_after = {_rel(p): _sha(p.read_text(encoding="utf-8"))
                    for p in sorted(sources)}
    all_reverted = source_after == source_before

    mismatches = [r["id"] for r in records if r["matched"] is False]
    #: 「没跑成」那几条单列 —— **它们既不算相符，也不算与声明不符**。
    unmeasured = [r["id"] for r in records if r["matched"] is None]
    if unmeasured:
        print(f"○ 没测到：{unmeasured} —— 那几轮没跑成，"
              f"它们的「相符」既不成立也不该被当成不符。")
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "not_a_pass_rate": True,
        "what_this_is": ("逐条改坏被测代码、看测试红不红的对照表。"
                         "**红色是期望的结果**；这不是通过率、不是覆盖率、不是得分。"),
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "cwd": "backend/",
            "pytest_command": " ".join(_PYTEST_CMD[1:]),
        },
        "script": {"path": "verification/mutations.py",
                   "sha256": _sha(pathlib.Path(__file__).read_text(encoding="utf-8"))},
        "sources": source_before,
        "sources_after": source_after,
        "source_count": len(sources),
        "selfcheck_tests": _selfcheck_test_count(),
        "suite_sha256": _suite_fingerprint(),
        "baseline": baseline,
        "mutations": records,
        "summary": {
            "total": len(records),
            "matched": sum(1 for r in records if r["matched"] is True),
            "mismatches": mismatches,
            "unmeasured": unmeasured,
            "all_sources_reverted": all_reverted,
            "baseline_green": (baseline["measured"]
                               and baseline["failed"] == 0
                               and baseline["returncode"] == 0),
        },
    }


def _selfcheck_test_count() -> int:
    """`tests/test_mutation_evidence.py` 里有几条用例 —— **数出来，不写死**。

    这份产物要说「上面那个规模不含这一组，它是 N 条」。N 写死过一次，
    加了用例之后那句话就悄悄过期了（报告里写着 5，文件里其实是 7）。
    数一遍最省事：`tests/test_mutation_evidence.py` 里那一条断言拿它跟自己
    收集到的条数对，两边任一变动都会当场红。
    """
    text = (HERE / "tests" / "test_mutation_evidence.py").read_text(encoding="utf-8")
    return len(re.findall(r"^def test_", text, re.M))


def _redact(text: str) -> str:
    """人读的产物里，那个字面量不再抄第二遍（抄一遍报告自己就会被抓红）。"""
    return text.replace(_MISQUOTE_WRONG, _REDACTION)


def _markdown(rep: dict) -> str:
    s, base = rep["summary"], rep["baseline"]
    L = []
    L.append("# 变异测试留痕（自动生成，别手改）")
    L.append("")
    L.append(f"> 生成时间 **{rep['generated_at']}** · Python {rep['environment']['python']} · "
             f"`cd backend && python -m verification.mutations`")
    L.append("")
    L.append("## 这份报告是什么、不是什么")
    L.append("")
    L.append("**是**：一张「把被测代码改坏了、测试会不会红」的对照表 —— "
             "`README.md` 里「验过它不是恒真的」那句话的证据。")
    L.append("")
    L.append("**不是**：通过率、覆盖率、质量分。这里的**红色是期望的结果**，"
             "一条红都没有才是坏消息。**别把红条数读成任何形式的得分。**")
    L.append("")
    L.append(f"- 基线（一点没改）：**{base['passed']} passed / {base['failed']} failed / "
             f"{base['skipped']} skipped**（= 全套 "
             f"{base['passed'] + base['failed'] + base['skipped']} 条），"
             f"退出码 {base['returncode']}，{base['seconds']}s —— 先证明测试集本身是绿的，"
             "底下那些红才有意义。")
    L.append("- **「红 N 条」一律是相对基线多出来的**（扣掉基线本来就红的那些）："
             "基线全绿时它与「原样数红条」逐字相同；基线红了时，原样的那个数"
             "也留在每条的明细里，扣没扣由读者自己核。"
             "**为什么要减这一下**：判据被污染之后照样给判定，正是这个装置盯别人的那件事"
             "（实测踩到过：基线红 2 条、靶子正好是那个文件，"
             "一条**按声明红掉**的变异被数成 3 条、判成「与声明不符」）。")
    L.append(f"- 上面这个规模**不含** `tests/test_mutation_evidence.py`"
             f"（{rep['selfcheck_tests']} 条）："
             "那一组问的是「这份报告有没有过期」，而本模块每一轮都在被改坏的源码上跑 —— "
             f"它见到环境变量 `{_MUTATION_ENV}` 会跳过自己。"
             "「报告过期」由普通 `pytest` 抓，见那个文件。")
    L.append(f"- {rep['source_count']} 个源文件跑完后逐字节还原："
             f"**{'是' if s['all_sources_reverted'] else '否（！）'}**"
             "（逐文件 `sha256` 见 `mutations_report.json` 的 `sources` / `sources_after`）。")
    L.append("")
    L.append("## 对照表")
    L.append("")
    L.append("「声明」是**材料里先写下的**数字；「实测」是这一轮跑出来的。两者不一致时**以实测为准**，"
             "并且材料要跟着改 —— 不许反过来把期望值改成漂移后的样子。")
    L.append("")
    L.append("| # | 组 | 变异成什么 | 声明 | 实测（目标文件红掉） | 判定 |")
    L.append("|---|---|---|---|---|---|")
    for r in rep["mutations"]:
        claim = "至少 1 条" if r["expect_failed"] is None else f"{r['expect_failed']} 条"
        L.append(f"| `{r['id']}` | {r['group']} | {r['what']} | {claim} | "
                 f"**{r['failed_in_target']} 条** | {_VERDICT_MARKS[r['matched']]} |")
    L.append("")
    L.append(f"共 **{s['total']}** 处变异，其中 **{s['matched']}** 处的实测与声明相符。")
    if s["mismatches"]:
        L.append("")
        L.append(f"⚠️ 与声明不符的是：`{'` `'.join(s['mismatches'])}`")
    if s["unmeasured"]:
        L.append("")
        L.append(f"○ **没测到**的是：`{'` `'.join(s['unmeasured'])}` —— "
                 f"那几轮没跑成（超时、收集失败、或退出码不是 0/1）。"
                 f"它们**既不算相符也不算不符**：`failed` 在这些情形下往往是 0，"
                 f"而「0 条红」和「根本没跑起来」长得一模一样。")
    L.append("")
    L.append("## 逐条明细")
    L.append("")
    L.append("每条的「改了什么」是**逐字节替换**（`old` → `new`），跑完立刻按字节还原。")
    L.append("")
    L.append(_REDACTION_NOTE)
    L.append("")
    for r in rep["mutations"]:
        L.append(f"### `{r['id']}` · {r['what']}")
        L.append("")
        L.append(f"- 组：{r['group']}　目标文件：`{r['target']}`")
        L.append(f"- 声明：{r['claim']}")
        raw_note = ""
        if (r["failed_in_target_raw"] != r["failed_in_target"]
                or r["failed"] != r["failed_delta"]):
            raw_note = (f"（原样数：目标文件 {r['failed_in_target_raw']} 条、"
                        f"整轮 {r['failed']} 条 —— 上面两个已经扣掉基线本来就红的 "
                        f"{r['baseline_in_target']} / {base['failed']} 条）")
        L.append(f"- 实测：目标文件红 **{r['failed_in_target']}** 条"
                 f"（相对基线多红的），整轮红 **{r['failed_delta']}** 条{raw_note}、"
                 f"绿 {r['passed']} 条、跳过 {r['skipped']} 条，"
                 f"退出码 {r['returncode']}，{r['seconds']}s")
        for e in r["edits"]:
            L.append(f"- 改：`{pathlib.Path(e['file']).name}`")
            L.append("")
            L.append("  ```diff")
            L.append("  - " + _redact(e["old"]).replace("\n", "\n  - "))
            L.append("  + " + _redact(e["new"]).replace("\n", "\n  + "))
            L.append("  ```")
            L.append("")
        if r["failed_ids"]:
            shown = r["failed_ids"][:15]
            L.append(f"- 红掉的用例（{'全部' if len(shown) == len(r['failed_ids']) else '前 15 条，共 ' + str(len(r['failed_ids'])) + ' 条'}）：")
            L.append("")
            for nid in shown:
                L.append(f"  - `{nid.split('::')[-1]}`")
            L.append("")
        else:
            L.append("- 一条都没红 —— 这正是这一条**期望**的结果。")
            L.append("")
        L.append("<details><summary>原样输出（末 12 行）</summary>")
        L.append("")
        L.append("```")
        L.append(r["raw_tail"])
        L.append("```")
        L.append("")
        L.append("</details>")
        L.append("")
    L.append("## 结论")
    L.append("")
    if s["unmeasured"]:
        # **排在「全对上了」前面**：有几轮没跑成时，`matched == total` 也可能是
        # 凑出来的（没跑的那几轮不参与计数）。先说不完整，再说别的。
        L.append(f"○ **这一份留痕不完整**：{len(s['unmeasured'])} 处变异那一轮没跑成"
                 f"（见上面那张表的「○ 没测到」）。"
                 f"**没测到不是结论** —— 先把它们跑成，再读这份产物。")
    elif s["matched"] == s["total"] and s["all_sources_reverted"] and s["baseline_green"]:
        # 「按声明」——**不是**「全部变红」：阴性对照 `K0` 的声明就是「一条都不红」。
        # 名字从记录里数出来，不写死（写死的名字会在这份产物里变成第二份事实）。
        quiet = [r["id"] for r in rep["mutations"] if r["expect_failed"] == 0]
        tail = (f"（其中 {'、'.join(f'`{i}`' for i in quiet)} 是阴性对照："
                f"按声明**一条都不该红**）" if quiet else "")
        L.append(f"**{s['total']} 处变异全部按声明对上{tail}，基线全绿，源文件逐字节还原。** "
                 "这份测试集不是恒真的 —— 它有**会被改坏**的地方，而那些地方都被盯着；"
                 "反过来，也有地方**被盯着「改了却什么都不该红」**："
                 "那处证明红是**冲着这个缺陷**红的，而不是改一行字就红。")
    else:
        L.append("**没有全部对上，先别下结论。** 逐条看上面的「判定」列：")
        L.append("")
        L.append("- 「不符」：先看**论断还成不成立**（测试是不是真的失去了鉴别力），"
                 "再决定是改材料里那个数字、还是补测试 —— **不许只把期望值改成漂移后的样子**。")
        if not s["all_sources_reverted"]:
            L.append("- 源文件没还原干净：**先去 `git diff` 看一眼**，别接着往下做。")
        if not s["baseline_green"]:
            L.append("- 基线本身就是红的：底下每条的「红几条」**已经扣掉**基线那部分，"
                     "但基线红这件事本身仍然要修 —— 它说明交付物此刻是红的，"
                     "而这份留痕说的是「改坏之后会不会红」，两件事不能互相顶账。")
    L.append("")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="变异测试留痕：改坏被测代码，看测试红不红")
    ap.add_argument("--only", default="", help="只跑这几条（逗号分隔，如 G1,V3）")
    ap.add_argument("--json", default=str(HERE / "mutations_report.json"))
    ap.add_argument("--md", default=str(HERE / "MUTATIONS.md"))
    args = ap.parse_args(argv)

    only = {x.strip() for x in args.only.split(",") if x.strip()} or None
    if only:
        # **编号写错一个字母，原先会静默地跑成「0/0 与声明相符」并退 `0`** ——
        # 过滤之后一条都不剩，`total` 就是 0，而 `matched == total`（`0 == 0`）
        # 于是「相符」。一份防假绿的产物不能自己开一条假绿的路：
        # 一条都没跑 = **没测到**，不是通过。所以这里先认编号，认不出来就退 `2`。
        known = {m["id"] for m in MUTATIONS}
        unknown = sorted(only - known)
        if unknown:
            print(f"\n○ 没测到：不认识的变异编号 {'、'.join(unknown)} —— 编号抄错了？",
                  file=sys.stderr)
            print(f"  本文件里声明的是：{'、'.join(sorted(known))}", file=sys.stderr)
            return 2

    # 落点先问一句，**问在 `run()` 之前**。这一句在这里比别处更要紧：`run()`
    # 会把被测源码逐个改成坏的、跑一轮 pytest、再改回来 —— 等这几十轮跑完才
    # 发现写不出去，等于把已经量到的留痕连同退出码一起丢掉，而那时按本表只能
    # 退 `1`（「与声明不符」）：**一个读数都没落盘，却报了一次不符。**
    #
    # `--only` 时不落产物，那就不必问 —— 问了反而会把一次合法的部分留痕挡掉。
    if only is None:
        from . import _probe as P      # 同 `run_all`：延迟导入，模块级别拉重依赖

        rc = P.refuse_out_path(args.json, args.md)
        if rc is not None:
            return rc

    try:
        rep = run(only)
    except MutationPremiseError as e:
        print(f"\n○ 没测到：{e}", file=sys.stderr)
        return 2

    if only is None:          # 只跑一部分时产物不完整，不落盘盖掉完整的那份
        try:
            pathlib.Path(args.json).write_text(
                json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
            pathlib.Path(args.md).write_text(_markdown(rep), encoding="utf-8")
        except OSError as exc:
            # 上面那道门挡不住的一半（目录在、但文件建不出来）。变异全跑完了、
            # 源文件也逐字节还原了，**但这一份留痕没落成** —— 按三种结果说清楚，
            # 不退 `1`。⚠️ 这里**不能**顺手重跑 `run()`：源文件此刻是好的。
            print(f"\n○ 没测到：留痕写不下去（{exc.__class__.__name__}: {exc}）—— "
                  "变异跑完了、源文件已还原，但**这一份产物没落成**。",
                  file=sys.stderr)
            return 2
        print(f"\n→ {args.json}")
        print(f"→ {args.md}")

    s = rep["summary"]
    print(f"\n{s['matched']}/{s['total']} 与声明相符；"
          f"源文件还原={'是' if s['all_sources_reverted'] else '否'}；"
          f"基线={'绿' if s['baseline_green'] else '红'}")
    # 「没测到」既不算相符也不算不符 —— 它自己一条出口（`2`）。
    # **`2` 不许折进 `1`**：那会让一次没跑成的留痕看起来像一处发现。
    if s["unmeasured"]:
        print(f"○ 没测到：{s['unmeasured']} —— 那几轮没跑成，"
              f"这一份留痕不完整，别照它下结论。", file=sys.stderr)
        return 2
    return 0 if (s["matched"] == s["total"] and s["all_sources_reverted"]
                 and s["baseline_green"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
