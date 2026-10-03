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

import ast
import pathlib
import sys

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


def test_the_frozen_clock_is_structural_not_a_written_flag():
    """复现二第二节那四臂，**必然**是从冻钟里跑出来的 —— 靠签名，不靠那句话。

    读数里有一格 `"frozen_clock": True`，它是**写死的常量**。它能被写成常量而不是
    一句空话，唯一的理由是 `_run_two_calls` 的 `freeze` 参数**没有默认值**：
    谁调用它都必须给出冻钟起点，于是任何产出读数的臂都必然是冻的。

    这条测试钉的就是那个签名。**没有它**，有人给 `freeze` 加个默认值（比如
    `freeze=None` 表示「不冻钟」）之后，读数会照旧印 `True` —— 而那一格正是
    第二节全部判据的前提（冻钟把它们变成逐位可复核、不读物理时钟）。
    **一个写死的 `True` 后面必须有一样东西替它作证，否则它就是在替一次
    没发生的冻钟作证。**
    """
    import inspect

    from verification import repro_02_timestamp as R2

    sig = inspect.signature(R2._run_two_calls)
    assert "freeze" in sig.parameters, (
        "`_run_two_calls` 没有 `freeze` 形参了 —— 冻钟那条路径变了")
    assert sig.parameters["freeze"].default is inspect.Parameter.empty, (
        "`freeze` 有默认值了 —— 那么「这条读数取自冻钟」就不再是结构保证，"
        "而读数里那一格还在印写死的 `True`")

    # 反向对照：这个判据**分得开**两种签名。少了它，一个恒判「没有默认值」的
    # 实现也能让上面那条变绿 —— 而那正是它要拦的情形。
    def _with_default(*, freeze=None):
        return None

    got = inspect.signature(_with_default).parameters["freeze"].default
    assert got is None and got is not inspect.Parameter.empty, (
        "这个判据连「有默认值」都认不出来 —— 上面那条因此是恒真的")


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

# ---------------------------------------------------------------------------
# 前提不成立时：**没测到**，不是「没达到预期」
# ---------------------------------------------------------------------------
#
# 这一节钉的是一条实测过的翻车（2026-09-19）：**断网 + 分词器缓存是冷的**时，
# `repro_01` / `repro_02` 会抛穿一个 `requests.exceptions.*`，退出码 1 ——
# 按装置那张表，「1」就是「没达到预期」。于是装置会去**断言上游那两个缺陷还在**，
# 而实际上一个读数都没取到。`e2e_stub` 更整齐：三档臂一起报「没达到预期」。
#
# 根因是分词器**懒加载**：`OpenAITokenCounter` 的构造不碰网络，第一次 `encode()`
# 才去取那份编码表。所以它躲过了 `pieces()` 里那个 `except`。
#
# 这两条测试都带反向对照 —— 否则「取不到分词器就返回 None」可以被一个恒真的
# `return None` 满足。

def test_a_missing_tokenizer_makes_the_probe_give_up_instead_of_raising(monkeypatch):
    """取不到分词器时，`pieces()` 必须**返回 None**（= 没测到），而不是抛出去。"""
    from verification import _probe as P

    monkeypatch.setattr(P, "tokenizer_or_none", lambda: None)
    assert P.pieces() is None, (
        "分词器取不到，`pieces()` 却照样返回了部件 —— 下一步就会抛穿脚本，"
        "而退出码 1 在装置的表里是「没达到预期」")


def test_the_tokenizer_probe_is_not_vacuously_none(monkeypatch):
    """反向对照：`pieces()` 不是恒真的 `None`，真实探针取得到时也该给出部件。

    **①和②分开写，为的是这一格不再取决于本机的网络。** 原先它开口就断言
    「本机取得到分词器」—— 于是**没网、或临时缓存被清过**的机器上它是红的，
    而红的时候报的是「失败」不是「没测到」：与本节开头钉的那次翻车同一个病，
    只是这回犯在测试自己身上。

    * ① **任何机器上都有条件判**：把探针钉成「拿得到」，`pieces()` 必须真的
      给出部件 —— 这条才是「上面那条测试不是空话」的正面对照；
    * ② 是本机的**真实读数**：取不到就记「没测到」（跳过），不记失败
      —— 与 `e2e_stub` / `run_all` 那一侧同样的口径。
    """
    from verification import _probe as P

    monkeypatch.setattr(P, "tokenizer_or_none", lambda: True)
    assert P.pieces() is not None, (
        "探针说拿得到，`pieces()` 却是 None —— 那第一条测试是恒真的")

    monkeypatch.undo()
    if P.tokenizer_or_none() is None:
        pytest.skip("本机取不到分词器（编码表没下过 / 临时缓存被清过）"
                    " —— 这一格没测到，不是没达到预期")
    assert P.pieces() is not None, (
        "分词器拿得到，`pieces()` 却是 None —— 那第一条测试是恒真的")


