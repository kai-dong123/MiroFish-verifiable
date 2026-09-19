"""「后果」那一列必须由读数算出来 —— 钉住这条，因为写死的那版从来不会报错。

这个文件是被一次真实的翻车逼出来的。`repro_02` 第三节那张表曾经把
「后果」写成字面量，于是有过一次运行一边打出 `3.35 ms / 9.66 拍`、
一边宣称「同拍 → 碰撞才发生」—— **同一张表里读数和结论互相打脸**。

那种错特别阴，因为它不抛异常：装置照样退出 0、汇总照样 3/3，
只有人盯着表格一行行看才发现。所以这里把「判定跟着读数走」写成断言。

## 这个文件真正钉的是什么

不是「`_tick_verdict` 返回了我想要的字符串」，而是**一个不变式**：

    表里说「同拍」的话，那一行的 gap 就必须真的小于 tick；反之亦然。

`test_verdict_never_contradicts_its_own_numbers` 在一整片
`(gap, tick)` 网格上扫这个不变式 —— 将来有人再把结论写死，那条会先红。
"""

from __future__ import annotations

import pytest

from verification.repro_02_timestamp import _tick_verdict

MS = 1e-3

#: 判词里表示「同一拍」和「跨拍」的词。**每边都要列全**：
#: 正常判词说「同拍 / 跨拍」，与预期相反时说的是「同一拍 / 跨到 N 拍」，
#: 四种字面各不相同 —— 只认其中一个会把另外两个漏判成「没说」。
_SAME_WORDS = ("同拍", "同一拍")
_CROSS_WORDS = ("跨拍", "跨到")


def _asserts_same(verdict: str) -> bool:
    """这句判词是在说「同一拍」吗（「与预期相反」那种也算）。"""
    return any(w in verdict for w in _SAME_WORDS)


def _asserts_cross(verdict: str) -> bool:
    return any(w in verdict for w in _CROSS_WORDS)


def test_the_word_probes_actually_discriminate():
    """先证明上面两个探针**分得开**四种字面 —— 否则整个文件都是空的。

    这是自带的自检：探针要是恒真或恒假，底下那些断言就全是摆设。
    """
    assert _asserts_same("同拍 → 碰撞才发生")
    assert _asserts_same("**同一拍**（与预期相反）")
    assert _asserts_cross("跨拍 → 误打误撞免疫")
    assert _asserts_cross("**跨到 11 拍**（与预期相反）")

    # 互斥：没有一种判词会同时落在两边
    for v in ("同拍 → 碰撞才发生", "**同一拍**（与预期相反）",
              "跨拍 → 误打误撞免疫", "**跨到 11 拍**（与预期相反）"):
        assert _asserts_same(v) != _asserts_cross(v), f"两种探针同时命中了：{v!r}"


# --------------------------------------------------------------------------
# 不变式：判词不能和自己的数字打架（这是本文件的重点）
# --------------------------------------------------------------------------


#: 一片有代表性的网格：正常情形、边界、以及「与预期相反」的两种。
GRID = [
    (0.0, 0.40 * MS), (0.10 * MS, 0.40 * MS), (0.39 * MS, 0.40 * MS),
    (0.40 * MS, 0.40 * MS), (0.41 * MS, 0.40 * MS), (1.0 * MS, 0.40 * MS),
    (10.0 * MS, 0.40 * MS), (120.0 * MS, 0.40 * MS),
    (0.0, 1.00 * MS), (0.99 * MS, 1.00 * MS), (1.01 * MS, 1.00 * MS),
    (3.35 * MS, 0.302 * MS), (3.80 * MS, 0.341 * MS),
]


@pytest.mark.parametrize("gap,tick", GRID)
@pytest.mark.parametrize("want_same", [True, False])
def test_verdict_never_contradicts_its_own_numbers(gap, tick, want_same):
    """**核心不变式**：说「同拍」就必须真 `gap < tick`，说「跨拍」就必须真不满足。

    两边都取 `want_same`，是为了确保这条在「符合预期」和「与预期相反」
    两种走法下都成立 —— 写死的那版正是在第二种走法下露的馅。
    """
    verdict = _tick_verdict(gap, tick, want_same)

    assert _asserts_same(verdict) != _asserts_cross(verdict), \
        f"判词没说清是同拍还是跨拍：{verdict!r}"

    if gap < tick:
        assert not _asserts_cross(verdict), \
            f"gap={gap} < tick={tick} 却是「跨拍」判词：{verdict!r}"
    else:
        assert not _asserts_same(verdict), \
            f"gap={gap} >= tick={tick} 却是「同拍」判词：{verdict!r}"


# --------------------------------------------------------------------------
# 回归：把翻车那次的原样钉住
# --------------------------------------------------------------------------


