"""自证：**这套判据不是恒绿的** —— 逐条拿单点受控扰动去试。

    cd backend && python -m verification.selfproof

不发 LLM、不要 API key、不重跑复现（检查器是读数的纯函数，所以这步几十毫秒）。

## 为什么要有这个文件

一套判据全判「通过」，可能是**装置真的好**，也可能是**判据根本分不出好坏**。
光看结果分不开这两种情形 —— 而一个分不出好坏的检查器，比没有检查器更坏：
它给的东西长得像证据。

所以这里不问「判据对不对」，只问一件能量的事：**改动一处，它会不会动。**
每一例都是**一处具名扰动**，配一张表态表：

* `touch` —— 我断言**会变**的判据，以及它变成什么。
* `untouched` —— 我断言**不许变**的判据。**必须覆盖剩下的全部判据**：
  运行时校验，漏掉一条就报错。少了这一半，「动了」也可能只是它整体在乱动。

漏声明不是靠自觉，是**校验**：`set(touch) | set(untouched)` 必须恰好等于判据全集。

## 扰动的层是一个闭集

`读数` / `断言` / `边界` —— 三层各管一件事：

| 层 | 动什么 | 它在证什么 |
|---|---|---|
| **读数** | 某一格的数值 | 判据真的读了这个量 |
| **断言** | 判据原文（含阈值）或它声明的 falsifier | 阈值是**从原文抠的**、falsifier 真的在起作用 |
| **边界** | 某一格的贴界／未测量声明 | 这两条规则真的会改结果，不是装饰 |

层写错一个字会让整例静默退化 —— 所以是个校验过的闭集，不是随手写的字符串。

## 两条元断言

1. **五格必须全出现**：通过·采信／通过·不采信／否决·采信／否决·不采信／不可判定。
   少一格就说明有一格是**死格** —— 那套判据压根到不了那个状态。
2. **每条判据要么自带一个能翻面的 falsifier，要么明说是「缺读数」。**
   给不出 falsifier、或者给出来却翻不动 → 判据**恒真** —— 它判出来的「通过」
   什么也不说明。这个判定由检查器自己做（见 `adjudicate.falsifier_report`），
   不是我在这个文件的注释里声称的。

## 这个文件不证明什么

它证明的是**这套判据对这批读数有鉴别力**，**不是**「装置是对的」。
判据是我们写的、读数是我们量的 —— 扰动能证明「一处改动会让它动」，
证明不了「两边不会一起错」。真锚在**对照臂**上：最有分量的一批判据不是
「270 好不好」，而是「守卫关与守卫开**必须不同、且朝这个方向不同**」。
"""

from __future__ import annotations

import argparse
import json
import pathlib
import platform
import sys
import time

from . import adjudicate as A

HERE = pathlib.Path(__file__).resolve().parent
MD_PATH = HERE / "SELFPROOF.md"
JS_PATH = HERE / "selfproof_report.json"

#: 扰动落在哪一层。**闭集**，写错就抛。
MUTATION_KINDS = ("读数", "断言", "边界")

#: (结果, 采信) 的全部合法组合。`不可判定` 的采信恒为 `None` ——
#: 判不了的断言不该被记成「不采信」（那会让不采信虚高），也不该记成「采信」。
GRIDS = ("通过·采信", "通过·不采信", "否决·采信", "否决·不采信", "不可判定")


class SelfproofError(Exception):
    pass


def grid_of(row) -> str:
    if row["verdict"] == A.UNDECIDED:
        return "不可判定"
    return f"{row['verdict']}·{'采信' if row['trusted'] else '不采信'}"


def _amend(cid: str, **kw):
    """把某一条判据改几个字段，其余原样。**改的是判据原文，不是代码里的数**。"""
    return tuple({**c, **kw} if c["id"] == cid else c for c in A.CLAIMS)