class _FakeMemory:
    def __init__(self, ctx_tokens, *, boom=False):
        self._ctx, self._boom = ctx_tokens, boom

    def get_context(self):
        if self._boom:
            raise RuntimeError("现造：取上下文失败")
        return None, self._ctx


class _FakeAgent:
    def __init__(self, ctx_tokens, *, boom=False):
        self.memory = _FakeMemory(ctx_tokens, boom=boom)


class _FakeCreator:
    def __init__(self, limit):
        self.token_limit = limit


def test_a_budget_that_could_not_be_measured_is_none_not_a_sentinel_number():
    """量不到残余预算 → `None`（**没测到**），不是一个像数的哨兵。

    这条挡的是一个具体的写法：原先失败时返回 `-1`。而 `token_limit - ctx_tokens`
    **真的能为负** —— 上下文被灌过上限正是那个切片缺陷本身 —— 所以 `-1` 和一次
    **合法测量**撞车：读到 `-1` 的人分不出「没量到」和「量到了，是 −1」。
    """
    from verification import _probe as P

    got = P.residual_budget(_FakeAgent(0, boom=True), _FakeCreator(100))
    assert got is None, (
        f"取上下文失败时返回了 `{got!r}` —— 该是 `None`；"
        "退回一个数会让「没量到」看起来像一次测量")


def test_a_genuinely_negative_budget_is_a_real_measurement():
    """反向对照：**真的**量到 −1 时必须原样返回 −1。

    没有这一条，一个恒返回 `None` 的实现也能让上面那条变绿 ——
    而「预算被压成负数」恰恰是这套装置要去证明的那件事，藏起来就等于把
    缺陷本身抹掉。这条同时钉住「`None` 是留给没测到的、不是留给小数字的」。
    """
    from verification import _probe as P

    assert P.residual_budget(_FakeAgent(101), _FakeCreator(100)) == -1, (
        "真的量到 −1（上下文比上限还大）却没返回 −1 —— 那正是切片缺陷的现场")
    assert P.residual_budget(_FakeAgent(40), _FakeCreator(100)) == 60, (
        "正常情形下算错了")


def test_a_failed_precondition_is_undecided_not_a_verdict():
    """e2e 的三档臂：前提不成立 → **没测到**（2），不是「没达到预期」（1）。

    **顺序就是判据**：`rc != 0` 有两类原因 —— 「跑了但撞上了」和「压根没跑起来」。
    只有第一类才叫「真有东西要看」。前提那一档必须排在 `rc` 前面。
    """
    from verification import e2e_stub as E

    run = {"timeout": False, "rc": 1, "counters": None, "db_posts": None,
           "precondition_unmet": True}
    assert E._arm_code(run) == E.ARM_UNMEASURED, (
        "前提不成立却报成了「没达到预期」—— 那等于替一个没跑起来的实验宣布结论")


def test_a_real_child_failure_is_still_a_verdict():
    """反向对照：前提**成立**、子进程真失败时，仍须报「没达到预期」。

    少了这条，一个「无条件返回没测到」的实现也能让上面那条测试变绿 ——
    而那会把装置里唯一一类真发现藏起来。
    """
    from verification import e2e_stub as E

    run = {"timeout": False, "rc": 1, "counters": None, "db_posts": None,
           "precondition_unmet": False}
    assert E._arm_code(run) == E.ARM_FAILED, (
        "子进程真失败（rc != 0）却被记成「没测到」—— 那是把发现藏起来")


def test_the_precondition_is_asked_before_the_arms_run():
    """`main()` 里**先问前提**，而不是等三档臂各自倒掉再猜原因。

    这条是源码级的：两件事都写在 `main()` 里，顺序错了就不会有任何东西变红 ——
    而错序的后果正是这条 bug 本身（三档齐刷刷 rc != 0，看起来跟「守卫没被走到」
    一模一样）。
    """
    import ast
    import inspect

    from verification import e2e_stub as E

    tree = ast.parse(inspect.getsource(E.main))
    src = ast.unparse(tree)
    assert "tokenizer_or_none" in src, (
        "`main()` 里没有先问前提 —— 三档臂会各自倒掉，然后被记成「没达到预期」")
    assert src.index("tokenizer_or_none()") < src.index("_run_arm("), (
        "前提问得比跑臂还晚 —— 那就拦不住了：臂已经倒掉了")


