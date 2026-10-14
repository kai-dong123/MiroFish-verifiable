"""展示层：把两份**已有的产物**并排演给人看。只读、不判定、不重跑。

    python -m verification.viewer        # 在 backend/ 下

## 这是什么

`adjudicate.py` 把读数判成**三种**结果（通过 / 否决 / **不可判定**），`selfproof.py`
证明这套判据对这批读数有鉴别力。两份都存在 `verification/` 下，都是 markdown + json。

**问题**：在 markdown 表和终端里，`√ 通过`、`○ 不可判定`、`不采信` 长得一样 ——
长得一样就等于看不出区别。而这个装置的全部主张就是「**三种结果不许互相折合**」。

本模块把这两份产物渲染成**一个自包含的 HTML**，并且按「一眼能看出重点」排三层：

1. **一句话**：这批有多少条判据、几条翻得动、几条判不了 —— 三个数都从产物里数出来，
   页面自己不算数；
2. **三张等重的卡**：三种结果各占一格，同一个模板、等宽等重等字号，谁也不折进谁；
   底下那条口径带把「没有分母」「贴界」「没量到」摆出来；
3. **逐条判据**：按层分组，行首那道边按结果着色（判不了是**虚的**），
   行内一眼能看到结果、采信、以及这条的 `falsifier`；展开才是它读到的读数。
   五格覆盖、口径（是什么 / 不是什么）在后面。

## 它不做什么

* **不判定、不重跑、不重算**：只读 `adjudication_report.json` 与 `selfproof_report.json`
  里**已经算好的**东西。判据、结果、读数一个都不重来。
* **不发任何请求、不调任何模型**：整页**没有一行 JavaScript**、没有一个外部引用。
  筛选、展开、下钻全部由 HTML `<details>` 与 CSS 完成（报告 §2.3 写着本装置
  「无常驻进程」，所以这里也不是一个服务）。
* **不产生比率**：三态各是一个**独立计数**，页面上不出现「x/y」这种合成。
  判不了的既不算通过也不算否决，所以没有分母 —— 这一句写在页面上（取自产物自己的
  `summary.note`，本文件不另抄）。
* **不落进仓库**：默认写到系统临时目录。`backend/verification/` 下多一个未跟踪文件
  会被 `git status` 看见 —— 本装置不给自己制造噪声。

## 退出码（**三种，不是两种**）

    0   两份产物都读到、HTML 落成，且展示层**自己没发现**任何「折合 / 自相矛盾」
    1   渲染完成了，但**发现了一件事**：某条判「不可判定」的判据，它的 `trusted`
        不是 `None`（三态被折成两态了）；或者两份产物对同一条判据的说法不一致。
        这是**要看的东西**，不是没测到 —— 与 `adjudicate` 用 `1` 报「判据恒真」同构。
    2   **没测到**：输入不在 / 读不出 / 形状不对 / 落点写不进去 —— 一个字都没渲染。

`2` 与 `1` 分开是刻意的，理由与 `run_all` 的 `## 退出码` 那一节逐字相同：
**「没测到」既不是通过，也不是失败。**
"""

from __future__ import annotations

import argparse
import html
import json
import os
import pathlib
import re
import sys
import tempfile

from . import _probe as P
from . import adjudicate as A
from . import selfproof as S

HERE = pathlib.Path(__file__).resolve().parent          # backend/verification

#: 两份**输入**（都入库，所以冷 clone 直接能渲染）。**只读。**
ADJ_JSON = HERE / "adjudication_report.json"
SP_JSON = HERE / "selfproof_report.json"

#: 默认落点**在系统临时目录**：`python -m verification.viewer` 裸跑不留东西在仓库里。
DEFAULT_OUT = pathlib.Path(tempfile.gettempdir()) / "verification_viewer.html"
DEFAULT_TITLE = "可验证性装置 · 展示层（零 JavaScript）"

#: 首屏**之上**那张「上游的毛病 → 装置的解」。**框景文字，与页脚、图例同类**：
#: 交代上游是谁、装置为了对付什么而存在、这一页是那条结论的证据。
#:
#: 三条**与头三条复现层一一对应**，层名从 `A.LAYERS` 取 —— 本文件**不另抄**层名
#: 的字面量（`test_viewer.py` 有一条阴性对照盯着这件事）。
#: **一个数都不写在这里**（切成几百块、膨胀一个数量级、弃权率……）：那些数就在下面
#: 那三层判据的读数栏里，抄第二份迟早只说两种话（同 `FALSIFIER_MARKS` 那条纪律）。
#: 三张卡的编号。只在这一处出现，卡片与正文的指代共用同一个来源。
_NUMS = ("①", "②", "③")

_UPSTREAM = (
    ("记忆容量不足时，上游会把一条长消息拆分为大量碎片后再写入。拆分粒度过细，"
     "导致占用不降反升；而记忆越满、拆分越细，形成正反馈。",
     "把判定收严为「**仅当该消息自身超出容量上限时才拆分**」。"
     "预算紧张的情形应由上下文淘汰处理，而不是拆分新消息。",
     "修复",
     "上游尚未收录该问题，由本装置定位。最小复现 "
     "`upstream/repro_min_01_slicing.py`，不需要 API 密钥，数秒内完成。"),
    ("同一响应中并行的两次工具调用会获得相同的时间戳，使「请求／回执」的配对被打散，"
     "该智能体本轮的全部动作被静默丢弃。上游不报错，仅在日志中留下一行。",
     "为每个智能体引入**严格递增的逻辑时钟**，"
     "使「后写入的时间戳必然更大」成为不变式。",
     "修复",
     "上游尚未收录该问题，由本装置定位。最小复现 "
     "`upstream/repro_min_02_timestamp.py`。"),
    ("**同一输入运行两次会得到不同的人群构成与不同的报告**，即使关闭全部随机性。",
     "**不修复。** 根源在于并发调度的执行次序，不在模型；串行化可以换取确定性，"
     "但会使仿真慢到不可用 —— 这是取舍，不是缺陷。装置对此只给出边界说明。",
     "不修复",
     "上游 **#751、#759** 记录的症状与此一致。"),
)


class ViewerError(Exception):
    """前提不成立（输入不在、形状不对）—— 该退 `2`，不是 `1`。"""


# --------------------------------------------------------------------------
# 一、读与自查形状
# --------------------------------------------------------------------------

