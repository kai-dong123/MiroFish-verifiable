"""`verification/README.md` 里那几个**写死的数目**，必须和现场对得上。

这份 README 自己写着一条纪律：

> ⚠️ **这个条数只写在这一处。** 加测试之后**只改这里**，别在别的章节再抄一遍 ——
> 抄了就一定会腐烂。

话是对的，可它当时**只是一句话**：写「154 条」的时候现场其实已经是 **156 条**了
（这个文件自己加的两条，加上 `test_mutation_evidence.py` 里新加的两条），
而**没有任何东西会因此变红**。人读的文档里写死的数目，天然就是这么烂掉的 ——
它不像代码，改错了会有测试来敲门。

所以这里给它配一个会敲门的：把 README 里那个数字和**真的去数一遍**的结果比。
数的是 `pytest --collect-only`（不是静态数 `def test_` —— 那会把 `parametrize`
展开出来的几十条漏掉），所以它是权威的那个数。

`MIROFISH_MUTATION_RUN` 在跑的时候跳过自己：那几轮是拿**改坏的源码**在跑，
收集到的条数本来就会变，那不是发现，是自问自答。

同一类东西还有一处：README 的「装与跑」里那句
**`Requires-Python: >=3.10.0,<3.12`**。那也不是我们定的数，是 `camel-oasis`
包元数据里的值 —— 上游放宽了，README 那句话就过期，而**没有任何东西会因此变红**。
所以它也在这里现场对一遍（同一份 README，同一种病）。
"""

from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent          # verification/tests
VERIFICATION = HERE.parent
BACKEND = VERIFICATION.parent
README = VERIFICATION / "README.md"

_COLLECT_CMD = [sys.executable, "-m", "pytest", "verification/tests",
                "--collect-only", "-q", "-p", "no:cacheprovider"]

#: 中文数目字。README 里用的是「八个文件」这种写法，所以得能对得上。
#: 这里**一直写到二十**：每加一个测试文件就要往上挪一格，写到这里为止的这十几个
#: 是「这个装置长得到多大」的合理上界 —— 到二十个测试文件还没拆开的话，
#: 该考虑的就不是加数字了，是这份测试集本身该分层了。
_CN = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五",
       6: "六", 7: "七", 8: "八", 9: "九", 10: "十",
       11: "十一", 12: "十二", 13: "十三", 14: "十四", 15: "十五",
       16: "十六", 17: "十七", 18: "十八", 19: "十九", 20: "二十"}


@pytest.fixture(scope="module", autouse=True)
def _not_inside_a_mutation_run():
    """变异那几轮里源码是被改坏的状态，收集到的条数本来就不该跟 README 对。"""
    from verification import mutations as MU
    if os.environ.get(MU._MUTATION_ENV):
        pytest.skip(f"正在跑变异 {os.environ[MU._MUTATION_ENV]}："
                    "源码此刻是被改坏的那个状态，这里问不出答案")


