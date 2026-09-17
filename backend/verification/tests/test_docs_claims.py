"""`docs/开源及第三方资源使用清单.md` 里的行数，必须和现场对得上。

那份清单自己写着一条纪律：

> 行数为实测（`wc -l`），测试条数为 `python -m pytest verification/tests` 实测。

它还在「待办」里承认：**行数会随开发变，改代码就要改这里 —— 这是本清单最容易过期的一栏。**

「最容易过期的一栏」+「靠人记得改」= 一定会烂。就在写这份测试之前，那张表里已经错了
两处：上游草稿写成 `3 份 184 行`（现场是 7 个文件 752 行 —— 中间加过一份回帖草稿，
数字没跟着动），合计因此写成 `8,199`（现场 8,767）。**错的数字看起来和真的一样。**

所以这里给它配一个会敲门的：把清单里每个 `（N 行）` 都拿去和 `wc -l` 比，
把三个分项和合计都拿实际文件去加一遍。

跟 `test_readme_claims.py` 一样，`MIROFISH_MUTATION_RUN` 在跑的时候跳过自己 ——
那几轮拿的是**改坏的源码**，行数本来就该变，在这里问等于自问自答。
"""

from __future__ import annotations

import os
import pathlib
import re

import pytest

HERE = pathlib.Path(__file__).resolve().parent          # verification/tests
VERIFICATION = HERE.parent
BACKEND = VERIFICATION.parent
REPO = BACKEND.parent
DOC = REPO / "docs" / "开源及第三方资源使用清单.md"


@pytest.fixture(scope="module", autouse=True)
def _not_inside_a_mutation_run():
    from verification import mutations as MU
    if os.environ.get(MU._MUTATION_ENV):
        pytest.skip(f"正在跑变异 {os.environ[MU._MUTATION_ENV]}："
                    "源码此刻是被改坏的那个状态，行数本来就会变")


@pytest.fixture(scope="module")
def doc_text() -> str:
    assert DOC.is_file(), f"这份清单不在了：{DOC}"
    return DOC.read_text(encoding="utf-8")


