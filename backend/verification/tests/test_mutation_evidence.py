"""变异留痕的产物必须**还在**，而且必须**对得上当下的源码**。

`MUTATIONS.md` 是「这套测试不是恒真的」那句话的证据。证据最容易坏的方式不是丢，
是**过期** —— 代码动了、报告没动，于是它继续替一份已经不在的代码作证，
而报告上的日期和哈希看着都挺像真的。这个文件就钉这一件事。

它**不重跑**变异（那要几十秒，跑测试的人不该为它等着）；它只核三件快事：

1. 产物在不在、能不能读；
2. 报告里那串变异，和 `mutations.py` 里现在那串，是不是同一串；
3. 报告记下的 `sha256`，和现在磁盘上的那几个文件，是不是同一份。

对不上就红，并且告诉你**下一步敲什么命令**。
"""

from __future__ import annotations

import json
import os
import pathlib
import re

import pytest

from verification import _probe as P
from verification import mutations as MU

HERE = pathlib.Path(__file__).resolve().parent          # verification/tests
VERIFICATION = HERE.parent
BACKEND = VERIFICATION.parent
REPORT = VERIFICATION / "mutations_report.json"
MARKDOWN = VERIFICATION / "MUTATIONS.md"
README = VERIFICATION / "README.md"

_RERUN = "重新跑一次：`cd backend && python -m verification.mutations`"


@pytest.fixture(scope="module", autouse=True)
def _not_inside_a_mutation_run():
    """`mutations.py` 跑的那几轮（含基线）里，这个文件整个跳过。

    那几轮是**故意把源码改坏**再跑的，问「报告有没有过期」当然对不上 ——
    那不是发现，是自问自答。基线那一轮更绕：它要断言的那份报告正是它自己
    这一轮要写的，一旦记下「基线是红的」就再也翻不了身。

    所以这条只在**普通 `pytest` 运行**里跑 —— 那也正是该抓它的时候。
    """
    if os.environ.get(MU._MUTATION_ENV):
        pytest.skip(f"正在跑变异 {os.environ[MU._MUTATION_ENV]}："
                    "源码此刻是被改坏的那个状态，这里问不出答案")


@pytest.fixture(scope="module")
def report() -> dict:
    if not REPORT.is_file():
        pytest.fail(f"变异留痕的产物不在：{REPORT.name}。{_RERUN}")
    return json.loads(REPORT.read_text(encoding="utf-8"))


def test_the_human_readable_side_is_there_too(report):
    """机读的那份在，不等于人读的那份在 —— 两边都要有。"""
    assert MARKDOWN.is_file(), f"人读的那份不在：{MARKDOWN.name}。{_RERUN}"
    text = MARKDOWN.read_text(encoding="utf-8")
    assert len(text) > 1000, "这份报告短得不像话，多半是半截产物"
    for mid in (m["id"] for m in report["mutations"]):
        assert f"`{mid}`" in text, f"报告里有 {mid}，人读的那份里却没有。{_RERUN}"


def test_the_report_does_not_claim_to_be_a_pass_rate(report):
    """这张表上的红色**是期望的结果** —— 别让人把它读成通过率。"""
    assert report["not_a_pass_rate"] is True
    s = report["summary"]
    assert s["baseline_green"] is True, (
        "基线本身就是红的，底下那些红条一条都解释不了 —— 先修基线，再看这张表")
    assert s["all_sources_reverted"] is True, (
        "跑完没还原文 —— 先 `git diff` 看清楚工作区被改成了什么样")


def test_the_report_covers_exactly_the_mutations_that_exist(report):
    """两边对不上，说明报告是上一版的变异集 —— 那它证明的就不是这批。"""
    in_report = [m["id"] for m in report["mutations"]]
    in_code = [m["id"] for m in MU.MUTATIONS]
    assert in_report == in_code, (
        f"报告里是 {in_report}，代码里是 {in_code}。{_RERUN}")