# ---------------------------------------------------------------------------
# 出口：**三种退出码，不是两种** —— 而且必须真的从 `main()` 走到 `SystemExit`
# ---------------------------------------------------------------------------
#
# `_probe.exit_with` 是三份复现共用的出口，本文件此前**一次都没提到过它**
# （`grep exit_with tests/` 零命中）。它防的是一个具体的写法：
#
#     0 if verdict else 1
#
# `None` 是假值，所以那个写法下 `main()` 返回 `None`（**没测到**）会退 **0**
# —— 而按装置自己的表，`0` 是「达到预期」。**一次一个读数都没取到的运行
# 会以「一切正常」收场**，正是这套装置专门去抓别人的那件事。
#
# 后两条看**源码的形状**：`exit_with` 自己写对了，可谁要是哪天把
# `if __name__` 下面那行改回 `raise SystemExit(main())`，三态当场丢两态 ——
# 而那种改动**跑起来照样绿**（`SystemExit(None)` 退 0，本机分母从不缺席）。

def test_exit_with_says_three_things_not_two():
    """`True`→`0`、`False`→`1`、`None`→`2`。"""
    from verification import _probe as P

    for verdict, want in ((True, 0), (False, 1), (None, 2)):
        with pytest.raises(SystemExit) as e:
            P.exit_with(verdict)
        assert e.value.code == want, (
            f"`exit_with({verdict!r})` 退了 {e.value.code}，该是 {want}")


def test_not_measured_is_not_silently_reported_as_success():
    """反向对照：单挑 `None` —— 它是唯一一个**假值**的三态出口。

    上面那条在 `True`/`False` 上碰巧对了的写法（`0 if verdict else 1`），
    只在 `None` 身上露馅。所以这一条必须单独把 `None` 拎出来验：
    既不许退 `0`（假绿），也不许退 `1`（把「压根没跑起来」报成「跑了但没达到预期」，
    等于指人去查一个不存在的失败）。
    """
    from verification import _probe as P

    with pytest.raises(SystemExit) as e:
        P.exit_with(None)
    assert e.value.code != 0, (
        "「没测到」退成了 `0` —— 装置会带着一次什么都没量的运行报「达到预期」出门")
    assert e.value.code == 2, (
        f"「没测到」退成了 {e.value.code} —— 该是 2；"
        "折进 1 就会让读者去查一个不存在的「没达到预期」")


def _exit_statement(tree):
    """三态 `main()` 的出口那一句长什么样；不是三态的返回 `"不适用"`。

    判据是**返回标注**，不是文件里有没有 `exit_with` 这个词 —— 只查关键词的话，
    标注是 `-> bool | None` 却照样 `raise SystemExit(main())` 的模块会被放过。
    """
    main = next((n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == "main"), None)
    assert main is not None, "这个模块里没有 `main()`"
    ann = ast.unparse(main.returns) if main.returns else ""
    if not ("bool" in ann and "None" in ann):
        return "不适用"
    guard = next((n for n in tree.body
                  if isinstance(n, ast.If) and "__name__" in ast.unparse(n.test)), None)
    assert guard is not None, "三态 `main()` 却没有 `if __name__` 出口"
    return ast.unparse(guard.body[0])


def test_a_three_state_main_is_not_routed_through_bare_systemexit():
    """三态的 `main()` 必须走 `exit_with`。`raise SystemExit(main())` 会把它压成两态。

    `SystemExit(None)` 的退出码是 **0** —— `main()` 返回 `None`（没测到）时，
    这条路子安安静静地报成功。
    """
    from verification import repro_01_slicing as _R1

    for mod in (_R1, _R2, _R3):
        got = _exit_statement(_tree(mod))
        assert got != "不适用", (
            f"`{mod.__name__}` 的 `main()` 不再是 `-> bool | None` 了 —— "
            "三态的契约变了？先看一眼再动这条")
        assert "exit_with" in got, (
            f"`{mod.__name__}` 的 `main()` 声明了 `-> bool | None`，"
            f"出口却是 `{got}` —— 三态被压成两态")


