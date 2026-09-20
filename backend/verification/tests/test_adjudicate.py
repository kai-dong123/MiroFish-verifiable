"""裁决与自证这两件产物，必须**还说得通**，而且必须**不是恒绿的**。

这个文件钉三件事，按重要性排：

1. **那三条规则真的会改结果** —— 贴界按**单元格**判（不是按「臂的集合 × 量的
   集合」的乘积判）、缺读数判**不可判定**而不是「否决」、没有 falsifier 的判据
   由检查器**自己**报恒真。这三条是整套东西的全部内容；它们要是退化成装饰，
   产物照样长得像证据。
2. **这一批产物对得上这一批源码** —— 报告最容易坏的方式不是丢，是**过期**：
   代码动了、报告没动，于是它继续替一份已经不在的代码作证。
3. **那两种状态不许混** —— 「读数里没有这一格」和「这一格是空的」必须分得开
   （本装置里「缺读数」记 `None`、不记 `""`，同一个道理）；
   「判不了」和「不采信」也必须分得开（前者 `trusted=None`，后者 `False`）。

第 1 组用**现造的读数**测，不依赖某次运行 —— 机制对就对，跟这次量到什么无关。
第 2、3 组读**入库的产物**，所以代码一改它们就该红，红是**对的**。
"""

from __future__ import annotations

import json
import os
import pathlib

import pytest

from verification import _probe as P
from verification import adjudicate as A
from verification import mutations as MU
from verification import selfproof as S

HERE = pathlib.Path(__file__).resolve().parent          # verification/tests
VERIFICATION = HERE.parent
BACKEND = VERIFICATION.parent

ADJ_JSON = VERIFICATION / "adjudication_report.json"
ADJ_MD = VERIFICATION / "ADJUDICATION.md"
SP_JSON = VERIFICATION / "selfproof_report.json"
SP_MD = VERIFICATION / "SELFPROOF.md"
RUN_REPORT = BACKEND / "verification_report.json"

_RERUN_A = "重新跑一次：`cd backend && python -m verification.adjudicate`"
_RERUN_S = "重新跑一次：`cd backend && python -m verification.selfproof`"


#: 这一轮是不是 `mutations.py` 起的（它把源码**故意改坏**再跑测试）。
_MUTATING = bool(os.environ.get(MU._MUTATION_ENV))

#: 只给**读入库产物**的那批测试用。理由是真的那一个：`mutations.py` 会故意改坏
#: `adjudicate.py` / `selfproof.py` 自己，于是「产物和源码的 sha 对不上」
#: 「用改坏的代码去重渲产物」都是**改坏的直接后果**，不是发现。
#:
#: **底下第一组不许挂这个** —— 那一组用现造的读数测机制，不读任何产物，
#: 而 J1/J2/J3 那三处变异正是要靠它们才红得起来。挂上去等于把变异集的三分之一
#: 变成摆设：源码改坏了，测试却整个跳过，报告上写着「0 条红 · 与声明不符」。
_SKIP_UNDER_MUTATION = pytest.mark.skipif(
    _MUTATING, reason="正在跑变异：源码此刻是被改坏的那个状态，这里问不出答案")