def test_every_recorded_mutation_actually_turned_something_red(report):
    """**这是整份报告存在的理由**：每条变异都要真的红过。

    唯一的例外是那条阴性对照（`expect_failed == 0`）—— 它必须**一条都不红**，
    否则上面那些红就没法排除「测试环境本来就红」这个解释。

    这里还钉住「红了几条」的**口径**：它是**相对基线多出来的**，不是原样数红条。
    基线自己红着时，那些红跟这条变异没关系；靶子恰好是同一个文件的话，
    差值就会被算进去 —— 实测踩到过（2026-09-18，`D1`）：一条**按声明变红**的
    变异被判成「与声明不符」，而它其实红得刚好。
    """
    base = report["baseline"]
    for m in report["mutations"]:
        # 「多红了几条」不是一个独立的数，是**原样数减基线**算出来的。
        base_in_target = base["failed_by_file"].get(m["target"], 0)
        assert m["baseline_in_target"] == base_in_target
        assert m["failed_in_target_raw"] == m["failed_by_file"].get(m["target"], 0)
        assert m["failed_in_target"] == m["failed_in_target_raw"] - base_in_target, (
            f"{m['id']}：报告记的「多红 {m['failed_in_target']} 条」，"
            f"而靶子这一轮原样红 {m['failed_in_target_raw']} 条、基线红 {base_in_target} 条 —— "
            f"这个差对不上，说明那个减法没按规矩做。{_RERUN}")
        assert m["failed_delta"] == m["failed"] - base["failed"], (
            f"{m['id']}：整轮那两个数对不上。{_RERUN}")

        if m["expect_failed"] == 0:
            assert m["failed"] == 0, (
                f"{m['id']} 是阴性对照，本该一条不红，却红了 {m['failed']} 条 —— "
                f"上面那些红条就都不能作数了。{_RERUN}")
            continue
        assert m["failed_in_target"] >= 1, (
            f"{m['id']}（{m['what']}）改坏了却一条都没红 —— "
            f"要么源码又漂了、要么这条测试失去了鉴别力。"
            f"**先看那个论断还成不成立**，别急着改期望值。{_RERUN}")

    # 上面那几条在**基线全绿**时是恒真的（减的是 0）—— 所以再拿一份「基线红」的
    # 假数据直接问那个减法。两个方向都问，少一个它就可能是个空动作。
    hot_base = {"failed": 2, "failed_by_file": {"x.py": 2}}
    assert MU._delta({"failed": 3, "failed_by_file": {"x.py": 3}},
                     hot_base, "x.py") == (1, 1), (
        "基线红着的时候它没扣 —— 于是被判「与声明不符」的，"
        "可能是一条完全按声明变红的变异")
    assert MU._delta({"failed": 3, "failed_by_file": {"x.py": 3}},
                     {"failed": 0, "failed_by_file": {}}, "x.py") == (3, 3), (
        "基线全绿它也去减 —— 那正常情形下的数字会跟以前不一样，"
        "这一改就动了本来不该动的东西")
    assert MU._delta({"failed": 1, "failed_by_file": {"y.py": 1}},
                     hot_base, "x.py") == (-2, -1), (
        "靶子上的红比基线还少时结果是负的 —— 照实记、别夹到 0："
        "那说明这条变异没让靶子多红，反而盖掉了基线那条红")


