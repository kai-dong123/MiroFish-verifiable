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
    """跑一条 git 命令。`git` 不在、没仓库、浅克隆 —— 都返回 `None`（= 没条件判）。"""
    if shutil.which("git") is None:
        return None
    try:
        return subprocess.run(["git", "-C", str(REPO), *args],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=120)
    except (OSError, subprocess.SubprocessError):        # pragma: no cover
        return None


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
    """
    kind = _git("cat-file", "-t", stated)
    if kind is None:
        pytest.skip("拿不到 git（或这里不是仓库）：无从核这个串。")
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
    if _git("rev-parse", "--is-shallow-repository") is None:   # pragma: no cover
        pytest.skip("拿不到 git：这一条没有可对照的东西。")

    kind = _git("cat-file", "-t", _BOGUS)
    assert kind is not None and kind.returncode != 0, (
        f"`{_BOGUS}` 不该存在，可 `git cat-file -t` 说它是个 "
        f"{kind.stdout.strip() if kind else '?'} —— 那么上面那条检查什么都没核。")

    anc = _git("merge-base", "--is-ancestor", _BOGUS, "HEAD")
    assert anc is not None and anc.returncode != 0, (
        "一个不存在的串居然被判成了 `HEAD` 的祖先 —— 上面那条检查是恒真的。")