def _case(cid, layer, why, *, touch, untouched, edit=None, unrail=(),
          unmeasured=None, claims=None, vacuous=()):
    if layer not in MUTATION_KINDS:
        raise SelfproofError(
            f"{cid} 的扰动层写成 {layer!r}，不在 {MUTATION_KINDS} 里 —— "
            f"层写错一个字会让这一例静默退化，所以这里直接抛。")
    both = set(touch) & set(untouched)
    if both:
        raise SelfproofError(f"{cid}: {sorted(both)} 同时出现在 touch 和 untouched 里")
    for i, g in touch.items():
        if g not in GRIDS:
            raise SelfproofError(
                f"{cid}: 断言 {i} 会变成 {g!r}，不是 {GRIDS} 里的任何一个 —— "
                f"**表态必须写全 `结果·采信`**：只写「通过」漏掉采信那一半，"
                f"就漏掉了贴界降级和未测量这两条规则。")
    return {"id": cid, "layer": layer, "why": why, "touch": dict(touch),
            "untouched": tuple(untouched), "edit": dict(edit or {}),
            "unrail": tuple(unrail), "unmeasured": dict(unmeasured or {}),
            "claims": claims, "vacuous": tuple(vacuous)}


_ALL = tuple(c["id"] for c in A.CLAIMS)