def test_the_actual_regression_is_reported_not_smoothed():
    """那次翻车的原样：修好之后量出 3.35 ms、当拍 0.302 ms，预期是同拍。

    真实结果是**跨到 11 拍**。这一格以前会说「同拍 → 碰撞才发生」。
    现在它必须说「与预期相反」—— **不许悄悄折回预期那一侧。**
    """
    verdict = _tick_verdict(3.35 * MS, 0.302 * MS, want_same=True)

    assert "与预期相反" in verdict, f"没报出与预期不符：{verdict!r}"
    assert _asserts_cross(verdict), f"判词和 11 拍这个读数不一致：{verdict!r}"
    assert "11" in verdict, f"没把实测的拍数写出来：{verdict!r}"


def test_opposite_direction_of_surprise_is_also_reported():
    """反方向也一样：缺陷那行要是量出同拍，同样不许装作符合预期。"""
    verdict = _tick_verdict(0.05 * MS, 0.40 * MS, want_same=False)

    assert "与预期相反" in verdict, f"没报出与预期不符：{verdict!r}"
    assert _asserts_same(verdict), f"判词和读数不一致：{verdict!r}"


# --------------------------------------------------------------------------
# 符合预期时，判词该怎么说
# --------------------------------------------------------------------------


def test_defect_row_crossing_many_ticks():
    """缺陷那行的常态：一百多毫秒、上百拍。"""
    verdict = _tick_verdict(120.0 * MS, 0.40 * MS, want_same=False)

    assert verdict == "跨拍 → 误打误撞免疫", verdict


def test_fixed_row_within_one_tick():
    """修好那行的常态：落在同一拍。"""
    verdict = _tick_verdict(0.0, 0.40 * MS, want_same=True)

    assert verdict == "同拍 → 碰撞才发生", verdict
    assert "与预期相反" not in verdict


# --------------------------------------------------------------------------
# 边界与退化输入
# --------------------------------------------------------------------------


def test_boundary_gap_equal_to_tick_counts_as_crossed():
    """`gap == tick` 算**跨拍** —— 判据是严格的 `gap < tick`。

    顶格不算同拍：同拍的定义是「读数落在同一格里」，恰好差一整格就不是。
    这一格单独钉，因为 `<=` 和 `<` 在这里只差一个字符，而两种写法都「看着对」。
    """
    assert _tick_verdict(0.40 * MS, 0.40 * MS, want_same=False) \
        == "跨拍 → 误打误撞免疫"


def test_zero_tick_does_not_explode():
    """一拍量不出来（返回 0）时不许除零 —— 那正是「没测到」的情形。

    这时 `gap < tick` 不成立，按跨拍记；`want_same=True` 会报「与预期相反」，
    也就是说**它不会把「量不到」悄悄算成通过**。
    """
    verdict = _tick_verdict(1.0 * MS, 0.0, want_same=True)

    assert isinstance(verdict, str) and verdict
    assert "与预期相反" in verdict, f"量不到一拍却当成符合预期：{verdict!r}"


def test_negative_tick_does_not_explode():
    """一拍量成负数（不该发生）也不许炸 —— 装置宁可按异常记，不许中断。"""
    verdict = _tick_verdict(1.0 * MS, -0.40 * MS, want_same=True)

    assert isinstance(verdict, str) and verdict


# ---------------------------------------------------------------------------
# 判据不许绑在宿主机上
# ---------------------------------------------------------------------------
#
# 2026-09-19：把装置搬到 Linux 上跑（CPython 3.11.16，时钟刻度 100 ns，
# 本机 Windows 是 375500 ns），**两条判据当场翻成「否决」**：
#
#   * `repro_02` 的那一臂间隔取的是「当场量到的一拍」—— 在刻度比 camel 那个
#     `1e-6` 偏移粗的机器上，它恰好等于「跨过了那个偏移」，于是看着像「跨拍就
#     免疫」；换到刻度更细的机器上同一臂照样违反。
#   * `repro_03` 的判据取的是「本机 1 微秒那一格就翻」—— 那个数其实是**这台
#     机器的调度粒度**，Linux 上要 100 微秒才翻。
#
# 两处改法是同一个：**判据的输入要写成与宿主机无关的量**（camel 的偏移、
# 两平台都翻的栅格点），本机量到的数降级成读数。
#
# 下面两条把这件事钉死。它们看的是**源码的形状**，不跑那两个脚本 ——
# 因为要防的正是「下次谁又把判据写回本机的数」，而那种改动跑起来照样绿。

import ast
import pathlib

from verification import repro_02_timestamp as _R2
from verification import repro_03_concurrency as _R3


def _tree(mod):
    return ast.parse(pathlib.Path(mod.__file__).read_text(encoding="utf-8"))


def _loop_tuples(tree):
    """源码里所有「`for ... in (元组, 元组, ...)`」的字面元组。"""
    for node in ast.walk(tree):
        if isinstance(node, ast.For) and isinstance(node.iter, ast.Tuple):
            got = [e for e in node.iter.elts
                   if isinstance(e, ast.Tuple) and len(e.elts) == 3]
            if got:
                yield got


