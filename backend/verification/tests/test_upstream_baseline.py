"""我们基于**哪个上游版本** —— 这句话有人核吗？

`NOTICE`、两份 `README`、《开源及第三方资源使用清单》、两份上游 issue 草稿，
**六处**都写着同一个 commit 串。而《清单》里那张「改动的性质」表
（`--ignore-all-space` 得到 **19 行插入 / 0 行删除**）是**对着那个 commit 量出来的**：
串里错一位，整张表就指向一个不存在的基线，**而没有任何东西会响**。
这跟「数目字写死在正文里」是同一个病，只不过这次写死的是一个四十位的串。

所以这里核两件事：

1. **六处写的是同一个串** —— 抄歪一处就红。
2. **那个 commit 真的在这个仓库里，而且是 `HEAD` 的祖先** —— 也就是「我们确实是基于它做的」
   这句话本身成立，不只是「串看起来对」。

**阴性才可能「没条件判」，阳性不用。** 浅克隆（`git clone --depth 1`）里祖先链可能被
边界截断 —— 所以**查出来是阴性**时，分不清「真的不是祖先」和「那一截没拉下来」，
那才跳过（跳过 ≠ 失败）。**查出来是阳性就直接采信**，浅不浅都一样：本仓自己就是浅克隆，
而基线 commit 在、祖先关系也成立。这两件事本装置分得很清楚（退出码 `0/1/2` 也是这么分的），
**别把它俩折成一个** —— 把「没条件判」报成「判不过」，正是本装置专门抓别人的那件事。
"""

from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

import pytest

HERE = pathlib.Path(__file__).resolve().parent          # verification/tests
VERIFICATION = HERE.parent
BACKEND = VERIFICATION.parent
REPO = BACKEND.parent

#: 写着「上游版本」的那六处。**都是对外的**（评委、上游读者、clone 下来的人都会看到）。
_STATED_IN = (
    REPO / "NOTICE",
    REPO / "README.md",
    REPO / "README-ZH.md",
    REPO / "docs" / "开源及第三方资源使用清单.md",
    VERIFICATION / "upstream" / "issue_01_memory_slicing.md",
    VERIFICATION / "upstream" / "issue_02_same_tick_collision.md",
)

_SHA = re.compile(r"\b([0-9a-f]{40})\b")

#: 一个**肯定不存在**的串，用来证明下面那条 git 检查不是恒过的（阴性对照）。
_BOGUS = "0" * 40


def _git(*args: str):
    """跑一条 git 命令。`git` 不在、浅克隆 —— 都可能返回 `None`（= 没条件判）。

    ⚠️ **`None` 不等于「这里不是仓库」**：`git` 不在才会返回 `None`。
    在**不是仓库**的目录里，`git` 会照常启动、照常退出，只是**退出码 128**
    （`fatal: not a git repository`）—— 那是一个**有返回值的失败**，不是「跑不起来」。
    分不清这两件事，就会把「没条件判」读成「判不过」（见 `_is_repo()`）。
    """
    if shutil.which("git") is None:
        return None
    try:
        return subprocess.run(["git", "-C", str(REPO), *args],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=120)
    except (OSError, subprocess.SubprocessError):        # pragma: no cover
        return None


def _is_repo(where: pathlib.Path | None = None) -> bool:
    """`where`（默认本仓库）**是不是一个 git 仓库** —— 问的是仓库在不在，不是 git 在不在。

    **这条区分是踩出来的**：有人从 GitHub 点「Download ZIP」拿到一份**没有 `.git`**
    的副本时，`git -C <那里> cat-file -t <基线串>` 会返回 **128**。此前那条测试把
    「返回值非零」一律当成「这个对象不在」，于是这种人会看到一条**红**，而红上写的
    指控是「**要么串打错了，要么这个 fork 的历史被人重写过**」。
    **真正的原因（这里根本没有历史可查）不但没说出口，还被换成了一个更重的指控。**
    这正是本装置专门抓别人的那件事：**把「没条件判」报成「判不过」**，
    而且**报错的原因还是错的** —— 比不报更坏。

    对照：同一件事在 `test_docs_claims.py` 那一侧**本来就是跳过的**。
    同一套纪律，一个地方执行了、另一个地方没有（与 D-32 同型）。
    """
    target = REPO if where is None else where
    if shutil.which("git") is None:
        return False
    try:
        out = subprocess.run(["git", "-C", str(target), "rev-parse", "--is-inside-work-tree"],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=120)
    except (OSError, subprocess.SubprocessError):        # pragma: no cover
        return False
    return out.returncode == 0 and out.stdout.strip() == "true"