def _require(cond, msg: str) -> None:
    if not cond:
        raise ViewerError(msg)


def load(path) -> dict:
    p = pathlib.Path(path)
    if not p.is_file():
        raise ViewerError(f"读不到产物：{p}")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except OSError as e:
        raise ViewerError(f"产物读不出来（{e.__class__.__name__}: {e}）：{p}")
    except json.JSONDecodeError as e:
        raise ViewerError(f"产物不是合法的 JSON（{e}）：{p}")


def check_shape(adj: dict, sp: dict) -> None:
    """形状不对就**别渲染** —— 一张渲染到一半的表比没有表更坏。

    **读什么就核什么。** 这条口径是踩出来的：闸原先只核到「判据行有没有
    `verdict`」，而渲染时还会读 `what` / `check`、falsifier 的 `kind`、用例的
    `moved`。那几格缺了会当场 `KeyError` —— 闸没拦住，异常一路冒到顶，
    退出码成了 `1`，而 `1` 在本模块里的定义是「渲染完成了，而且展示层
    **发现了一件事**」。**「没测到」被报成了「发现了一处折合」** ——
    正是本装置盯着别人的那一族（坏掉的东西恰好长成了另一个合法值的样子）。

    所以：渲染器**直接读**的每一格都得在这里核过；用 `.get()` 读的不核
    （读不到就是「无」，那不是崩）。核不出来的（多出来的键）也不管 ——
    多一个键不是缺陷，少一个键会让整页静默缺一块。
    """
    for key in ("rows", "falsifiers", "summary", "what_this_is",
                "what_this_is_NOT", "what_it_does_NOT_prove", "not_solid",
                "cells_total", "railed_cells", "unmeasured_cells"):
        _require(key in adj, f"裁决产物里没有 `{key}`")
    for key in ("rows", "falsifiers"):
        _require(isinstance(adj[key], list), f"裁决产物的 `{key}` 不是一张表")
    for key in ("total", "by_verdict", "falsifiable", "trusted", "not_trusted",
                "undecided_trusted", "vacuous", "note"):
        _require(key in adj["summary"], f"裁决产物的 summary 里没有 `{key}`")
    for v in (A.PASS_, A.FAIL_, A.UNDECIDED):
        _require(v in adj["summary"]["by_verdict"],
                 f"summary.by_verdict 里没有 `{v}`（三态必须各占一格）")
    for r in adj["rows"]:
        for key in ("id", "layer", "verdict", "trusted", "values", "what", "check"):
            _require(key in r, f"判据行 {r.get('id')!r} 里没有 `{key}`")
        _require(r["verdict"] in (A.PASS_, A.FAIL_, A.UNDECIDED),
                 f"判据 {r['id']} 的结果是 {r['verdict']!r}，不在三态里")
        _require(isinstance(r["values"], dict),
                 f"判据 {r['id']} 的 `values` 不是一张表 —— 读数那一栏是按名读它的")
        # 判据是**按层分组**陈列的：`layer` 不在 `A.LAYERS` 里的那一行
        # 匹配不到任何一组 —— **从页面上静默消失**，而页眉照样报总数。
        # 「静默少一块」比「拒绝渲染」坏（同下面 `moved` 那一条）。
        _require(r["layer"] in A.LAYERS,
                 f"判据 {r['id']} 的层是 {r['layer']!r}，而层只有 {list(A.LAYERS)}")
    for f in adj["falsifiers"]:
        _require("id" in f, "裁决产物里有一条 falsifier 没有 `id`")
        _require("kind" in f, f"falsifier {f['id']!r} 里没有 `kind`")
        # 这里核的**不是**「有没有 `kind`」，是「这个 `kind` 在不在那张表里」——
        # 那张「种类 → 字形」的表只有 `adjudicate` 一份（本文件不另抄，见渲染约定 2），
        # 落到表外的一个种类，到渲染那一刻就是 `KeyError`。
        _require(f["kind"] in A.FALSIFIER_MARKS,
                 f"falsifier {f['id']!r} 的种类 {f['kind']!r} 不在 "
                 "`adjudicate.FALSIFIER_MARKS` 那张表里")
    for key in ("base", "cases", "meta"):
        _require(key in sp, f"自证产物里没有 `{key}`")
    for key in ("base", "cases"):
        _require(isinstance(sp[key], list), f"自证产物的 `{key}` 不是一张表")
    for key in ("grids_seen", "grids_required", "grids_missing", "cases_ok", "all_ok"):
        _require(key in sp["meta"], f"自证产物的 meta 里没有 `{key}`")
    for b in sp["base"]:
        for key in ("id", "verdict", "trusted"):
            _require(key in b, f"自证 base 里的 {b.get('id')!r} 没有 `{key}`")
        # 两份产物要逐条对得上（`findings`）。凭空一个不在三态里的值，
        # 会让对账**凭空翻脸**：那条「不一致」是产物坏了，不是两边真说了两样话。
        _require(b["verdict"] in (A.PASS_, A.FAIL_, A.UNDECIDED),
                 f"自证 base 里 {b['id']} 的结果是 {b['verdict']!r}，不在三态里")
    for c in sp["cases"]:
        for key in ("id", "layer", "moved"):
            _require(key in c, f"自证用例 {c.get('id')!r} 里没有 `{key}`")
        _require(isinstance(c["moved"], dict),
                 f"用例 {c['id']} 的 `moved` 不是一张表")
        # 用例是**按「它落到了哪一格」分组**的：`moved` 空着、或指到一个不存在的格，
        # 这一例就匹配不到任何一格 —— **从页面上静默消失**，而页眉照样报总数
        # （那个数取自 `cases` 的长度，不是渲染出来的条数）。「静默少一块」
        # 比「拒绝渲染」坏，所以这两件事都算形状不对。
        _require(c["moved"], f"用例 {c['id']} 的 `moved` 是空的 —— 它会从页面上静默消失")
        for v in c["moved"].values():
            _require(v in S.GRIDS,
                     f"用例 {c['id']} 说它落到了 {v!r}，而五格是 {list(S.GRIDS)}")


