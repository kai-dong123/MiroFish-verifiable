"""对账自检的产物必须**还在**，而且必须**对得上当下那两个文件**。

`RECONCILE_SELFCHECK.md` 是 `README.md` 里「**也验过它会红**」那句话的证据。
和变异留痕一样，证据最容易坏的方式不是丢，是**过期** —— 草稿改了、留痕没重跑，
于是它继续替一份已经不在的草稿作证，而报告上的日期和哈希看着都挺像真的。

它**不重跑**自检（那要二十几秒）；只核几件快事：

1. 两份产物在不在、能不能读；
2. 报告里记的 `sha256`，和现在磁盘上的脚本与草稿，是不是同一份；
3. **植入的那一处还能不能植进去** —— 草稿①里 `range(90)` 得恰好出现一次；
4. 记下来的那一轮「该红的红了、不该动的没动」是不是真的如此。

对不上就红，并且告诉你**下一步敲什么命令**。
"""

from __future__ import annotations

import json
import os
import pathlib

import pytest

from verification import mutations as MU
from verification import reconcile_selfcheck as RC

HERE = pathlib.Path(__file__).resolve().parent          # verification/tests
VERIFICATION = HERE.parent
BACKEND = VERIFICATION.parent
REPORT = VERIFICATION / "reconcile_selfcheck_report.json"
MARKDOWN = VERIFICATION / "RECONCILE_SELFCHECK.md"

_RERUN = "重新跑一次：`cd backend && python -m verification.reconcile_selfcheck`"


@pytest.fixture(scope="module", autouse=True)
def _not_inside_a_mutation_run():
    """变异轮里整个跳过。

    和 `test_mutation_evidence.py` 那条不一样：这里**不是**因为「否则会对不上」——
    变异那几轮不碰本文件核的这两个文件（`reconcile_selfcheck.py` 和两份草稿），
    当场核也是对的。跳过的理由只是**省时间与口径统一**：那些轮次跑十几遍，
    不该每一遍都来这儿重问一次同样的三件事。

    所以这条在**普通 `pytest` 运行**里跑 —— 那也正是该抓它的时候。
    """
    if os.environ.get(MU._MUTATION_ENV):
        pytest.skip(f"正在跑变异 {os.environ[MU._MUTATION_ENV]}：这两份产物不受它影响，跳过只为省时间")


@pytest.fixture(scope="module")
def report() -> dict:
    if not REPORT.is_file():
        pytest.fail(f"对账自检的产物不在：{REPORT.name}。{_RERUN}")
    return json.loads(REPORT.read_text(encoding="utf-8"))


def test_the_human_readable_side_is_there_too(report):
    """机读的那份在，不等于人读的那份在 —— 两边都要有。"""
    assert MARKDOWN.is_file(), f"人读的那份不在：{MARKDOWN.name}。{_RERUN}"
    text = MARKDOWN.read_text(encoding="utf-8")
    assert len(text) > 800, "这份报告短得不像话，多半是半截产物"
    for rnd in ("A", "B"):
        assert f"### {rnd} 轮" in text, f"人读的那份里没有 {rnd} 轮。{_RERUN}"


def test_the_report_does_not_claim_to_be_a_pass_rate(report):
    """这张表上的红色**是期望的结果** —— 别让人把它读成通过率。"""
    assert report["not_a_pass_rate"] is True
    s = report["summary"]
    assert s["all_ok"] is True, (
        "自检自己都没全对上 —— 先逐项看报告里那张核对表再动报告"
        "（**不许只把期望值改成漂移后的样子**）")
    assert report["reverted"] is True, (
        "跑完没把草稿改回去 —— 先 `git diff` 看清楚工作区被改成了什么样")


def test_the_recorded_checks_all_passed(report):
    """没通过的项必须一条不剩，否则 `all_ok` 就是个骗人的汇总。"""
    bad = [c["name"] for c in report["checks"] if not c["ok"]]
    assert not bad, f"报告里记着没通过的项：{bad}。{_RERUN}"
    assert report["summary"]["checks_ok"] == report["summary"]["checks_total"]


def test_the_planted_round_changed_only_what_it_should(report):
    """**这是整份产物存在的理由**：把草稿改坏一个数字，对账要当场响。

    而且只能响在**该响的那两行**上 —— 第二行（同拍违反数）来自另一条复现，
    它跟着一起红，说明响的不是「草稿变了」而是「对账坏了」。
    """
    a, b = report["rounds"]["A"], report["rounds"]["B"]
    assert a["reconcile_rc"] == 0, "A 轮（原样）本该一致"
    assert b["reconcile_rc"] == 1, "B 轮（植入后）本该报不一致"

    def verdict(rnd, what):
        return next(r["verdict"] for r in rnd["rows"] if r["what"] == what)

    for what in RC.EXPECT_RED:
        assert verdict(b, what) == "不一致", (
            f"{what} 在植入后**没红** —— 要么对账失去了鉴别力、要么植入没生效。"
            f"**先看那句论断还成不成立**，别急着改期望值。{_RERUN}")
    for what in RC.EXPECT_GREEN:
        assert verdict(b, what) == "一致", (
            f"{what} 不该受影响却红了 —— 红的原因就不是那个植入。{_RERUN}")


def test_the_readme_claim_is_what_was_measured(report):
    """报告里「声明」和「实测」两列必须**逐项相等**。

    这条钉的是这份产物的口径：它存在的意义是替 `README.md` 那句话作证，
    不是替一句改过的期望值作证。
    """
    b = report["rounds"]["B"]
    for what, (claim_dev, claim_draft) in report["claim_from_readme"].items():
        row = next(r for r in b["rows"] if r["what"] == what)
        assert (row["device"], row["draft"]) == (claim_dev, claim_draft), (
            f"{what}：声明 装置{claim_dev}→草稿{claim_draft}，"
            f"实测 装置{row['device']}→草稿{row['draft']}。"
            f"材料里的数字要跟着实测改，**别把实测改成声明**。{_RERUN}")


def test_the_planted_number_is_still_there_to_plant(report):
    """植入点还得在，而且**只此一处**。

    这条比哈希更直白：草稿①要是被改过，丢的往往就是这行；而 `range(90)`
    命中不止一次时，`str.replace(..., 1)` 换掉的可能不是对账看的那一处。
    """
    plant = report["plant"]
    text = (BACKEND / plant["file"]).read_text(encoding="utf-8")
    assert text.count(plant["old"]) == 1, (
        f"{plant['file']} 里 {plant['old']!r} 命中 "
        f"{text.count(plant['old'])} 次（要求正好 1 次）—— 草稿动过了，"
        f"先看 README 那句论断还成不成立。{_RERUN}")


def test_the_recorded_hashes_still_describe_the_files_on_disk(report):
    """报告不能替一份**已经不在**的代码作证。"""
    assert report["script"]["sha256"] == RC._sha(
        (VERIFICATION / "reconcile_selfcheck.py").read_text(encoding="utf-8")), (
        f"{report['script']['path']} 动过了，报告是改动之前的。{_RERUN}")

    for key, want in report["sources"].items():
        now = RC._sha((BACKEND / key).read_text(encoding="utf-8"))
        assert now == want, (
            f"{key} 的 sha256 与报告里记的对不上 —— 报告已经过期。{_RERUN}")
