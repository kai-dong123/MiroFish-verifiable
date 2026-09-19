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
def _not_inside_a_source_mutation_run():
    """变异轮里**有理由才跳** —— 不是「见了变异就跳」。

    这个文件量两样东西：`verification/` 下的行数，和清单第一节那张
    「对上游的改动」表。**只有前一样**会随源码被改坏而变 —— 那一轮里问它
    等于自问自答。清单那张表不一样：除非那一轮动的就是清单自己，
    否则它和源码被改坏没关系，**该跑就得跑**。

    原先这里写的是「只要在跑变异就跳过全部」——那正是本装置专门批评别人的
    那件事（**能判的判成不判**，见 `test_upstream_baseline.py` 里记着的那次误跳）。
    `D1` 那条变异（把清单里的数目改歪）当初就是因为这个才做不出来：
    它要抓的检查被那句无条件的跳过挡在了外面。
    """
    from verification import mutations as MU
    label = os.environ.get(MU._MUTATION_ENV)
    if not label:
        return
    if label == "baseline":
        return                        # 一点没改：量出来的就是真的，没有理由跳
    touched = MU.targets_of(label.removeprefix("mutation:"))
    if not touched:                   # 认不出这次动的是谁 —— 稳妥起见还是跳
        pytest.skip(f"正在跑变异 {label}：认不出这次动的是哪个文件，稳妥起见跳过。")
    if all(t.startswith("verification/") for t in touched):
        pytest.skip(f"正在跑变异 {label}：动的是 `verification/` 下的文件（{sorted(touched)}），"
                    "这个文件量的行数此刻本来就会变")


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


# ---------------------------------------------------------------------------
# 第一节那张「对上游的改动」表
#
# 那是本作品**最要命的一张表**：「交付本体是上游的衍生仓库」这句话全靠它落地，
# 而它此前是**纯手工**的。写这段检查之前，那张表里错了三处（都是实测出来的）：
#
#   1. `backend/requirements.txt` 被改了 15 行（`mcp<2` 上界 + `tiktoken` 锁定），
#      **表里根本没有这一行** —— 漏报自己的改动；
#   2. `.gitignore` 那格写「11 插入 / 2 删除」，而 `11` 是 `--stat` 的**变化行总数**
#      （9 插入 + 2 删除），插入数被多读了一遍，实际是 9 / 2；
#   3. 表头没写用不用 `--ignore-all-space`，而三脚本那行用的是忽略空白、
#      `.gitignore` 那行用的是原始 —— **同一张表里两种口径**，谁也看不出来。
#
# 三处都是「数字看起来和真的一样」那一类。所以这里两件事一起核：
# **逐行的数目对现场 diff**，以及**改动过的文件一个都不能漏**。
# ---------------------------------------------------------------------------

_NUMBERS = re.compile(r"(\d+) 行插入(?: / (\d+) 行删除)?")


def _baseline() -> str:
    """上游基线 commit —— 从写它的那六处取，不在这里再抄一遍。"""
    from test_upstream_baseline import _STATED_IN, _sha_stated_in
    return _sha_stated_in(_STATED_IN[0])


def _diff_table_rows(doc_text: str) -> list:
    """只取第一节那张表的数据行（表头/分隔行不要），返回每个单元格的列表。

    定位方式是从表头往下取连续的 `|` 开头的行 —— 不靠「第几个表格」这种会漂的说法。
    """
    lines = doc_text.splitlines()
    start = next((i for i, l in enumerate(lines) if l.startswith("| 上游文件 | 改动 |")), None)
    assert start is not None, (
        "第一节那张「对上游的改动」表的表头找不到了 —— "
        "改写法就把这里的定位一起改。")
    rows = []
    for line in lines[start + 2:]:
        if not line.startswith("|"):
            break
        rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    return rows