@pytest.fixture(scope="module")
def readme_text() -> str:
    assert README.is_file(), f"这份 README 不在了：{README}"
    return README.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def collected_count() -> int:
    """真的去数一遍。**在子进程里数** —— 在被测的这次 pytest 里再起一次收集，
    插件状态是同一个进程的，数出来的东西不好说是不是它自己的。"""
    proc = subprocess.run(_COLLECT_CMD, cwd=BACKEND, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    m = re.search(r"(\d+) tests? collected", proc.stdout or "")
    assert m, ("数不出来。命令：`cd backend && "
               + " ".join(_COLLECT_CMD[1:]) + "`\n"
               f"退出码 {proc.returncode}\n--- stdout ---\n{proc.stdout}\n"
               f"--- stderr ---\n{proc.stderr}")
    return int(m.group(1))


def test_the_test_count_in_the_readme_matches_reality(readme_text, collected_count):
    """README 上写的那条命令旁边那个「当前 N 条」，就是现场那个 N。"""
    m = re.search(r"pytest verification/tests -q\s*#\s*当前 (\d+) 条", readme_text)
    assert m, ("README 里那条命令后面没写「当前 N 条」了 —— 要么改过写法，"
               "要么那句话被删了。删掉的话，这一条就失去要核的东西了；"
               "改写法的话，把这里的正则一起改。")
    stated = int(m.group(1))
    assert stated == collected_count, (
        f"README 写着 **{stated} 条**，现场是 **{collected_count} 条**。\n"
        f"改了测试条数就顺手把 `verification/README.md` 里那一处数字改掉 —— "
        f"**只改那一处**（README 自己说了：别在别的章节再抄一遍）。")


def test_the_file_count_in_the_readme_matches_reality(readme_text):
    """README 说「N 个文件，管 N 件不同的事」，那张表就得真有 N 行。"""
    files = sorted(p.name for p in HERE.glob("test_*.py"))
    m = re.search(r"^(\S+)个文件，管\1件不同的事：", readme_text, re.M)
    assert m, "README 里「N 个文件，管 N 件不同的事」那句话找不到了，改过写法？"
    stated_cn = m.group(1)
    assert stated_cn in _CN.values(), f"「{stated_cn}个文件」这个数目字读不出来"
    assert _CN[len(files)] == stated_cn, (
        f"README 写着「{stated_cn}个文件」，`tests/` 下实际有 {len(files)} 个："
        f"{'、'.join(files)}")

    # 表里每一条都得点到名 —— 加了文件只改数目、忘了加行，这里会红。
    for name in files:
        assert f"`{name}`" in readme_text, (
            f"`{name}` 在 `tests/` 下，README 那张表里却没有它 —— 加一行。")


#: README 里引 `camel-oasis` 的 `Requires-Python` 时用的写法。**只认这一处**：
#: 前面那句「`camel-ai 0.2.78` 是 `<3.13,>=3.10`」故意不匹配 —— 它没有
#: `Requires-Python: ` 这个前缀，写的是给人读的简写。核的是被引用的那一个。
_QUOTED_BOUND = re.compile(r"Requires-Python:\s*([^\s`，。]+)")


def _bound_mismatch(readme: str, live: str) -> str | None:
    """README 引的界和现场元数据对不上就返回一句人话，对得上返回 `None`。

    单拎出来是为了下面那条阴性对照能拿它验一次：**它现在不报错，
    可能只是因为它永远不报错。**
    """
    m = _QUOTED_BOUND.search(readme)
    if not m:
        return "README 里找不到引用的 `Requires-Python: …`"
    if m.group(1) == live:
        return None
    return f"README 引的是 `{m.group(1)}`，现场元数据是 `{live}`"


def test_the_python_bound_quoted_in_the_readme_matches_the_live_metadata(readme_text):
    """README 说「3.10 / 3.11 装得上、3.12 装不上、卡住的是 camel-oasis」。

    这三句都不是我们的判断，是从依赖元数据里读出来的。**读出来的东西会漂。**
    所以现场读一遍；顺便把「卡住的是谁」这个归属也验掉 ——
    真正的约束是四个直接相关包的**交集**（`camel-oasis <3.12`、`camel-ai <3.13`、
    `tiktoken >=3.8`、`mcp >=3.10`），卡住上界的是 `camel-oasis`。
    哪天 `camel-ai` 收得比它还紧，README 那句归因就指错人了，这一条会红。
    """
    from importlib.metadata import metadata

    live = metadata("camel-oasis")["Requires-Python"]
    problem = _bound_mismatch(readme_text, live)
    assert problem is None, (
        f"{problem}。\n以包元数据为准改 `verification/README.md`（那句界**只写在那一个地方**）—— "
        "它是 `camel-oasis` 自己声明的，不是我们设的。")

    assert "<3.12" in live, (
        f"`camel-oasis` 现在声明 `{live}` —— 它不再排除 3.12 了，"
        "README 那句「3.12 装不上」跟着过期。")

    other = metadata("camel-ai")["Requires-Python"]
    assert "<3.12" not in other, (
        f"`camel-ai` 现在声明 `{other}`，也把 3.12 挡在外面了 —— "
        "README 把上界归给了 `camel-oasis`，这个归属要跟着改。")


def test_the_python_bound_comparison_would_flag_a_wrong_bound(readme_text):
    """阴性对照：把界换成一个假的，上面那段比较必须说「不对」。

    没有这一条，`_bound_mismatch` 可能是恒返回 `None` 的（正则写歪了、
    或者元数据根本没读出来），那么上面那条测试永远绿 —— 而 README 里那串
    数字**一次都没被核过**。（跟 `test_docs_claims.py` 里那条数目对照同一个道理。）
    """
    from importlib.metadata import metadata

    live = metadata("camel-oasis")["Requires-Python"]

    # 先拿真值确认它不报错，否则下面那个「报错」可能只是因为它总在报错
    assert _bound_mismatch(readme_text, live) is None, (
        "拿真值喂进去也说不对 —— 那 `_bound_mismatch` 本身坏了，上面那条是假绿。")
    assert _bound_mismatch(readme_text, ">=3.9") is not None, (
        "换一个假的上界进去，它居然还说「对得上」—— 那么上面那条什么都没核。")


# ---------------------------------------------------------------------------
# 第三种同病：README 那句「三份产物的判定与本机一致」后面抄的那三个数
# ---------------------------------------------------------------------------
#
# 那句话说的是「第二平台上重跑，判定与本机**一致**，具体是
# `run_all` 3/3、`adjudicate` 13 通过 / 0 否决 / 2 不可判定、`selfproof` 15/15」。
#
# **正因为论断的内容是「一致」，拿本机产物去对它就是**在核那句话本身**，不是
# 在核另一台机器。** 哪天某条判据翻了面、README 没跟着改，这里就会红：
# 要么是那句话过期了，要么是「两个平台一致」这件事不再成立 —— 两种都该有人看。
#
# 这三个数字此前**没有任何东西看着**（`grep` 在 tests/ 里零命中），而它们正是
# 读者会记住的那一行。

_README_NUMS = (
    ("run_all", re.compile(r"`run_all`\s*(\d+)\s*/\s*(\d+)")),
    ("adjudicate", re.compile(
        r"`adjudicate`\s*(\d+)\s*通过\s*/\s*(\d+)\s*否决\s*/\s*(\d+)\s*不可判定")),
    ("selfproof", re.compile(r"`selfproof`\s*(\d+)\s*/\s*(\d+)")),
)


def _readme_run_numbers(text: str) -> dict:
    """从 README 那段里抠出那三组数；抠不到就抛 —— 那是**没测到**，不是「不符」。"""
    out = {}
    for name, pat in _README_NUMS:
        m = pat.search(text)
        assert m, (f"README 里找不到 `{name}` 那组数了（正则 `{pat.pattern}`）—— "
                   f"改了写法就把这里的正则一起改；删了的话这一条就失去要核的东西了")
        out[name] = tuple(int(g) for g in m.groups())
    return out


def _artifact_numbers() -> dict:
    import json

    adj = json.loads((VERIFICATION / "adjudication_report.json")
                     .read_text(encoding="utf-8"))
    sp = json.loads((VERIFICATION / "selfproof_report.json")
                    .read_text(encoding="utf-8"))
    run = json.loads((BACKEND / "verification_report.json")
                     .read_text(encoding="utf-8"))
    return {
        "run_all": (run["summary"]["reached_expectation"], run["summary"]["total"]),
        "adjudicate": (adj["summary"]["by_verdict"]["通过"],
                       adj["summary"]["by_verdict"]["否决"],
                       adj["summary"]["by_verdict"]["不可判定"]),
        "selfproof": (sp["meta"]["cases_ok"], len(sp["cases"])),
    }


#: 这一条要的三份产物。**缺一份就是「没条件判」**，不是「判不过」—— 和
#: `test_adjudicate.py` 里那条新鲜度测试同一个道理（本装置反复用的那条三态）。
#:
#: 这是**实测踩出来的**：README 说「刚 clone 下来第一次跑是 `243 passed /
#: 1 skipped`」，而把工作区按 `git ls-files` 摊成一份「clone 完的样子」再跑，
#: 屏幕上是**一红** —— 就是这一条，抛的还是 `FileNotFoundError` 的 traceback。
#: 读者照 README 做，只会以为自己装错了；而真相是这三份产物本来就不入库，
#: 这一条**没条件判**。（同一份副本里另一条红是 `.git` 不在 —— 真 clone 里有。）
_NEEDED_ARTIFACTS = (VERIFICATION / "adjudication_report.json",
                     VERIFICATION / "selfproof_report.json",
                     BACKEND / "verification_report.json")

_MISSING_HINT = ("先跑一次 `cd backend && python -m verification.run_all`、"
                 "`python -m verification.adjudicate`、`python -m verification.selfproof`，"
                 "三份产物齐了这一条才判得动。")


def _missing_artifacts() -> list:
    return [p.name for p in _NEEDED_ARTIFACTS if not p.is_file()]


def test_the_readme_numbers_are_the_numbers_the_artifacts_produced(readme_text):
    """README 那一行里抄的三个数，和三份**本机产物**对得上。

    那句论断是「第二平台上重跑，判定与本机一致 —— 就是这三个数」。所以这份
    产物里的数**必须**正是 README 写的数：对不上，要么是 README 过期了，
    要么是「两个平台一致」不再成立。
    """
    missing = _missing_artifacts()
    if missing:
        pytest.skip(f"产物不齐（缺 {'、'.join(missing)}），这一条没条件判。{_MISSING_HINT}")
    said, got = _readme_run_numbers(readme_text), _artifact_numbers()
    for name in said:
        assert said[name] == got[name], (
            f"README 写 `{name}` 是 {said[name]}，本机产物给的是 {got[name]}。\n"
            f"**先弄清是哪一种**：产物过期了（重跑一次）、还是判定真的变了"
            f"（那「两个平台一致」这句话就不再成立，得改的是那句话，不是产物）。")


def test_the_numbers_comparison_really_compares(monkeypatch, readme_text):
    """反向对照：前提齐着的时候，数对不上必须**当场红**。

    少了它，一个「不管前提齐不齐都跳过」的实现也能让上面那条全绿 ——
    而它要拦的，正是「README 上的数烂掉了却没有任何东西会因此变红」这件事。

    这里把**产物读数**换成一望即知不对的一组，并把**前提门**换成「齐的」——
    于是这条对照不依赖本机有没有跑过 `run_all`：刚开始 clone 下来它照样判得动，
    不会跟着上面那条一起变成第二个跳过（跳过的那一条已经在上面了，够演示了）。
    """
    monkeypatch.setattr(sys.modules[__name__], "_missing_artifacts", lambda: [])
    monkeypatch.setattr(sys.modules[__name__], "_artifact_numbers",
                        lambda: {"run_all": (99, 99), "adjudicate": (0, 0, 0),
                                 "selfproof": (0, 0)})
    with pytest.raises(AssertionError) as e:
        test_the_readme_numbers_are_the_numbers_the_artifacts_produced(readme_text)
    assert "本机产物给的是" in str(e.value), (
        f"红了，但红在别的地方（{e.value!r}）—— 那这条对照证的就不是「比对照」")


def test_that_number_parser_actually_discriminates():
    """反向对照：那三组数要真的**从文本里读出来**，不是恒返回一组好看的值。

    少了它，一个恒返回 `{'run_all': (3,3), ...}` 的实现也能让上面那条变绿 ——
    而那正是它要拦的（README 上的数烂掉了却没人知道）。
    """
    text = README.read_text(encoding="utf-8")
    got = _readme_run_numbers(text)
    assert set(got) == {"run_all", "adjudicate", "selfproof"}

    tweaked = text.replace("`selfproof` 15/15", "`selfproof` 7/9")
    assert tweaked != text, "README 那句 `selfproof` 的写法变了，先看一眼"
    assert _readme_run_numbers(tweaked)["selfproof"] == (7, 9), (
        "改了 README 里的数，读出来却没变 —— 那它不是从那一行读的")

    # 抠不到时必须是**抛**（没测到），不许悄悄退回一个默认值。
    with pytest.raises(AssertionError):
        _readme_run_numbers(tweaked.replace("`run_all` 3/3", "`run_all` ?/?"))