def test_the_recorded_hashes_still_describe_the_files_on_disk(report):
    """报告不能替一份**已经不在**的代码作证。

    哈希对不上只有两种解释，都要人去看一眼：源码动了（报告过期），
    或者有人手工改过报告（那它就不是产物了）。
    """
    assert report["script"]["sha256"] == MU._sha(
        (VERIFICATION / "mutations.py").read_text(encoding="utf-8")), (
        f"{report['script']['path']} 动过了，报告是改动之前的。{_RERUN}")

    for key, want in report["sources"].items():
        now = MU._sha((BACKEND / key).read_text(encoding="utf-8"))
        assert now == want, (
            f"{key} 的 sha256 与报告里记的对不上 —— 报告已经过期。{_RERUN}")

    assert report["suite_sha256"] == MU._suite_fingerprint(), (
        "测试目录动过了 —— 报告里「红了几条、绿了几条」只对改动前那套测试成立。"
        f"{_RERUN}")

    assert report["sources"] == report["sources_after"], (
        "跑完之后文件没回到原样，这份报告记录的是一个被改坏过的状态。先 `git diff`")


def test_the_suite_fingerprint_does_not_depend_on_line_endings(tmp_path):
    """**这一条是踩出来的，不是想出来的。**

    2026-09-17 在一个干净 clone 里，普通 `pytest` 第一条就红：上面那一条
    `test_the_recorded_hashes_still_describe_the_files_on_disk` 说「测试目录
    动过了」—— 而其实**一个字都没动**。

    真正发生的事：`core.autocrlf` 在 Windows 上默认开着，clone 时 git 把仓库里的
    LF 换成了 CRLF，而那个指纹当时是拿 `read_bytes()` 算的。于是它钉住的是
    **「谁的检出配置」**，不是「测试有没有变」—— 换句话说，它给**每一个用默认
    配置 clone 的人**报了一个**不存在的问题**。

    这与本装置已经踩过两次的毛病同源（`README.md`「产物没过期」那一节、`D-21`）：
    别去钉一个**本来就会合法地变**的东西，然后说它变了就是有问题。

    这一条把「换行符不算改动」钉死：同一份测试内容，两种换行，指纹必须一样。
    """
    lf, crlf = tmp_path / "lf", tmp_path / "crlf"
    lf.mkdir()
    crlf.mkdir()
    body = "def test_示例():\n    assert 1 + 1 == 2\n"
    (lf / "test_sample.py").write_bytes(body.encode("utf-8"))
    (crlf / "test_sample.py").write_bytes(
        body.replace("\n", "\r\n").encode("utf-8"))
    # 先证明这两个文件在**字节**上确实不同 —— 否则这一条测了个空气：
    assert ((crlf / "test_sample.py").read_bytes()
            != (lf / "test_sample.py").read_bytes())
    assert MU._suite_fingerprint(lf) == MU._suite_fingerprint(crlf), (
        "指纹又按字节算了 —— 它会在**每一个用默认 git 配置 clone 的人**"
        "那里先红一次，而那里根本没有问题")