def _sha_stated_in(path: pathlib.Path) -> str:
    if not path.is_file():                               # pragma: no cover
        pytest.fail(f"这一处不在了：{path} —— 它上面写着本作品基于哪个上游版本。")
    found = _SHA.findall(path.read_text(encoding="utf-8"))
    assert found, (
        f"`{path.name}` 里找不到那个 40 位的上游 commit 串了。"
        "**删掉不等于不用交代** —— 它是本作品对上游关系与自研边界的唯一落点；"
        "改写法就把这条测试一起改。")
    return found[0]


@pytest.fixture(scope="module")
def stated() -> str:
    return _sha_stated_in(_STATED_IN[0])


def test_all_six_places_state_the_same_commit(stated):
    """六处**同一个**串 —— 抄歪任何一处都当场红。"""
    others = {p: _sha_stated_in(p) for p in _STATED_IN[1:]}
    wrong = {p: s for p, s in others.items() if s != stated}
    assert not wrong, (
        "上游基线 commit 在不同文件里写得不一样：\n"
        + "\n".join(f"  {p.relative_to(REPO)}: {s}" for p, s in wrong.items())
        + f"\n以 `{_STATED_IN[0].name}` 为准：{stated}\n"
        "**先弄清哪个是对的再统一** —— 那张「改动的性质」表是对着它量出来的。")


def test_that_commit_really_is_our_ancestor(stated):
    """那个 commit 真的在仓库里，而且是 `HEAD` 的祖先。

    **浅克隆（`git clone --depth 1`）不是「跳过」的理由，只是「失败不作数」的理由。**
    这两件事要分开：

    - 查出来是**阳性**（「在」/「是祖先」）—— 浅不浅都一样算数，直接采信；
    - 查出来是**阴性**（「不在」/「不是祖先」）—— 浅克隆里祖先链可能被边界截断，
      分不清是「真的不是」还是「这一截没拉下来」，那才是**没条件判**，跳过。

    一开始这里写成了「浅克隆一律跳过」，结果在本机**当场误跳过一次**：
    本仓就是浅克隆，而基线 commit 明明在、祖先关系也成立 —— 那本该是一条绿，
    却被跳掉了。**能判的判成「不判」，和判错一样是在放水。**

    **另一头也栽过**：这里曾经把「`git` 返回非零」当成「这个对象不在」，
    于是**没有 `.git` 的副本**（从 GitHub 下载 ZIP 就是）会撞上一条红，
    而红上指控的是「历史被人重写过」。**没条件判 ≠ 判不过** —— 先问清仓库在不在。
    """
    if not _is_repo():
        pytest.skip(
            f"这里不是 git 仓库（`{REPO}` 下没有 `.git`）—— 比如从 GitHub "
            "点「Download ZIP」拿到的副本。**没有历史可查，所以这一条是「没条件判」，"
            "不是「判不过」**：既不能说基线 commit 是祖先，也不能说它不是。"
            "想要这条检查成立，用 `git clone` 拿仓库（顺带这样才复核得了那张改动表）。")
    kind = _git("cat-file", "-t", stated)
    assert kind is not None, "git 起不来，这一条判不了。"
    assert kind.returncode == 0, (
        f"`{stated}` 在这个仓库里**不是一个对象** —— 六处都写着它，"
        "可它根本不存在。要么串打错了，要么这个 fork 的历史被人重写过。")
    assert kind.stdout.strip() == "commit", (
        f"`{stated}` 是个 {kind.stdout.strip()}，不是 commit。")

    anc = _git("merge-base", "--is-ancestor", stated, "HEAD")
    if anc is not None and anc.returncode == 0:
        return                                            # 阳性：采信，浅克隆也一样
    shallow = _git("rev-parse", "--is-shallow-repository")
    if shallow is not None and shallow.stdout.strip() == "true":
        pytest.skip(f"`{stated}` 不在祖先链上，但**这里是浅克隆**，"
                    "分不清是「真的不是」还是「那一截没拉下来」。"
                    "想要这条检查成立，就拉全历史再跑一次。")
    assert anc is not None, "git 跑不动了，这一条判不了。"
    pytest.fail(
        f"`{stated}` 不是 `HEAD` 的祖先 —— 「本项目基于它做」这句话就不成立。\n"
        "（如果你刚 rebase / squash 过历史，这就是代价：基线与衍生的关系断了。）")


