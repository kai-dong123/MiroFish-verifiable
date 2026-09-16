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

T_GUARDS = "verification/tests/test_camel_guards.py"
T_VERDICTS = "verification/tests/test_repro_verdicts.py"
T_CITATIONS = "verification/tests/test_citations.py"
T_ADJ = "verification/tests/test_adjudicate.py"
T_ADJ_E2E = "verification/tests/test_e2e_stub.py"

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


def _M(mid, group, what, target, edits, *, expect=None, claim=""):
    """一条变异。`expect` = **材料里声明的**红条数；None 表示只声明「至少一条红」。"""
    return {
        "id": mid,
        "group": group,
        "what": what,
        "target": target,
        "edits": [{"file": str(f), "old": o, "new": n} for f, o, n in edits],
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

    # ---- 裁决：三处 --------------------------------------------------------
    # 判据表那三条规则里，**贴界按单元格判**是最深的一条：它错成乘积式，
    # 产物照样长得像证据，而且降级得**没人看得出来**（weiran 那边真踩过）。
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
       expect=3, claim="README「裁决」：缺读数判不可判定，折进「否决」当场红"),

    _M("J3", G_ADJ_VAC, "falsifier 只查在不在，**不实例化** —— 于是它永远「翻得动」",
       T_ADJ, [(ADJUDICATE,
                '            if after[cid]["verdict"] != base[cid]["verdict"]:',
                '            if True:  # 变异：声明了就算数，不去试它')],
       expect=1, claim="README「裁决·非空泛」：falsifier 必须实例化，只查在不在当场红"),

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


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _suite_fingerprint() -> str:
    """整个测试目录的指纹。

    报告里那些「红了几条、绿了几条」只对**跑的时候那套测试**成立。测试文件
    增删改一条，这些数字就全是旧的了 —— 而报告本身不会因此变红。所以把整个
    `tests/` 的指纹一起记下来：测试一动，指纹就对不上，`test_the_recorded_hashes_
    still_describe_the_files_on_disk` 会先红，逼着重新跑一遍。
    """
    h = hashlib.sha256()
    for path in sorted((HERE / "tests").rglob("*.py")):
        h.update(str(path.relative_to(BACKEND)).replace("\\", "/").encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def _run_pytest(label: str) -> dict:
    t0 = time.time()
    env = {**os.environ, _MUTATION_ENV: label}
    proc = subprocess.run(_PYTEST_CMD, cwd=BACKEND, capture_output=True, env=env,
                          text=True, encoding="utf-8", errors="replace")
    out = (proc.stdout or "") + (proc.stderr or "")
    ids = FAILED_RE.findall(out)
    by_file: dict = {}
    for nid in ids:
        head = nid.split("::", 1)[0]
        by_file[head] = by_file.get(head, 0) + 1

    def _count(word: str) -> int:
        m = re.search(rf"(\d+) {word}\b", out)
        return int(m.group(1)) if m else 0

    return {
        "returncode": proc.returncode,
        "failed": _count("failed"),
        "passed": _count("passed"),
        "skipped": _count("skipped"),
        "errors": _count("error") + _count("errors"),
        "failed_ids": ids,
        "failed_by_file": by_file,
        "seconds": round(time.time() - t0, 2),
        "raw_tail": "\n".join(out.strip().splitlines()[-12:]),
    }


def _apply(edits, backups: dict) -> None:
    """按顺序改文件，把**改动前**的内容记进 `backups`（调用方必须用 `_revert` 还回去）。

    `backups` 由调用方持有、先建后用：这样**中途出错**时前面已经改掉的那几个文件
    也在 `backups` 里，`finally` 里照样能还原 —— 不留一个改坏一半的工作区。
    """
    for e in edits:
        path = pathlib.Path(e["file"])
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


def run(only: set | None = None) -> dict:
    sources = {GUARDS, TIMESTAMP, CITATIONS, ADJUDICATE}
    source_before = {str(p.relative_to(BACKEND)).replace("\\", "/"): _sha(p.read_text(encoding="utf-8"))
                     for p in sorted(sources)}

    print("基线（一点没改）：", end=" ", flush=True)
    baseline = _run_pytest("baseline")
    print(f"{baseline['passed']} passed / {baseline['failed']} failed "
          f"（{baseline['seconds']}s，退出码 {baseline['returncode']}）")

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

        in_target = res["failed_by_file"].get(mut["target"], 0)
        expect = mut["expect_failed"]
        matched = (in_target >= 1) if expect is None else (in_target == expect)
        records.append({**mut, **res, "failed_in_target": in_target,
                        "matched": matched, "reverted": reverted})
        print(f"红 {in_target} 条（目标文件）· 整轮 {res['failed']} 条"
              f" · {'相符' if matched else '**与声明不符**'}")

    # 再确认一遍：全跑完，三个源文件必须逐字节回到原样
    source_after = {str(p.relative_to(BACKEND)).replace("\\", "/"): _sha(p.read_text(encoding="utf-8"))
                    for p in sorted(sources)}
    all_reverted = source_after == source_before

    mismatches = [r["id"] for r in records if not r["matched"]]
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
        "suite_sha256": _suite_fingerprint(),
        "baseline": baseline,
        "mutations": records,
        "summary": {
            "total": len(records),
            "matched": sum(1 for r in records if r["matched"]),
            "mismatches": mismatches,
            "all_sources_reverted": all_reverted,
            "baseline_green": baseline["failed"] == 0 and baseline["returncode"] == 0,
        },
    }


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
    L.append(f"- 上面这个规模**不含** `tests/test_mutation_evidence.py`（5 条）："
             "那一组问的是「这份报告有没有过期」，而本模块每一轮都在被改坏的源码上跑 —— "
             f"它见到环境变量 `{_MUTATION_ENV}` 会跳过自己。"
             "「报告过期」由普通 `pytest` 抓，见那个文件。")
    L.append(f"- 三个源文件跑完后逐字节还原：**{'是' if s['all_sources_reverted'] else '否（！）'}**"
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
                 f"**{r['failed_in_target']} 条** | {'相符' if r['matched'] else '**不符**'} |")
    L.append("")
    L.append(f"共 **{s['total']}** 处变异，其中 **{s['matched']}** 处的实测与声明相符。")
    if s["mismatches"]:
        L.append("")
        L.append(f"⚠️ 与声明不符的是：`{'` `'.join(s['mismatches'])}`")
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
        L.append(f"- 实测：目标文件红 **{r['failed_in_target']}** 条，"
                 f"整轮红 **{r['failed']}** 条、绿 {r['passed']} 条、跳过 {r['skipped']} 条，"
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
    if s["matched"] == s["total"] and s["all_sources_reverted"] and s["baseline_green"]:
        L.append(f"**{s['total']} 处变异全部按声明变红，基线全绿，源文件逐字节还原。** "
                 "这份测试集不是恒真的 —— 它有**会被改坏**的地方，而那些地方都被盯着。")
    else:
        L.append("**没有全部对上，先别下结论。** 逐条看上面的「判定」列：")
        L.append("")
        L.append("- 「不符」：先看**论断还成不成立**（测试是不是真的失去了鉴别力），"
                 "再决定是改材料里那个数字、还是补测试 —— **不许只把期望值改成漂移后的样子**。")
        if not s["all_sources_reverted"]:
            L.append("- 源文件没还原干净：**先去 `git diff` 看一眼**，别接着往下做。")
        if not s["baseline_green"]:
            L.append("- 基线本身就是红的：底下所有红条都无法解释，先修基线。")
    L.append("")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="变异测试留痕：改坏被测代码，看测试红不红")
    ap.add_argument("--only", default="", help="只跑这几条（逗号分隔，如 G1,V3）")
    ap.add_argument("--json", default=str(HERE / "mutations_report.json"))
    ap.add_argument("--md", default=str(HERE / "MUTATIONS.md"))
    args = ap.parse_args(argv)

    only = {x.strip() for x in args.only.split(",") if x.strip()} or None
    rep = run(only)

    if only is None:          # 只跑一部分时产物不完整，不落盘盖掉完整的那份
        pathlib.Path(args.json).write_text(
            json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
        pathlib.Path(args.md).write_text(_markdown(rep), encoding="utf-8")
        print(f"\n→ {args.json}")
        print(f"→ {args.md}")

    s = rep["summary"]
    print(f"\n{s['matched']}/{s['total']} 与声明相符；"
          f"源文件还原={'是' if s['all_sources_reverted'] else '否'}；"
          f"基线={'绿' if s['baseline_green'] else '红'}")
    return 0 if (s["matched"] == s["total"] and s["all_sources_reverted"]
                 and s["baseline_green"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