def test_that_source_shape_check_can_actually_go_red():
    """反向对照：`_exit_statement` 真的分得开那两种出口。

    少了这条，一个恒返回 `"exit_with"` 的实现也能让上面那条测试变绿 ——
    而它本该拦住的正是 `raise SystemExit(main())`。
    """
    bad = _exit_statement(ast.parse(
        "import sys\n"
        "def main() -> bool | None:\n"
        "    return None\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n"))
    assert "exit_with" not in bad, (
        f"`raise SystemExit(main())` 被判成了 `{bad}` —— 那条检查是恒绿的")
    assert "SystemExit" in bad, (
        f"读出来的不是出口那一句，而是 `{bad}` —— 探针指错了地方")

    good = _exit_statement(ast.parse(
        "from verification import _probe as P\n"
        "def main() -> bool | None:\n"
        "    return None\n"
        "if __name__ == '__main__':\n"
        "    P.exit_with(main())\n"))
    assert "exit_with" in good, f"写对了的出口却读成 `{good}`"

    # 返回标注不是三态的模块**不适用**，不该被这条检查扫进来（`selfproof` 就是）。
    assert _exit_statement(ast.parse(
        "def main() -> int:\n"
        "    return 0\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n")) == "不适用"


# ---------------------------------------------------------------------------
# 同一类bug在**汇总那一行**上的残骸：句子写死了「先看没通过的那条」。
#
# 前半截修好之后（前提不成立 → 报「没测到」），断网时汇总会变成
# `1/3 条达到预期 —— 先看上面没通过的那条` —— 可另外两条根本不是
# 「没通过」，是**没量到**。于是它又叫读者去查一个不存在的失败，
# 跟修之前是同一句话、同一个错，只是矮了一层。
#
# 所以那句话必须**按缺口是哪一类**分岔。反向对照同样要有：
# 真有 `1` 的时候还得叫人去看，不然这条修法会顺手把真发现也糊掉。

def _results(*codes):
    """把退出码列表包成 `_write_report` / 汇总看到的那种 `results`。"""
    return [(f"m{i}", f"第{i}条", rc, "") for i, rc in enumerate(codes)]


def test_a_purely_unmeasured_shortfall_does_not_send_anyone_looking():
    """缺口全是「没测到」时，**不许**出现「没通过」或「先看…那条」。"""
    from verification.run_all import _what_to_look_at

    tail = _what_to_look_at(_results(0, 2, 2), "上面")
    assert "先看" not in tail, (
        f"整批缺口都是「没测到」，汇总却叫人「先看那条」：{tail!r} —— "
        "那是在指人去查一个不存在的失败")
    # 提「没通过」可以，**只能是被否掉的那种提法**（口径红线：这几个词
    # 出现时必须是否定式）。所以查的是「有没有说它」，不是「有没有这个词」。
    assert "不是「没通过」" in tail, (
        f"缺口是「没测到」，汇总那句话里却没把这一点说破：{tail!r}")


def test_a_real_failure_still_sends_people_looking():
    """反向对照：真有一条 `rc == 1` 时，那句话必须照旧叫人去看。"""
    from verification.run_all import _what_to_look_at

    tail = _what_to_look_at(_results(0, 1, 0), "上面")
    assert "先看上面没通过的那条" in tail, (
        f"真有「没达到预期」却不叫人去看：{tail!r} —— 那是把发现藏起来")


def test_a_mixed_shortfall_says_both_are_there():
    """两类缺口同时在时，**两类都要说到**，不许只提其中一类。"""
    from verification.run_all import _what_to_look_at

    tail = _what_to_look_at(_results(1, 2, 0), "下面")
    assert "先看下面没通过的那条" in tail and "没测到" in tail, (
        f"两类缺口同时存在，汇总只提了一类：{tail!r}")


def test_a_clean_run_has_no_pointer_at_all():
    """全绿时那句尾巴必须是空的 —— 别在没事的时候也加一句。"""
    from verification.run_all import _what_to_look_at

    assert _what_to_look_at(_results(0, 0, 0)) == ""


# ---------------------------------------------------------------------------
# 同一类毛病的第二处：那句「边界那条不适用」的免责声明。
#
# 它原先**无条件**打印，而且按下标说「第 3 条」。而第 3 条在常态下报的是
# 「达到预期」（它量的是边界，本来就该达到自己声明的预期）—— 于是屏幕上
# 每次都在替一个**没发生的「没达到预期」**开脱。

def test_a_clean_boundary_case_needs_no_disclaimer():
    """三档全绿 → 一个字都不说。

    这是**常态**，也正是原先那版出错的地方：它在这种时候照样替第 3 条开脱。
    """
    from verification.run_all import _boundary_disclaimer

    assert _boundary_disclaimer(_results(0, 0, 0)) == [], (
        "边界那条报的是「达到预期」，却还是给它补了一句「不适用」—— "
        "那是替一件没发生的事作解释")