CASES = (
    # ---- 读数层：判据真的读了这个量吗 ----------------------------------
    _case("P1", "读数",
          "把守卫开那格从 1 抬到 5 —— 两个数量级那句话就不成立了，"
          "而且这一格**不再贴界**（值不再卡在最小值上）",
          edit={("guard_on", "records_added"): 5},
          touch={"B1": "否决·采信"},
          untouched=("B2", "B3", "B4", "B5", "B6", "B7", "B8", "B9", "B10",
                     "E1", "E2", "E3", "E4", "E5")),

    _case("P2", "读数",
          "把守卫关那格从 270 压到 1 —— 两边一样了。这一格**没被扰动**，"
          "所以「守卫开贴界」这条声明仍然挂着：判成否决，**且不采信**",
          edit={("guard_off_1", "records_added"): 1},
          touch={"B1": "否决·不采信", "B2": "否决·采信"},
          untouched=("B3", "B4", "B5", "B6", "B7", "B8", "B9", "B10",
                     "E1", "E2", "E3", "E4", "E5")),

    _case("P3", "读数", "把守卫关第 2 遍的 token 数改掉一个 —— 「逐位相同」就不成立了",
          edit={("guard_off_2", "tokens_added"): 5016},
          touch={"B2": "否决·采信"},
          untouched=("B1", "B3", "B4", "B5", "B6", "B7", "B8", "B9", "B10",
                     "E1", "E2", "E3", "E4", "E5")),

    _case("P4", "读数", "把守卫关下的原文改成完整可寻回 —— 「被撕碎」是这条判据的全部内容",
          edit={("guard_off_1", "head_intact"): True},
          touch={"B3": "否决·采信"},
          untouched=("B1", "B2", "B4", "B5", "B6", "B7", "B8", "B9", "B10",
                     "E1", "E2", "E3", "E4", "E5")),

    _case("P5", "读数", "把膨胀从 18.5 倍压到 1.5 倍 —— 越过 ≥10 那条线",
          edit={("guard_off_1", "expansion"): 1.5},
          touch={"B4": "否决·采信"},
          untouched=("B1", "B2", "B3", "B5", "B6", "B7", "B8", "B9", "B10",
                     "E1", "E2", "E3", "E4", "E5")),

    _case("P6", "读数",
          "让「隔一拍」也出现违反 —— 那样「违反只在同拍出现」这个因果说法就垮了",
          edit={("guard_off_one_tick", "violations"): 2},
          touch={"B6": "否决·采信"},
          untouched=("B1", "B2", "B3", "B4", "B5", "B7", "B8", "B9", "B10",
                     "E1", "E2", "E3", "E4", "E5")),

    _case("P7", "读数",
          "让守卫开着时也出现违反 —— 这一条正是「守卫有用」的那一半，"
          "它必须会被弄红，否则它是装饰",
          edit={("guard_on_same", "violations"): 1},
          touch={"B7": "否决·采信"},
          untouched=("B1", "B2", "B3", "B4", "B5", "B6", "B8", "B9", "B10",
                     "E1", "E2", "E3", "E4", "E5")),

    _case("P8", "读数", "把 1 微秒那一格改成「没变样」—— 灵敏度那句话就不成立了",
          edit={("probe_0", "flipped"): False},
          touch={"B9": "否决·采信"},
          untouched=("B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B10",
                     "E1", "E2", "E3", "E4", "E5")),

    _case("P9", "读数",
          "把「耗时全相同时两遍相同」改成 False —— 连「次序是耗时的确定函数」都垮了",
          edit={("orders", "deterministic"): False},
          touch={"B10": "否决·采信"},
          untouched=("B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B9",
                     "E1", "E2", "E3", "E4", "E5")),

    # ---- 边界层：那两条规则真的会改结果吗 --------------------------------
    _case("P10", "边界",
          "**把「守卫开那格贴界」这条声明撤掉**（读数一个字不动）——"
          "B1 仍然通过，但**变成采信**。这证明那条降级是声明在起作用，"
          "不是因为数值凑巧",
          unrail=(("guard_on", "records_added"),),
          touch={"B1": "通过·采信"},
          untouched=("B2", "B3", "B4", "B5", "B6", "B7", "B8", "B9", "B10",
                     "E1", "E2", "E3", "E4", "E5")),

    _case("P11", "边界",
          "**把守卫开那格改标成「未测量」**（仍然是同一套读数）——"
          "B1 立刻变成**不可判定**。同源的两条规则走的是两条路："
          "贴界是「量到了但分不出」，未测量是「根本没量到」",
          unmeasured={("guard_on", "records_added"):
                      "（自证扰动：假设这一格这次没量到）"},
          touch={"B1": "不可判定"},
          untouched=("B2", "B3", "B4", "B5", "B6", "B7", "B8", "B9", "B10",
                     "E1", "E2", "E3", "E4", "E5")),

    # ---- 断言层：阈值真是从原文抠的吗、falsifier 真的在起作用吗 ----------
    _case("P12", "断言",
          "**只改判据原文里的阈值**（≥10 → ≥1000），代码一个字不动 ——"
          "B4 判成否决。这证明那个阈值是**从判据原文里抠出来的**，"
          "不是代码里另抄的一份",
          claims=_amend("B4", check="`guard_off_1.expansion` ≥ 1000"),
          touch={"B4": "否决·采信"},
          untouched=("B1", "B2", "B3", "B5", "B6", "B7", "B8", "B9", "B10",
                     "E1", "E2", "E3", "E4", "E5")),

    _case("P13", "断言",
          "**把 B4 声明的 falsifier 抽掉** —— 它照样判「通过」，"
          "但检查器应当**自己**把它标成恒真。这一例证明的是："
          "「这条判据没有鉴别力」是**机器**判出来的，不是我在注释里说的",
          claims=_amend("B4", falsifier=None),
          touch={}, untouched=tuple(_ALL),
          vacuous=("B4",)),

    # ---- 端到端那一层：后加的读数来源也得受同一套检验 ---------------------
    _case("P14", "读数",
          "**把端到端那条关系断言的两边扳平**（回落支那档的 `still_sliced` "
          "改成 0，和基线一样）—— 「加长助手文本才逼出回落支」这句话就不成立了。"
          "这一例证明端到端那一路的读数是**真的**在判据里起作用，"
          "不是摆在产物里好看的",
          edit={("bigtext_e2e", "still_sliced"): 0},
          touch={"E2": "否决·采信"},
          untouched=("B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B9", "B10",
                     "E1", "E3", "E4", "E5")),

    _case("P15", "边界",
          "**把「回落支那格恒为 0」这条贴界声明撤掉**（读数一个字不动）——"
          "E5 仍然通过，但**变成采信**。这一例和 P10 是一个意思，"
          "只是这次那格长在端到端那一路：**贴界降级是声明在起作用**",
          unrail=(("bigtext_e2e", "timestamp_pushed"),),
          touch={"E5": "通过·采信"},
          untouched=("B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B9", "B10",
                     "E1", "E2", "E3", "E4")),
)