def _mismatch(path: str, stated_ins: int, stated_del: int) -> str | None:
    """现场量一次 `path`，和写死的数目比。对得上返回 `None`，对不上返回人话。

    抽成函数是为了能被下面那条**阴性对照**直接喂一个错数字 —— 没有那一条，
    这段比较逻辑自己是恒真的还是真在比，谁也说不清。
    """
    from test_upstream_baseline import _git
    out = _git("diff", "--numstat", "--ignore-all-space", _baseline(), "--", path)
    if out is None or out.returncode != 0:
        return None                      # 没条件判 —— 由调用处决定跳过
    text = out.stdout.strip()
    actual_ins, actual_del = (int(x) for x in text.split()[:2]) if text else (0, 0)
    if (actual_ins, actual_del) == (stated_ins, stated_del):
        return None
    return (f"  {path}：清单写 {stated_ins} 插入 / {stated_del} 删除，"
            f"现场是 {actual_ins} 插入 / {actual_del} 删除")


def test_every_changed_file_is_listed_in_the_diff_table(doc_text):
    """表里**一个改动过的文件都不能漏** —— 漏报自己的改动，也是「边界说不清」。

    这是这张表最容易烂的地方，而且烂了看不出来：多列一行很显眼，
    **少列一行完全不显眼** —— 读者只看到一张整齐的表。
    （真实发生过：`backend/requirements.txt` 被改了 15 行，表里没有它。）
    """
    from test_upstream_baseline import _git
    # `-c core.quotePath=false`：**不加它，git 会把非 ASCII 路径转成八进制转义**
    # （`docs/\345\274\200...`）—— 于是清单里那个中文文件名永远匹配不上，
    # 这条检查会以「漏列一个文件」的样子报假警。这个坑当场踩到过。
    out = _git("-c", "core.quotePath=false", "diff", "--name-only", _baseline())
    if out is None or out.returncode != 0:
        pytest.skip("拿不到 git / 这里不是 git 仓库 / 没有基线 commit：无从对 diff。"
                    "（浅克隆 `--depth 1`、或从 GitHub 下载的 ZIP，都会这样 —— "
                    "想要这条检查成立就用 `git clone` 拉全历史。）")

    changed = {l.strip().replace("\\", "/") for l in out.stdout.splitlines() if l.strip()}
    assert changed, "对基线 commit 的 diff 是空的 —— 那本作品就不是衍生作品了，先查基线串。"
    rows = _diff_table_rows(doc_text)
    assert len(rows) >= 8, (
        f"那张表只有 {len(rows)} 行 —— 被拆散或改写了？这一条检查的就是它的完整性。")
    listed = {r[0].strip("`").strip() for r in rows}
    dirs = tuple(p.rstrip("/") + "/" for p in listed if p.endswith("/"))

    missing = sorted(p for p in changed
                     if p not in listed and not p.startswith(dirs))
    assert not missing, (
        "这些文件被改过（或新增），但那张表里没有：\n"
        + "\n".join(f"  {p}" for p in missing)
        + "\n**加上去，并把数目量准**；或者把表头那句「改动清单」改掉。"
          "漏报自己的改动，和把没用到的东西写进依赖表一样，都是自研边界没说完。")


def test_the_diff_numbers_match_a_live_diff(doc_text):
    """表里每一行的插入/删除数，都拿现场 diff 重算一遍。"""
    rows = _diff_table_rows(doc_text)
    wrong, checked = [], 0
    for cells in rows:
        path = cells[0].strip("`").strip()
        m = _NUMBERS.search(cells[2])
        if not m:
            continue                      # 新增文件/目录那几行报的是「—」
        assert not path.endswith("/"), f"目录行不该写数目：{cells[0]}"
        ins, dele = int(m.group(1)), int(m.group(2) or 0)
        if not _can_diff(path):
            pytest.skip(f"拿不到 git / 这里不是 git 仓库 / 没有基线 commit：核不了 {path}。")
        bad = _mismatch(path, ins, dele)
        if bad:
            wrong.append(bad)
        checked += 1
    assert checked >= 6, (
        f"只核到 {checked} 行带数目的 —— 表被改写了就等于没查。")
    assert not wrong, (
        "对上游的改动数目对不上了：\n" + "\n".join(wrong) +
        "\n量法写在表头：`git diff --numstat --ignore-all-space <基线>`。")


def _can_diff(path: str) -> bool:
    from test_upstream_baseline import _git, _is_repo
    if not _is_repo():
        return False
    out = _git("diff", "--numstat", "--ignore-all-space", _baseline(), "--", path)
    return out is not None and out.returncode == 0