def test_a_boundary_case_that_really_was_not_expected_says_so():
    """反向对照：边界那条**真**报「没达到预期」时，这句必须出现。"""
    from verification.run_all import _boundary_disclaimer

    got = "\n".join(_boundary_disclaimer(_results(0, 0, 1)))
    assert got, "边界那条真的报了「没达到预期」，却一个字都不说"
    assert "边界" in got, f"说了话，但没点明那是边界：{got!r}"


def test_a_failing_fix_gets_no_boundary_excuse():
    """反向对照之二：**可修**那两条报「没达到预期」时，不许拿边界来开脱。

    少了这条，一个「只要有任何一条 rc == 1 就说是边界」的实现也能让上面
    那条变绿 —— 而那会把一处真的修法失效糊过去。
    """
    from verification.run_all import _boundary_disclaimer

    assert _boundary_disclaimer(_results(1, 0, 0)) == [], (
        "可修的那条没达到预期，却拿「边界」替它开脱 —— 那是把发现藏起来")
    assert _boundary_disclaimer(_results(0, 1, 0)) == [], (
        "同上：第 2 条也是「可修」")


def test_a_boundary_case_that_was_not_measured_gets_no_excuse():
    """「没测到」不是「没达到预期」—— 不许用这句去解释一次没量到的运行。"""
    from verification.run_all import _boundary_disclaimer

    assert _boundary_disclaimer(_results(0, 0, 2)) == [], (
        "边界那条根本没测到，却给它补了一句「这不是修法失效」—— "
        "两件事要看的地方完全不同")


# ---------------------------------------------------------------------------
# `_run_one` 的超时：卡死要占住 `2`，不能占 `1`
# ---------------------------------------------------------------------------

def _python(code: str) -> list:
    """一条现成的子进程命令。超时那两条要有一条**真的会久留**的东西可掐。"""
    import sys
    return [sys.executable, "-c", code]


def test_a_repro_that_never_returns_is_not_measured():
    """一条**永远不返回**的复现要报「没测到」—— 不是「没达到预期」，也不是挂着。

    原先 `_run_one` 没有上限：真发生这种事（并发那条最可能），`run_all` 就一直
    在那儿等，报告一个字都不落 —— 屏幕上**什么判定都没有**，比三种状态里最差的
    那种还少一层。
    """
    from verification.run_all import _run_one

    rc, body = _run_one("never", echo=False, timeout=1.0,
                        argv=_python("import time; time.sleep(60)"))
    assert rc == 2, f"一条没跑完的复现被译成了 `{rc}` —— 「没测到」必须是 `2`"
    assert "没测到" in body, (
        "掐掉了却没在正文里说为什么 —— 报告里它会和「跑完了但没达到预期」"
        "长得一模一样")


def test_a_repro_that_returns_keeps_its_own_code():
    """反向对照：跑得完的那条，返回码仍是它自己的 —— 超时器不许抢。

    这一条专门盯**撞车**：本机实测，被 `kill()` 之后 `returncode` 也是 **`1`**。
    一个「到点了就掐掉、然后照返回码翻译」的实现，会把一条**根本没跑完**的复现
    报成「没达到预期」—— 一个听起来像发现、其实是空白的结论。
    """
    from verification.run_all import _run_one

    rc, body = _run_one("exits_1", echo=False, timeout=30.0,
                        argv=_python("import sys; sys.exit(1)"))
    assert rc == 1, f"跑完了的复现，返回码被改成了 `{rc}`"
    assert "没测到" not in body, "它跑完了，正文里不该出现「没测到」那句话"

    rc, body = _run_one("exits_0", echo=False, timeout=30.0,
                        argv=_python("print('ok')"))
    assert rc == 0, f"跑完了而且是好的复现，返回码被改成了 `{rc}`"


def test_an_out_of_contract_exit_code_is_not_measured():
    """**契约外的退出码 = 没跑完。** 三条复现的契约只有 `{0, 1, 2}`。

    原先 `_run_one` 原样返回 `proc.wait()`，而 POSIX 上死于信号的子进程给的是
    **负数**（`SIGKILL` 给 `-9`）。它一旦进了 `main()` 的 `max(...)`，`0` 比任何
    负数都大 —— 于是一条**没跑成**的复现会从那个洞里被读成「达到预期」，进程还
    退 `0`：屏幕上打「2/3 条达到预期」，下面却印着「**不会**把没跑成的记成没达到
    预期」。那句话没说谎 —— 它记成了**更高**的一档。
    """
    from verification.run_all import _run_one

    rc, body = _run_one("exits_7", echo=False, timeout=30.0,
                        argv=_python("import sys; sys.exit(7)"))
    assert rc == 2, f"契约外的退出码 `7` 被译成了 `{rc}` —— 「没跑完」必须是 `2`"
    assert "没测到" in body, (
        "没跑完这件事得在正文里说出来，不能只在数字上悄悄改一格")


