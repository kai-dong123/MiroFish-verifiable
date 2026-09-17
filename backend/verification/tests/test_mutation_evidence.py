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
    """
    for m in report["mutations"]:
        if m["expect_failed"] == 0:
            assert m["failed"] == 0, (
                f"{m['id']} 是阴性对照，本该一条不红，却红了 {m['failed']} 条 —— "
                f"上面那些红条就都不能作数了。{_RERUN}")
            continue
        assert m["failed_in_target"] >= 1, (
            f"{m['id']}（{m['what']}）改坏了却一条都没红 —— "
            f"要么源码又漂了、要么这条测试失去了鉴别力。"
            f"**先看那个论断还成不成立**，别急着改期望值。{_RERUN}")


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