def findings(adj: dict, sp: dict) -> list[str]:
    """展示层**自己**看出来的两件事。空表 = 没看出问题（退 `0`）。

    这不是「再判一遍」—— 只是把已经算好的两份产物摆到一起，看有没有**自相矛盾**。
    """
    out = []
    for r in adj["rows"]:
        # 三态被折成两态的签名：判「不可判定」却给了个采信值。
        if r["verdict"] == A.UNDECIDED and r["trusted"] is not None:
            out.append(f"`{r['id']}` 判「{A.UNDECIDED}」却带着 `trusted={r['trusted']!r}` —— "
                       "三态被折成两态了")
    left = {r["id"]: (r["verdict"], r["trusted"]) for r in adj["rows"]}
    right = {b["id"]: (b["verdict"], b["trusted"]) for b in sp["base"]}
    for cid in sorted(set(left) & set(right)):
        if left[cid] != right[cid]:
            out.append(f"`{cid}` 两份产物说法不一致：裁决 {left[cid]} · 自证 {right[cid]}")
    return out


# --------------------------------------------------------------------------
# 二、渲染成 HTML（**零 JavaScript**）
# --------------------------------------------------------------------------
#
# 三个渲染约定，逐条对应一条纪律：
#
# 1. **先转义、再做行内变换。** 产物里的字符串可能带 `<script>`，而
#    `FALSIFIER_MARKS` 的取值本身带 markdown（`× **恒真**`）、`_show()` 也带
#    （`—（**读数里没有这一格**）`）。顺序反了就是注入，顺序对了就是排版。
# 2. **三态的字形与标签只写一处。** `FALSIFIER_MARKS` / `GRIDS` / 三个结果常量
#    一律从 `adjudicate` / `selfproof` 取，本文件不另抄一份 ——
#    `selfproof.py` 就因为另抄了一张表，在 Linux 上 `KeyError` 过一次（报告 §7.5）。
# 3. **`trusted is None` 走第三路。** 判不了**不是**不采信。写 `False` 会让
#    「不采信」虚高，写 `True` 又等于说它可信 —— 同 `adjudicate` 第 28-30 行。

#: 结果 → 字形。**键是 `adjudicate` 的三个常量**，改一个名字这里就当场 KeyError。
_GLYPH = {A.PASS_: "√", A.FAIL_: "×", A.UNDECIDED: "○"}