def test_the_ancestor_check_is_not_vacuous(stated):
    """阴性对照：拿一个**肯定不存在**的串去问同样的问题，它必须说「不是」。

    没有这一条，上面那条测试可能是恒真的 —— 比如 `git` 在别的机器上换了行为、
    或者命令写错却恰好返回 0，它就会一直绿，而基线其实早就漂了。
    「一条永远绿的检查」和没有检查是一回事（本装置在别处栽过这个跟头）。
    """
    if not _is_repo():
        pytest.skip("这里不是 git 仓库：这一条没有可对照的东西（理由同上）。")

    kind = _git("cat-file", "-t", _BOGUS)
    assert kind is not None and kind.returncode != 0, (
        f"`{_BOGUS}` 不该存在，可 `git cat-file -t` 说它是个 "
        f"{kind.stdout.strip() if kind else '?'} —— 那么上面那条检查什么都没核。")

    anc = _git("merge-base", "--is-ancestor", _BOGUS, "HEAD")
    assert anc is not None and anc.returncode != 0, (
        "一个不存在的串居然被判成了 `HEAD` 的祖先 —— 上面那条检查是恒真的。")


def test_the_repo_check_is_not_vacuous():
    """阴性对照：本仓**是**仓库、一个不在任何仓库里的目录**不是** —— 两问两答都得有。

    守的是上面那两道 `_is_repo()` 门。**两个方向都得堵**：

    - 谓词**恒真** → 门永远开着 → 没有 `.git` 的副本又撞上那条指控「历史被重写过」的红；
    - 谓词**恒假** → 门永远关着 → **本仓里这条检查再也不跑了**，
      而本仓恰恰是唯一它能判得动的地方 —— **能判的判成「不判」，和判错一样是在放水**
      （`D-37` 就是这么栽的：那条跳过一度把本仓里一条本该绿的检查跳掉了）。

    阳性那一半永远可判（本仓一定在），所以它写在前面、无条件执行。
    """
    assert _is_repo(), (
        f"本仓（{REPO}）居然被判成「不是 git 仓库」——那么上面那条祖先检查"
        "在**本仓里也永远是跳过的**，等于没跑。")

    empty = pathlib.Path(tempfile.mkdtemp(prefix="not-a-repo-"))
    try:
        if _is_repo(empty):
            # `git rev-parse --is-inside-work-tree` 会**向上找**。临时目录落在某个
            # 仓库里面时，这台机器上就造不出「不在任何仓库里」的目录 ——
            # 那是环境限制，不是发现（D-21 的教训：别让环境差异报成红）。
            pytest.skip(
                f"{empty} 落在某个仓库里面，这台机器上造不出「不在任何仓库里」的目录，"
                "阴性那一半没法验。（**阳性那一半已经过了**，所以门本身不是恒真的。）")
        assert not _is_repo(empty), (
            f"{empty} 里没有 `.git`，却被判成 git 仓库 —— 谓词恒真，上面那两道门形同虚设。")
    finally:
        shutil.rmtree(empty, ignore_errors=True)


# ---------------------------------------------------------------------------
# `NOTICE` 那张改动表 —— **它是《清单》里那张表的第二份副本**
#
# 2026-09-19 发现：`backend/requirements.txt` 被改了 15 行（`mcp<2` 上界 +
# `tiktoken` 锁定），**《清单》那份早就补上了这一行，`NOTICE` 这份没跟着补**。
# 而 `NOTICE` 抬头那句宣示比《清单》更强：「除下表所列文件外，上游代码未作改动
# —— 包括未改动上游目录树中的任何其他文件。」表里少一行，**这句话就是假的**。
#
# 根因不是「忘了改」，是**同一张表有两份副本，而只有一份长了机检**：
# D-38 修的是《清单》那份，修的时候没人想到另一份还在原地。
# 所以这里钉两件事：**行一个不多一个不少**，以及**两份副本写的数目不许分家**。
#
# `NOTICE` 这张的判据比《清单》那张严：《清单》问的是「表里的数目对不对」，
# 这里问的是「表 == 对基线 diff 出来的全部上游改动文件」——
# 多列一个没改过的上游文件，和少列一个改过的，都是在说假话。
# ---------------------------------------------------------------------------

_NOTICE = REPO / "NOTICE"


def _notice_table_rows() -> list:
    """`NOTICE` 那张「对上游文件的改动声明」表的数据行（表头/分隔行不要）。"""
    lines = _NOTICE.read_text(encoding="utf-8").splitlines()
    start = next((i for i, l in enumerate(lines) if l.startswith("| 上游文件 | 改动 |")), None)
    assert start is not None, (
        "`NOTICE` 里那张改动表的表头找不到了 —— 改写法就把这里的定位一起改。")
    rows = []
    for line in lines[start + 2:]:
        if not line.startswith("|"):
            break
        rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    return rows