def _lines(path: pathlib.Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def _num(s: str) -> int:
    return int(s.replace(",", ""))


def _resolve(name: str) -> pathlib.Path:
    """清单里有的写全路径、有的只写文件名（同一个单元格里的第二个起）。"""
    return REPO / name if "/" in name else VERIFICATION / name


def _content_files(root: pathlib.Path) -> list:
    """目录里的**内容文件** —— 不数 `__pycache__` 那种跑出来的东西。

    清单写的是「这个目录里有多少东西」，不是在数盘上有几个文件；
    把编译缓存算进去，数字会随「谁刚跑过什么」漂移 —— 那就又是一个
    「本来就会合法地变」的东西（这个坑本装置在别处已经踩过三次）。
    """
    return sorted(p for p in root.rglob("*")
                  if p.is_file() and "__pycache__" not in p.parts
                  and not p.name.startswith("."))


def _strip_or_die(text: str, pattern: str, why: str) -> re.Match:
    m = re.search(pattern, text)
    assert m, f"{why}（正则：{pattern}）—— 改写法就把这里的正则一起改。"
    return m


def test_every_per_file_line_count_matches_wc_l(doc_text):
    """每个 `（N 行）` 都是真的数出来的那个 N。"""
    hits = re.findall(r"`([^`]+\.py)`（(\d+) 行）", doc_text)
    assert len(hits) >= 12, (
        f"只找到 {len(hits)} 个带行数的文件 —— 这张表要么被改写了、要么被拆散了。"
        "这一条检查的就是这些行数，找不到就等于没查。")
    wrong = []
    for name, stated in hits:
        p = _resolve(name)
        assert p.is_file(), f"清单点了名，文件却不在：{p}"
        actual = _lines(p)
        if actual != int(stated):
            wrong.append(f"  {name}：清单写 {stated} 行，现场 {actual} 行")
    assert not wrong, (
        "清单里的行数对不上了：\n" + "\n".join(wrong) +
        "\n改了代码就把清单第三节那张表改掉 —— 那一栏本来就是靠这份测试兜着的。")


def test_the_directory_rows_add_up(doc_text):
    """目录那两行（测试、上游草稿）报的是**目录里所有文件的和**，不是某一个文件。"""
    m = _strip_or_die(doc_text,
                      r"`backend/verification/tests/`（([\d,]+) 行",
                      "「装置自带的测试」那一行的目录行数找不到了")
    actual = sum(_lines(p) for p in sorted(HERE.glob("*.py")))
    assert _num(m.group(1)) == actual, (
        f"清单写 `verification/tests/` 共 {m.group(1)} 行，现场 {actual} 行")

    m = _strip_or_die(doc_text,
                      r"`backend/verification/upstream/`（(\d+) 个文件 / ([\d,]+) 行",
                      "「上游草稿」那一行的文件数/行数找不到了")
    ups = _content_files(VERIFICATION / "upstream")
    assert int(m.group(1)) == len(ups), (
        f"清单写上游草稿 {m.group(1)} 个文件，现场 {len(ups)} 个："
        f"{'、'.join(p.name for p in ups)}")
    assert _num(m.group(2)) == sum(_lines(p) for p in ups), (
        f"清单写上游草稿共 {m.group(2)} 行，现场 {sum(_lines(p) for p in ups)} 行")


def test_the_grand_total_is_the_sum_not_a_guess(doc_text):
    """合计那一行：三个分项各自要对，加起来也要对。"""
    m = _strip_or_die(
        doc_text,
        r"装置本体 (\d+) 个模块 \*\*([\d,]+) 行\*\* \+ "
        r"上游草稿 (\d+) 个文件 \*\*([\d,]+) 行\*\* \+ "
        r"测试 (\d+) 套 \*\*([\d,]+) 行\*\*\s*\n= \*\*([\d,]+) 行\*\*",
        "「合计」那一行找不到了")

    modules = sorted(p for p in VERIFICATION.glob("*.py"))
    upstreams = _content_files(VERIFICATION / "upstream")
    #: 行数按**目录里全部** `.py` 算（含 `conftest.py` —— 它也是这个目录的行数）；
    #: 文件数只算 `test_*.py`，因为清单那一行写的是「9 个文件 **+ `conftest.py`**」——
    #: 它把 conftest 单独点出来了。两边口径不同是**照抄清单的说法**，不是笔误。
    tests_all = sorted(HERE.glob("*.py"))
    tests_named = sorted(HERE.glob("test_*.py"))

    for label, stated, group in (("模块数", m.group(1), modules),
                                 ("上游草稿文件数", m.group(3), upstreams),
                                 ("测试文件数", m.group(5), tests_named)):
        assert int(stated) == len(group), (
            f"清单写{label} {stated}，现场 {len(group)} 个")

    real = {"模块": sum(_lines(p) for p in modules),
            "上游草稿": sum(_lines(p) for p in upstreams),
            "测试": sum(_lines(p) for p in tests_all)}
    stated = {"模块": _num(m.group(2)), "上游草稿": _num(m.group(4)),
              "测试": _num(m.group(6))}
    for k in real:
        assert stated[k] == real[k], f"{k}：清单写 {stated[k]} 行，现场 {real[k]} 行"
    assert _num(m.group(7)) == sum(real.values()), (
        f"合计写 {m.group(7)} 行，三个分项加起来是 {sum(real.values())} 行")


def test_the_test_count_here_is_not_a_second_copy(doc_text):
    """清单里那个测试条数，**不许自成一套** —— 它必须和 README 那处（已被现场核过）一致。

    真正去数一遍的是 `test_readme_claims.py`：它拿 `pytest --collect-only` 对
    README 里的数字。这里只保证**这一份没有抄歪**：两处数字必须相等。
    两份各自去数一遍，等于把同一件事验两遍，还多花一次收集。
    """
    from test_readme_claims import README
    readme = README.read_text(encoding="utf-8")

    a = re.search(r"pytest verification/tests -q\s*#\s*当前 (\d+) 条", readme)
    b = re.search(r"\*\*(\d+) 条\*\*，实测 `(\d+) passed`", doc_text)
    assert a, "README 里那个「当前 N 条」不见了"
    assert b, ("清单里「**N 条**，实测 `N passed`」这句话找不到了 —— "
               "改写法就把这里的正则一起改。")
    assert b.group(1) == b.group(2), (
        f"清单里自己就前后不一致：写「{b.group(1)} 条」，又说「{b.group(2)} passed」")
    assert b.group(1) == a.group(1), (
        f"README 写 {a.group(1)} 条，清单写 {b.group(1)} 条。"
        "两处指的是同一批测试，必须同进同退 —— "
        "README 那处是被 `pytest --collect-only` 核过的，清单这处以它为准。")
