"""对账那一步的留痕 —— 把「验过它会红」变成一份**可复核的产物**。

`run_all.py` 跑完三条复现之后还有一步对账：**装置本体报的数，和 `upstream/` 里
准备发出去的那两份最小复现报的数，是不是同一组。** `README.md` 里那句话是：

> 也**验过它会红**：把草稿①的探针消息从 90 条记录改成 88 条，对账立刻报
> **不一致**（270 → 264、5130 → 5016 两行都标 `×`）并给出退出码 `1`，
> 而三条复现自己**照样是绿的**。

**这句话此前没有产物** —— 做过，但仓库里查不到，
有人追问「你凭什么叫它对账」时只能靠叙述回答。这个模块把它做实，
形状和 `mutations.py` 一样：**改坏 → 跑 → 记录 → 逐字节还原**。

    python -m verification.reconcile_selfcheck        # 在 backend/ 下，约一分钟

两轮：

| 轮 | 改了什么 | 跑什么 | 期望 |
|---|---|---|---|
| **A** | 什么都不改 | 装置①、装置②、草稿①、草稿② | 对账退出码 **0**，三行都「一致」 |
| **B** | 草稿①的探针消息 **90 条 → 88 条** | 只重跑草稿①（装置侧沿用 A 轮正文） | 对账退出码 **1**，① 那两行「不一致」，② 那行仍「一致」 |

产物落盘：`RECONCILE_SELFCHECK.md`（人读）与 `reconcile_selfcheck_report.json`（机读）。

## 这份产物是什么、不是什么

* **是**：一次「故意把准备发出去的材料改坏一边、看对账会不会响」的实验记录。
* **不是**：通过率、覆盖率、质量分。**B 轮那个退出码 `1` 是期望的结果。**
* **也不证明**「装置报的数就是对的」—— 对账只回答「两边是不是同一组」，
  它回答不了「这一组数对不对」。那是复现自己那条线的事。

## 为什么 B 轮不重跑装置那两条

因为植入只动了**草稿那一个文件**，而三条复现**都不读草稿**（这一条脚本里
当场核一遍：`repro_0*.py` 里不出现 `upstream`）。所以装置侧的正文在 A、B 两轮
之间是同一份文本 —— 这不是「重跑后仍然一致」，是**根本不受影响**。
把这件事说清楚，比多花二十秒再跑一遍更有用。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import platform
import re
import sys
import time

from verification import run_all as R

from . import _probe as P

HERE = pathlib.Path(__file__).resolve().parent          # backend/verification
BACKEND = HERE.parent                                   # backend/

DRAFT1 = HERE / "upstream" / "repro_min_01_slicing.py"
DRAFT2 = HERE / "upstream" / "repro_min_02_timestamp.py"

#: 对账要用到的四条正文分别由谁产生。**不含装置③** —— 对账那三条读数里
#: 没有一条来自复现③，跑它是白花十秒。
DEVICES = (("verification.repro_01_slicing", "装置①"),
           ("verification.repro_02_timestamp", "装置②"))
DRAFTS = (("verification.upstream.repro_min_01_slicing", "草稿①", DRAFT1),
          ("verification.upstream.repro_min_02_timestamp", "草稿②", DRAFT2))

#: 植入的那一处。**只动这一个数字**，其余一个字不改。
PLANT_OLD = "range(90)"
PLANT_NEW = "range(88)"

class PremiseError(RuntimeError):
    """这一轮的**前提不成立** —— 该报「没测到」（退出码 `2`），不是「不符」（`1`）。

    和装置其它三条线同一个契约：一个数都没量到、或者声明的原文读不出来了，
    就没有资格判「不符」。把这两种折在一起，等于**把「没测到」报成「没通过」**。
    """


#: README 里那几处声明的**原文形状**。解析失败就报「没测到」（退出码 2），
#: **绝不退回一份写死的副本** —— 那正是这份产物上一版干的事：常量叫
#: `claim_from_readme`、产物上印着「README 声明的数对得上 ✅」，而它比的是
#: 本文件里的字面量，**从头到尾没有打开过 README**。两份副本只钉了一份，
#: README 那一份改掉任意一个数字都照样全绿。
_CLAIM_IN_PROSE = re.compile(r"（(\d+) → (\d+)、(\d+) → (\d+) 两行都标")
_CLAIM_IN_TABLE = re.compile(r"^\s*② 同拍违反数\s+(\d+)\s+(\d+)\s", re.M)


def claim_from_readme(text: str) -> dict:
    """从 `README.md` **现场读**出那三行声明的数：`{共有数字: (装置侧, 草稿侧)}`。

    三行数分在两处，都得读出来：

    * ① 那两行在「也验过它会红」那句话里 —— `（270 → 264、5130 → 5016 两行都标 ×）`
    * ② 那一行在 A 轮那张小表里 —— `② 同拍违反数  1         1         √ 一致`

    读不到就抛 `PremiseError`：**声明被改写过了，这一轮没资格判任何东西**。
    """
    prose = _CLAIM_IN_PROSE.search(text)
    table = _CLAIM_IN_TABLE.search(text)
    missing = [name for name, m in (("「也验过它会红」那句话（① 两行）", prose),
                                    ("A 轮那张表（② 那一行）", table)) if not m]
    if missing:
        raise PremiseError(
            "README 里读不到声明的数：" + "、".join(missing)
            + "。**这不是「不符」** —— 是这一轮的前提没了。"
              "先看那句论断是不是被改写过了，再决定改哪一边。")
    return {"① 新增记录数": (prose.group(1), prose.group(2)),
            "① 实增 token": (prose.group(3), prose.group(4)),
            "② 同拍违反数": (table.group(1), table.group(2))}


#: 核对项的三种状态 —— 和 A/B 两轮标题上印的、以及退出码是同一套口径。
_STATES = ("相符", "不符", "没测到")
_STATE_MARKS = {"相符": "✅", "不符": "❌ **不符**", "没测到": "○ 没测到"}


def _check(name: str, ok: bool, detail: str, *, measured: bool = True) -> dict:
    """一条核对。`state` 是三态的，`ok` 只是它的便利读法。

    `measured=False` 说的是**这件事这一轮没量到**（读数抽不出来、子进程压根没跑成），
    那就不许判「不符」—— 见 `PremiseError` 的注释。
    """
    state = "没测到" if not measured else ("相符" if ok else "不符")
    return {"name": name, "ok": state == "相符", "state": state, "detail": detail}


def _exit_code(rep: dict) -> int:
    """三态退出码：`0` 相符 / `1` 不符 / `2` 没测到。

    这份产物一直**印着**这三态（A/B 两轮标题那行），此前却只有两个退出码：
    `return 0 if s["all_ok"] else 1`。于是子进程真退 2 时（最典型是分词器取不到，
    见 D-52），7 项核对全 ❌、退 **1**、屏幕上打「0/7 项相符」——
    **一次「一个数都没量到」被报成了「自检没通过」**，正是这套装置专门抓别人的那件事。
    """
    if any(c["state"] == "没测到" for c in rep["checks"]):
        return 2
    return 0 if rep["summary"]["all_ok"] else 1
EXPECT_RED = ("① 新增记录数", "① 实增 token")
EXPECT_GREEN = ("② 同拍违反数",)

#: 三条复现里**不读草稿**这件事，是上面那条「B 轮不用重跑装置侧」的依据。
_REPRO_MODULES = ("repro_01_slicing.py", "repro_02_timestamp.py",
                  "repro_03_concurrency.py")
_FORBIDDEN_IN_REPROS = ("upstream", "repro_min")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _rows(transcripts: dict) -> list:
    """按 `run_all._SHARED_NUMBERS` 那三条，把两边的读数抽出来。

    **用的是同一张表和同一批正则** —— 这里要是另写一套，抽出来的数就不再
    是 `_reconcile` 看到的那个数，这份产物也就证明不了它。
    """
    rows = []
    for what, dev_key, pat_dev, draft_key, pat_draft in R._SHARED_NUMBERS:
        got = {}
        for side, key, pat in (("device", dev_key, pat_dev),
                               ("draft", draft_key, pat_draft)):
            m = re.search(pat, transcripts.get(key, ""))
            got[side] = m.group(1).replace(",", "") if m else None
        if not (got["device"] and got["draft"]):
            verdict = "没测到"
        elif got["device"] == got["draft"]:
            verdict = "一致"
        else:
            verdict = "不一致"
        rows.append({"what": what, **got, "verdict": verdict})
    return rows


def _run(mod: str, label: str) -> tuple:
    print(f"  · 跑 {label} … ", end="", flush=True)
    rc, body = R._run_one(mod, echo=False)
    print(f"退出码 {rc}")
    return rc, body


def _repros_do_not_read_the_draft() -> dict:
    """静态核一遍：三条复现里不出现 `upstream` / `repro_min`。

    这是「B 轮不用重跑装置侧」的依据 —— **是结构事实，不是重跑结论**，
    所以它便宜、且不会因环境而变。
    """
    hits = {}
    for name in _REPRO_MODULES:
        text = (HERE / name).read_text(encoding="utf-8")
        found = [w for w in _FORBIDDEN_IN_REPROS if w in text]
        hits[name] = found
    return hits


def _render_round(title: str, rc: int, rows: list, lines: list) -> list:
    L = [f"### {title}", "",
         f"- 对账退出码：**{rc}**（`0` 一致 / `1` 不一致 / `2` 没测到）", "",
         "| 共有数字 | 装置侧 | 草稿侧 | 判定 |", "|---|---|---|---|"]
    for r in rows:
        mark = {"一致": "√ 一致", "不一致": "× **不一致**",
                "没测到": "○ 没测到"}[r["verdict"]]
        L.append(f"| {r['what']} | {r['device'] or '○ 抽不到'} | "
                 f"{r['draft'] or '○ 抽不到'} | {mark} |")
    L += ["", "对账自己打出来的原文：", "", "```"]
    L += [ln.rstrip() for ln in lines if ln.strip() != ""]
    L += ["```", ""]
    return L


def run() -> dict:
    os.chdir(BACKEND)                      # `_run_one` 用 cwd 起子进程
    t0 = time.time()

    # **先把声明读了，读不到就当场停** —— 别白跑一分钟才发现这一轮没资格判任何东西。
    readme_text = (HERE / "README.md").read_text(encoding="utf-8")
    claim = claim_from_readme(readme_text)

    print("A 轮（什么都不改）")
    a_dev = {}
    for mod, key in DEVICES:
        _, a_dev[key] = _run(mod, key)
    a_draft = {}
    draft1_before = DRAFT1.read_text(encoding="utf-8")
    for mod, key, path in DRAFTS:
        _, a_draft[key] = _run(mod, key)

    a_transcripts = {**a_dev, **a_draft}
    a_rc, a_lines = R._reconcile(a_transcripts)
    a_rows = _rows(a_transcripts)
    print(f"  → 对账退出码 {a_rc}")

    print("B 轮（把草稿①的探针消息从 90 条改成 88 条）")
    n = draft1_before.count(PLANT_OLD)
    if n != 1:
        raise RuntimeError(
            f"植入目标不唯一：{DRAFT1.name} 里 {PLANT_OLD!r} 命中 {n} 次"
            "（要求正好 1 次）—— 草稿动过了，先看那句论断还成不成立")
    try:
        DRAFT1.write_text(draft1_before.replace(PLANT_OLD, PLANT_NEW, 1),
                          encoding="utf-8")
        _, b_draft1 = _run(DRAFTS[0][0], "草稿①（已植入）")
    finally:
        DRAFT1.write_text(draft1_before, encoding="utf-8")
    reverted = DRAFT1.read_text(encoding="utf-8") == draft1_before

    b_transcripts = {**a_transcripts, "草稿①": b_draft1}   # 装置侧沿用 A 轮
    b_rc, b_lines = R._reconcile(b_transcripts)
    b_rows = _rows(b_transcripts)
    print(f"  → 对账退出码 {b_rc}")

    # -- 核对：把「声明」和「实测」逐项摆在一起 ---------------------------------
    def _row(rows, what):
        return next(r for r in rows if r["what"] == what)

    def _all_measured(rows, whats) -> bool:
        """这几行**两边都抽到了数**吗 —— 有一行抽不出来就算没测到。"""
        return all(_row(rows, w)["verdict"] != "没测到" for w in whats)

    _every = [w for w, _, _, _, _ in R._SHARED_NUMBERS]
    checks = [
        _check("A 轮对账一致（退出码 0）", a_rc == 0,
               f"实测退出码 {a_rc}", measured=a_rc != 2),
        _check("A 轮三行都「一致」",
               all(r["verdict"] == "一致" for r in a_rows),
               "、".join(f"{r['what']}={r['verdict']}" for r in a_rows),
               measured=_all_measured(a_rows, _every)),
        _check("B 轮对账报不一致（退出码 1）", b_rc == 1,
               f"实测退出码 {b_rc}", measured=b_rc != 2),
        _check("植入后**该红的**两行红了",
               all(_row(b_rows, w)["verdict"] == "不一致" for w in EXPECT_RED),
               "、".join(f"{w}={_row(b_rows, w)['verdict']}" for w in EXPECT_RED),
               measured=_all_measured(b_rows, EXPECT_RED)),
        _check("植入后**不该动的**那行没动",
               all(_row(b_rows, w)["verdict"] == "一致" for w in EXPECT_GREEN),
               "、".join(f"{w}={_row(b_rows, w)['verdict']}" for w in EXPECT_GREEN),
               measured=_all_measured(b_rows, EXPECT_GREEN)),
        _check("草稿①改回去了（逐字节）", reverted,
               f"sha256 {_sha(draft1_before)[:12]} 与还原后"
               + ("相同" if reverted else "**不同**")),
    ]

    for what, (claim_dev, claim_draft) in claim.items():
        got_dev = _row(b_rows, what)["device"]
        got_draft = _row(b_rows, what)["draft"]
        checks.append(_check(
            f"README 声明的数对得上：{what}",
            (got_dev, got_draft) == (claim_dev, claim_draft),
            f"声明 装置{claim_dev}→草稿{claim_draft}；"
            f"实测 装置{got_dev or '○抽不到'}→草稿{got_draft or '○抽不到'}",
            measured=bool(got_dev and got_draft)))

    reads = _repros_do_not_read_the_draft()
    checks.append(_check(
        "三条复现都不读草稿（「B 轮不用重跑装置侧」的依据）",
        all(not v for v in reads.values()),
        "、".join(f"{k}:{'命中' + str(v) if v else '无'}" for k, v in reads.items())))

    all_ok = all(c["ok"] for c in checks)
    not_measured = [c["name"] for c in checks if c["state"] == "没测到"]

    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "not_a_pass_rate": True,
        "what_this_is": ("故意把准备发出去的材料改坏一边、看对账会不会响的实验记录。"
                         "**B 轮那个退出码 1 是期望的结果**；这不是通过率，也不是得分。"),
        "environment": {"python": sys.version.split()[0],
                        "platform": platform.platform(),
                        "cwd": "backend/"},
        "script": {"path": "verification/reconcile_selfcheck.py",
                   "sha256": _sha(pathlib.Path(__file__).read_text(encoding="utf-8"))},
        "sources": {str(p.relative_to(BACKEND)).replace("\\", "/"): _sha(
            p.read_text(encoding="utf-8")) for p in (DRAFT1, DRAFT2)},
        "plant": {"file": str(DRAFT1.relative_to(BACKEND)).replace("\\", "/"),
                  "old": PLANT_OLD, "new": PLANT_NEW},
        "rounds": {
            "A": {"label": "什么都不改", "reconcile_rc": a_rc, "rows": a_rows,
                  "reconcile_lines": [ln.rstrip() for ln in a_lines],
                  "transcripts": a_transcripts},
            "B": {"label": "草稿①的探针消息 90 条 → 88 条", "reconcile_rc": b_rc,
                  "rows": b_rows,
                  "reconcile_lines": [ln.rstrip() for ln in b_lines],
                  "transcripts": b_transcripts},
        },
        "claim_from_readme": claim,
        "claim_source": {
            "path": "verification/README.md",
            "sha256": _sha(readme_text),
            "where": "① 那两行读自「也验过它会红」那句话；"
                     "② 那一行读自 A 轮那张小表 —— **现场读的，不是抄的**"},
        "checks": checks,
        "reverted": reverted,
        "seconds": round(time.time() - t0, 2),
        "summary": {"checks_total": len(checks),
                    "checks_ok": sum(1 for c in checks if c["ok"]),
                    "checks_not_measured": len(not_measured),
                    "not_measured_which": not_measured,
                    "all_ok": all_ok},
    }


def _markdown(rep: dict) -> str:
    s = rep["summary"]
    L = ["# 对账自检留痕（自动生成，别手改）", "",
         f"> 生成时间 **{rep['generated_at']}** · Python {rep['environment']['python']} · "
         f"`cd backend && python -m verification.reconcile_selfcheck`（{rep['seconds']}s）", "",
         "## 这份产物是什么、不是什么", "",
         "**是**：一次「**故意把准备发出去的材料改坏一边、看对账会不会响**」"
         "的实验记录 —— `README.md` 里「也验过它会红」那句话的证据。", "",
         "**不是**：通过率、覆盖率、质量分。**B 轮那个退出码 `1` 是期望的结果。**", "",
         "**也不证明**「装置报的数就是对的」—— 对账只回答「两边是不是同一组」，"
         "回答不了「这一组数对不对」。那是复现自己那条线的事。", "",
         f"植入的那一处：`{rep['plant']['file']}` 里 "
         f"`{rep['plant']['old']}` → `{rep['plant']['new']}`（只动这一个数字）。", ""]
    L += _render_round("A 轮 · 什么都不改（期望：一致）", rep["rounds"]["A"]["reconcile_rc"],
                       rep["rounds"]["A"]["rows"], rep["rounds"]["A"]["reconcile_lines"])
    L += _render_round("B 轮 · 草稿①的探针消息从 90 条改成 88 条（期望：不一致）",
                       rep["rounds"]["B"]["reconcile_rc"], rep["rounds"]["B"]["rows"],
                       rep["rounds"]["B"]["reconcile_lines"])
    L += ["## 逐项核对（声明 vs 实测）", "",
          "| 核对项 | 结果 | 明细 |", "|---|---|---|"]
    for c in rep["checks"]:
        L.append(f"| {c['name']} | {_STATE_MARKS[c['state']]} | {c['detail']} |")
    L.append("")
    if s["checks_not_measured"]:
        L += [f"**{s['checks_ok']}/{s['checks_total']} 项相符；"
              f"{s['checks_not_measured']} 项没测到** —— "
              f"没测到的是：" + "、".join(s["not_measured_which"])
              + "。**「没测到」没有资格说「不符」**（退出码 `2`）。", ""]
    else:
        L += [f"**{s['checks_ok']}/{s['checks_total']} 项相符。**", ""]
    L += ["## 为什么 B 轮不重跑装置那两条", "",
          "植入只动了**草稿那一个文件**，而三条复现**都不读草稿** —— 上面那条静态核对"
          "（`repro_0*.py` 里不出现 `upstream` / `repro_min`）就是依据。所以装置侧的正文"
          "在 A、B 两轮之间是**同一份文本**：这不是「重跑后仍然一致」，是**根本不受影响**。", "",
          "把这件事说清楚，比多花二十秒再跑一遍更有用 —— 而且它不会因环境而变。", ""]
    L += ["## 结论", ""]
    if s["all_ok"]:
        L += ["**两轮都按预期走，改回也逐字节还原了。** 对账那一步不是恒过的：",
              "把准备发出去的材料改坏一个数字，它会**当场响**，而三条复现不受影响。"]
    elif s["checks_not_measured"]:
        L += ["**没测到，先别下结论。** 上面那张表里带 ○ 的那几项，这一轮根本没量到 ——",
              "先看它们**为什么**量不到（多半是分词器取不到、或者子进程压根没跑成），",
              "把前提补上再来。**这不是「不符」**：一个数都没量到的时候，",
              "说「没通过」和说「通过」一样没有依据。"]
    else:
        L += ["**没有全部对上，先别下结论。** 逐项看上面那张表 ——",
              "「不符」时先看**那句论断还成不成立**，再决定是改材料里的数字、",
              "还是改对账本身。**不许只把期望值改成漂移后的样子。**"]
    L.append("")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="对账那一步的自检留痕")
    ap.add_argument("--json", default=str(HERE / "reconcile_selfcheck_report.json"))
    ap.add_argument("--md", default=str(HERE / "RECONCILE_SELFCHECK.md"))
    args = ap.parse_args(argv)

    # 落点先问一句，**问在 `run()` 之前**（同 `adjudicate` / `run_all` /
    # `selfproof`）。否则坏落点抛的 `FileNotFoundError` 没人接、进程退 `1` ——
    # 而本表把 `1` 读成「**不符**」：一个读数都没落下来，却报了一次对账失败。
    rc = P.refuse_out_path(args.json, args.md)
    if rc is not None:
        return rc

    try:
        rep = run()
    except PremiseError as e:
        # 前提不成立 = **没测到**（退出码 `2`），不是「不符」（`1`）。
        # 也不落产物：一份「没量到」的产物长得像一份「量到了」的。
        print(f"\n没测到：{e}")
        return 2

    try:
        pathlib.Path(args.json).write_text(
            json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
        pathlib.Path(args.md).write_text(_markdown(rep), encoding="utf-8")
    except OSError as exc:
        # 上面那道门挡不住的一半（目录在、但文件建不出来）。两轮对账都算完了，
        # **但这一份没落成** —— 按三种结果说清楚，不退 `1`（那是「不符」）。
        print(f"\n○ 没测到：对账留痕写不下去（{exc.__class__.__name__}: {exc}）—— "
              "两轮都跑完了，但**这一份产物没落成**。")
        return 2
    print(f"\n→ {args.json}")
    print(f"→ {args.md}")

    s = rep["summary"]
    print(f"\n{s['checks_ok']}/{s['checks_total']} 项相符"
          + (f"（其中 {s['checks_not_measured']} 项**没测到**）"
             if s["checks_not_measured"] else "")
          + f"；A 轮退出码 {rep['rounds']['A']['reconcile_rc']}；"
          f"B 轮退出码 {rep['rounds']['B']['reconcile_rc']}；"
          f"草稿还原={'是' if rep['reverted'] else '否'}")
    for c in rep["checks"]:
        if not c["ok"]:
            print(f"  {_STATE_MARKS[c['state']]} {c['name']}：{c['detail']}")
    return _exit_code(rep)


if __name__ == "__main__":
    raise SystemExit(main())