def _changed_vs_baseline():
    """对基线 commit 的改动：`{路径: 状态首字母}`。`None` = 没条件判。"""
    out = _git("-c", "core.quotePath=false", "diff", "--name-status",
               _sha_stated_in(_STATED_IN[0]))
    if out is None or out.returncode != 0:
        return None
    status = {}
    for line in out.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 2:                    # 重命名会是 `R100\t旧\t新`，取新路径
            status[parts[-1].strip().replace("\\", "/")] = parts[0][0]
    return status


def test_notice_lists_exactly_the_upstream_files_we_touched():
    """`NOTICE` 那张表 == 被我们改过的上游文件，**一个不多一个不少**。

    这是「除下表所列文件外，上游代码未作改动」这句话的**唯一**机检。
    在这条测试之前，那张表少列了 `backend/requirements.txt` —— 十五行的改动，
    表里没有它，而抬头那句照旧说得斩钉截铁。**多列一行很显眼，少列一行完全不显眼**，
    所以两个方向都要判。
    """
    changed = _changed_vs_baseline()
    if changed is None:
        pytest.skip("拿不到 git / 这里不是 git 仓库 / 没有基线 commit：无从对 diff。"
                    "（浅克隆、或从 GitHub 下载的 ZIP 都会这样 —— "
                    "想要这条检查成立就用 `git clone` 拉全历史。）")

    # 阴性对照：我们自己的新文件必须是「新增」。若 `--name-status` 解析坏了、
    # 把什么都读成「改动」，下面「一个不多」那半就会变成恒真的废话。
    assert changed.get("NOTICE") == "A", (
        "`NOTICE` 在本仓库里是**新增文件**，可 diff 的状态不是 `A` —— "
        "状态解析坏了，这条测试的「一个不多」那半就不可信了。")

    touched = sorted(p for p, s in changed.items() if s != "A")
    assert touched, (
        "对基线 commit 一个上游文件都没改过 —— 那先去查基线串，不是这条测试的事。")

    listed = [r[0].strip("`").strip() for r in _notice_table_rows()]
    missing = [p for p in touched if p not in listed]
    extra = sorted({p for p in listed if changed.get(p) != "M"})
    assert not (missing or extra), (
        "`NOTICE` 那张改动表和对基线的 diff 对不上 —— "
        "而它抬头上写着「除下表所列文件外，上游代码未作改动」。\n"
        + ("  表里没有、但确实改过：\n" + "\n".join(f"    {p}" for p in missing) + "\n" if missing else "")
        + ("  表里有、但没改过（或根本不是上游文件）：\n"
           + "\n".join(f"    {p}" for p in extra) + "\n" if extra else "")
        + "**补上/删掉，并把下面那段「改动的性质」里的数目一起重测。**"
          "（若要列一行目录，得先把表头那句宣示改掉，再改这条检查。）")


def test_notice_states_the_same_numbers_as_the_inventory():
    """两份副本的**数目**不许分家 —— 引《清单》那张表，不另量一遍 git。

    判据不重复劳动：《清单》那张表的数目已经被 `test_docs_claims.py`
    逐行对着现场 diff 核过了，所以这里只要求 `NOTICE` 写的是同一个数。
    「同一张表两份副本各说各的」，正是漏掉 `backend/requirements.txt` 那次的根因。
    """
    from test_docs_claims import _NUMBERS, _diff_table_rows
    inventory = REPO / "docs" / "开源及第三方资源使用清单.md"
    stated = {}
    for cells in _diff_table_rows(inventory.read_text(encoding="utf-8")):
        path = cells[0].strip("`").strip()
        m = _NUMBERS.search(cells[2])
        if m:
            stated[path] = (int(m.group(1)), int(m.group(2) or 0))
    assert stated, "《清单》那张表里一行带数目的都没有 —— 先去看 `test_docs_claims.py`。"

    text = _NOTICE.read_text(encoding="utf-8")

    # ① 逐个点名的那几份：`NOTICE` 必须写出同一个插入数。
    for path in ("README.md", "README-ZH.md", "backend/requirements.txt"):
        assert path in stated, f"《清单》表里少了 `{path}` 那一行。"
        ins, _ = stated[path]
        assert f"`+{ins}`" in text, (
            f"《清单》说 `{path}` 是 `+{ins}`，而 `NOTICE` 里找不到这个数 —— "
            "两份副本分家了，改一处必须改另一处。")

    # ② 三个入口脚本是**合并成一句**说的：总数对得上才算。
    scripts = ("backend/scripts/run_parallel_simulation.py",
               "backend/scripts/run_reddit_simulation.py",
               "backend/scripts/run_twitter_simulation.py")
    ins_sum = sum(stated[p][0] for p in scripts if p in stated)
    del_sum = sum(stated[p][1] for p in scripts if p in stated)
    assert f"{ins_sum} 行插入、{del_sum} 行删除" in text, (
        f"三个入口脚本合计在《清单》里是 {ins_sum} 插入 / {del_sum} 删除，"
        f"而 `NOTICE` 里那句「{ins_sum} 行插入、{del_sum} 行删除」不在了 —— "
        "两份副本分家了。")