def test_the_timestamp_arms_are_written_in_units_of_the_offset_not_the_tick():
    """`repro_02` 四臂的间隔必须**按 camel 那个偏移**写，不按本机量到的一拍写。

    先认值（半个偏移 / 两倍偏移这种换算不能在重构里被改掉），再认写法
    （源码里必须看得见 `CAMEL_BUMP`）—— 只认值的话，有人把本机量到的那一拍
    直接写死成一个数字，值碰巧对了也看不出来。
    """
    arms = [t for t in _loop_tuples(_tree(_R2))
            if "守卫关" in ast.unparse(t[0].elts[0])]
    assert arms, "没在 repro_02 源码里找到那四臂 —— 这条断言成了空话"

    gaps = [e.elts[1] for e in arms[0]]
    got = [eval(ast.unparse(g), {"CAMEL_BUMP": _R2.CAMEL_BUMP})  # noqa: S307
           for g in gaps]
    want = [0.0, _R2.CAMEL_BUMP / 2, _R2.CAMEL_BUMP * 2, 0.0]
    assert got == want, (
        f"四臂的间隔不再是「0 / 半个偏移 / 两倍偏移 / 0」：{got}\n"
        f"判据的输入必须与宿主机的时钟刻度无关，否则换台机器就翻面。")

    # 同拍那两臂的间隔就是 0，没什么可写的；**要按偏移写的是跨拍那两臂**。
    for g in gaps:
        text = ast.unparse(g)
        if eval(text, {"CAMEL_BUMP": _R2.CAMEL_BUMP}) == 0.0:   # noqa: S307
            continue
        assert "CAMEL_BUMP" in text, (
            f"这一臂的间隔写成 `{text}` —— 没有以 `CAMEL_BUMP` 为单位。"
            f"换成宿主机的数（比如当场量到的一拍）会让判定随机器变。")


def test_no_host_measured_quantity_decides_the_concurrency_criterion():
    """`repro_03` 的判据那一格必须是字面量，本机量到的最小格点不得有否决权。

    量出来的 `smallest`（本机 1 微秒 / Linux 100 微秒）是**读数**，它进报告、
    不进判据。判据取的是栅格上两个平台都翻的那一格。
    """
    tree = _tree(_R3)

    cuts = [n for n in ast.walk(tree)
            if isinstance(n, ast.Assign)
            and any(getattr(t, "id", None) == "cut" for t in n.targets)]
    assert len(cuts) == 1, f"`cut` 应恰好定义一次，实为 {len(cuts)} 次"
    cut = cuts[0].value
    assert isinstance(cut, ast.Constant) and cut.value == 1e-4, (
        f"判据那一格必须是写死的字面量 0.1 毫秒，实为 `{ast.unparse(cut)}`；"
        f"写成算出来的量就会随宿主机变。")

    smallest = [n for n in ast.walk(tree)
                if isinstance(n, ast.Assign)
                and any(getattr(t, "id", None) == "smallest" for t in n.targets)]
    assert smallest, "源码里没有 `smallest` —— 这条断言成了空话"

    # 决定红绿的那些 `if`（分支里给 `ok` 赋值的那些）的条件里出现过的名字。
    # **只扫这些**，不扫全部 `if`：`if smallest is not None:` 这种是「读数拿得
    # 到就打印一行」的护栏，它不决定红绿 —— 把它算进来，这条断言就成了
    # 「不许打印本机读数」，那是另一件事。
    def _decides_ok(node) -> bool:
        for sub in list(node.body) + list(node.orelse):
            for inner in ast.walk(sub):
                if isinstance(inner, ast.Assign) and any(
                        getattr(t, "id", None) == "ok" for t in inner.targets):
                    return True
        return False

    in_tests = {n.id for node in ast.walk(tree)
                if isinstance(node, ast.If) and _decides_ok(node)
                for n in ast.walk(node.test) if isinstance(n, ast.Name)}
    assert in_tests, "一个「给 `ok` 赋值」的 `if` 都没扫到 —— 这条断言成了空话"
    assert "cut" in in_tests, (
        "`cut` 没出现在任何分支条件里 —— 那它就不是判据的输入，"
        "上面那条「必须是字面量」也就没钉住东西")
    assert "smallest" not in in_tests, (
        f"本机量出来的 `smallest` 进了分支条件：{sorted(in_tests)}。"
        f"那是**这台机器**的调度粒度（Windows 1 微秒、Linux 100 微秒），"
        f"拿它当判据就是把判据绑在宿主机上。")

    src = ast.unparse(tree)
    assert "smallest_flipped_s" in src, (
        "`smallest` 降级成读数之后仍须进报告（`smallest_flipped_s`），"
        "否则就是把它藏起来而不是交代清楚")