def run() -> dict:
    t0 = time.time()
    report = A.load_report()

    # **端到端那一路不在，这里就不许装作跑过。**
    #
    # 为什么是硬要求、不是「跳过」：E1–E5 的 `touch`/`untouched` 是照着
    # 「这几条有定论」写的（比如 P14 期望 E2 从「通过」变「否决」）——
    # 读数不在时它们全是「不可判定」，实测和表态对不上，一跑就是一片红。
    # 那片红**不是发现**，是缺前提。所以按装置自己的三态惯用法：退 2，
    # 说清缺什么、怎么补（`exit_with(None)`）。**假红和假绿一样坏。**
    if A.load_e2e_report() is None:
        raise SelfproofError(
            f"没有 `{A.E2E_REPORT.name}` —— 端到端那一层（E1–E5）读不到数，"
            f"而本自证的表态是照着「这一层有定论」写的。\n"
            f"  先跑一次：cd backend && python -m verification.e2e_stub\n"
            f"  这是**没测到**，不是「没通过」。(exit 2)")

    cells, railed, unmeasured = A.all_cells()

    base_rows = A.evaluate(A.CLAIMS, cells, railed, unmeasured)
    base = {r["id"]: r for r in base_rows}

    seen = {grid_of(r) for r in base_rows}
    problems = []
    cases_out = []

    for c in CASES:
        covered = set(c["touch"]) | set(c["untouched"])
        if covered != set(_ALL):
            problems.append(
                f"{c['id']}：表态表没覆盖全部判据 —— "
                f"漏了 {sorted(set(_ALL) - covered)}、多了 {sorted(covered - set(_ALL))}")
        railed2 = {k: v for k, v in railed.items() if k not in c["unrail"]}
        unmeasured2 = dict(unmeasured)
        unmeasured2.update(c["unmeasured"])
        claims = c["claims"] or A.CLAIMS

        rows = A.evaluate(claims, cells, railed2, unmeasured2,
                          override=c["edit"] or None)
        now = {r["id"]: r for r in rows}
        # 表态写的是**整格**：`结果·采信`。只比结果会漏掉贴界降级 ——
        # 「通过·不采信」变成「通过·采信」是**该看见**的一次变化（见 P10）。
        moved = {i: grid_of(now[i]) for i in _ALL
                 if grid_of(now[i]) != grid_of(base[i])}

        # falsifier **一律在没扰动过的读数上实例化**：一条判据的 falsifier 是
        # 关于「原始读数」的声明。拿扰动后的状态去试它自己，等于把它的扰动
        # 用掉之后再要求它再翻一次 —— 那会把自己判成恒真，是**假警报**。
        fals = A.falsifier_report(claims, cells, railed, unmeasured)
        vacuous = tuple(f["id"] for f in fals if f["kind"] == "恒真")

        if moved != c["touch"]:
            problems.append(
                f"{c['id']}：断言会变的是 {c['touch']}，**实测**是 {moved}")
        for i in c["untouched"]:
            if grid_of(now[i]) != grid_of(base[i]):
                problems.append(
                    f"{c['id']}：断言 {i} **不许变**，实测从 {grid_of(base[i])} "
                    f"变成了 {grid_of(now[i])}")
        if vacuous != c["vacuous"]:
            problems.append(
                f"{c['id']}：期望恒真的是 {c['vacuous']}，实测是 {vacuous}")

        for r in rows:
            seen.add(grid_of(r))
        cases_out.append({
            "id": c["id"], "layer": c["layer"], "why": c["why"],
            "edit": {f"{a}.{m}": v for (a, m), v in c["edit"].items()},
            "unrail": [f"{a}.{m}" for a, m in c["unrail"]],
            "unmeasured": {f"{a}.{m}": w for (a, m), w in c["unmeasured"].items()},
            "claims_amended": sorted({i for i in _ALL if c["claims"]
                                      and [x for x in c["claims"] if x["id"] == i]
                                      != [x for x in A.CLAIMS if x["id"] == i]}),
            "touch": c["touch"], "untouched": list(c["untouched"]),
            "moved": moved, "vacuous": list(vacuous),
            "ok": not any(p.startswith(c["id"] + "：") for p in problems),
        })

    # -- 元断言一：五格全出现 ---------------------------------------------
    missing = [g for g in GRIDS if g not in seen]
    # -- 元断言二：每条判据要么可翻面、要么明说缺读数 -----------------------
    fals_base = A.falsifier_report(A.CLAIMS, cells, railed, unmeasured,
                                   base_rows=base_rows)
    vac_base = [f["id"] for f in fals_base if f["kind"] == "恒真"]
    unreachable = [f["id"] for f in fals_base if f["kind"] == "不可判定"]

    if missing:
        problems.append(f"**有死格**：这几种状态一次都没到达 —— {missing}")
    if vac_base:
        problems.append(f"**判据恒真**（任何单点扰动都翻不动）：{vac_base}")

    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "not_a_pass_rate": True,
        "what_this_is": "对**真读数**做单点受控扰动，逐条检验这套判据有没有鉴别力。",
        "what_this_is_NOT":
            "不是「判据对不对」的证明 —— 它证明的是「一处改动会让它动」，"
            "证明不了「判据和读数不会一起错」。真锚在对照臂上。",
        "environment": {"python": sys.version.split()[0],
                        "platform": platform.platform(), "cwd": "backend/"},
        "script": {"path": "verification/selfproof.py",
                   "sha256": A._sha(pathlib.Path(__file__).read_text(encoding="utf-8"))},
        # 同 `adjudicate`：钉的是**这批读数**的指纹，不是报告文件的 sha
        # （报告每跑一次 `run_all` 就会重写，钉文件等于「谁重跑谁就红」）。
        "report": {"path": A.REPORT.name,
                   "generated_at": report.get("generated_at"),
                   # 两份报告一起出指纹 —— 只钉住其中一份，另一份换了读数这张表
                   # 就不会响（见 `A.readings_digest`）。
                   "readings_sha256": A.readings_digest(
                       report, A.load_e2e_report())},
        "claims": {"count": len(A.CLAIMS), "ids": list(_ALL),
                   "source": "verification/adjudicate.py"},
        "base": [{"id": r["id"], "verdict": r["verdict"], "trusted": r["trusted"],
                  "grid": grid_of(r), "why": r["why_not_solid"]}
                 for r in base_rows],
        "cases": cases_out,
        # 基础状态（没扰动）下每条判据的 falsifier 实例化结果 —— 这是**检查器自己**
        # 判出来的，不是这个文件的注释声称的。
        "falsifiers": fals_base,
        "meta": {
            "grids_seen": sorted(seen), "grids_required": list(GRIDS),
            "grids_missing": missing,
            "claims_with_working_falsifier":
                [f["id"] for f in fals_base if f["kind"] == "可翻面"],
            "claims_undecidable": unreachable,
            "claims_vacuous": vac_base,
            "cases_ok": sum(1 for c in cases_out if c["ok"]),
            "all_ok": not problems,
        },
        "problems": problems,
        "seconds": round(time.time() - t0, 2),
    }