#: `NOTICE` 第三栏那个日期的形状。**只取开头那个 `YYYY-MM-DD`** ——
#: 后面可以挂人话（比如「（`mcp<2` 先落在 09-17）」），人话不参与比对。
_NOTICE_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def _date_mismatch(path: str, stated: str) -> str | None:
    """现场问一次 git「这个文件最后一次改动是哪天」，和写死的比。

    对得上返回 `None`。抽成函数是为了能被下面那条**阴性对照**直接喂一个错日期 ——
    没有那一条，这段比较逻辑自己是恒真的还是真在比，谁也说不清。
    """
    out = _git("log", "-1", "--date=short", "--format=%ad", "--", path)
    if out is None or out.returncode != 0 or not out.stdout.strip():
        return None                      # 没条件判 —— 由调用处决定跳过
    actual = out.stdout.strip()
    if actual == stated:
        return None
    return f"  {path}：`NOTICE` 写 {stated}，现场是 {actual}"


def test_notice_dates_match_the_last_commit_touching_each_file():
    """表里第三栏那个日期是**量出来的**，不是抄的。

    AGPL-3.0 §5(a) 要的是「显著的改动应予说明」**并且给出相关日期**。日期写错
    和改动清单写漏是同一类问题：**声明的比实际强**。而在这一栏之前，
    `NOTICE` 上写的是一句「改动均在本 fork 的工作期内完成」—— 那是范围，
    不是日期；范围可以一直是对的，日期会烂。
    """
    if not _is_repo():
        pytest.skip("这里不是 git 仓库：查不了提交历史，这一栏没条件判"
                    "（与上面那条祖先检查同样的道理）。")
    wrong, checked = [], 0
    for cells in _notice_table_rows():
        if len(cells) < 3:
            pytest.fail(
                f"`NOTICE` 那张表少了第三栏（`{cells[0]}` 那一行只有 {len(cells)} 格）"
                " —— 改写法就把这条检查一起改。")
        path = cells[0].strip("`").strip()
        m = _NOTICE_DATE.match(cells[2].strip())
        assert m, (
            f"`{path}` 那一行的日期不是 `YYYY-MM-DD` 开头：{cells[2]!r} —— "
            "「最后改动」这一栏要能被机器读。")
        if _git("log", "-1", "--date=short", "--format=%ad", "--", path) is None:
            pytest.skip("git 起不来，这一条判不了。")
        bad = _date_mismatch(path, m.group(1))
        if bad:
            wrong.append(bad)
        checked += 1
    assert not wrong, (
        "`NOTICE` 里那些日期和提交历史对不上了：\n" + "\n".join(wrong) +
        "\n**改了上游文件就顺手把这一栏改掉** —— 它和那张改动表一样，"
        "是「我们到底动过什么」的一部分。")
    assert checked >= 7, (
        f"只核到 {checked} 行带日期的 —— 表被拆散或改写了，这条检查就等于没跑。")


def test_the_date_comparison_would_flag_a_wrong_date():
    """阴性对照：拿真日期喂进去它不会乱报，改一天就必须报。

    没有这一条，`_date_mismatch` 完全可能是**恒返回 `None`** 的
    （命令写错、路径没传对、git 的输出被读歪）—— 那么上面那条测试就是一条
    永远绿的检查，和没有检查是一回事。
    """
    if not _is_repo():
        pytest.skip("这里不是 git 仓库：没有可对照的历史（理由同上）。")
    rows = _notice_table_rows()
    path = rows[0][0].strip("`").strip()
    m = _NOTICE_DATE.match(rows[0][2].strip())
    assert m, f"`{path}` 那一行的日期读不出来：{rows[0][2]!r}"
    stated = m.group(1)

    assert _date_mismatch(path, stated) is None, (
        "把 `NOTICE` 里那个真日期喂进去它也说不对 —— 那 `_date_mismatch` 本身坏了，"
        "上面那条测试是假绿。")
    assert _date_mismatch(path, "1999-01-01") is not None, (
        "把日期改成 1999-01-01 它还说对得上 —— 这条比较根本没在看日期。")