@pytest.fixture(scope="module")
def adj() -> dict:
    if not ADJ_JSON.is_file():
        pytest.fail(f"裁决的产物不在：{ADJ_JSON.name}。{_RERUN_A}")
    return json.loads(ADJ_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def sp() -> dict:
    if not SP_JSON.is_file():
        pytest.fail(f"自证的产物不在：{SP_JSON.name}。{_RERUN_S}")
    return json.loads(SP_JSON.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 现造的读数与判据：只测机制，不碰某次运行的结果
# ---------------------------------------------------------------------------

CELLS = {("A", "x"): 10, ("A", "y"): 20, ("B", "x"): 30, ("B", "y"): 40}


def _claim(cid, operands, holds, *, check="", thresholds=(), falsifier=None,
           undecidable=None, to_fix=None, layer="复现一"):
    return A._c(cid, layer, "测试用", check, operands, holds,
                thresholds=thresholds, falsifier=falsifier,
                undecidable=undecidable, to_fix=to_fix)


def _one(claim, cells=None, railed=None, unmeasured=None, override=None) -> dict:
    rows = A.evaluate((claim,), cells or CELLS, railed or {}, unmeasured or {},
                      override=override)
    return rows[0]


# ---------------------------------------------------------------------------
# 一、那三条规则真的会改结果
# ---------------------------------------------------------------------------

def test_the_first_real_assertion_is_not_vacuous():
    """**先自证这个文件不是空的。** 上面那套造数真的能判出三种结果吗？

    跑一趟最小的三态，不然底下那些断言全是在测一个连结果都产不出来的函数 ——
    那是空的，不是绿的。
    """
    ok = _one(_claim("T1", (("A", "x"),), lambda v, t: v[0] == 10))
    no = _one(_claim("T2", (("A", "x"),), lambda v, t: v[0] == 99))
    un = _one(_claim("T3", (("Z", "x"),), lambda v, t: True))
    assert [ok["verdict"], no["verdict"], un["verdict"]] == [
        A.PASS_, A.FAIL_, A.UNDECIDED]
    assert len({ok["verdict"], no["verdict"], un["verdict"]}) == 3, (
        "三态折成了不到三种 —— 这个文件底下所有的绿都不算数")


def test_railing_is_judged_per_cell_not_by_the_product_of_two_sets():
    """**贴界按单元格判，不按「臂的集合 × 量的集合」的乘积判。**

    本装置在别处真踩过这个：拿 `railed_rounds × railed_dims` 的乘积去圈定
    「贴界的单元格」，于是**每一格都被圈进去了** —— 一臂贴界，那一臂的**所有**
    量、以及那一量的**所有**臂，全被降级。判据于是变成「碰过贴界的臂就不可信」，
    比它该有的强得多，而且强得**没人看得出来**。

    这里就造那个形状：`A` 的 `x` 贴界。然后问两条判据：

    * 读 `(B, x)` 与 `(A, y)` —— **两格都没贴界**，必须**采信**。
      乘积式的判法会把它们都降级（`B ∈ 有贴界的臂？` 不，但 `x ∈ 有贴界的量？` 是）。
    * 读 `(A, x)` —— **这一格贴界**，必须**不采信**。
    """
    railed = {("A", "x"): "测试：这一格卡在机制下界上"}

    clean = _one(_claim("T4", (("B", "x"), ("A", "y")),
                        lambda v, t: v[0] + v[1] == 50), railed=railed)
    assert clean["verdict"] == A.PASS_
    assert clean["trusted"] is True, (
        f"这一格没贴界却被降级了 —— 多半是拿「臂的集合 × 量的集合」的乘积判的。"
        f"命中：{clean['tainted_by_railing']}")
    assert clean["tainted_by_railing"] == []

    hit = _one(_claim("T5", (("A", "x"),), lambda v, t: v[0] == 10), railed=railed)
    assert hit["verdict"] == A.PASS_
    assert hit["trusted"] is False
    assert hit["no_trust_because"] == [A.NO_TRUST_RAIL], (
        "不采信的理由是一串，不是布尔 —— 而且这里只该有「贴界」这一条")
    assert hit["tainted_by_railing"] == ["A.x"]


def test_a_claim_that_no_single_change_can_flip_is_not_trusted():
    """**「判据恒真 → 记 `trusted=False`」这条规则是实装的，不是写着的。**

    它从建表那天就写在本模块开头和产物开头（「给不出、或者给了却翻不动它的，
    检查器就判它**判据恒真**、记 `trusted=False`」），可算 `trusted` 的地方一度只看
    贴界那一条 —— `NO_TRUST_VACUOUS` 全仓没有第二处引用。于是一份产物会**自己打
    自己**：上半张表写「通过 · 采信」，下半张 falsifier 表写「恒真」。

    这里造的是 E4 那个形状（真读数里那条就是这么脆的）：判据是 `x > y`，falsifier
    把 `x` 改成 2 —— 只要 `y` 也是 0，改完 `2 > 0` 照样成立，它就翻不动了。
    """
    cells = {("A", "x"): 4, ("B", "y"): 0}
    c = _claim("T7", (("A", "x"), ("B", "y")), lambda v, t: v[0] > v[1],
               falsifier={("A", "x"): 2})
    rows = A.evaluate((c,), cells, {}, {})
    fals = A.falsifier_report((c,), cells, {}, {}, base_rows=rows)
    assert [f["kind"] for f in fals] == ["恒真"], (
        f"这个形状没被判成恒真，而是 {fals[0]['kind']!r} —— 前提不成立，"
        f"下面那几条测不到东西")
    assert rows[0]["trusted"] is True, (
        "回填之前它应当是 `trusted=True` —— 否则测的不是回填这件事")

    assert A.apply_vacuous_no_trust(rows, fals) == ["T7"]
    assert rows[0]["trusted"] is False, (
        "判据说「恒真就记 trusted=False」，回填却没动它 —— "
        "那这条规则还是只写在注释里")
    assert rows[0]["no_trust_because"] == [A.NO_TRUST_VACUOUS]
    assert "判据恒真" in rows[0]["detail"], "理由要写进 detail，读产物的人才看得见"

    s = A.summarize(rows, fals)
    assert s["vacuous"] == ["T7"]
    assert s["not_trusted"] == 1 and s["trusted"] == 0, (
        "汇总必须反映回填**之后**的状态，否则上半张表和下半张表还是两套口径")


def test_the_vacuous_backfill_leaves_things_alone_when_there_is_nothing_vacuous():
    """反向对照：**没有恒真的判据时，回填一个都不该动。**

    没有这一条，上面那条完全可能是靠「把 `trusted` 一律改成 False」过的。
    """
    c = _claim("T8", (("A", "x"),), lambda v, t: v[0] == 10,
               falsifier={("A", "x"): 99})
    rows = A.evaluate((c,), CELLS, {}, {})
    fals = A.falsifier_report((c,), CELLS, {}, {}, base_rows=rows)
    assert [f["kind"] for f in fals] == ["可翻面"], "前提不成立"
    before = (rows[0]["trusted"], list(rows[0]["no_trust_because"]), rows[0]["detail"])

    assert A.apply_vacuous_no_trust(rows, fals) == []
    assert (rows[0]["trusted"], list(rows[0]["no_trust_because"]),
            rows[0]["detail"]) == before, "没有恒真的判据被动了"


def test_a_reading_that_is_not_there_is_undecided_not_failed():
    """**缺读数判「不可判定」，不判「否决」。**

    这条不是措辞讲究。判成「否决」等于说「这件事不成立」—— 而事实是**没量过**。
    一个把「没测到」折进「失败」的装置，回头也会把「没测到」折进「通过」，
    两边都不值钱了（README 那一节的整个理由）。
    """
    row = _one(_claim("T6", (("Z", "x"),), lambda v, t: False,
                      undecidable="这一格本轮没量到", to_fix="去量它"))
    assert row["verdict"] == A.UNDECIDED, (
        "缺读数的判据判成了别的 —— 而它下面那个 `holds` 甚至返回 False，"
        "正是会被误折成「否决」的形状")
    assert row["trusted"] is None, (
        "判不了的判据**不谈采信**：记 False 会让「不采信」这个数虚高，"
        "记 True 又等于说它可信")
    assert row["no_trust_because"] == []
    assert row["undecidable_because"]
    assert row["to_make_decidable"]
    assert row["values"] == {"Z.x": None}, (
        "缺的格子要如实记成「没有这一格」（None），不是 0、不是空串、"
        "也不是干脆不写 —— 那三种都会被人当成一个读数")

    # 判据自己没交代「怎么才能判」时，那条也得填上 —— **一条都不许留空档**。
    # 空档读起来像「没办法」，而这里几乎总是有办法：把缺的那格量出来。
    auto = _one(_claim("T6b", (("Z", "x"),), lambda v, t: False))
    assert auto["verdict"] == A.UNDECIDED
    assert auto["undecidable_because"] and auto["to_make_decidable"], (
        f"自动判出的「不可判定」缺了交代：{auto['undecidable_because']!r} / "
        f"{auto['to_make_decidable']!r}")
    assert "Z.x" in auto["to_make_decidable"] and "Z.x" in auto["undecidable_because"]


def test_undecided_must_carry_both_what_is_missing_and_how_to_fix_it():
    """「缺什么」和「怎么才能判」必须成对出现 —— 说一半就抛。"""
    with pytest.raises(A.AdjudicationError, match="怎么才能判"):
        _claim("T7", (("A", "x"),), lambda v, t: True,
               undecidable="缺某某读数")
    with pytest.raises(A.AdjudicationError, match="缺什么"):
        _claim("T8", (("A", "x"),), lambda v, t: True, to_fix="去量它")
    ok = _claim("T9", (("A", "x"),), lambda v, t: True,
                undecidable="缺某某读数", to_fix="去量它")
    assert ok["undecidable_because"] and ok["to_make_decidable"]


def test_a_claim_with_no_falsifier_is_reported_vacuous_by_the_checker():
    """**没有 falsifier 的判据，由检查器自己报「恒真」。**

    这不是我在注释里声称的 —— `falsifier_report` 是机器判的，而它对每条判据
    做的是同一件事：改一处，看它动不动。改不动的判据，它判出来的「通过」
    什么也不说明。
    """
    good = _claim("T10", (("A", "x"),), lambda v, t: v[0] == 10,
                  falsifier={("A", "x"): 11})
    bad = _claim("T11", (("A", "x"),), lambda v, t: v[0] == 10)
    out = {f["id"]: f for f in A.falsifier_report((good, bad), CELLS, {}, {})}
    assert out["T10"]["kind"] == "可翻面", out["T10"]["detail"]
    assert out["T10"]["flipped"] is True
    assert out["T11"]["kind"] == "恒真", (
        "没声明 falsifier 的判据没被报成恒真 —— 那它判的「通过」就没法被检验")
    assert out["T11"]["flipped"] is False


def test_a_claim_whose_falsifier_does_not_bite_is_vacuous():
    """**声明了 falsifier，但它翻不动这条判据** —— 一样是恒真。

    这是更要紧的一半：`falsifier` 字段在不在，看代码就知道；它在不在**起作用**，
    只看代码看不出来。所以要**实例化**它，不是检查它存不存在。
    """
    toothless = _claim("T12", (("A", "x"), ("A", "y")),
                       lambda v, t: v[0] < v[1],
                       # 动了，但动的是这条判据读的另一个量 —— 结果纹丝不动
                       falsifier={("B", "z"): 0})
    out = {f["id"]: f for f in A.falsifier_report((toothless,), CELLS, {}, {})}[
        "T12"]
    assert out["kind"] == "恒真", out["detail"]
    assert "无感" in out["detail"]


def test_a_claim_already_failed_does_not_need_a_falsifier():
    """已经判「否决」的判据不算恒真 —— 它已经红过了，不必再证明它错得出来。

    混起来的代价很实际：一条真发现了问题的判据会被标成「没有鉴别力」，
    正好把最有用的那条读反。
    """
    already_red = _claim("T13", (("A", "x"),), lambda v, t: False)
    out = {f["id"]: f for f in A.falsifier_report((already_red,), CELLS, {}, {})}[
        "T13"]
    assert out["kind"] == "已否决", out["detail"]


def test_every_falsifier_result_the_checker_can_emit_is_renderable():
    """**闭集里四种结果，检查器吐得出、渲染器就得画得出。**

    这条是 2026-09-19 拿血换来的。`adjudicate.py` 与 `selfproof.py` 各有一张
    「判据非空泛性」表，两张表**各抄了一份**结果→写法的映射；`selfproof` 那份
    只写了三态，少了「已否决」（判据本来就判「否决」）。而本机的判据**从来没
    真的判过否决**，于是那个洞跑不到 —— 直到把它拿到 Linux 上跑（那台机器的
    时钟刻度比 camel 那个 `1e-6` 偏移还细，真有几条判据翻了面），
    `selfproof` 当场 `KeyError: '已否决'`：**报告算完了，写不出来。**

    所以这里不测「本机出现过的那几种」，测**四种全部**：
    先确认这四种都真吐得出来（否则闭集里的是空话），再确认映射表一个不少。
    两份产物现在是同一张表（`A.FALSIFIER_MARKS`），键一缺就在这里红。
    """
    # 「不可判定」的入口是**读数缺席**（`("Z", "x")` 不在 `CELLS` 里），不是给
    # `undecidable=` 传一段话 —— 那个参数是缺席时**用的说明文字**。话传了而读数
    # 给全了，这条会被判成「恒真」，于是这条测试自己就成了它要抓的那种错：
    # 测的东西和以为在测的东西不是一回事。
    und = _claim("T20", (("Z", "x"),), lambda v, t: True,
                 undecidable="没量到", to_fix="去量")
    red = _claim("T21", (("A", "x"),), lambda v, t: False)
    vac = _claim("T22", (("A", "x"),), lambda v, t: True)          # 没有 falsifier
    flip = _claim("T23", (("A", "x"),), lambda v, t: v[0] >= 5,
                  check="`A.x` ≥ 5", thresholds=((r"≥\s*([\d.]+)", "下界"),),
                  falsifier={("A", "x"): 1})

    got = {f["id"]: f["kind"] for f in
           A.falsifier_report((und, red, vac, flip), CELLS, {}, {})}
    assert got == {"T20": "不可判定", "T21": "已否决",
                   "T22": "恒真", "T23": "可翻面"}, got

    assert set(A.FALSIFIER_MARKS) == set(A.FALSIFIER_KINDS), (
        f"两张表不同键：渲染用 {sorted(A.FALSIFIER_MARKS)}，"
        f"闭集是 {sorted(A.FALSIFIER_KINDS)}")
    assert set(got.values()) <= set(A.FALSIFIER_MARKS), (
        f"检查器吐出了渲染器画不出来的结果："
        f"{sorted(set(got.values()) - set(A.FALSIFIER_MARKS))}")


@_SKIP_UNDER_MUTATION
def test_the_selfproof_renderer_survives_a_denied_claim(sp):
    """再把那个**真实的崩溃**在产物上走一遍：给自证报告塞一条「已否决」的
    falsifier，渲染器必须照样出得来。

    上面那条测的是机制，这条测的是**那份产物渲染函数**真的接到了同一张表上 ——
    只测机制的话，渲染器里再手抄一份三态的表也照样绿。
    """
    import copy

    rep = copy.deepcopy(sp)
    rep["falsifiers"] = [{"id": "T99", "kind": "已否决", "detail": "试一下"}]
    text = S.render_markdown(rep)
    assert "T99" in text, "自证的渲染器没能把这一行画出来"
    assert A.FALSIFIER_MARKS["已否决"] in text, (
        f"画出来的不是 {A.FALSIFIER_MARKS['已否决']!r} —— 渲染器里又抄了一份表？")


def test_undecided_is_not_counted_as_vacuous():
    """缺读数翻不动，**不是**恒真 —— 两者不能混成一个数。"""
    row = _one(_claim("T14", (("Z", "x"),), lambda v, t: True,
                      undecidable="没量到", to_fix="去量"))
    out = {f["id"]: f for f in A.falsifier_report(
        (_claim("T14", (("Z", "x"),), lambda v, t: True,
                undecidable="没量到", to_fix="去量"),), CELLS, {}, {})}["T14"]
    assert row["verdict"] == A.UNDECIDED
    assert out["kind"] == "不可判定"
    assert out["flipped"] is None, "记 False 会跟「恒真」混成同一个数"


def test_thresholds_are_read_from_the_claim_text_not_reimplemented():
    """阈值从判据**原文**里抠。代码里另抄一份，判据改了阈值代码不知道 ——
    而这张表会拿着旧阈值去判新判据，它自己不会知道。"""
    for text, want in (("`A.x` ≥ 7", 7.0), ("`A.x` ≥ 7.5 个", 7.5)):
        assert A._num(r"≥\s*([\d.]+)", text, "下界") == want
    with pytest.raises(A.AdjudicationError, match="找不到"):
        A._num(r"≥\s*([\d.]+)", "`A.x` 大于七", "下界")

    # 同一个 `holds`、同一批读数，**只改判据原文里的数**，结果就应当不同。
    loose = _claim("T15", (("A", "x"),), lambda v, t: v[0] >= t[0],
                   check="`A.x` ≥ 5", thresholds=((r"≥\s*([\d.]+)", "下界"),))
    tight = _claim("T16", (("A", "x"),), lambda v, t: v[0] >= t[0],
                   check="`A.x` ≥ 50", thresholds=((r"≥\s*([\d.]+)", "下界"),))
    rows = A.evaluate((loose, tight), CELLS, {}, {})
    assert [r["verdict"] for r in rows] == [A.PASS_, A.FAIL_], (
        "改判据原文里的阈值改不动结果 —— 那阈值是代码里另有一份，"
        "这份表拿的是那一份")


def test_the_layer_is_a_closed_set_and_a_typo_raises():
    """层写错一个字会让整条判据静默退化（本装置在别处 `产出` 写成 `产物`）——
    所以是校验过的闭集，不是随手写的字符串。"""
    with pytest.raises(A.AdjudicationError, match="不在"):
        _claim("T17", (("A", "x"),), lambda v, t: True, layer="复现壹")
    assert "复现一" in A.LAYERS


def test_the_claim_table_must_declare_what_it_is_not():
    """判据表必须**自己**交代它是什么、不是什么、哪几条不结实。

    缺了就抛、不生成表 —— 这句话不能由检查器代说。代说就成了贴标签：
    标签可以贴，也可以不贴，而这句话是**这张表读法的前提**。
    """
    full = {k: "x" for k in A.REQUIRED_DECLARATIONS}
    A.require_declarations(full)          # 齐全时不抛
    for missing in A.REQUIRED_DECLARATIONS:
        partial = dict(full)
        partial.pop(missing)
        with pytest.raises(A.AdjudicationError, match=missing):
            A.require_declarations(partial)
    with pytest.raises(A.AdjudicationError, match="not_solid"):
        A.require_declarations({**full, "not_solid": ""})
    # 真表必须交代齐 —— 上面那几条测的是函数，这条测的是**它真的被调用了**
    A.require_declarations(A.CLAIM_SET)


def test_the_summary_refuses_to_produce_a_rate():
    """**这不是分数**：判不了的既不算通过也不算否决，所以没有分母。

    这条得由产物自己带着，不能靠读的人自觉 —— 一张有「8 条通过」的表摆在那里，
    不写清楚就会被人读成 8/10。
    """
    rows = A.evaluate(A.CLAIMS, CELLS, {}, {})
    s = A.summarize(rows, [])
    assert s["not_a_rate"] is True
    assert "没有分母" in s["note"]
    assert s["undecided_trusted"] == s["by_verdict"][A.UNDECIDED], (
        "判不了的那几条必须单列，不能并进采信或不采信任何一边")
    for key in ("rate", "ratio", "score", "percent", "pass_rate"):
        assert key not in s, f"汇总里出现了 {key!r} —— 这份产物不是分数"


# ---------------------------------------------------------------------------
# 一之二、「产物过期」这四个字必须钉在**读数**上，不是钉在文件上
# ---------------------------------------------------------------------------

def _fake_report(cells=None, generated_at="2026-01-01 00:00:00") -> dict:
    """一份**现造的** `verification_report.json` —— 只长成 `cells_from` 认的样子。"""
    cells = cells or CELLS
    arms: dict = {}
    for (arm, metric), value in cells.items():
        arms.setdefault(arm, {})[metric] = value
    return {"generated_at": generated_at,
            "results": [{"readings": {"readings": arms, "boundaries": []}}]}


def test_the_readings_digest_ignores_when_the_report_was_written():
    """指纹钉的是**读数**，不是**文件**。

    这条是踩出来的：原先产物里记的是 `verification_report.json` 的**文件 sha**，
    而那个文件每跑一次 `run_all` 就会重写、`generated_at` 必然不同 ——
    于是**每一个照 README 跑一遍的人**（clone → run_all → pytest）都会撞上一条红，
    可那批读数一个字节都没变。那是假警报，不是发现。

    ⚠️ 注意这条**只**管「写文件的时刻不同不该改指纹」。它**不能**被读成
    「同一套判据在两次运行上必然得到同一个指纹」—— 读数里有物理时钟取样
    （`clock.tick_ns`、`gap_s`、`ticks_ratio`），**每次运行本来就不一样**。
    所以「产物过没过期」查的不是指纹，是**结果表**（见下一条）。
    """
    a = A.readings_digest(_fake_report(generated_at="2026-01-01 00:00:00"))
    b = A.readings_digest(_fake_report(generated_at="2026-09-17 23:59:59"))
    assert a == b, "报告换个时间重写，读数没变，指纹却变了 —— 那又变成钉文件了"

    moved = {**CELLS, ("A", "x"): CELLS[("A", "x")] + 1}
    assert A.readings_digest(_fake_report(moved)) != a, (
        "动了一个读数，指纹却没变 —— 那这份产物过期了也查不出来")

    # 贴界/未测量也是「被判的读数」的一部分：它们的声明变了，产物同样过期。
    rep = _fake_report()
    rep["results"][0]["readings"]["boundaries"] = [
        {"arm": "A", "metric": "x", "kind": P.BOUND_RAILED, "why": "测试用"}]
    assert A.readings_digest(rep) != a, "贴界声明变了，指纹却没变"


def test_no_report_is_undecided_and_gets_no_traceback(monkeypatch, tmp_path):
    """前提不成立是**没测到**（退出码 `2`），不是「没达到预期」（`1`），
    也不该甩一个 traceback 出去。

    一个把「没跑起来」报成「失败」的装置，不配去要求别人别把「没测到」折成两边。
    """
    def _boom(*a, **k):
        raise A.AdjudicationError("没有 `verification_report.json` —— 先跑一次 run_all")
    monkeypatch.setattr(A, "load_report", _boom)

    rc = A.main(["--json", str(tmp_path / "a.json"), "--md", str(tmp_path / "a.md")])
    assert rc == 2, f"报告不在时退出码是 {rc} —— 该是「没测到」的 2"
    assert not (tmp_path / "a.json").exists(), "判都没判定，不该落下产物"


def test_a_report_that_is_readable_json_but_wrongly_shaped_is_refused(tmp_path):
    """**读得成 JSON ≠ 结构对。** 结构不对要当场说清，不许甩 traceback。

    这条在防的是「一半的防线」：原先只接住了 `JSONDecodeError`（文件不是 JSON），
    没接住「是 JSON、但形状不对」。而 `cells_from` 是在**下标取值那一层**消费这份
    报告的（`b["arm"]`、`block.get("readings", {})` 再 `.items()`）—— 那里抛的
    `KeyError` / `AttributeError` / `TypeError` **不是** `AdjudicationError`，
    于是逃出 `main()`、甩一个 traceback、按 Python 默认退成 `1`。
    而 `1` 在这台装置里的意思是「**有子进程没跑成**」：一次「这份产物读不出来」
    被报成了「跑了但失败了」，读者会去查一个并不存在的失败。

    和 `load_report` 里 `JSONDecodeError` 那一段是同一个病。修法也同一条：
    在读进来那一刻就把形状查一遍，判成**没测到**（`2`）。
    """
    bad = tmp_path / "verification_report.json"
    # 合法 JSON，但 `results[0].readings.readings` 那一层是**数**不是**对象**
    # —— 「有人手工补了一条」最常长成的样子。
    bad.write_text(json.dumps({"results": [{"readings": {"readings": {"A": 1}}}]},
                              ensure_ascii=False), encoding="utf-8")

    with pytest.raises(A.AdjudicationError) as exc:
        A.load_report(bad)
    assert "结构不对" in str(exc.value), (
        f"结构不对时抛的是 {exc.value!r} —— 得说清是**结构**的问题，"
        "不然读的人会去查读数")
    assert exc.value.__class__ is A.AdjudicationError, (
        "必须是这一种异常：`main()` 只接得住它，别的一律逃出去变成 traceback")

    # 端到端那份的惯例不同，**故意不改**：它读不了就返回 `None`，
    # 下游按「不可判定」处理（同文件里那条 `load_e2e_report` 的说明）。
    assert A.load_e2e_report(bad) is None, (
        "端到端那份读不了时该返回 `None`（→ 不可判定），不是抛")

    # 反向对照：好形状必须照过。少了这一半，一个「一律拒收」的实现也能让上面全绿。
    good = tmp_path / "good.json"
    good.write_text(json.dumps(_fake_report(), ensure_ascii=False), encoding="utf-8")
    assert A.load_report(good)["results"], "好端端的一份报告被拒了"


def test_a_vacuous_claim_makes_the_table_refuse_to_exit_green(monkeypatch, tmp_path):
    """有判据恒真就不许退 `0`。

    那几条「通过」是恒真的，等于这张表里有一格白写了 —— 那是**发现**，
    得让人看一眼。退出码不发 `0` 是这张表**自己**不愿意被当成绿的。
    """
    monkeypatch.setattr(A, "load_report", lambda *a, **k: _fake_report())
    monkeypatch.setattr(A, "CLAIMS", (
        _claim("T9", (("A", "x"),), lambda v, t: v[0] == 10),   # 没有 falsifier
    ))
    rc = A.main(["--json", str(tmp_path / "b.json"), "--md", str(tmp_path / "b.md")])
    assert rc == 1, f"判据恒真时退出码是 {rc} —— 该是 1（表生成了，但有东西白写）"
    assert (tmp_path / "b.json").is_file(), "表还是要落下来，人得看得见它"

    # 同一张表，给同一条判据补上会咬的 falsifier → 退 0。不然上面那条是恒真的。
    monkeypatch.setattr(A, "CLAIMS", (
        _claim("T9", (("A", "x"),), lambda v, t: v[0] == 10,
               falsifier={("A", "x"): 99}),
    ))
    assert A.main(["--json", str(tmp_path / "c.json"),
                   "--md", str(tmp_path / "c.md")]) == 0, (
        "补上 falsifier 之后还是不让退 0 —— 那上面那条断言是恒真的")


# ---------------------------------------------------------------------------
# 二、入库的产物：还说得通吗
# ---------------------------------------------------------------------------

@_SKIP_UNDER_MUTATION
def test_the_two_human_readable_sides_are_there_too(adj, sp):
    """机读的那份在，不等于人读的那份在 —— 两边都要有。"""
    for path, rerun in ((ADJ_MD, _RERUN_A), (SP_MD, _RERUN_S)):
        assert path.is_file(), f"人读的那份不在：{path.name}。{rerun}"
        assert len(path.read_text(encoding="utf-8")) > 800, (
            f"{path.name} 短得不像话，多半是半截产物")
    for r in adj["rows"]:
        assert f"`{r['id']}`" in ADJ_MD.read_text(encoding="utf-8"), (
            f"报告里有 {r['id']}，人读的那份里却没有。{_RERUN_A}")
    sp_text = SP_MD.read_text(encoding="utf-8")
    for c in sp["cases"]:
        assert f"`{c['id']}`" in sp_text, (
            f"报告里有 {c['id']}，人读的那份里却没有。{_RERUN_S}")


@_SKIP_UNDER_MUTATION
def test_neither_artifact_claims_to_be_a_pass_rate(adj, sp):
    for rep in (adj, sp):
        assert rep["not_a_pass_rate"] is True, (
            "产物没说清自己不是通过率 —— 那它会被读成一份评分")
    assert "不是分数" in adj["what_this_is_NOT"]
    assert "不是分数" in A.render_markdown(adj)


@_SKIP_UNDER_MUTATION
def test_the_artifacts_still_describe_the_code_on_disk(adj, sp):
    """产物不能替一份**已经不在**的代码作证。

    对不上只有两种解释，都要人去看一眼：源码动了（产物过期），
    或者有人手工改过产物（那它就不是产物了）。
    """
    for rep, name, rerun in ((adj, "adjudicate.py", _RERUN_A),
                             (sp, "selfproof.py", _RERUN_S)):
        assert rep["script"]["path"] == f"verification/{name}"
        assert rep["script"]["sha256"] == A._sha(
            (VERIFICATION / name).read_text(encoding="utf-8")), (
            f"{name} 动过了，产物是改动之前的。{rerun}")

    # 报告那边钉的是**结果表**，不是读数指纹，也不是文件 sha。两级都是踩出来的：
    #
    #   ① 钉文件 sha → 报告每跑一次 `run_all` 就重写，**人人撞红**；
    #   ② 钉读数指纹 → 读数里有**物理时钟取样**（`clock.tick_ns`、`gap_s`、
    #      `ticks_ratio`），**每次运行本来就不一样**，照样每次重跑都红。
    #
    # 这份产物真正声称的是「**这批读数**会得到**这张表**」。那就照它声称的查：
    # 把盘上那份报告重新判一遍，看结果表一不一样。读数变了但没动摇任何一条判定
    # → 这张表没过期；哪条判定的结果变了 → 产物真过期（或者那条判据本来就在
    # 抖动的量上，那也是要看一眼的发现）。
    #
    # 报告不在（刚 clone 下来还没跑过 `run_all`）→ **跳过，不是失败**：
    # 这不是产物有问题，是这一条**没条件判**。硬判下去就是拿一个不存在的读数
    # 去判「产物过没过期」，那正是本装置不许别人做的事。
    try:
        report = A.load_report()
    except A.AdjudicationError:
        pytest.skip(f"`{RUN_REPORT.name}` 不在，这一条没条件判。"
                    f"先跑一次 `cd backend && python -m verification.run_all`。")
    # 走 `all_cells()`：格子有**两个**来源（三条复现 + 端到端），
    # 这里若只读一份，就会把「端到端那一层不在」误判成「产物过期」。
    live = A.evaluate(A.CLAIMS, *A.all_cells())

    want = {r["id"]: (r["verdict"], r["trusted"]) for r in live}
    for rep, rerun in ((adj, _RERUN_A), (sp, _RERUN_S)):
        assert rep["report"]["path"] == RUN_REPORT.name
        # 裁决那份记在 `rows` 里，自证那份记在 `base` 里。
        keyed = rep.get("rows") or rep.get("base") or []
        got = {r["id"]: (r["verdict"], r["trusted"]) for r in keyed}
        assert got == want, (
            f"`{RUN_REPORT.name}` 重新判一遍，结果表和产物的对不上 —— "
            f"要么产物是上一批读数判出来的，要么有判据在抖动的量上。{rerun}")


@_SKIP_UNDER_MUTATION
def test_the_adjudication_read_real_readings_not_a_fallback(adj):
    """判的必须是**那次运行量到的**读数。三条复现里少一条读数块，
    这张表就有断言是在对着空气判 —— 而它照样会打出一片绿。"""
    assert adj["cells_total"] > 40, (
        f"只读到 {adj['cells_total']} 个格子 —— 太少，像是有复现的读数块没抽出来")
    assert adj["railed_cells"], "一条贴界声明都没有？那两条贴界规则根本没被测到"
    assert adj["unmeasured_cells"], "一条未测量声明都没有，同上"


@_SKIP_UNDER_MUTATION
def test_no_claim_row_betrays_the_three_states(adj, sp):
    """三态不许折、`trusted=None` 只准出现在「不可判定」上。

    这条是把那三条规则**反过来**查一遍：不是「规则会不会改结果」，
    而是**入库的这批结果有没有违反规则**。
    """
    for r in adj["rows"]:
        assert r["verdict"] in (A.PASS_, A.FAIL_, A.UNDECIDED)
        if r["verdict"] == A.UNDECIDED:
            assert r["trusted"] is None
            assert r["undecidable_because"], f"{r['id']} 判不了却没说缺什么"
            assert r["to_make_decidable"], f"{r['id']} 判不了却没说怎么才能判"
        else:
            assert isinstance(r["trusted"], bool), (
                f"{r['id']} 判出了结果，`trusted` 却是 {r['trusted']!r} —— "
                f"不让它落在布尔上，就等于给「不采信」留了个后备档")
            assert isinstance(r["no_trust_because"], list), (
                "不采信的理由是一**串**，不是布尔 —— 布尔说不出为什么")
        assert (A.NO_TRUST_RAIL in r["no_trust_because"]) == bool(
            r["tainted_by_railing"]), (
            f"{r['id']}：说贴界却给不出贴界的格子，或者反过来 —— 对不上")

    # 三态必须真的都出现过，否则上面那些断言只是在测一个退化的表
    got = {r["verdict"] for r in adj["rows"]}
    assert got == {A.PASS_, A.FAIL_, A.UNDECIDED} or (
        got == {A.PASS_, A.UNDECIDED} and all(
            f["kind"] != "恒真" for f in adj["falsifiers"])), (
        f"这一批裁决只出现过 {sorted(got)} —— 有一条路根本没被走到，"
        f"而那条路走不走得到由自证那边负责（见 `selfproof_report.json`）")


@_SKIP_UNDER_MUTATION
def test_the_adjudication_has_no_claim_that_is_vacuous(adj):
    """**这是整份裁决存在的理由**：每条判据要么有一个真能翻动它的单点扰动，
    要么明说是「缺读数」。翻不动又说不出缺什么的，就是恒真 —— 它判的「通过」
    什么也不说明。"""
    kinds = {f["id"]: f["kind"] for f in adj["falsifiers"]}
    assert len(kinds) == len(adj["rows"]), "有判据没被 falsifier 检查过"
    vacuous = [i for i, k in kinds.items() if k == "恒真"]
    assert not vacuous, (
        f"这几条判据对任何单点扰动都无感（恒真）：{vacuous} —— "
        f"它们判的「通过」不算证据。{_RERUN_A}")
    undecided = [r["id"] for r in adj["rows"] if r["verdict"] == A.UNDECIDED]
    assert sorted(i for i, k in kinds.items() if k == "不可判定") == sorted(undecided), (
        "「不可判定」的判据集合和 falsifier 那边的对不上")


# ---------------------------------------------------------------------------
# 三、自证：五格全到过、每条都试过
# ---------------------------------------------------------------------------

@_SKIP_UNDER_MUTATION
def test_the_selfproof_ran_clean(sp):
    assert sp["problems"] == [], (
        f"自证自己报了问题：{sp['problems']}。{_RERUN_S}")
    assert sp["meta"]["all_ok"] is True
    assert sp["meta"]["cases_ok"] == len(sp["cases"]), (
        f"{sp['meta']['cases_ok']}/{len(sp['cases'])} 例表态相符 —— "
        f"有例子的实测和它自己的表态对不上")


# ---------------------------------------------------------------------------
# 自证自己的出口也是**三态**（`0` 干净 / `1` 有问题 / `2` 缺前提）
# ---------------------------------------------------------------------------
#
# 这一节此前是**整块空的**：`grep -n "S\.main\|SelfproofError" tests/*.py`
# 零命中 —— 自证的退出码从来没被验过。而它和 `reconcile_selfcheck` 是同一条
# 契约、同一种翻车方式：**「没测到」折进「没达到预期」**，或者更糟 ——
# `SystemExit(None)` 退 `0`，一次什么都没量的运行报「一切正常」。
#
# 三档都用现造的 `run()` 测，**不跑真的自证**：真跑会依赖 `adjudicate.CLAIMS`，
# 而 J1/J3/J4 那几个变异正是把它改坏的 —— 那几轮里真跑出来的数没有意义。

def _fake_selfproof_run(monkeypatch, *, all_ok: bool, problems: list):
    """把 `S.run` / `S.render_markdown` 换成现造的，只为测 `main` 的出口。"""
    monkeypatch.setattr(S, "render_markdown", lambda rep: "（现造的）")
    monkeypatch.setattr(S, "run", lambda: {
        "meta": {"all_ok": all_ok, "grids_seen": [], "grids_missing": [],
                 "cases_ok": 0, "claims_with_working_falsifier": [],
                 "claims_vacuous": []},
        "cases": [], "claims": {"count": 0}, "problems": problems})


def test_a_missing_premise_makes_the_selfproof_exit_two_not_one(monkeypatch, tmp_path):
    """前提不成立（端到端那层没跑过）→ `2`，**不是** `1`。

    `1` 在装置自己的表里是「没达到预期」—— 那会让读者去查一个不存在的失败，
    而实际发生的是**一个读数都没取到**。README 那句「退出码：三种，不是两种」
    就是冲这个写的。
    """
    def boom():
        raise S.SelfproofError("现造：没有 e2e 报告")
    monkeypatch.setattr(S, "run", boom)

    out_json, out_md = tmp_path / "s.json", tmp_path / "s.md"
    rc = S.main(["--json", str(out_json), "--md", str(out_md)])

    assert rc == 2, f"缺前提时自证退了 {rc} —— 该是 2（没测到），不许折进 1"
    assert not out_json.is_file() and not out_md.is_file(), (
        "前提都不成立，却还是落了一份产物下来 —— 下一轮谁读到它就会当成一次真跑")


def test_an_adjudication_error_is_also_not_measured(monkeypatch, tmp_path):
    """反向对照之一：另一类前提错误（`AdjudicationError`）走同一个出口。

    少了这条，一个只 `except SelfproofError` 的实现也能让上面那条变绿 ——
    而读数文件坏掉时抛的是另一类。
    """
    def boom():
        raise A.AdjudicationError("现造：读数文件坏了")
    monkeypatch.setattr(S, "run", boom)

    assert S.main(["--json", str(tmp_path / "e.json"),
                   "--md", str(tmp_path / "e.md")]) == 2, (
        "`AdjudicationError` 没走「没测到」那条出口 —— 只接了一类前提错误")


def test_a_problem_makes_the_selfproof_exit_one_and_a_clean_one_zero(
        monkeypatch, tmp_path):
    """反向对照之二：**真有**问题退 `1`、真干净退 `0`。

    没有这一条，一个恒返回 `2` 的实现也能让上面那两条全绿 ——
    而恒返回 `2` 会把自证唯一一类真发现（判据恒真、有死格）整个藏起来。
    """
    _fake_selfproof_run(monkeypatch, all_ok=False, problems=["现造：有死格"])
    assert S.main(["--json", str(tmp_path / "a.json"),
                   "--md", str(tmp_path / "a.md")]) == 1, (
        "自证报了问题却退 0 —— 那这份产物就是在装绿")

    _fake_selfproof_run(monkeypatch, all_ok=True, problems=[])
    rc = S.main(["--json", str(tmp_path / "b.json"), "--md", str(tmp_path / "b.md")])
    assert rc == 0, f"自证一切干净却退了 {rc} —— 该是 0"


@_SKIP_UNDER_MUTATION
def test_all_five_grids_were_reached(sp):
    """**五格必须全出现过**：通过·采信／通过·不采信／否决·采信／否决·不采信／
    不可判定。少一格就是有**死格** —— 那套判据压根到不了那个状态，
    而到不了的状态上写着的规则全是空话。"""
    assert sp["meta"]["grids_missing"] == [], (
        f"这几格一次都没到达过：{sp['meta']['grids_missing']}。{_RERUN_S}")
    assert set(sp["meta"]["grids_seen"]) == set(S.GRIDS), (
        f"到过的格是 {sp['meta']['grids_seen']}，应当是 {list(S.GRIDS)}")


@_SKIP_UNDER_MUTATION
def test_every_case_states_a_verdict_for_every_claim(sp):
    """每例的 `touch` + `untouched` 必须**恰好覆盖全部判据**。

    只表态「会变的那些」，等于没表态「其余不许变」—— 那样整体乱动也会通过。
    """
    ids = set(sp["claims"]["ids"])
    assert len(ids) == sp["claims"]["count"]
    for c in sp["cases"]:
        covered = set(c["touch"]) | set(c["untouched"])
        assert covered == ids, (
            f"{c['id']}：表态表没覆盖全部判据 —— "
            f"漏了 {sorted(ids - covered)}、多了 {sorted(covered - ids)}")
        assert not (set(c["touch"]) & set(c["untouched"]))
        for g in c["touch"].values():
            assert g in S.GRIDS, (
                f"{c['id']}：表态写成 {g!r} —— 必须写全 `结果·采信`，"
                f"只写「通过」就漏掉了贴界降级那一半")


@_SKIP_UNDER_MUTATION
def test_the_selfproof_covers_all_three_mutation_kinds(sp):
    """三个扰动层各要有人走：读数 / 断言 / 边界。

    只动读数层，「阈值是从原文抠的」「贴界声明真的会改结果」这两件事
    就一次都没被检验过 —— 而它们正好是那两条最容易退化成装饰的规则。
    """
    got = {c["layer"] for c in sp["cases"]}
    assert got == set(S.MUTATION_KINDS), (
        f"只动了 {sorted(got)} 这几层，{sorted(set(S.MUTATION_KINDS) - got)} 没动过")


@_SKIP_UNDER_MUTATION
def test_the_selfproof_did_not_find_a_vacuous_claim(sp):
    """自证那边也要确认没有恒真的判据 —— 两份产物对同一件事的说法必须一致。"""
    assert sp["meta"]["claims_vacuous"] == [], (
        f"自证抓到恒真的判据：{sp['meta']['claims_vacuous']}。{_RERUN_S}")
    assert sp["meta"]["claims_with_working_falsifier"], "一条能翻面的都没有？"
    # 判不了的那几条**不算**恒真 —— 两者混起来会把「缺读数」读成「没鉴别力」
    assert not set(sp["meta"]["claims_undecidable"]) & set(
        sp["meta"]["claims_vacuous"])


# ---------------------------------------------------------------------------
# 四、GBK：产物里的字，中文 Windows 的 cmd 也打得出来
# ---------------------------------------------------------------------------

@_SKIP_UNDER_MUTATION
def test_the_artifacts_are_printable_on_a_chinese_windows_console(adj, sp):
    """产物的字必须**GBK 编得出**。

    `_harden_streams()` 把编不出的字符降级成 `?`，于是损坏是**无声的** ——
    屏幕上一片 `?`，文件里却是好的，两边对不上还查不出来。
    这条纪律在装置里是有来历的：`µ`（U+00B5）编不出，一度让读数块里的
    「1 ?s」脏掉。所以产物一律用 `√ × ○` 和「微秒」这种编得出的写法。

    同时测**当场渲染的**那两份，不只是入库的那两份 —— 否则改了渲染代码、
    还没重跑产物，这条测试会在一个**已经不存在的**版本上通过。
    """
    for name, rep in (("ADJUDICATION.md", adj), ("SELFPROOF.md", sp)):
        for label, text in (("入库的", (VERIFICATION / name).read_text(encoding="utf-8")),
                            ("当场渲染的", A.render_markdown(rep)
                             if name == "ADJUDICATION.md" else S.render_markdown(rep))):
            bad = P.non_gbk_chars(text)
            assert not bad, f"{name}（{label}）里有 GBK 编不出的字符：{bad!r}"


# ---------------------------------------------------------------------------
# 落点：写不出来是「没测到」（`2`），不是「没达到预期」（`1`）
# ---------------------------------------------------------------------------
#
# 这一节补的是一处**已经量到过**的边界：`--out` / `--json` / `--md` 指到一个不
# 存在的目录时，落盘那一步抛 `FileNotFoundError`，没人接 → 进程退 `1`。按本装置
# 自己的表，`1` 是「跑成了但没达到预期」—— 而那一刻**一个读数都没落下来**。
#
# 修法是跑之前先问一句落点。所以这里要钉的**不只是**「坏落点退 2」，还有
# 「它是**在动手之前**退的」：判定算了一半才发现写不出去，结论就已经脏了。
#
# 两道出口都要问：门（跑之前）和 `except OSError`（门挡不住的那一半）。

def _nowhere(tmp_path) -> str:
    """一个**目录不存在**的落点。"""
    return str(tmp_path / "没有这个目录" / "x")


#: 一份现造的裁决产物 —— 只为了走到 `main` 的落盘那一步，不依赖任何真读数。
_FAKE_ADJ = {
    "summary": {"total": 1, "by_verdict": {A.PASS_: 1, A.FAIL_: 0, A.UNDECIDED: 0},
                "trusted": 1, "not_trusted": 0, "undecided_trusted": 0,
                "falsifiable": 1, "vacuous": 0},
    "rows": [{"id": "现造", "verdict": A.PASS_, "trusted": True,
              "undecidable_because": None, "no_trust_because": []}],
    "falsifiers": [{"id": "现造", "kind": "能翻面"}],
}


def test_a_bad_place_stops_both_entry_points_before_they_compute(
        monkeypatch, tmp_path, capsys):
    """坏落点 → `2`，而且 `run()` **一次都没被调**。

    「跑之前」这条不是洁癖：真算一场要读读数、判一遍、再自证一遍，然后把结论
    丢掉、退回一个会被读成「有失败」的码。所以这里把 `run` 换成一个记账的桩 ——
    它被调到就是这条测试要抓的事。

    两道入口各测一个**不同的**旗标（一个 `--json`、一个 `--md`），免得只挡住了
    其中一个。
    """
    calls: list = []
    monkeypatch.setattr(A, "run", lambda: (calls.append("A"), {})[1])

    rc = A.main(["--json", _nowhere(tmp_path), "--md", str(tmp_path / "a.md")])
    out = capsys.readouterr().out
    assert rc == 2, f"裁决：坏落点退了 `{rc}` —— 该退 `2`（没测到）"
    assert "落点" in out, "得说清是**落点**的问题，不是读数的问题"
    assert calls == [], "落点都不通，裁决却先算了一场 —— 该在动手之前就退"

    monkeypatch.setattr(S, "run", lambda: (calls.append("S"), {})[1])
    rc = S.main(["--json", str(tmp_path / "s.json"), "--md", _nowhere(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 2, f"自证：坏落点退了 `{rc}` —— 该退 `2`（没测到）"
    assert "落点" in out
    assert calls == [], (
        f"落点都不通，两道入口还是先各算了一场：{calls} —— 该在动手之前就退")


def test_a_write_that_fails_anyway_is_still_not_measured(
        monkeypatch, tmp_path, capsys):
    """门挡不住的那一半：目录在、真写的时候才炸，也必须是 `2`。

    门只问得出「目录在不在、可不可写」，问不出磁盘满、路径太长、文件被占。
    那一步抛的 `OSError` 要是没人接，进程还是退 `1` —— 同一个病换个入口。
    """
    def refuse(*a, **k):
        raise OSError(28, "现造：磁盘满了")
    monkeypatch.setattr(pathlib.Path, "write_text", refuse)
    monkeypatch.setattr(A, "render_markdown", lambda rep: "（现造的）")

    monkeypatch.setattr(A, "run", lambda: _FAKE_ADJ)
    rc = A.main(["--json", str(tmp_path / "a.json"), "--md", str(tmp_path / "a.md")])
    out = capsys.readouterr().out
    assert rc == 2, f"裁决：写不下去时退了 `{rc}` —— 该退 `2`（没测到）"
    assert "没测到" in out and "没落成" in out, (
        "得说清「算出来了，但这一份产物没落成」—— 只说「失败」会把人指去查判据")

    monkeypatch.setattr(S, "render_markdown", lambda rep: "（现造的）")
    monkeypatch.setattr(S, "run", lambda: {"meta": {"all_ok": True}})
    rc = S.main(["--json", str(tmp_path / "s.json"), "--md", str(tmp_path / "s.md")])
    out = capsys.readouterr().out
    assert rc == 2, f"自证：写不下去时退了 `{rc}` —— 该退 `2`（没测到）"
    assert "没测到" in out and "没落成" in out


def test_a_good_place_still_writes_the_artifacts(monkeypatch, tmp_path):
    """反向对照：落点好着、写也写得成的时候，两份产物照落、退出码照原样。

    少了这一条，一个「一律退 `2`」的实现也能让上面那两条全绿 —— 而它会把裁决
    唯一的真发现（判据恒真）整个藏起来。这里连**退出码 0** 一起验：全通过、
    没有恒真，就该是 `0`。
    """
    monkeypatch.setattr(A, "run", lambda: _FAKE_ADJ)
    monkeypatch.setattr(A, "render_markdown", lambda rep: "（现造的）")

    js, md = tmp_path / "a.json", tmp_path / "a.md"
    rc = A.main(["--json", str(js), "--md", str(md)])

    assert rc == 0, f"落点好着、产物也该落成，却退了 `{rc}`"
    assert js.is_file() and md.is_file(), "落点好着，两份产物却没落下来"
    assert json.loads(js.read_text(encoding="utf-8"))["summary"]["total"] == 1, (
        "落下来的 json 不是这一场的产物")