def test_the_counts_in_this_report_are_counted_not_typed(report):
    """报告里那几个**数目**必须是从现场数出来的，不是写死在正文里的。

    这一条也是踩出来的。报告原先有一句话是「上面这个规模**不含**
    `tests/test_mutation_evidence.py`（5 条）」，另有一句「**三个**源文件跑完后
    逐字节还原」。后来这个文件加了两条用例（5 → 7），源文件的集合也从三个变成了
    四个 —— 两句话都**没人再去看一眼**，产物照样签发，一路带到要公开的目录里。

    数目字写死在正文里，就等于给自己留了一个**没有任何东西会去核**的声明。
    现在这两处都由现场数出来（`_selfcheck_test_count()` / `len(sources)`），
    这一条把「数出来的那个数」和「现场实际有多少」钉在一起：谁加了用例、
    谁往 `sources` 里添了文件，这里都会当场红，而不是等它漂进报告。
    """
    here = len(re.findall(r"^def test_", pathlib.Path(__file__).read_text(encoding="utf-8"),
                          re.M))
    # 上面这个 `here` 就是**这个文件自己**的用例数 —— 加了用例它会跟着涨。
    assert report["selfcheck_tests"] == here, (
        f"报告说那一组是 {report['selfcheck_tests']} 条，现场是 {here} 条 —— "
        f"数目漂了。{_RERUN}")

    assert report["source_count"] == len(report["sources"]), (
        f"报告说 {report['source_count']} 个源文件，`sources` 里其实是 "
        f"{len(report['sources'])} 个。{_RERUN}")

    text = MARKDOWN.read_text(encoding="utf-8")
    assert f"（{report['selfcheck_tests']} 条）" in text, (
        f"人读的那份里没写「（{report['selfcheck_tests']} 条）」。{_RERUN}")
    assert f"{report['source_count']} 个源文件" in text, (
        f"人读的那份里没写「{report['source_count']} 个源文件」。{_RERUN}")

    # 上面那两个数是**从现场数出来**的，可 README 里还有第三处 —— 那份被哈希的
    # 文件**名单本身**（「碰过的每一个文件：…」）。它原先是一句散文，枚举还写错过一次
    # （把两个**测试**文件说成「四个源码」，而 `sources` 里根本没有那回事）。
    # 名单漏一个文件，读者就不知道有谁在被核对 —— 所以它也归这一条管。
    seg = _README_SOURCE_LIST.search(README.read_text(encoding="utf-8"))
    assert seg, ("README 里「报告不许过期」那一段找不到了 —— "
                 "改写法就把这里的定位一起改。")
    missing = sorted(k for k in report["sources"]
                     if pathlib.PurePosixPath(k).stem not in seg.group(1))
    assert not missing, (
        f"报告里记着这些文件被碰过，README 那份枚举里却一个都没提到：{missing}。\n"
        "**名单会漂**：加一条改到新文件的变异，这里就会多一格，而正文不会自己跟着动。\n"
        "把名字补进 README 那段，或者（更省事）改成从 `sources` 现场生成。")


def test_no_recorded_mutation_leaks_a_host_path(report):
    """产物里不许出现本机绝对路径 —— 它是给外面看的。

    `edits[].file` 原先写的是 `str(pathlib.Path)`，于是一份要公开的报告里
    明晃晃地记着 `D:\\open_source\\...\\camel_guards.py` 这样的**带盘符、带用户名**
    的全路径。那条路径与结论毫无关系，却把「这是在哪台机器上跑的」一并交了出去。
    （`e2e_stub` 的产物早就只写相对路径，只有这里漏了。）

    这一条按**形状**抓，不按某个具体前缀抓：盘符、UNC、`/home/`、`/Users/` 都算。
    """
    bad = []
    for m in report["mutations"]:
        for e in m["edits"]:
            f = e["file"]
            if (pathlib.PurePosixPath(f).is_absolute()
                    or pathlib.PureWindowsPath(f).is_absolute()
                    or f.startswith(("/", "\\\\"))):
                bad.append(f"{m['id']}: {f}")
    assert not bad, (
        "产物里有绝对路径：\n  " + "\n  ".join(bad) + f"\n{_RERUN}")

    # 顺带核一句：报告里记的那个相对路径，真能在 backend/ 下找到 ——
    # 换个写法把路径写没了、却仍然「不是绝对路径」，这里会红。
    for m in report["mutations"]:
        for e in m["edits"]:
            assert (BACKEND / e["file"]).is_file(), (
                f"报告里记的 `{e['file']}` 在 backend/ 下找不到 —— "
                f"它记的到底是哪个文件？{_RERUN}")


def test_the_text_sha_ignores_line_endings(tmp_path):
    """上面那条依赖的口径本身：受版本控制的**文本**文件，sha 按文本算。"""
    a, b = tmp_path / "a.py", tmp_path / "b.py"
    a.write_bytes(b"x = 1\ny = 2\n")
    b.write_bytes(b"x = 1\r\ny = 2\r\n")
    assert a.read_bytes() != b.read_bytes()
    assert P.sha256_text(a) == P.sha256_text(b)