_CSS = """
:root{--fg:#17191d;--dim:#666c76;--bg:#f4f4f0;--card:#fff;--line:#e3e3dc;--line2:#cbcbc1;
  --ink:#12141a;--pass:#1f6b3a;--fail:#a12a2a;--undec:#6a707a;--rail:#8a5a00}
*{box-sizing:border-box}
body{margin:0 auto;padding:2.3rem 1.6rem 5rem;max-width:76rem;
  font:15.5px/1.68 -apple-system,"Segoe UI","Microsoft YaHei",system-ui,sans-serif;
  color:var(--fg);background:var(--bg)}
h1{font-size:1.95rem;line-height:1.3;margin:0 0 .5rem;letter-spacing:-.015em}
h2{font-size:1.08rem;margin:2.9rem 0 .9rem;padding-bottom:.34rem;border-bottom:2px solid var(--ink)}
h3{font-size:.88rem;font-weight:600;margin:1.1rem 0 .2rem;color:var(--fg)}
p{margin:.45rem 0}
code{background:#ecebe4;border:1px solid #e0dfd6;border-radius:4px;padding:.02em .32em;
  font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:.88em;word-break:break-word}
strong{font-weight:650}
.dim{color:var(--dim)}
.chip{font-size:.78rem;border:1px solid var(--line2);border-radius:999px;padding:0 .4rem;
  color:var(--dim);white-space:nowrap}

/* --- 首屏之上：这一页在讲什么（上游是谁、装置解决了什么） --- */
.anchor{background:var(--card);border:1px solid var(--line);border-radius:14px;
  padding:1.4rem 1.7rem 1.2rem;margin:0 0 1.1rem}
.anchor p{margin:.5rem 0}
.anchor .kicker{font-size:.8rem;letter-spacing:.08em;color:var(--dim);margin:0}
.issues{display:grid;grid-template-columns:1fr;gap:.55rem;margin:.85rem 0 .5rem}
.issue{border:1px solid var(--line);border-radius:10px;padding:.6rem .85rem;background:var(--bg)}
.issue p{margin:.22rem 0}
.issue .bad{font-weight:600}
.issue .fix{margin-top:.42rem;padding:.32rem .6rem;background:var(--card);
  border-left:3px solid var(--ink);border-radius:0 6px 6px 0}
.issue .lay{font-size:.83rem;color:var(--dim);margin-top:.34rem}
.issue .src{font-size:.83rem;color:var(--dim);margin-top:.2rem;border-top:1px dashed var(--line);padding-top:.28rem}

/* --- 首屏：先给结论 --- */
.hero{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:1.5rem 1.7rem 1.15rem}
.kicker{font-size:.8rem;letter-spacing:.08em;color:var(--dim);margin:0}
.lede{font-size:1.06rem;line-height:1.6;margin:.6rem 0 0;max-width:58rem}
.hint{font-size:.95rem;margin:.75rem 0 0;background:#fbf7ec;border:1px solid #e8dfc6;
  border-radius:9px;padding:.5rem .75rem}
.src{font-size:.83rem;color:var(--dim);margin:1rem 0 0;padding-top:.7rem;
  border-top:1px dashed var(--line2)}

/* --- 三张等重的卡：同一个模板，只有字形／名字／计数／那句话不同 --- */
.states{display:grid;grid-template-columns:repeat(3,1fr);gap:.8rem;margin:1.1rem 0 .9rem}
.state{background:var(--card);border:1px solid var(--line);border-top:4px solid var(--ink);
  border-radius:12px;padding:1rem 1rem .95rem;text-align:center}
.states .state:nth-child(1){border-top-color:var(--pass)}
.states .state:nth-child(2){border-top-color:var(--fail)}
.states .state:nth-child(3){border-top-color:var(--undec)}
.state .g{font-size:1.05rem;color:var(--dim);margin-right:.25rem}
.state .t{font-size:1.05rem;font-weight:600}
.state .n{display:block;font-size:2.6rem;line-height:1.05;font-weight:700;
  font-variant-numeric:tabular-nums;margin:.1rem 0 .25rem}
.states .state:nth-child(1) .n{color:var(--pass)}
.states .state:nth-child(2) .n{color:var(--fail)}
.states .state:nth-child(3) .n{color:var(--undec)}
.state .sub{display:block;font-size:.84rem;color:var(--dim)}

/* --- 口径带：产物自己的那句话 + 这批读数的三个总量 --- */
.callout{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--ink);
  border-radius:10px;padding:.9rem 1.15rem;margin:.2rem 0 .3rem}
.callout p{margin:.32rem 0}
.callout .big{font-size:1.04rem;font-weight:600}

/* --- 筛选：全 CSS，无 JS --- */
.filters{display:flex;flex-wrap:wrap;gap:.45rem 1.5rem;align-items:center;margin:.6rem 0 .25rem}
.fgroup{display:flex;flex-wrap:wrap;gap:.35rem;align-items:center}
.flabel{font-size:.85rem;color:var(--dim);margin-right:.2rem}
.filters input{position:absolute;left:-9999px;width:0;height:0}
.filters label{border:1px solid var(--line2);border-radius:999px;padding:.12rem .62rem;
  cursor:pointer;font-size:.87rem;background:var(--card);user-select:none}
.filters input:checked + label{background:var(--ink);color:#fff;border-color:var(--ink)}
.filters input:focus-visible + label{outline:2px solid #2a6;outline-offset:1px}
body:has(#vf-1:checked) .claim:not([data-verdict="__V1__"]){display:none}
body:has(#vf-2:checked) .claim:not([data-verdict="__V2__"]){display:none}
body:has(#vf-3:checked) .claim:not([data-verdict="__V3__"]){display:none}
__LAYER_RULES__

/* --- 逐条判据：按层分组，一组一抬头 --- */
.group{margin:.2rem 0 1rem}
.ghead{font-size:.9rem;font-weight:650;color:var(--fg);margin:.95rem 0 .35rem}
.ghead .gt{font-weight:400;color:var(--dim);border-left:1px solid var(--line2);
  margin-left:.55rem;padding-left:.55rem}
.gempty{font-size:.88rem;color:var(--dim);margin:.15rem 0 .4rem}
.claim{border:1px solid var(--line);border-left-width:4px;border-left-color:var(--line2);
  border-radius:9px;background:var(--card);margin:.28rem 0}
.claim[data-verdict="__V1__"]{border-left-color:var(--pass)}
.claim[data-verdict="__V2__"]{border-left-color:var(--fail)}
.claim[data-verdict="__V3__"]{border-left-color:var(--undec);border-left-style:dashed}
.claim>summary{cursor:pointer;padding:.5rem .8rem;display:grid;
  grid-template-columns:max-content max-content max-content;
  gap:.15rem .7rem;align-items:baseline;justify-content:start}
.claim>summary:hover{background:#faf9f5}
.claim[open]>summary{border-bottom:1px solid var(--line);background:#faf9f5}
.cid{font-weight:700;font-family:ui-monospace,Consolas,monospace;font-size:.95rem;min-width:2.2rem}
.cv{font-weight:600;min-width:5.4rem}
.ctrust{font-size:.84rem}
.cfals{grid-column:1/-1;font-size:.83rem;color:var(--dim)}
.cwhat{grid-column:1/-1;font-weight:600;font-size:.98rem;line-height:1.5;margin-top:.1rem}
/* --- 采信那格：三路各一形状（虚框=缺读数） --- */
.t-true{border:1px solid #9ccdb2;background:#f2faf5;color:#1d6b42;border-radius:999px;padding:0 .45rem}
.t-false{border:1px solid #e0bd7c;background:#fdf7ea;color:var(--rail);border-radius:999px;padding:0 .45rem}
.t-none{border:1px dashed var(--line2);color:var(--dim);border-radius:999px;padding:0 .45rem}
/* --- 展开之后：判据原文、读数、以及那几条附注 --- */
.cbody{padding:.5rem .85rem .75rem}
.cbody p{margin:.4rem 0}
.cbody dl{margin:.5rem 0;padding:.45rem 0;display:grid;grid-template-columns:max-content 1fr;
  gap:.15rem .8rem;border-top:1px dotted var(--line2);border-bottom:1px dotted var(--line2)}
.cbody dt{font-family:ui-monospace,Consolas,monospace;font-size:.87rem;color:var(--dim);
  display:flex;gap:.3rem;align-items:baseline}
.cbody dd{margin:0;font-variant-numeric:tabular-nums}
.warn{border-left:3px solid #e0bd7c;background:#fdf9ef;border-radius:6px;padding:.5rem .75rem;margin:.5rem 0}
.warn p{margin:.22rem 0}

/* --- 五格：一个 <details> 一格 --- */
.grid{border:1px solid var(--line);border-radius:9px;background:var(--card);margin:.28rem 0}
.grid>summary{cursor:pointer;padding:.5rem .8rem;font-weight:600}
.grid .body{padding:.35rem .85rem .65rem}
.dead{color:var(--fail);font-weight:600}
.case{border-top:1px dotted var(--line2);padding:.35rem 0}
.case b{font-family:ui-monospace,Consolas,monospace}

/* --- 末尾：是什么／不是什么、怎么读 --- */
.policy{background:var(--card);border:1px solid var(--line);border-radius:12px;
  padding:.5rem 1.15rem 1rem;margin:.4rem 0}
.policy h3.no{color:var(--fail)}
.policy h3+ p{margin-top:.15rem}
footer{margin-top:2.8rem;border-top:1px solid var(--line2);padding-top:.8rem;
  font-size:.85rem;color:var(--dim)}
"""


def _esc(s) -> str:
    return html.escape(str(s), quote=True)


def _md(s) -> str:
    """先转义，再认**两种**行内 markdown。别的一概不动。"""
    t = _esc(s)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    return t


def _verdict_cell(verdict: str) -> str:
    """`○ 不可判定` 这样的一格。**三态同一套写法**，谁也不比谁显眼。"""
    return f'<span class="cv">{_GLYPH[verdict]} {_esc(verdict)}</span>'


def _trust_cell(trusted, no_trust_because) -> str:
    """采信那一格。**判不了走第三路**，不许折成「不采信」。"""
    if trusted is None:
        return '<span class="ctrust t-none">— 判不了（<strong>不是「不采信」</strong>）</span>'
    if trusted is True:
        return '<span class="ctrust t-true">采信</span>'
    why = "、".join(no_trust_because or [])
    return f'<span class="ctrust t-false"><strong>不采信</strong>（{_esc(why)}）</span>'