@pytest.mark.skipif(sys.platform == "win32",
                    reason="Windows 上 `wait()` 不返回负值（`kill` 给的是 `1`，"
                           "那一种撞车 `_probe.py` 已声明过），本机量不出负数")
def test_a_signal_killed_repro_is_not_measured():
    """真实来路：**被信号杀死**。

    `sys.exit(7)` 那一条证的是「契约外的值一律收进 `2`」；这一条证的是那个负值
    **真会来**：OOM killer、容器 `stop`、C 扩展段错误走的都是这条路，而它正是
    「一条复现压根没跑」最字面的样子。
    """
    import signal

    from verification.run_all import _run_one

    rc, body = _run_one(
        "killed", echo=False, timeout=30.0,
        argv=_python("import os, signal; os.kill(os.getpid(), signal.SIGKILL)"))
    assert rc == 2, f"被信号杀死的复现被译成了 `{rc}`"
    assert "没测到" in body, "被杀死这件事得在正文里说出来"


def test_the_return_code_alone_cannot_tell_a_kill_from_a_failure():
    """为什么非要单独占住 `2`：**光看返回码分不出这两种事**。

    把那个事实当场量出来（而不是写在注释里）：被掐死的进程，它的返回码可能是
    `1`，也就是「跑完了、只是没达到预期」那个码。所以「照返回码翻译」那条路走不
    通，超时必须在**上层**记一笔、自己写死 `2`。
    """
    import subprocess
    import time

    proc = subprocess.Popen(_python("import time; time.sleep(60)"),
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        time.sleep(0.5)
        proc.kill()
        killed = proc.wait()
    finally:
        if proc.poll() is None:
            proc.kill()
    assert killed != 2, (
        f"这台机器上，被掐死的进程退了 `{killed}` —— 恰好就是 `2`：那么 `2` 就"
        "不再独占「没测到」这个意思，本装置得换一个说法")


# ---------------------------------------------------------------------------
# 落点：写不出来时报「没测到」（`2`），不许报「没达到预期」（`1`）
# ---------------------------------------------------------------------------

def _nowhere(tmp_path) -> str:
    """一个**目录不存在**的落点。"""
    return str(tmp_path / "没有这个目录" / "x")


def test_the_out_path_check_discriminates(tmp_path):
    """落点这道门自己：好的放行、坏的拦下 —— 两个方向都要问。

    少了「好的放行」那一半，一个「一律拦下」的实现也能让下面那几条变绿。
    """
    from verification import _probe as P

    assert P.out_path_problem(str(tmp_path / "ok.md")) is None, (
        "目录存在、名字也正常，这道门却把它拦下了")
    assert P.out_path_problem(str(tmp_path / "ok.json")) is None

    assert P.out_path_problem(_nowhere(tmp_path)) is not None, (
        "目录根本不存在，这道门却放行了 —— 接下来那一步会抛 `FileNotFoundError`")

    (tmp_path / "一个目录.md").mkdir()
    assert P.out_path_problem(str(tmp_path / "一个目录.md")) is not None, (
        "落点是个目录、写不进文件，这道门也该拦")

    # 反向的一半：名字看着怪、但落点本身没问题 —— 不许拦。
    # `没有这个目录` 当**文件名**放在一个存在的目录里，是个好落点；
    # 只有它当**目录**、而那个目录不存在时才是坏的（上面那一条）。
    # 少了这一半，一个「名字里带敏感词就拦」的实现也能让上面全绿。
    assert P.out_path_problem(str(tmp_path / "没有这个目录")) is None, (
        "落点是个现有目录下的普通新文件，这道门不该拦")


def test_run_all_refuses_a_bad_out_place_before_running_the_repros(tmp_path, capsys):
    """落点不通 → 退 `2`，而且**一行活都不许白干**。

    「跑在动手之前」是这一条的实质：三个复现要跑一分来钟，等它们跑完再发现写不
    出去，等于把已经量到的读数连同退出码一起丢掉。那时按契约只能退 `1`，而 `1`
    的意思是「有真的要看的东西」—— 读者会去找一个并不存在的失败。
    """
    from verification import run_all as R

    rc = R.main(["--out", _nowhere(tmp_path)])
    out = capsys.readouterr().out

    assert rc == 2, (
        f"落点不通时退了 `{rc}` —— 该退 `2`（没测到）。退 `1` 会让人去查复现，"
        "而一条读数都没量到")
    assert "没测到" in out, "拦下了却没说为什么"
    assert "落点" in out, "得说清是**落点**的问题，不是读数的问题"
    assert "装置自检" not in out, (
        "这条在跑复现之前就该退出来 —— 屏幕上连开场白都打出来了，说明它先跑了")


def test_the_other_three_entry_points_refuse_a_bad_out_place_too(
        tmp_path, capsys, monkeypatch):
    """**六道入口，六道门。** 这三道此前**没有门**。

    没有门的后果不是「不便」：坏落点抛的 `FileNotFoundError` 没人接 → traceback →
    进程退 `1`，而三家的表里 `1` 分别是「没达到预期」（`e2e_stub`）、
    「不符」（`reconcile_selfcheck`）、「与声明不符」（`mutations`）—— **一个读数
    都没落下来，却宣布了一个发现。**

    ⚠️ 这三条各自把「动手那一步」（`_run_arm` / `run`）换成会炸的替身，所以它们
    同时证了两件事：① 拦下了（`rc == 2`）；② **拦在动手之前**（替身没被走到）。
    少了 ②，一个「先把活干完、再问落点」的实现也能让 `rc == 2` 成立 —— 而那时
    读数已经白量了一场。这也正是本条**敢**碰 `mutations` 的原因：替身把 `run()`
    换掉了，那套会改源码的留痕一步都不会跑。
    """
    from verification import e2e_stub as E
    from verification import mutations as MU
    from verification import reconcile_selfcheck as RC

    called = []

    def boom(*a, **k):                      # 「动手」那一步：被走到就该炸
        called.append(1)
        raise AssertionError("门在动手之前就该退 —— 它不该被走到")

    monkeypatch.setattr(E, "_run_arm", boom)
    assert E.main(["--out", _nowhere(tmp_path)]) == 2, "端到端那道门没拦住"

    monkeypatch.setattr(RC, "run", boom)
    assert RC.main(["--json", _nowhere(tmp_path),
                    "--md", _nowhere(tmp_path)]) == 2, "对账那道门没拦住"

    monkeypatch.setattr(MU, "run", boom)
    assert MU.main(["--json", _nowhere(tmp_path),
                    "--md", _nowhere(tmp_path)]) == 2, "留痕那道门没拦住"

    assert not called, "落点不通，却已经动过手了 —— 门必须在动手之前"
    out = capsys.readouterr().out
    assert "没测到" in out, "拦下了却没说为什么"
    assert "落点" in out, "得说清是**落点**的问题，不是读数的问题"


def test_the_report_writer_still_writes_when_the_place_is_good(tmp_path):
    """反向对照：落点好着的时候，两份产物照落。

    少了这一条，一个「永远拒收落点」的实现也能让上面那条变绿。
    （这里直接问写器，不走 `main()` —— `main()` 会把三条复现真跑一遍，一分来钟，
    这个测试不值得。跑得通不通由端到端那几条命令负责。）
    """
    from verification import run_all as R

    results = [("verification.repro_01_slicing", "切片", 0, "（现造的正文）")]
    md, js = R._write_report(str(tmp_path / "报告"), results, {},
                             0, ("（现造的）",))

    assert pathlib.Path(md).is_file() and pathlib.Path(js).is_file(), (
        f"落点好着，产物却没落下来：{md} / {js}")
    assert pathlib.Path(md).read_text(encoding="utf-8").strip(), "markdown 那份是空的"


def test_a_missing_number_does_not_disappear_behind_a_mismatch():
    """对账里「抽不出来」压过「不符」—— 两件事**各自说一遍**，不许互相顶掉。

    原先的写法是 `if missing and rc == 0: rc = 2`，配一个 `if/elif/else` 的收尾。
    于是：一行抽不出来、另一行不一致时，`rc` 早已因不一致变成 `1`，那一句不再
    升到 `2`；收尾又是一个 `elif`，只剩第一支成立时才说「抽不出来」。
    **结果是一句都没说**：读者拿到「两份材料对不上」，而其中一项**根本没量到**。

    这正是这台装置盯着别人的那件事（没量到被当成结论），只不过发生在它自己身上。
    修法是两道：`rc` 无条件升 `2`；两句各用一个 `if`，谁也不 `elif` 谁。
    """
    from verification import run_all as R

    transcripts = {
        "装置①": "被切成 **277 条**\n实增 554 token",
        # ① 的实增 token 与装置侧**不一致** —— 这一行该判「不符」。
        "草稿①": "→ 一条消息变成 277 条记录\ntoken 实增 999（现造的）",
        "装置②": "两次调用同拍：**0 处违反**",
        # ② 的草稿侧整块抽不出来 —— 这一行该判「没测到」。
    }

    rc, lines = R._reconcile(transcripts)
    body = "\n".join(lines)

    assert "× **不一致**" in body and "○ 抽不到" in body, (
        "这两行本来就该各判各的 —— 先确认这一条测的是「两者同时成立」那种局面")
    assert "抽不出来" in body, (
        "有一边抽不出来，正文却一个字没提 —— 缺读数被那处不一致顶掉了")
    assert "对不上" in body, (
        "两处不一致，正文却只说了「没测到」—— 更硬的那个事实不该被盖住")
    assert rc == 2, (
        f"退了 `{rc}`。有一项**根本没量到**时必须退 `2`：`1` 的意思是"
        "「量到了但对不上」，读者会去找一个并不存在的对不上")

    # 反向对照：两行都好着时必须退 `0`、说「同一组数」。少了这一半，一个
    # 「一律退 2」的实现也能让上面全绿。
    good = dict(transcripts)
    good["草稿②"] = "违反「tool_calls 后必须紧跟它的回执」： 0 处"
    good["草稿①"] = "→ 一条消息变成 277 条记录\ntoken 实增 554（现造的）"
    rc_ok, lines_ok = R._reconcile(good)
    assert rc_ok == 0, f"两行都一致时退了 `{rc_ok}`"
    assert "同一组数" in "\n".join(lines_ok)


#: 「0/1/2 → 一句话」那张表的判据里，拿来找词的两个词根。
#: `没达到预期` 里含 `达到预期`，所以两个就够盖住三档。
_VERDICT_WORDS = ("达到预期", "没测到")


def _int_keyed_word_tables(source: str) -> list:
    """模块里所有「整数键 → 一句话」形状的字典**字面量**，返回它们的值列表。

    只认字面量（`ast.Dict`）：这正是「又抄了一份表」的形状 —— 引用别人那张表
    写出来的是 `Name`，不是 `Dict`，所以这一条**不会**把正当的引用也算进来。
    """
    out = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Dict) or not node.keys:
            continue
        if not all(isinstance(k, ast.Constant) and isinstance(k.value, int)
                   for k in node.keys):
            continue
        vals = [v.value for v in node.values
                if isinstance(v, ast.Constant) and isinstance(v.value, str)]
        if len(vals) != len(node.keys):
            continue
        if all(any(w in v for w in _VERDICT_WORDS) for v in vals):
            out.append(vals)
    return out