def render_markdown(rep: dict) -> str:
    m = rep["meta"]
    L = ["# 自证留痕（自动生成，别手改）", "",
         f"> 生成时间 **{rep['generated_at']}** · Python {rep['environment']['python']} · "
         f"`cd backend && python -m verification.selfproof`（{rep['seconds']}s）", "",
         f"> 扰动的对象：**`{rep['report']['path']}` 里那一次运行的真实读数**"
         f"（读数指纹 `{rep['report']['readings_sha256'][:12]}…`）—— **不重跑复现**。"
         f"**钉的是读数不是文件**：报告重写一遍、数没变，这份产物就没过期。", "",
         f"**是**：{rep['what_this_is']}", "",
         f"**不是**：{rep['what_this_is_NOT']}", "",
         "## 一、五格必须全出现", "",
         "| 状态 | 出现过 |", "|---|---|"]
    for g in GRIDS:
        L.append(f"| {g} | {'√' if g in m['grids_seen'] else '× **死格**'} |")
    L += ["",
          "少一格就说明那套判据**根本到不了那个状态** —— 有一格是死的。", "",
          "## 二、每条判据的 falsifier", "",
          "每条判据都声明了一处**具名的单点扰动**。它必须真能把这条判据翻面 ——",
          "翻不动的就是**判据恒真**，它判出来的「通过」什么也不说明。",
          "（判不了的那几条翻不动的原因**是缺读数，不是恒真** —— 两者不能混。）", "",
          "| 判据 | 试的结果 | 明细 |", "|---|---|---|"]
    for f in rep["falsifiers"]:
        mark = {"可翻面": "√ 翻得动", "恒真": "× **恒真**",
                "不可判定": "—（缺读数）"}[f["kind"]]
        L.append(f"| `{f['id']}` | {mark} | {f['detail']} |")
    L += ["", "## 三、逐例", "",
          "| 例 | 扰动层 | 动了什么 | 断言会变的 | 断言不许变的 | 结果 |",
          "|---|---|---|---|---|---|"]
    for c in rep["cases"]:
        what = ("、".join(f"{k}→{v}" for k, v in c["edit"].items())
                or "、".join(f"撤掉 {k} 的贴界声明" for k in c["unrail"])
                or "、".join(f"{k} 改标未测量" for k in c["unmeasured"])
                or ("改判据原文：" + "、".join(c["claims_amended"])))
        moved = "、".join(f"{k}→{v}" for k, v in c["moved"].items()) or "（无）"
        L.append(f"| `{c['id']}` | {c['layer']} | {what} | {moved} | "
                 f"{len(c['untouched'])} 条 | {'√' if c['ok'] else '×'} |")
    L += ["", "### 每例到底在证什么", ""]
    for c in rep["cases"]:
        L.append(f"**`{c['id']}` · {c['layer']}** —— {c['why']}")
        L.append("")
    if rep["problems"]:
        L += ["##  有问题", ""] + [f"- {p}" for p in rep["problems"]] + [""]
    else:
        L += ["## 结论", "",
              f"- 五格全出现过：**{'是' if not m['grids_missing'] else '否'}**",
              f"- 能拿单点扰动翻面的判据：**{len(m['claims_with_working_falsifier'])}"
              f"/{rep['claims']['count']}**；"
              f"恒真的：**{m['claims_vacuous'] or '没有'}**",
              f"- 逐例表态全部相符：**{m['cases_ok']}/{len(rep['cases'])}**",
              f"- **这就是全部**：它证明这套判据对这批读数有鉴别力，"
              f"**不证明装置是对的**。", ""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="自证：这套判据不是恒绿的")
    ap.add_argument("--json", default=str(JS_PATH))
    ap.add_argument("--md", default=str(MD_PATH))
    args = ap.parse_args(argv)

    try:
        rep = run()
    except (A.AdjudicationError, SelfproofError) as e:
        # 同 `adjudicate`：前提不成立是「没测到」（`2`），不是「没达到预期」（`1`）。
        # `SelfproofError` 也走这条路：端到端那一层没跑过时，本文件退 `2` 并说清
        # 怎么补 —— 那**不是**一次发现，缺的是前提。**假红和假绿一样坏。**
        print(f"\n○ 没测到：{e}")
        return 2

    pathlib.Path(args.json).write_text(
        json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    pathlib.Path(args.md).write_text(render_markdown(rep), encoding="utf-8")

    m = rep["meta"]
    print(f"\n→ {args.json}")
    print(f"→ {args.md}")
    print(f"\n五格：{'、'.join(m['grids_seen'])}")
    if m["grids_missing"]:
        print(f"  × **有死格**：{m['grids_missing']}")
    print(f"逐例表态：{m['cases_ok']}/{len(rep['cases'])} 相符")
    print(f"能翻面的判据：{len(m['claims_with_working_falsifier'])}"
          f"/{rep['claims']['count']}；恒真：{m['claims_vacuous'] or '没有'}")
    for p in rep["problems"]:
        print(f"  × {p}")
    print("（下一步：`python -m verification.mutations` 重记指纹 —— "
          "tests/ 或 verification/ 改过就必须重跑。）")
    return 0 if m["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