def _falsifier_cell(f: dict | None) -> str:
    """行内那一格：这条判据的 `falsifier` 是什么、试的结果如何。

    `FALSIFIER_MARKS` 从 `adjudicate` 取（**不另抄**）。
    """
    if f is None:
        return '<span class="cfals">falsifier：—（没有这一条）</span>'
    mark = A.FALSIFIER_MARKS[f["kind"]]
    return f'<span class="cfals">falsifier：{_md(mark)} · {_md(f.get("detail") or "")}</span>'


# --------------------------------------------------------------------------
# 二之零、首屏**之上**：上游是谁、装置解决了什么、这一页是哪条结论的证据
# --------------------------------------------------------------------------

def _what_this_solves() -> str:
    """先把「上游的缺陷 → 处置」**一对一对**摆出来，再谈判据。

    这一节是整页的锚：**开头就把最核心的事说掉** —— 在上游定位到两个会静默
    损坏产物的缺陷，每个配一份可独立复现的最小用例、和一处不改动上游依赖的修法。
    **一个缺陷紧跟它的处置**，不把所有缺陷写完再一起给处置。
    **措辞按正式书面语写**（面向评委与外部使用者），同时避免「守卫」「token」这类术语。
    三张卡**逐条对应头三层复现**（层名从 `A.LAYERS` 取，不另抄字面量）。
    **出处如实标**：第三张卡上游确有编号（`#751`／`#759`，且是**边界不是修复**，
    正文里另说）；前两张由本装置定位，上游没有 —— 就地写明「尚未收录」
    并给出可复现的最小用例。
    **数字一律不写**：读数在下面各层的行里，这里只讲「缺陷是什么、如何处置」。
    """
    cards = []
    for i, (bad, fix, kind, src) in enumerate(_UPSTREAM):
        cards.append(
            '<div class="issue">'
            f'<p class="bad"><strong>问题 {_NUMS[i]}</strong>　{_md(bad)}</p>'
            f'<p class="fix">处置：{_md(fix)}'
            f' <span class="chip">{_esc(kind)}</span></p>'
            f'<p class="lay">证据：见下面「<code>{_esc(A.LAYERS[i])}</code>」一组。</p>'
            f'<p class="src">来源：{_md(src)}</p>'
            "</div>")
    return (
        '<div class="anchor">'
        '<p class="kicker">上游 · MiroFish</p>'
        "<p><strong>MiroFish</strong> 是一个群体智能仿真引擎：输入一段事件描述，"
        "它驱动大量具备人格与记忆的智能体进行推演，最终输出一份形式完整的预测报告。"
        "它的缺陷具有同一类特征 —— <strong>不抛异常、不中断仿真</strong>，"
        "只让产物显得更完整、更像结论，因此更难被使用者察觉。</p>"
        "<p>本作品在 MiroFish 之上构建一层可验证性装置，"
        "<strong>在上游定位到两个此类缺陷，并为每一个提供可独立复现的最小用例与一处修法</strong>。"
        "缺陷是否真实存在，可依据最小复现自行验证：</p>"
        '<div class="issues">' + "".join(cards) + "</div>"
        "<p>两处修复均<strong>不改动上游依赖库</strong>，而是在 MiroFish 自身的驱动脚本外"
        "包裹一层运行时保护，<strong>默认不启用</strong>，"
        "不启用时行为与上游逐字一致。另需说明："
        "问题 ② 由问题 ① 的修复引入 —— 记忆切片修复后写入变快，"
        "原本不会落在同一刻度内的两次写入开始发生冲突，"
        "因此两处保护必须<strong>可独立开关</strong>。</p>"
        '<p class="dim">本页由装置已有的两份产物（裁决与自证）渲染而成。'
        "以下各节是<strong>上述缺陷确实存在、修复确实生效</strong>的证据；"
        "末节说明这些证据凭什么可信。"
        "最后一组（" + _esc(A.LAYERS[-1]) + "）不是缺陷，"
        "用于证明两处保护已被真实流量触达。</p>"
        "</div>")


# --------------------------------------------------------------------------
# 二之一、首屏：一句话 + 三张等重的卡 + 一条口径带
# --------------------------------------------------------------------------

def _state_cards(adj: dict) -> str:
    """三种结果各占一格。**同一个模板**，只有字形／名字／计数／底下那句话不同。

    三个计数一律取自产物自己的 `summary`，本页不重数。底下那句是**口径**不是数：
    「读数让它成立」说的是这批读数对这条判据做了什么，不是它的质量。
    """
    by = adj["summary"]["by_verdict"]
    subs = {
        A.PASS_: "本批读数使其成立",
        A.FAIL_: "本批读数使其不成立",
        A.UNDECIDED: f"缺读数 —— 不是「{A.FAIL_}」",
    }
    cells = "".join(
        f'<div class="state"><span class="g">{_GLYPH[v]}</span>'
        f'<span class="t">{_esc(v)}</span>'
        f'<span class="n">{by[v]}</span>'
        f'<span class="sub">{_esc(subs[v]) if by[v] else "本批一条都没有"}</span></div>'
        for v in (A.PASS_, A.FAIL_, A.UNDECIDED))
    return f'<div class="states">{cells}</div>'


def _callout(adj: dict) -> str:
    """口径带：**产物自己那句话**（没有分母）+ 这批读数的三个总量。

    「没有分母」这一句是从 `summary.note` 取的，本文件不另抄一份措辞 ——
    同一个意思抄两份，迟早只说两种话（`selfproof.py` 在 Linux 上就那么栽过）。
    """
    s = adj["summary"]
    railed, unmeasured = len(adj["railed_cells"]), len(adj["unmeasured_cells"])
    vac = s["vacuous"]
    vacuous = (f'判据<strong>恒真</strong> {len(vac)} 条（{_esc("、".join(vac))}）—— 恒真 = 给不出 '
               "falsifier，由机器判定，不是自行声明"
               if vac else "判据<strong>恒真 0 条</strong>（给不出 falsifier 的会被机器判成恒真）")
    return (
        '<div class="callout">'
        f'<p class="big">{_md(s["note"])}</p>'
        f'<p>本批共使用 <strong>{adj["cells_total"]}</strong> 格读数：'
        f'<strong>{railed}</strong> 格<strong>贴界</strong>'
        "（已量到，但落在边界上、分不出差别）、"
        f'<strong>{unmeasured}</strong> 格<strong>没量到</strong>。'
        "贴界即降级 —— 结论仍然成立，但<strong>不予采信</strong>。</p>"
        f'<p>采信栏：采信 <strong>{s["trusted"]}</strong> · '
        f'不采信 <strong>{s["not_trusted"]}</strong> · '
        f'判不了 <strong>{s["undecided_trusted"]}</strong> —— '
        "<strong>判不了不是「不采信」</strong>。</p>"
        f'<p>{vacuous}。</p>'
        "</div>")