def test_the_verdict_wording_lives_in_exactly_one_table():
    """`0/1/2 → 措辞` 那张表**只许有一份**：打屏和产物都要从它出来。

    原先 `_MARK`（打屏那一列）和 `_write_report` 里的 `verdicts`（产物那一栏）
    各写了一份。两张都是 `.get(rc, …)`：**改一张不会炸，只会让同一档在屏幕上
    和产物里说两种话**，而读的人通常只看其中一份。

    形状和 `SELFPROOF.md` 里记的那次 `KeyError: '已否决'` 是同一个病（同一份语义
    两张副本，只改了一张）。那次炸了、被抓住；这次不炸 —— 不炸的那种更难发现，
    所以只能靠形状去抓：数一数这份源码里有几张这样的表。
    """
    from verification import run_all as R

    src = pathlib.Path(R.__file__).read_text(encoding="utf-8")
    tables = _int_keyed_word_tables(src)

    assert len(tables) == 1, (
        f"`0/1/2 → 措辞` 的表有 {len(tables)} 张：{tables} —— "
        "同一份语义抄了第二遍。屏幕和产物会各说各的，而且不会报错")

    assert set(tables[0]) == set(R.VERDICTS.values()), (
        f"表里的话与 `VERDICTS` 对不上：{sorted(tables[0])}")

    # 打屏那一列仍然要有记号（`√ / × / ○`），并且**从同一张表派生**。
    assert set(R._MARK) == set(R.VERDICTS), "打屏那列少了几档"
    for rc in (0, 1, 2):
        assert R._MARK[rc].endswith(R.VERDICTS[rc]), (
            f"`{rc}` 在屏幕上印的是 {R._MARK[rc]!r}，产物里却是 "
            f"{R.VERDICTS[rc]!r} —— 两处已经不是同一句话了")