def test_the_tokenizer_cache_bytes_agree_everywhere(doc_text):
    """编码表落盘字节数：**三处写的是同一个数**（清单、装置 README、生成的产物）。

    它是《清单》第二节里最后一个纯手写的数。三处不是「多抄一遍保险」，
    而是「同一件事写了三遍」—— 一处改了另两处不动，读的人不会知道该信哪个。
    产物那份是 `run_all` 实测落盘、写进环境一节的（`tokenizer_cache_bytes`）。

    **这条不新增跳过**：两份提交进仓库的（清单 + 装置 README）必须对上；
    生成的那份在盘上就一起核，不在就只核前两处 —— 少一份核对不是「没条件判」。
    """
    from test_readme_claims import README as DEVICE_README
    device = DEVICE_README.read_text(encoding="utf-8")

    def bytes_claims(text: str) -> set:
        # 按**上下文**定位（「落盘 … 字节」），不靠位数猜 ——
        # 第一版写成「7 位以上的数字+字节」，结果把《清单》里另一个数
        # `11,343 字节`（随包 LICENSE 的大小）连前面那个中文逗号一起吞了进来。
        return {int(m.replace(",", ""))
                for m in re.findall(r"落盘[^\d]{0,8}([\d,]+)\s*字节", text)}

    in_doc, in_device = bytes_claims(doc_text), bytes_claims(device)
    assert in_doc, "《清单》里那个「3,613,922 字节」找不到了 —— 改写法就一起改正则。"
    assert in_device, "装置 README 里那个编码表字节数找不到了 —— 它是这个数的另一处落点。"
    assert in_doc == in_device, (
        f"同一个数两处写得不一样：《清单》{sorted(in_doc)}，装置 README {sorted(in_device)}。\n"
        "两处指的都是 `run_all` 实测落盘的那个字节数 —— 以实测那份为准，"
        "**别顺手改一个**。")

    report = VERIFICATION / "verification_report.json"
    if report.is_file():                       # run_all 跑过才有；没有就不核这一份
        import json
        generated = json.loads(report.read_text(encoding="utf-8"))
        env = generated.get("environment", {})
        assert env.get("tokenizer_cache_bytes") in in_doc, (
            f"生成的产物里记的是 {env.get('tokenizer_cache_bytes')}，"
            f"而两处正文写的是 {sorted(in_doc)} —— "
            "正文那个数字是从这份产物里引的，引歪了就该按产物改回去。")


def test_the_number_comparison_would_flag_a_wrong_number():
    """阴性对照：**故意把一个数目写错**，喂给上面那段比较逻辑，它必须说「不对」。

    没有这一条，`_mismatch` 可能是恒返回 `None` 的（比如命令写错、
    或者 git 的输出解析出来永远是 0/0），那么上面那条测试就是绿的 ——
    而表里的数字其实一个都没被核过。**一条永远绿的检查等于没有检查**
    （本装置在别处栽过这个跟头，变异留痕就是为它存在的）。
    """
    path = "backend/requirements.txt"
    if not _can_diff(path):                                  # pragma: no cover
        pytest.skip("拿不到 git / 这里不是 git 仓库 / 没有基线 commit："
                    "这条对照没有可用的样本。")

    # 先拿**真数字**确认它不报错（否则下面那个「报错」可能只是因为它总在报错）
    from test_upstream_baseline import _git
    text = _git("diff", "--numstat", "--ignore-all-space", _baseline(), "--", path).stdout
    ins, dele = (int(x) for x in text.split()[:2])
    assert _mismatch(path, ins, dele) is None, (
        "拿真数字喂进去它也说不对 —— 那 `_mismatch` 本身坏了，上面那条测试是假绿。")
    assert _mismatch(path, ins + 1, dele) is not None, (
        "把插入数改大 1，它居然还说「对得上」—— 那么上面那条测试什么都没核。")
    assert _mismatch(path, ins, dele + 1) is not None, (
        "把删除数改大 1，它居然还说「对得上」—— 删除那一半没被核过。")