def _hero(adj: dict, sp: dict, title: str) -> str:
    """首屏：**先给结论**。三个数从产物里数出来，一个都不写死。"""
    s = adj["summary"]
    by, rep = s["by_verdict"], (adj.get("report") or {})
    undec = [r["id"] for r in adj["rows"] if r["verdict"] == A.UNDECIDED]
    hint = ("本批没有一条判不了 —— 三态中的第三格为空，并非不存在这一格。"
            if not undec else
            f"本批有 <strong>{len(undec)}</strong> 条<strong>判不了</strong>：不是"
            f"「{A.FAIL_}」，而是<strong>没量到</strong>。缺的是哪一格读数，展开以下各行可查："
            + "、".join(f"<code>{_esc(i)}</code>" for i in undec) + "。")
    return (
        '<div class="hero">'
        f'<p class="kicker">{_esc(title)}</p>'
        f'<h1>{s["total"]} 条判据：{s["falsifiable"]} 条翻得动，'
        f'{by[A.UNDECIDED]} 条判不了</h1>'
        f'<p class="lede">{_md(adj["what_this_is"])}'
        "「翻得动」＝ 修改一处单点读数即可将其翻转为「否决」—— "
        "这一步由机器核对，不是本页的声明。</p>"
        f'<p class="hint">{hint}</p>'
        f'<p class="src">来源：裁决产物生成于 {_esc(adj.get("generated_at") or "—")}'
        + (f'，判的是读数指纹 <code>{_esc(rep["readings_sha256"][:12])}…</code>'
           if rep.get("readings_sha256") else "")
        + f' ｜ 自证产物生成于 {_esc(sp.get("generated_at") or "—")}。'
        "两份都是<strong>既有产物</strong> —— 本页<strong>不重跑任何东西</strong>。</p>"
        "</div>")


# --------------------------------------------------------------------------
# 二之二、逐条判据：按层分组，一行一条
# --------------------------------------------------------------------------

def _claim_row(r: dict, f: dict | None, railed: dict) -> str:
    """一条判据：`<details>` 一行。行内那一段就是「结果 + 采信 + falsifier + 它说什么」。

    ⚠️ 开头这几行的形状被 `tests/test_viewer.py` 的 `_CLAIM_HEAD` 钉着
    （`<details class="claim" …><summary><span class="cid">`，中间不许有别的东西）——
    改这里先看那条判据。
    """
    val_rows = []
    operands = list(r.get("operands") or [])
    order = operands + [k for k in r["values"] if k not in operands]
    tainted = set(r.get("tainted_by_railing") or [])
    for k in order:
        chip = '<span class="chip">贴界</span>' if k in tainted else ""
        val_rows.append(f'<dt><span>{_esc(k)}</span>{chip}</dt>'
                        f'<dd>{_md(A._show(r["values"].get(k)))}</dd>')

    extra = ""
    if r.get("undecidable_because") or r.get("to_make_decidable"):
        extra += ('<div class="warn">'
                  f'<p><strong>为什么判不了</strong>：{_md(r.get("undecidable_because") or "（未交代）")}</p>'
                  f'<p><strong>怎么才能判</strong>：{_md(r.get("to_make_decidable") or "（未交代）")}</p>'
                  "</div>")
    if r.get("trusted") is False:
        extra += (f'<p class="dim"><strong>不采信的原因</strong>：'
                  f'{_esc("、".join(r.get("no_trust_because") or []))}</p>')
        for k in (r.get("tainted_by_railing") or []):
            if k in railed:
                extra += (f'<p class="dim">贴界的格子 <code>{_esc(k)}</code>：'
                          f'{_md(railed[k])}</p>')
    if r.get("why_not_solid"):
        extra += (f'<p class="dim"><strong>该条判据的薄弱之处</strong>：'
                  f'{_md(r["why_not_solid"])}</p>')

    # 印出来的结果**就取产物里的那一个**：属性那格与行内那格都印它，三态各印各的。
    # 这一步看着多余（`vshow` 就是 `r["verdict"]`），但它把「最后一米不许折合」
    # 摆成一处看得见的代码 —— 变异 `W1` 捅的正是这一行。
    vshow = r["verdict"]
    return (
        f'<details class="claim" data-verdict="{_esc(vshow)}" '
        f'data-layer="{_esc(r["layer"])}">'
        f'<summary><span class="cid">{_esc(r["id"])}</span>'
        f'{_verdict_cell(vshow)}'
        f'{_trust_cell(r["trusted"], r.get("no_trust_because"))}'
        f'<span class="cwhat">{_md(r["what"])}</span>'
        f'{_falsifier_cell(f)}</summary>'
        f'<div class="cbody">'
        f'<p>判据：{_md(r["check"])}</p>'
        f'<dl>{"".join(val_rows)}</dl>'
        f'{extra}'
        f"</div></details>")


def _claims_section(adj: dict) -> str:
    """15 条按层分组陈列。层与层的顺序取自 `adjudicate.LAYERS`（**不另抄**）。

    分组不只是好看：结果是**按层分布的**（哪一层量得粗、哪一层根本没量到），
    平铺成一大片就把这件事埋掉了。某一层这批里没有判据，也**照实说出来** ——
    空着不说话，读者会以为是自己没找到。
    """
    fals = {f["id"]: f for f in adj["falsifiers"]}
    railed = adj["railed_cells"]
    groups = []
    for l in A.LAYERS:
        rows = [r for r in adj["rows"] if r["layer"] == l]
        n = {v: sum(1 for r in rows if r["verdict"] == v)
             for v in (A.PASS_, A.FAIL_, A.UNDECIDED)}
        counts = " · ".join(f"{_GLYPH[v]} {n[v]}" for v in (A.PASS_, A.FAIL_, A.UNDECIDED) if n[v])
        head = (f'<p class="ghead">{_esc(l)}'
                f'<span class="gt">本层 {len(rows)} 条</span>'
                + (f'<span class="gt">{counts}</span>' if counts else "")
                + "</p>")
        body = ("".join(_claim_row(r, fals.get(r["id"]), railed) for r in rows)
                or '<p class="gempty">本层在这一批里没有判据 —— 此处为空，并非未找到。</p>')
        groups.append(f'<div class="group" data-layer="{_esc(l)}">{head}{body}</div>')
    return "\n".join(groups)