#: README 里那句总数。**这一栏原先没有东西核，于是它真的烂过。**
_STATED_TOTAL = re.compile(r"眼下是 \*\*(\d+) 处\*\*")
#: 同一段里还有第二处数：含基线一共跑几轮。它和上面那个数是两个数（`+1`），
#: 只核一个的话另一个照样能漂 —— 所以两个都核。
_STATED_ROUNDS = re.compile(r"连基线 (\d+) 轮")
#: README 里「被哈希的文件名单」那一整段（从「报告不许过期」到「整个 tests/ 目录的指纹」）。
#: 枚举本身也归上面那条数目测试管 —— 见那里的注释。
_README_SOURCE_LIST = re.compile(
    r"\*\*报告不许过期\*\*：(.+?)\*\*整个 `tests/` 目录的指纹\*\*", re.S)
#: README 里点名用两种写法：单条 `` `J6` ``，和省字的区间 `` `G1`–`G7` ``。
_ID = re.compile(r"`([A-Z]\d)`")
_RANGE = re.compile(r"`([A-Z]\d)`\s*[–\-]\s*`([A-Z]\d)`")


def test_the_mutation_count_in_the_readme_is_the_real_one():
    """README 那个「眼下是 N 处」== `mutations.py` 里真的条数，而且**每条都被点到名**。

    这一栏原先没人核，也就真的烂过：README 写着「**24 处**」、列到 `C1`–`C6` 为止，
    而代码里已经有 `C7` 了 —— 它是后来单独加的，加的时候只改了变异、没改这句话。
    这正是本装置反复强调的那条纪律（**写在正文里的数目字必须有东西去核**），
    轮到它自己头上也一样：一张自称「每条都验过」的表，条数本身错了，
    比表里少一条更难发现。
    """
    assert README.is_file(), f"这份 README 不在了：{README}"
    text = README.read_text(encoding="utf-8")
    ids = [m["id"] for m in MU.MUTATIONS]

    stated = _STATED_TOTAL.search(text)
    assert stated, ("README 里那句「眼下是 **N 处**」找不到了 —— "
                    "改写法就把这里的正则一起改。")
    assert int(stated.group(1)) == len(ids), (
        f"README 写「眼下是 {stated.group(1)} 处」，而 `mutations.py` 里有 {len(ids)} 条："
        f"{ids}。**加一条变异就要改这句话** —— 不加，读者看到的就是个过期的数目。")

    # 紧挨着的第二个数：每一轮都要把整套测试重跑一遍，**基线那一轮也算一轮**，
    # 所以轮数 = 条数 + 1。它和上面那个数是两个数，只核一个，另一个照样能漂。
    rounds = _STATED_ROUNDS.search(text)
    assert rounds, ("README 里那句「连基线 N 轮」找不到了 —— "
                    "改写法就把这里的正则一起改（**别把这一处悄悄删掉**："
                    "它是「跑一次要多久」那个量级里唯一的另一半）。")
    assert int(rounds.group(1)) == len(ids) + 1, (
        f"README 写「连基线 {rounds.group(1)} 轮」，而 `mutations.py` 里 {len(ids)} 条"
        f"变异 —— 加上基线那一轮应当是 {len(ids) + 1} 轮。"
        "这个数是算得出来的，但**算得出来的数也会漂**：改了一处忘了另一处，就是 D-41。")

    covered = set(_ID.findall(text))
    for lo, hi in _RANGE.findall(text):
        if lo[0] == hi[0]:             # 同一个字母才算区间（`G1`–`G7`）
            covered |= {f"{lo[0]}{n}" for n in range(int(lo[1]), int(hi[1]) + 1)}
    missing = [i for i in ids if i not in covered]
    assert not missing, (
        f"这些变异在 README 里没被点到名：{missing}。"
        "每一条都要说一句「它验的是什么」，**尤其是新加的那几条** —— "
        "否则读者不知道那张表上多出来的一行是什么，也就无从判断它该不该红。")


