"""裁决：把三条复现的**读数**拿一套判据判一遍，判成**三种**结果，并说出哪些判不了。

    python -m verification.adjudicate        # 在 backend/ 下；先跑过 run_all

## 这是什么

三条复现各自报「达到预期 / 没达到预期 / 没测到」，那是**每一条自己的**判定。
这里做的是另一件事：把三条各自的读数**摆到一张桌上**，用一套**跨复现的**判据去判 ——
比如「守卫关与守卫开的记录数至少差两个数量级」这种话，任何单独一条复现都判不了。

判据不是事后从读数里总结出来的（那样它只会复述代码干了什么）。每一条都是关于
**系统**的假设，写在版本库里，并且必须自带一个 `falsifier`：**一处具名的单点读数
改动，能把这条断言弄红**。给不出、或者给了却翻不动它的，检查器就判它**判据恒真**、
记 `trusted=False`，理由写明「任何单点扰动都翻不动它」。

于是「这套判据有没有鉴别力」是被**机检**的，不是被声称的。`selfproof.py` 就是那台
自证的机器。

## 三种结果

| 结果 | 含义 |
|---|---|
| **通过** | 判据成立 |
| **否决** | 判据不成立 |
| **不可判定** | **缺读数**，判不了。必须带 `undecidable_because`（缺什么）与 `to_make_decidable`（怎么才能判） |

不可判定**既不算通过也不算否决**。它与 `trusted` 正交：一条「通过」可以是
**不采信**的（读数还在，但那格卡在夹逼上、分不出差别），而不可判定的 `trusted`
记 `None` —— 记 `False` 会让「不采信」这个数虚高，记 `True` 又等于说它可信。

## 采信（`trusted`）与结果分开

`no_trust_because` 是**一串理由**，不是布尔。两条规则：

* **贴界一票降级**：断言读到的格子里有一个是**贴界**的（值被机制压住、失去分辨力），
  这条断言就不采信 —— 量还在，但它分不出差别，结论不牢。
* **判据恒真**：`falsifier` 实例化后翻不动这条断言 → 不采信。

## 这份产物不是什么

不是分数。**没有分母，不产生比率。** 「10 条里 6 条通过」不是这里的读法：
判不了的那几条不是「没通过」，它们**根本没被判定**。聚合就违背了这件事。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import platform
import re
import sys
import time

from . import _probe as P

HERE = pathlib.Path(__file__).resolve().parent          # backend/verification
BACKEND = HERE.parent                                   # backend/

REPORT = BACKEND / "verification_report.json"
#: 端到端那份（`e2e_stub.py` 落的）。**可以在，也可以不在** —— 见 `load_e2e_report`。
E2E_REPORT = HERE / "e2e_report.json"
MD_PATH = HERE / "ADJUDICATION.md"
JS_PATH = HERE / "adjudication_report.json"

#: 三种结果。`不可判定` 与另两个**并列**，不是它们的子类。
PASS_, FAIL_, UNDECIDED = "通过", "否决", "不可判定"

#: 不采信的两条理由。
NO_TRUST_RAIL = "贴界"
NO_TRUST_VACUOUS = "判据恒真"

#: 断言声明的「层」是一个**闭集**。写错一个字会让整条断言静默退化 ——
#: 所以这里校验，不认识的层直接抛。（本装置在别处真踩过：`产出` 写成 `产物`。）
#:
#: 「端到端」是后加的一层：前四层读的是 `run_all` 那三条复现的读数（全离线），
#: 这一层读的是 `e2e_stub` 那份**另跑一次**的读数（替身模型驱真入口脚本）。
#: 两份报告分开落、分开读 —— 因为端到端那一条**可以不在**（没跑就没有），
#: 而前三条复现的读数**不许不在**。
LAYERS = ("复现一", "复现二", "复现三", "跨复现", "端到端")


class AdjudicationError(Exception):
    """判据表本身有问题 —— 这种错必须在生成表**之前**停下来。"""


def _num(pattern: str, check: str, what: str) -> float:
    """从判据 `check` 原文里**抠出阈值**，而不是在代码里再抄一遍。

    抄一遍等于给同一件事写两个数：判据改了阈值，代码不知道，这张表就会拿着
    旧阈值去判新断言 —— 而它自己不会知道。抠不出来就抛，**不猜**。
    """
    m = re.search(pattern, check)
    if not m:
        raise AdjudicationError(
            f"判据里找不到{what}：`{check}`\n"
            f"  本表不替它补一个默认阈值 —— 补出来的数没人会发现它是编的。")
    return float(m.group(1))


# ---------------------------------------------------------------------------
# 判据表
# ---------------------------------------------------------------------------

def _c(cid, layer, what, check, operands, holds, *, thresholds=(),
       falsifier=None, undecidable=None, to_fix=None, why_not_solid=""):
    """组装一条判据。

    * `check` —— 判据原文。阈值写在这里面，代码用 `thresholds` 的正则去抠。
    * `operands` —— 这条判据读过的单元格，`(臂, 量)` 的元组。**读不到就是不可判定**。
    * `holds` —— `(值列表, 抠出来的阈值列表) -> bool`。
    * `falsifier` —— **一处具名的单点读数改动**，能让这条判据翻面。
      给不出（`None`）而判据又不是不可判定的 → 判它恒真。
    """
    if layer not in LAYERS:
        raise AdjudicationError(
            f"{cid} 的层写成 {layer!r}，不在 {LAYERS} 里 —— "
            f"写错一个字会让这条判据静默退化，所以这里直接抛。")
    # 「缺什么」和「怎么才能判」必须成对：只说缺什么，读的人知道判不了、
    # 却不知道该去量什么；只说怎么补，又不知道当下缺的到底是哪一样。
    if undecidable and not to_fix:
        raise AdjudicationError(
            f"{cid} 说了「缺什么」却没说「怎么才能判」—— 这两条必须成对，"
            f"不然那条「不可判定」就成了一个死胡同。")
    if to_fix and not undecidable:
        raise AdjudicationError(
            f"{cid} 交代了「怎么才能判」却没说「缺什么」—— 这两条必须成对。")
    return {"id": cid, "layer": layer, "what": what, "check": check,
            "operands": tuple(operands), "holds": holds,
            "thresholds": tuple(thresholds), "falsifier": falsifier,
            "undecidable_because": undecidable, "to_make_decidable": to_fix,
            "why_not_solid": why_not_solid}


#: **判据表必须自己说清楚它是什么、哪几条不结实。**
#: 缺了就直接抛、不生成表 —— 这句话不能由检查器代说。
CLAIM_SET = {
    "what_this_is": (
        "一套**跨复现的**判据：把三条复现各自的读数摆到一张桌上判。"
        "每条都自带 falsifier，所以「它有没有鉴别力」是可机检的。"),
    "what_this_is_NOT": (
        "不是分数，不是通过率，不是质量评价。判不了的那几条**根本没被判定**，"
        "不算「未通过」—— 所以这张表**不许被聚合成任何比率**。"),
    "what_it_does_NOT_prove": (
        "它证明的是「**这套判据对这批读数有鉴别力**」，"
        "**不是**「装置是对的」。判据是我们写的，读数是我们量的 —— "
        "这张表能排除的是「判据恒真／被贴界蒙混」，排除不了「两边一起错」。"
        "**还有一件照实说**：判据是**读到读数之后**才写下来的，不是先验的。"
        "所以「对这批读数有鉴别力」不等于「对任何别的读数也有」—— 换一批读数，"
        "这套判据必须重写、重跑自证，不能搬过去当结论用。"
        "**这里一句条数都不写**：判不了几条、哪几条不采信，都随「端到端那一跑在不在」"
        "而变，写死的数会变成一句**听着像事实的过期话**。要看数就看 `summary` —— "
        "那两个数（`by_verdict`、`not_trusted`）是**当场数出来的**，不是写在这里的。"
        "它没被写成一张更好看的表，靠的不是我们自觉，是下面三件事："
        "**判不了的不计进任何一边**（缺读数就如实判不了）、"
        "**贴界一票降级**（成立但不结实）、"
        "**给不出 falsifier 的判据自己判自己恒真**。"),
    "not_solid": (
        "**通过但不采信**的那些，逐条理由在每行的 `no_trust_because` 里。这里举三类："
        "① **分母卡在本量的最小值上** —— B1 守卫开那格是 1，而 1 是这个量的最小可能值；"
        "② **比较基准退化** —— B10 比的是「耗时全相同」这个情形；"
        "③ **计数在那一支上按构造加不动** —— 端到端里「回落支那档的 "
        "`timestamp_pushed`」恒为 0（计数只加在快路径上）。"
        "三类都成立，但都**分不出差别**，所以都不足以论证「守卫好」。"),
}
#: 判据表**必须**自己交代的四件事。缺一件就抛 —— 这句话不能由检查器代说。
REQUIRED_DECLARATIONS = ("what_this_is", "what_this_is_NOT",
                         "what_it_does_NOT_prove", "not_solid")


def require_declarations(d) -> None:
    """判据表没交代「自己是什么、不是什么」，就不许生成表。

    这不是格式检查。一张只有判据、没有自我限定的话的表，读起来就是一份评分 ——
    而这份东西**不是**评分：它没有分母，判不了的那几条根本没被判定。
    这句话得由判据表**自己**说，检查器代说就成了贴标签。
    （`gold_check.py:679` 的纪律：写器必须自己声明「这不是分数」。）
    """
    for k in REQUIRED_DECLARATIONS:
        if not d.get(k):
            raise AdjudicationError(
                f"判据表没有交代 `{k}` —— 这句话必须由判据表自己说，"
                f"不能由本表代说。缺了它，这张表就会被读成一份评分。")


require_declarations(CLAIM_SET)


CLAIMS = (
    # ---- 复现一（切片）----------------------------------------------------
    _c("B1", "复现一",
       "守卫关把一条消息切成几百条记录，守卫开只切一条 —— 至少差两个数量级",
       "`guard_off_1.records_added` > `guard_on.records_added` × 100",
       (("guard_off_1", "records_added"), ("guard_on", "records_added")),
       lambda v, t: v[0] > v[1] * t[0],
       thresholds=((r"×\s*([\d.]+)", "倍数下界"),),
       falsifier={("guard_on", "records_added"): 5},
       why_not_solid="分母卡在本量的最小值上，这一格分不出「更好」"),

    _c("B2", "复现一",
       "守卫关那两遍在同一份前提下逐位相同 —— 这是确定性的复现，不是碰巧",
       "`guard_off_1.records_added` == `guard_off_2.records_added` 且 "
       "`guard_off_1.tokens_added` == `guard_off_2.tokens_added`",
       (("guard_off_1", "records_added"), ("guard_off_2", "records_added"),
        ("guard_off_1", "tokens_added"), ("guard_off_2", "tokens_added")),
       lambda v, t: v[0] == v[1] and v[2] == v[3],
       falsifier={("guard_off_2", "records_added"): 269}),

    _c("B3", "复现一",
       "原文在守卫关下已经找不回连续片段，在守卫开下完整可寻回",
       "`guard_on.head_intact` == True 且 `guard_off_1.head_intact` == False",
       (("guard_on", "head_intact"), ("guard_off_1", "head_intact")),
       lambda v, t: v[0] is True and v[1] is False,
       falsifier={("guard_off_1", "head_intact"): True}),

    _c("B4", "复现一",
       "切片把这一次写入放大了至少一个数量级",
       "`guard_off_1.expansion` ≥ 10",
       (("guard_off_1", "expansion"),),
       lambda v, t: v[0] >= t[0],
       thresholds=((r"≥\s*([\d.]+)", "膨胀下界"),),
       falsifier={("guard_off_1", "expansion"): 1.5}),

    # ---- 复现二（同拍）----------------------------------------------------
    _c("B6", "复现二",
       "违反只在「同拍」时出现 —— 隔一拍就合法，说明节拍是成因",
       "`guard_off_same.violations` ≥ 1 且 `guard_off_one_tick.violations` == 0",
       (("guard_off_same", "violations"), ("guard_off_one_tick", "violations")),
       lambda v, t: v[0] >= t[0] and v[1] == 0,
       thresholds=((r"≥\s*([\d.]+)", "违反数下界"),),
       falsifier={("guard_off_one_tick", "violations"): 2}),

    _c("B7", "复现二",
       "守卫开着时**同样是同拍**（碰撞还在），但违反为零 —— 破坏不了了",
       "`guard_on_same.violations` == 0 且 `guard_on_same.gap_ns` == 0",
       (("guard_on_same", "violations"), ("guard_on_same", "gap_ns")),
       lambda v, t: v[0] == 0 and v[1] == 0,
       falsifier={("guard_on_same", "violations"): 1}),

    # ---- 复现三（并发）----------------------------------------------------
    _c("B9", "复现三",
       "栅格上最小的那一格（1 微秒）就已经让落库次序变样",
       "`probe_0.flipped` == True 且 `probe_0.probe_s` ≤ 0.000001 秒",
       (("probe_0", "flipped"), ("probe_0", "probe_s")),
       lambda v, t: v[0] is True and v[1] <= t[0],
       thresholds=((r"≤\s*([\d.]+)\s*秒", "耗时差上界"),),
       falsifier={("probe_0", "flipped"): False}),

    _c("B10", "复现三",
       "耗时全相同时，两遍次序逐位相同 —— 这一层是确定的，乱的是喂给它的耗时",
       "`orders.deterministic` == True",
       (("orders", "deterministic"),),
       lambda v, t: v[0] is True,
       falsifier={("orders", "deterministic"): False},
       why_not_solid="比较基准是「耗时全相同」这个退化情形，不是「按提交顺序」"),

    # ---- 不可判定 ---------------------------------------------------------
    _c("B5", "复现三",
       "两次真实 LLM 调用之间的耗时差是毫秒到秒量级 —— "
       "所以「1 微秒就能让次序变样」这个阈值**根本没有安全余量**",
       "`real_llm_call.gap_s` ≥ 0.001",
       (("real_llm_call", "gap_s"),),
       lambda v, t: v[0] >= t[0],
       thresholds=((r"≥\s*([\d.]+)", "耗时差下界"),),
       undecidable="本轮读数里**没有一格**能量到真实调用耗时 —— "
                   "三条复现全部离线、不发请求，量不到它",
       to_fix="量一次真实 LLM 调用的往返耗时差，把它打进读数块"),

    _c("B8", "复现一",
       "装上切片守卫没有把单次写入变慢到影响可用性",
       "`guard_on.write_seconds` ≤ `guard_off_1.write_seconds` × 2",
       (("guard_on", "write_seconds"), ("guard_off_1", "write_seconds")),
       lambda v, t: v[0] <= v[1] * t[0],
       thresholds=((r"×\s*([\d.]+)", "允许的倍数"),),
       undecidable="三条复现量的都是写入的**后果**（记录数、token 数），"
                   "**没有量写入本身的耗时** —— 这一格不存在",
       to_fix="在写入前后各读一次时钟，把耗时也打进读数块"),

    # ---- 端到端（替身模型 · 真入口脚本）------------------------------------
    #
    # 这一层的读数来自**另一次运行**（`python -m verification.e2e_stub`），
    # 与上面那三层的 `verification_report.json` 分开落盘。它**可以不在** ——
    # 没跑过那一趟，这几条就如实判「不可判定」，不是「没通过」（`evaluate`
    # 的缺格子分支已经这么做了，这里只把「怎么补」写得更可操作）。
    #
    # **这一层主张什么、不主张什么**（照实写在这里，因为它决定了这几条判据
    # 该被读成什么）：它主张的是「**守卫的两个分支都被真实流量走到了**」——
    # 快路径写入走通了、超限回落支走通了、同拍写入被推了时间戳、动作真落进了
    # 平台库。它**不主张「守卫修好了什么」** —— 那是复现一／复现二的活：
    # 那两条量的是「装上前后差多少」，这一层量的是「装上了、并且被走到了」。
    _c("E1", "端到端",
       "快路径写入被真实流量走到 —— 守卫装上了，而且那支真的在干活",
       "`roomy_e2e.written_whole` > 0",
       (("roomy_e2e", "written_whole"),),
       lambda v, t: v[0] > t[0],
       thresholds=((r">\s*([\d.]+)", "下界"),),
       falsifier={("roomy_e2e", "written_whole"): 0},
       undecidable="本轮没跑 `python -m verification.e2e_stub` —— "
                   "端到端那份报告不在，这几格读不到",
       to_fix="在 backend/ 下跑一次 `python -m verification.e2e_stub`"),

    _c("E2", "端到端",
       "超限回落支被真实流量走到 —— 把助手文本加到 20000 字，"
       "「自己就超上限」那一支才动；不加它一次都不动",
       "`bigtext_e2e.still_sliced` > `roomy_e2e.still_sliced`",
       (("bigtext_e2e", "still_sliced"), ("roomy_e2e", "still_sliced")),
       lambda v, t: v[0] > v[1],
       falsifier={("bigtext_e2e", "still_sliced"): 0},
       undecidable="本轮没跑 `python -m verification.e2e_stub` —— "
                   "端到端那份报告不在，这几格读不到",
       to_fix="在 backend/ 下跑一次 `python -m verification.e2e_stub`"),

    _c("E3", "端到端",
       "一次响应里并排两个动作时，写入时间戳真被推开了 —— "
       "同拍那一路在端到端上也被走到",
       "`two_e2e.timestamp_pushed` > 0",
       (("two_e2e", "timestamp_pushed"),),
       lambda v, t: v[0] > t[0],
       thresholds=((r">\s*([\d.]+)", "下界"),),
       falsifier={("two_e2e", "timestamp_pushed"): 0},
       undecidable="本轮没跑 `python -m verification.e2e_stub` —— "
                   "端到端那份报告不在，这几格读不到",
       to_fix="在 backend/ 下跑一次 `python -m verification.e2e_stub`"),

    _c("E4", "端到端",
       "同一次响应里的**第二个动作没有被吞掉** —— 它一路走到了平台库"
       "（两个动作的库里行数是单动作那档的两倍）",
       "`two_e2e.db_posts` > `roomy_e2e.db_posts`",
       (("two_e2e", "db_posts"), ("roomy_e2e", "db_posts")),
       lambda v, t: v[0] > v[1],
       falsifier={("two_e2e", "db_posts"): 2},
       why_not_solid="两档臂的 agent 数相同、每个 agent 恰恰一轮 —— "
                     "所以这个比较**有分母**，比值本身不额外说明什么；"
                     "它说的是「第二个动作没被吞」，不是「吞吐更高」",
       undecidable="本轮没跑 `python -m verification.e2e_stub` —— "
                   "端到端那份报告不在，这几格读不到",
       to_fix="在 backend/ 下跑一次 `python -m verification.e2e_stub`"),

    _c("E5", "端到端",
       "回落支那档**没有**发生同拍碰撞",
       "`bigtext_e2e.timestamp_pushed` == 0",
       (("bigtext_e2e", "timestamp_pushed"),),
       lambda v, t: v[0] == 0,
       falsifier={("bigtext_e2e", "timestamp_pushed"): 1},
       undecidable="本轮没跑 `python -m verification.e2e_stub` —— "
                   "端到端那份报告不在，这几格读不到",
       to_fix="在 backend/ 下跑一次 `python -m verification.e2e_stub`",
       why_not_solid="**这一格按构造恒为 0**：`timestamp_pushed` 只在快路径写入"
                     "那一支累加，而这一档走的正是回落支 —— 它分不出「有没有碰撞」。"
                     "这条「通过」因此**不采信**（见 `no_trust_because`）。"
                     "它留在这里是有用的：它把「我们想主张、但这格撑不住」"
                     "这件事摆到台面上，而不是把它藏起来。"),
)


# ---------------------------------------------------------------------------
# 读数 → 单元格
# ---------------------------------------------------------------------------

def load_report(path: pathlib.Path = REPORT) -> dict:
    if not path.is_file():
        raise AdjudicationError(
            f"没有 `{path.name}` —— 先跑一次 `cd backend && python -m verification.run_all`。"
            f"本表判的是**那次运行**的读数，不自己重跑（重跑就不是同一批读数了）。")
    return json.loads(path.read_text(encoding="utf-8"))


def load_e2e_report(path: pathlib.Path = E2E_REPORT):
    """端到端那份报告。**不在就返回 `None` —— 不抛。**

    和 `load_report` 的处置**故意不同**：三条复现的读数**必须**在（不在就说明
    谁把前提搞坏了，该停下来），而端到端这一趟**本来就可以没跑过**。所以这里
    返回 `None`，由 `evaluate` 的缺格子分支把那几条如实判成「不可判定」，
    并带着「跑一次 e2e_stub」这条补法。**这正是三态里那一格的用处** ——
    把「没测到」和「没通过」分开，而不是让它静默少几条。
    """
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        # 文件在、但不是 JSON —— 这是**没测到**，不是「读数为空」。返回 None，
        # 让它按同样的路走到「不可判定」，而不是在这里崩掉整张表。
        return None


def cells_from(report: dict, *extra):
    """把报告里各条复现的读数摊平成 `{(臂, 量): 值}`，并分出贴界/未测量的格。

    `extra` 是**另外几份同形的报告**（端到端那份就是这么进来的）。加可变参数
    而不是加一个专用分支：一份报告一个来源，来源之间不互相知道。
    """
    cells, railed, unmeasured = {}, {}, {}
    for rep in (report, *extra):
        if not rep:
            continue
        for entry in rep.get("results", []):
            block = entry.get("readings")
            if not block:
                continue
            for arm, vals in block.get("readings", {}).items():
                for metric, value in vals.items():
                    cells[(arm, metric)] = value
            for b in block.get("boundaries", []):
                key = (b["arm"], b["metric"])
                if b["kind"] == P.BOUND_UNMEASURED:
                    unmeasured[key] = b["why"]
                else:
                    railed[key] = b["why"]
    return cells, railed, unmeasured


def all_cells():
    """**本表判的全部格子**，一个入口。`run()` 与 `selfproof` 都走它。

    存在的理由：格子有**两个**来源了（三条复现 + 端到端），而「两边都读上」
    这件事必须是**一处**说了算 —— 两处各读一半，就会出现「这份产物判了 15 条、
    那份判了 10 条」而没人发现。
    """
    return cells_from(load_report(), load_e2e_report())


# ---------------------------------------------------------------------------
# 判
# ---------------------------------------------------------------------------

def evaluate(claims=CLAIMS, cells=None, railed=None, unmeasured=None,
             override=None) -> list:
    """把判据逐条判一遍。`override` 是单点扰动：`{(臂,量): 新值}`。"""
    cells = dict(cells or {})
    railed, unmeasured = railed or {}, unmeasured or {}
    if override:
        cells.update(override)
        # 被扰动过的格子，它的贴界声明就不再适用了：那一格已经不是量到的那一格。
        railed = {k: v for k, v in railed.items() if k not in override}
        unmeasured = {k: v for k, v in unmeasured.items() if k not in override}

    rows = []
    for c in claims:
        missing = [k for k in c["operands"]
                   if k not in cells or k in unmeasured]
        if missing:
            rows.append({
                "id": c["id"], "layer": c["layer"], "what": c["what"],
                "check": c["check"], "verdict": UNDECIDED,
                # 判不了的断言**不谈采信**：记 None，不记 False。
                "trusted": None, "no_trust_because": [],
                "values": {f"{a}.{m}": cells.get((a, m)) for a, m in c["operands"]},
                "operands": [f"{a}.{m}" for a, m in c["operands"]],
                "tainted_by_railing": [],
                "undecidable_because": c["undecidable_because"] or
                    "读不到这些格子：" + "、".join(f"{a}.{m}" for a, m in missing),
                # **每一条「不可判定」都要说得出怎么才能判**，一条都不许漏。
                # 判据自己没交代时，那个答案其实显而易见 —— 把缺的那格量出来。
                # 与其留一个空档，不如把它写出来：空档读起来像「没办法」，
                # 而这里几乎总是有办法。
                "to_make_decidable": c["to_make_decidable"] or
                    "把 " + "、".join(f"{a}.{m}" for a, m in missing)
                    + " 量出来，打进读数块",
                "why_not_solid": c["why_not_solid"],
                "detail": "缺 " + "、".join(f"{a}.{m}" for a, m in missing),
            })
            continue

        vals = [cells[k] for k in c["operands"]]
        t = [_num(pat, c["check"], what) for pat, what in c["thresholds"]]
        ok = bool(c["holds"](vals, t))
        hits = [f"{a}.{m}" for a, m in c["operands"] if (a, m) in railed]
        reasons = [NO_TRUST_RAIL] if hits else []
        rows.append({
            "id": c["id"], "layer": c["layer"], "what": c["what"],
            "check": c["check"], "verdict": PASS_ if ok else FAIL_,
            "trusted": not reasons, "no_trust_because": reasons,
            "values": {f"{a}.{m}": cells[(a, m)] for a, m in c["operands"]},
            "operands": [f"{a}.{m}" for a, m in c["operands"]],
            "tainted_by_railing": hits,
            "undecidable_because": None, "to_make_decidable": None,
            "why_not_solid": c["why_not_solid"],
            "detail": ("成立" if ok else "不成立")
                      + ("；读数贴界：" + "、".join(
                          f"{h}（{railed[tuple(h.split('.'))]}）" for h in hits)
                         if hits else ""),
        })
    return rows


def falsifier_report(claims=CLAIMS, cells=None, railed=None, unmeasured=None,
                     base_rows=None) -> list:
    """逐条实例化 `falsifier`：**它必须真的能把这条判据从「通过」弄红**。

    falsifier 只在**这条判据当前是「通过」**的时候才有活干 —— 一条已经判「否决」
    的判据不需要再证明「它错得出来」，它已经错了。所以：

    * 通过 + 扰动翻得动 → **可翻面**（这就是要的）
    * 通过 + 扰动翻不动 → **恒真** —— 任何单点扰动都改不了它的结果，
      它判出来的「通过」什么也不说明。这正是要抓的东西。
    * 否决 → **已否决**，不适用
    * 不可判定 → 翻不动的原因是**缺读数**，**不是恒真**，两者不能混

    **一律在**（可能被改过的）判据表 + 传进来的那批读数上实例化，
    不看别的状态 —— 否则「扰动后再试一次自己」会把自己判成恒真。
    """
    cells, railed, unmeasured = cells or {}, railed or {}, unmeasured or {}
    if base_rows is None:
        base_rows = evaluate(claims, cells, railed, unmeasured)
    base = {r["id"]: r for r in base_rows}

    out = []
    for c in claims:
        cid = c["id"]
        f = c["falsifier"]
        probe = "、".join(f"{a}.{m} 改成 {v!r}" for (a, m), v in f.items()) if f else ""
        # 四种情形各判各的，**顺序有意**：先看这条判据现在是什么状态，
        # 再看它的 falsifier 有没有活干。反过来会把一条已经红的判据说成恒真。
        if base[cid]["verdict"] == UNDECIDED:
            kind, detail = "不可判定", (
                "缺读数，翻不动的原因是缺读数 —— **不是恒真**；"
                "该怎么补见 `to_make_decidable`")
        elif base[cid]["verdict"] == FAIL_:
            kind, detail = "已否决", (
                "这条判据本来就判「否决」—— "
                "**已经红了的判据不需要再证明它错得出来**")
        elif not f:
            kind, detail = "恒真", (
                "这条判据**没有声明 falsifier** —— "
                "给不出「怎么才能证明它错」，它的通过就不说明什么")
        else:
            after = {r["id"]: r for r in
                     evaluate(claims, cells, railed, unmeasured, override=f)}
            if after[cid]["verdict"] != base[cid]["verdict"]:
                kind, detail = "可翻面", (
                    f"把 {probe} → {base[cid]['verdict']} 变 "
                    f"{after[cid]['verdict']}")
            else:
                kind, detail = "恒真", (
                    f"把 {probe} → 仍然判 {base[cid]['verdict']}，"
                    f"**这条判据对这次单点扰动无感**")
        out.append({"id": cid, "kind": kind,
                    # `不可判定` 是 None：它翻不动的原因是**缺读数**，
                    # 记 False 会跟「恒真」混成同一个数。
                    "flipped": {"可翻面": True, "恒真": False,
                                "已否决": False, "不可判定": None}[kind],
                    "detail": detail})
    return out


def summarize(rows, fals) -> dict:
    """汇总。**刻意不给出任何比率** —— 判不了的几条不是「没通过」。"""
    by_verdict = {v: sum(1 for r in rows if r["verdict"] == v)
                  for v in (PASS_, FAIL_, UNDECIDED)}
    return {
        "total": len(rows),
        "by_verdict": by_verdict,
        "trusted": sum(1 for r in rows if r["trusted"] is True),
        "not_trusted": sum(1 for r in rows if r["trusted"] is False),
        # 判不了的不计进退两边的任何一边。
        "undecided_trusted": by_verdict[UNDECIDED],
        "falsifiable": sum(1 for f in fals if f["kind"] == "可翻面"),
        "vacuous": [f["id"] for f in fals if f["kind"] == "恒真"],
        "not_a_rate": True,
        "note": "判不了的既不算通过也不算否决，所以这里没有分母。",
    }


def _show(v) -> str:
    """读数格子的显示形式。**「没有这一格」和「这一格是空的」必须看得出区别** ——
    同一个道理：本装置里「缺读数」记 `None`，不记 `""`。"""
    if v is None:
        return "—（**读数里没有这一格**）"
    return repr(v)


def render_markdown(rep: dict) -> str:
    L = ["# 裁决留痕（自动生成，别手改）", "",
         f"> 生成时间 **{rep['generated_at']}** · Python {rep['environment']['python']} · "
         f"`cd backend && python -m verification.adjudicate`（{rep['seconds']}s）", "",
         f"> 判的是 **`verification_report.json`** 里那一次运行的读数"
         f"（那份报告生成于 {rep['report']['generated_at']}，"
         f"读数指纹 `{rep['report']['readings_sha256'][:12]}…`）—— **不重跑**。"
         f"**钉的是读数不是文件**：报告重写一遍、数没变，这份产物就没过期。", "",
         "## 这份产物是什么、不是什么", "",
         f"**是**：{rep['what_this_is']}", "",
         f"**不是**：{rep['what_this_is_NOT']}", "",
         f"**它也不证明**：{rep['what_it_does_NOT_prove']}", "",
         f"**哪几条不结实**：{rep['not_solid']}", "",
         "## 逐条", "",
         "| 判据 | 层 | 结果 | 采信 | 读到的读数 |", "|---|---|---|---|---|"]
    for r in rep["rows"]:
        verdict = {PASS_: "√ 通过", FAIL_: "× 否决",
                   UNDECIDED: "○ 不可判定"}[r["verdict"]]
        trust = ("—（判不了）" if r["trusted"] is None
                 else ("采信" if r["trusted"] else
                       "**不采信**（" + "、".join(r["no_trust_because"]) + "）"))
        vals = "、".join(f"{k}={_show(v)}" for k, v in r["values"].items())
        L.append(f"| `{r['id']}` | {r['layer']} | {verdict} | {trust} | {vals} |")

    L += ["", "## 每条判据到底在说什么", ""]
    for r in rep["rows"]:
        L.append(f"### `{r['id']}` · {r['layer']} —— {r['what']}")
        L.append("")
        L.append(f"- 判据：{r['check']}")
        L.append(f"- 结果：**{r['verdict']}**｜{r['detail']}")
        if r["undecidable_because"]:
            L.append(f"- **为什么判不了**：{r['undecidable_because']}")
            L.append(f"- **怎么才能判**：{r['to_make_decidable'] or '（未交代）'}")
        if r["trusted"] is False:
            L.append(f"- 不采信的原因：{'、'.join(r['no_trust_because'])}")
            L.append(f"- 具体是哪些格子贴界：{'、'.join(r['tainted_by_railing']) or '（无）'}")
        if r["why_not_solid"]:
            L.append(f"- 这条本身不结实在哪：{r['why_not_solid']}")
        L.append("")

    L += ["## 判据非空泛性（逐条拿单点扰动试）", "",
          "每条判据都声明了一个 `falsifier`：**一处具名的单点读数改动**。"
          "它必须真的能把这条判据翻面 —— 翻不动的就是**判据恒真**，"
          "它判出来的「通过」什么也不说明。", "",
          "| 判据 | 试的结果 | 明细 |", "|---|---|---|"]
    for f in rep["falsifiers"]:
        mark = {"可翻面": "√ 翻得动", "恒真": "× **恒真**",
                "已否决": "× 已否决（不适用）",
                "不可判定": "—（缺读数）"}[f["kind"]]
        L.append(f"| `{f['id']}` | {mark} | {f['detail']} |")

    s = rep["summary"]
    L += ["", "## 汇总（**不是分数**）", "",
          f"- 共 **{s['total']}** 条判据：通过 **{s['by_verdict'][PASS_]}** · "
          f"否决 **{s['by_verdict'][FAIL_]}** · 不可判定 **{s['by_verdict'][UNDECIDED]}**",
          f"- 采信 **{s['trusted']}** 条 · 不采信 **{s['not_trusted']}** 条 · "
          f"判不了 **{s['undecided_trusted']}** 条（**判不了的不谈采信**）",
          f"- 判据里能拿单点扰动翻面的：**{s['falsifiable']}/{s['total']}**"
          + (f"；恒真的：{s['vacuous']}" if s["vacuous"] else "（没有恒真的）"),
          "",
          f"> **{s['note']}** 「{s['by_verdict'][PASS_]} 条通过」不是 "
          f"「{s['by_verdict'][PASS_]}/{s['total']} 的通过率」—— "
          f"判不了的那 {s['by_verdict'][UNDECIDED]} 条**根本没被判定**，"
          f"不是「没通过」。", ""]
    return "\n".join(L)


def readings_digest(report: dict, *extra) -> str:
    """这批**读数**的指纹 —— 不是报告文件的指纹。

    `verification_report.json` 每跑一次 `run_all` 就会重写，`generated_at`
    必然不同。钉文件 sha 等于「谁再跑一遍谁就红」—— 那是个**假警报**。

    ⚠️ 但这个指纹**也不能**拿来判「产物过没过期」：读数里有物理时钟取样
    （`clock.tick_ns`、`gap_s`、`ticks_ratio`），**每次运行本来就不一样**。
    它记的是「这份产物判的是**哪一批**读数」，给人对照用的；判过期查的是
    **结果表**（`tests/test_adjudicate.py::test_the_artifacts_still_describe_...`）。

    `extra` 同 `cells_from` —— 端到端那份也算进来。**两份报告一起出指纹**：
    只钉住其中一份，另一份换了读数这张表就不会响。
    """
    return readings_digest_of(*cells_from(report, *extra))


def _e2e_provenance(e2e) -> dict:
    """端到端那一路的来路。**「没跑过」和「跑了」都要说得出是哪一种。**

    少了五条断言，读的人必须能一眼看出是「这一层没跑」还是「这张表就这么多」。
    没有这一格，两种情况长得一模一样 —— 那就是把「没测到」伪装成「没有这一项」。
    """
    if not e2e:
        return {"path": E2E_REPORT.name, "present": False,
                "why": "本轮没跑端到端 —— 那一层的断言如实判「不可判定」，"
                       "**不是「没通过」**",
                "to_make_decidable":
                    "cd backend && python -m verification.e2e_stub"}
    entry = (e2e.get("results") or [{}])[0]
    return {"path": E2E_REPORT.name, "present": True,
            "generated_at": e2e.get("generated_at"),
            "arms": entry.get("arms") or [],
            "arms_missing": e2e.get("arms_missing") or [],
            # 替身这件事必须跟着读数走到这里：判据表读的是「真入口脚本跑出来的
            # 计数」，而那个脚本里的模型是替身 —— 换一处理解就是另一回事了。
            "model_is_stub": True,
            "what_it_does_NOT_prove": e2e.get("what_it_does_NOT_prove")}


def readings_digest_of(cells, railed, unmeasured) -> str:
    """`readings_digest` 的正身 —— 只吃**已经抽出来的**读数，不自己再抽一遍。"""
    payload = {
        "cells": {f"{a}.{m}": v for (a, m), v in sorted(cells.items())},
        "railed": {f"{a}.{m}": w for (a, m), w in sorted(railed.items())},
        "unmeasured": {f"{a}.{m}": w for (a, m), w in sorted(unmeasured.items())},
    }
    return _sha(json.dumps(payload, sort_keys=True, ensure_ascii=False))


def run() -> dict:
    t0 = time.time()
    report = load_report()
    e2e = load_e2e_report()
    cells, railed, unmeasured = cells_from(report, e2e)
    rows = evaluate(CLAIMS, cells, railed, unmeasured)
    fals = falsifier_report(CLAIMS, cells, railed, unmeasured, base_rows=rows)
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "not_a_pass_rate": True,
        "what_this_is": CLAIM_SET["what_this_is"],
        "what_this_is_NOT": CLAIM_SET["what_this_is_NOT"],
        "what_it_does_NOT_prove": CLAIM_SET["what_it_does_NOT_prove"],
        "not_solid": CLAIM_SET["not_solid"],
        "environment": {"python": sys.version.split()[0],
                        "platform": platform.platform(), "cwd": "backend/"},
        "script": {"path": "verification/adjudicate.py",
                   "sha256": _sha(pathlib.Path(__file__).read_text(encoding="utf-8"))},
        # 判的是**这一批读数**，所以钉住的是读数本身（不是报告文件 —— 见
        # `readings_digest` 的注释）：读数一改，这份产物就过期。
        "report": {"path": REPORT.name, "generated_at": report.get("generated_at"),
                   "readings_sha256": readings_digest_of(cells, railed, unmeasured)},
        # **端到端那一路在不在，是这份产物要说的一件事。** 「没跑过」和
        # 「跑了、那几条判不了」都合法，但**读的人必须看得出来是哪一种** ——
        # 否则少了五条断言会被读成「这张表就这么多」。
        "e2e_report": _e2e_provenance(e2e),
        "claims_source": {"path": "verification/adjudicate.py",
                          "ids": [c["id"] for c in CLAIMS],
                          "layers": sorted({c["layer"] for c in CLAIMS})},
        "cells_total": len(cells),
        "railed_cells": {f"{a}.{m}": w for (a, m), w in railed.items()},
        "unmeasured_cells": {f"{a}.{m}": w for (a, m), w in unmeasured.items()},
        "rows": rows,
        "falsifiers": fals,
        "summary": summarize(rows, fals),
        "seconds": round(time.time() - t0, 2),
    }


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="把复现读数判成三种结果")
    ap.add_argument("--json", default=str(JS_PATH))
    ap.add_argument("--md", default=str(MD_PATH))
    args = ap.parse_args(argv)

    try:
        rep = run()
    except AdjudicationError as e:
        # **不发 traceback，也不发退出码 1。** 前提不成立（报告不在、判据表缺声明）
        # 是「没测到」，不是「没达到预期」—— 按本装置自己的三种结果，那该是 `2`。
        # 一个把「没跑起来」报成「失败」的装置，不配去要求别人别把「没测到」
        # 折成两边（README「退出码：三种不是两种」）。
        print(f"\n○ 没测到：{e}")
        return 2

    pathlib.Path(args.json).write_text(
        json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    pathlib.Path(args.md).write_text(render_markdown(rep), encoding="utf-8")

    s = rep["summary"]
    print(f"\n→ {args.json}")
    print(f"→ {args.md}")
    print(f"\n共 {s['total']} 条：通过 {s['by_verdict'][PASS_]} · "
          f"否决 {s['by_verdict'][FAIL_]} · 不可判定 {s['by_verdict'][UNDECIDED]}")
    print(f"采信 {s['trusted']} · 不采信 {s['not_trusted']} · 判不了 {s['undecided_trusted']}")
    print(f"能拿单点扰动翻面的：{s['falsifiable']}/{s['total']}"
          + (f"；**恒真的**：{s['vacuous']}" if s["vacuous"] else ""))
    for r in rep["rows"]:
        if r["verdict"] == UNDECIDED:
            print(f"  ○ {r['id']} 判不了：{r['undecidable_because']}")
        elif r["trusted"] is False:
            print(f"  · {r['id']} {r['verdict']}但不采信：{'、'.join(r['no_trust_because'])}")
    bad = [f for f in rep["falsifiers"] if f["kind"] == "恒真"]
    if bad:
        print(f"  × 判据恒真（任何单点扰动都翻不动）：{[f['id'] for f in bad]}")
    print("\n**这不是分数**：判不了的既不算通过也不算否决，所以没有分母。")
    # **有判据恒真就不许退出 0。** 那几条「通过」是恒真的，等于这张表里有一格
    # 是白写的 —— 是发现，得让人看一眼。不发 0 是这张表**自己**不愿意被当成绿的。
    if bad:
        print(f"\n× 有 {len(bad)} 条判据恒真 —— 这套判据里有一部分对这批读数没有"
              f"鉴别力，不按「表是好的」退出。")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