# --------------------------------------------------------------------------
# 二之三、五格覆盖、口径与页脚
# --------------------------------------------------------------------------

def _grids_section(sp: dict) -> str:
    seen = set(sp["meta"]["grids_seen"])
    out = []
    shown = 0
    for g in S.GRIDS:
        cases = [c for c in sp["cases"] if g in (c.get("moved") or {}).values()]
        shown += len(cases)
        dead = "" if g in seen else ' <span class="dead">× 死格（这批里没出现过）</span>'
        body = []
        for c in cases:
            edited = "、".join(f"{k}→{v}" for k, v in (c.get("edit") or {}).items()) \
                or "、".join(f"撤掉 {k} 的贴界声明" for k in (c.get("unrail") or [])) \
                or "、".join(f"{k} 改标未测量" for k in (c.get("unmeasured") or {})) \
                or ("改判据原文：" + "、".join(c.get("claims_amended") or [])) or "（无）"
            moved = "、".join(f"{k}→{v}" for k, v in (c["moved"] or {}).items()) or "（无）"
            keep = "、".join(_esc(i) for i in (c.get("untouched") or []))
            body.append(
                f'<div class="case"><p><b>{_esc(c["id"])}</b>（{_esc(c["layer"])}）—— '
                f'{_md(c.get("why") or "")}</p>'
                f'<p class="dim">动了什么：{_esc(edited)}</p>'
                f'<p>该动的动了：{_esc(moved)}</p>'
                f'<p class="dim">不该动的没动（{len(c.get("untouched") or [])} 条，各自仍在 base 那一格）：'
                f'{keep}</p></div>')
        out.append(
            f'<details class="grid"><summary>{_esc(g)} · {len(cases)} 例{dead}</summary>'
            f'<div class="body">{"".join(body) or "<p>（这一格没有用例走到 —— 那就是死格）</p>"}'
            f"</div></details>")
    m = sp["meta"]
    total = len(sp["cases"])
    # **不写「15/15」** —— 这个页面自己的规矩是「不合成比率」。相符的例数与总例数
    # 各说各的，用「全相符 / 有几例不符」表述，不用斜杠把两个数连起来。
    if m["cases_ok"] == total:
        saying = f"逐例表态 <strong>全相符</strong>（{total} 例）"
    else:
        saying = (f"逐例表态：{m['cases_ok']} 例相符、"
                  f"{total - m['cases_ok']} 例<b class=\"dead\">不符</b>（共 {total} 例）")
    # **一例可以落两格**（它同时动了两个断言），于是**条目数会多于例数**：
    # 这批里是 `P2`（`B1` 与 `B2` 各变一格）。两个数各是各的，页面上把**两句都说出来** ——
    # 否则读者拿下面数出来的条目去对上面那个「（N 例）」，就会读出一个不存在的不一致
    # （同族的毛病：一个数被当成了另一个数）。
    if shown != total:
        multi = "、".join(c["id"] for c in sp["cases"]
                          if len([g for g in S.GRIDS if g in c["moved"].values()]) > 1)
        saying += (f"；下面<strong>按格陈列</strong>共 <strong>{shown}</strong> 条 —— "
                   f"比上面多出的 {shown - total} 条，是<strong>一例同时落了两格</strong>"
                   f"（{_esc(multi)} 同时动了两个断言）。"
                   "<strong>条目数与例数是两个数，不是一回事</strong>")
    head = (f'<p>五格：{_esc("、".join(m["grids_required"]))}。'
            f'出现过 <strong>{len(m["grids_seen"])}</strong> 格'
            + (f'，缺 <span class="dead">{_esc("、".join(m["grids_missing"]))}</span>'
               if m["grids_missing"] else "（<strong>五格全到过</strong>）")
            + f'。{saying}。</p>')
    return head + "\n".join(out)


def _policy(adj: dict) -> str:
    """末尾两节：这份页面对应的是什么／不是什么；这一页怎么读。"""
    return (
        "<h2>本页说明什么、不说明什么</h2>"
        '<div class="policy">'
        f'<h3>本页说明</h3><p>{_md(adj["what_this_is"])}</p>'
        f'<h3 class="no">本页不说明</h3><p>{_md(adj["what_this_is_NOT"])}</p>'
        f'<h3 class="no">本页也不证明</h3><p>{_md(adj["what_it_does_NOT_prove"])}</p>'
        f'<h3 class="no">哪几条判据不够扎实</h3><p>{_md(adj["not_solid"])}</p>'
        "</div>"
        "<h2>怎么读这一页</h2>"
        '<div class="policy">'
        f'<p>结果一栏只有三种写法：<code>{_GLYPH[A.PASS_]}</code> 成立、'
        f'<code>{_GLYPH[A.FAIL_]}</code> 不成立、'
        f'<code>{_GLYPH[A.UNDECIDED]}</code> <strong>缺读数，判不了</strong> —— '
        "判不了的<strong>既不算通过也不算否决</strong>：它的读数栏写的是"
        "「读数里没有这一格」，行首那道边为<strong>虚线</strong>。</p>"
        "<p>采信与结果<strong>分列两栏</strong>：一条「通过」可以是<strong>不采信</strong>的"
        "（读数贴界，分不出差别）；判不了的<strong>不谈采信</strong> —— "
        '它那一栏是「判不了」，<strong>不是「不采信」</strong>。</p>'
        "<p>每行行内那句 falsifier 印的是<strong>实测结果</strong>"
        "（以一处单点读数翻转该条判据，是否翻得动），不是自行声明。</p>"
        "</div>"
        "<footer>本页由 <code>verification/viewer.py</code> 从两份入库产物渲染，"
        "整页<strong>没有一行 JavaScript、没有一个外部引用</strong>；不判定、不重跑、不发任何请求。"
        "它是<strong>展示层</strong>，不是装置的一部分。</footer>")