#: 这几个测试文件**当不了**变异靶子，理由写在值里。
#: 三个是同一个原因：它们在变异轮里**整组跳过自己**（`MU._MUTATION_ENV`），
#: 于是「改坏源码 → 看它红不红」这件事在这里问不出答案 —— 红 0 条不是发现，是自问自答。
_CANNOT_BE_MUTATION_TARGET = {
    "test_mutation_evidence.py": "问的是产物过没过期 —— 变异轮里源码正是被改坏的那个状态",
    "test_reconcile_evidence.py": "核的是产物与草稿 —— 变异轮里它整组跳过自己",
    "test_readme_claims.py": "数的是 `pytest --collect-only` —— 源码被改坏时条数本来就会变",
}

#: 上面那个理由的机器可核形式：这三句跳过都长这样。
_SELF_SKIP = "MU._MUTATION_ENV"


def test_every_test_file_is_either_a_mutation_target_or_says_why_not():
    """**「每个新测试文件都做过变异测试」这句话，本身得有东西去核。**

    这句话原先写在骨架里，而现场是 **8 / 11** —— 三个文件既不是任何一条变异的靶子，
    也没说自己为什么不能是。**它没说错，它只是比现场大**：那种话最危险的地方在于，
    它对**下一个**加测试文件的人没有约束力 —— 新文件默认落进那三个的空隙里，
    而「没靶子的测试」和「恒真的测试」从外面看是一模一样的。

    所以这里把「配了靶子」和「明确豁免」之间**不留空隙**：新加一个 `test_*.py`，
    要么在 `mutations.py` 里给它配一条变异，要么写进上面那张豁免名单并说清理由。
    两条都不做，这一条就红。

    三个方向都堵：

    - 有文件两边都不在 → 红（就是上面那句空话的来源）；
    - 豁免名单里挂着一个已经不存在的名字 → 红（**名单会过期**，而且过期的名单
      会连累将来同名的新文件：它一建出来就自动被豁免了）；
    - 豁免的**理由**是「变异轮里跳过自己」→ 那它就得**真的**写了那句跳过。
      否则豁免掉的是一个**不跳**的文件 —— 拿它当靶子明明会有红条，
      却被名单挡在了外面，等于把一条本来抓得到的变异放掉了。
    """
    targets = {pathlib.PurePosixPath(m["target"]).name for m in MU.MUTATIONS}
    files = {p.name for p in HERE.glob("test_*.py")}

    uncovered = sorted(files - targets - set(_CANNOT_BE_MUTATION_TARGET))
    assert not uncovered, (
        f"这些测试文件既不是任何一条变异的靶子，也没说自己为什么不能是：{uncovered}。\n"
        "两条路选一条：**给它配一条变异**（改坏它盯着的那个东西，证明它会红），"
        "或者**写进 `_CANNOT_BE_MUTATION_TARGET` 并说清理由**。\n"
        "「新文件默认不用做变异」不是选项 —— 无靶子的测试和恒真的测试，"
        "从外面看是一样的。")

    stale = sorted(set(_CANNOT_BE_MUTATION_TARGET) - files)
    assert not stale, (
        f"`_CANNOT_BE_MUTATION_TARGET` 里这些名字已经不存在了：{stale} —— "
        "豁免名单过期了。删掉它们：留着的话，将来谁建一个同名文件，"
        "就会**不声不响地**落进豁免里。")

    not_skipping = [name for name in sorted(_CANNOT_BE_MUTATION_TARGET)
                    if _SELF_SKIP not in (HERE / name).read_text(encoding="utf-8")]
    assert not not_skipping, (
        f"这些文件被豁免，理由是「变异轮里跳过自己」，可里面根本没有那句跳过："
        f"{not_skipping}。\n"
        "那它其实**是**个合格的靶子（改坏源码它会红），豁免名单把它挡在了外面。\n"
        "要么把它从名单里删掉、配上变异；要么把理由改掉 —— "
        "**豁免的理由和现场对不上时，这一条连同理由一起改。**")
