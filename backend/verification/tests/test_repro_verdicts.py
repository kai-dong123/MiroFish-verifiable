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