def render_html(adj: dict, sp: dict, title: str) -> str:
    css = (_CSS.replace("__V1__", A.PASS_).replace("__V2__", A.FAIL_).replace("__V3__", A.UNDECIDED))
    # 层轴隐藏的是**整组**（组头跟着走），结果轴隐藏的是行 ——
    # 两轴叠加时互不干扰，而且规则条数不变（一条一层）。
    layer_rules = "\n".join(
        f'body:has(#lf-{i}:checked) .group:not([data-layer="{_esc(l)}"]){{display:none}}'
        for i, l in enumerate(A.LAYERS, start=1))
    css = css.replace("__LAYER_RULES__", layer_rules)

    vradios = "".join(
        f'<input type="radio" name="v" id="vf-{i}"{" checked" if i == 0 else ""}>'
        f'<label for="vf-{i}">{_esc(text)}</label>'
        for i, text in enumerate(["全部"] + [A.PASS_, A.FAIL_, A.UNDECIDED]))
    lradios = "".join(
        f'<input type="radio" name="l" id="lf-{i}"{" checked" if i == 0 else ""}>'
        f'<label for="lf-{i}">{_esc(text)}</label>'
        for i, text in enumerate(["全部"] + list(A.LAYERS)))
    nav = (f'<div class="filters"><span class="fgroup"><span class="flabel">结果</span>{vradios}</span>'
           f'<span class="fgroup"><span class="flabel">层</span>{lradios}</span></div>'
           '<p class="dim">筛选只改变<strong>显示</strong>，不影响计数。'
           "点击任意一行可展开：判据原文、它读到的读数、以及该条判据本身的薄弱之处。"
           "（筛选由 CSS <code>:has()</code> 完成；浏览器不支持时<strong>全部照常显示</strong>，"
           "内容不减少。）</p>")

    return (
        '<!doctype html>\n<html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{_esc(title)}</title><style>{css}</style></head><body>'
        f'{_what_this_solves()}'
        f'{_hero(adj, sp, title)}'
        f'<h2>三态：三个计数，各是各的</h2>{_state_cards(adj)}{_callout(adj)}'
        f'<h2>逐条判据（{len(adj["rows"])} 条）</h2>{nav}{_claims_section(adj)}'
        f'<h2>反例自证：五格覆盖</h2>{_grids_section(sp)}'
        f'{_policy(adj)}</body></html>\n')


# --------------------------------------------------------------------------
# 三、入口
# --------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="把两份产物渲染成一个自包含的展示页（零 JavaScript，只读）")
    ap.add_argument("--adj", default=str(ADJ_JSON), help="裁决产物（只读）")
    ap.add_argument("--sp", default=str(SP_JSON), help="自证产物（只读）")
    ap.add_argument("--out", default=str(DEFAULT_OUT),
                    help="写到哪儿（默认系统临时目录，不落进仓库）")
    ap.add_argument("--stdout", action="store_true", help="打到标准输出，不落盘")
    ap.add_argument("--title", default=DEFAULT_TITLE)
    args = ap.parse_args(argv)

    # 落点先问一句，**问在读取之前**（同 `adjudicate` / `selfproof`）：前提再全，
    # 写不出去也等于一条都没量到，该退 `2`。`--stdout` 时没有落点，跳过。
    if not args.stdout:
        rc = P.refuse_out_path(args.out)
        if rc is not None:
            return rc

    try:
        adj = load(args.adj)
        sp = load(args.sp)
        check_shape(adj, sp)
        page = render_html(adj, sp, args.title)
    except ViewerError as e:
        # 前提不成立是「没测到」（`2`），不是「没达到预期」（`1`）——
        # 同 `adjudicate`：**不发 traceback。**
        print(f"\n○ 没测到：{e}")
        return 2
    except (KeyError, TypeError, IndexError, AttributeError) as e:
        # 上面那道闸兜不住的一半：产物长成了**还没想到的**那种样子，渲染当场撞上。
        # 这不许按「发现了一处折合」退 `1` 走出去 —— 页面上**一个字都没有**，
        # 一句「展示层发现了 1 处折合」会是凭空报出来的发现（口径同 `run_all`：
        # 「没测到」既不是通过，也不是失败）。闸已经按「读什么就核什么」补齐，
        # 这一条是给闸外面剩下的那点余地留的。
        print(f"\n○ 没测到：渲染到一半撞上 {e.__class__.__name__}: {e} —— "
              "页面上一个字都没有，既不是「通过」，也不是「发现了一处折合」。")
        return 2

    if args.stdout:
        sys.stdout.write(page)
    else:
        try:
            with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(page)
        except OSError as exc:
            # 上面那道门挡不住的一半（目录在、文件建不出来）。渲染已经完成了，
            # **但这一份没落成** —— 按三种结果说清楚，不退 `1`。
            print(f"\n○ 没测到：展示页写不下去（{exc.__class__.__name__}: {exc}）—— "
                  "页面渲染出来了，但**这一份没落成**。")
            return 2
        print(f"\n→ {os.path.abspath(args.out)}")

    s = adj["summary"]["by_verdict"]
    sink = sys.stderr if args.stdout else sys.stdout
    print(f"\n共 {len(adj['rows'])} 条：{A.PASS_} {s[A.PASS_]} · "
          f"{A.FAIL_} {s[A.FAIL_]} · {A.UNDECIDED} {s[A.UNDECIDED]}", file=sink)
    for r in adj["rows"]:
        if r["verdict"] == A.UNDECIDED:
            print(f"  ○ {r['id']} 判不了：{r.get('undecidable_because')}", file=sink)
    print("**这不是分数**：判不了的条目既不计入通过、也不计入否决，因此没有分母。", file=sink)

    found = findings(adj, sp)
    if found:
        # 渲染是完成了的，但展示层**自己看出了一件事** —— 这是发现，退 `1`
        # （同 `adjudicate`：有判据恒真就不许退出 0）。
        for x in found:
            print(f"  × {x}", file=sink)
        print(f"\n× 展示层发现 {len(found)} 处折合／不一致 —— 不按「表是好的」退出。", file=sink)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
