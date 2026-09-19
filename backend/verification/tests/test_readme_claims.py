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
