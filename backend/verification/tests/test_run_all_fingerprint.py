"""读数集的指纹：**这份报告是不是用这棵树跑的**。

`run_all` 在动手之前与落盘之前各算一次 `_probe.readings_fingerprint()`。
两次不一样，说明跑的过程中输入被改过 —— 那种报告不能算数：它的三条读数
可能分别来自两棵树。

这里钉三件事：

1. 指纹本身能指出**缺了哪一份**（不补空串、不猜）；
2. 两次不一致时，`main()` 退 `2`，产物里 `run_stable: false`、
   `readings_sha256: null`（**留一份「这次没测到」的产物**，不是留旧的那份）；
3. 反向对照：两次一致时照常退原码、指纹写进产物 —— 少了这一半，
   一个「一律退 2」的实现也能让上面全绿。
"""

from __future__ import annotations

import json
import pathlib

import pytest

from verification import _probe as P
from verification import run_all as R


def _make_tree(root, *, drop=None):
    """在 `root` 下造一份完整的读数集（内容随意，只要能读成文本）。"""
    for rel in P.READING_SOURCES:
        if rel == drop:
            continue
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# {rel}\n", encoding="utf-8")
    return root


def test_the_environment_records_rejected_external_tables(monkeypatch):
    """外部表被拒这件事必须进环境一节 —— 否则账上还是「没设过外部缓存」。

    只退回仓库、不说为什么，读者会以为那台机器没有外部缓存；
    而真相是「有，但内容不对，被闸挡下了」。
    """
    from verification import tokenizer_cache as T

    monkeypatch.setattr(T, "describe", lambda: {
        "source": "vendor", "path": "vendor/x", "sha256": "a" * 64,
        "bytes": 1, "external_rejected": ["D:/bad-table"]})

    env = R._environment()
    assert env["tokenizer_external_rejected"] == ["D:/bad-table"]


def test_the_markdown_environment_table_shows_rejected_dirs(tmp_path):
    """人读的那份也要有 —— 评委看的是 MD，不是 JSON。"""
    env = {"tokenizer_external_rejected": ["D:/bad-table"]}
    md_path, js_path = R._write_report(
        str(tmp_path / "rep"), [("verification.repro_01_slicing", "切片", 0, "body")],
        env, readings=())

    md = pathlib.Path(md_path).read_text(encoding="utf-8")
    assert "被拒的外部缓存目录" in md
    assert "D:/bad-table" in md
    assert json.loads(pathlib.Path(js_path).read_text(encoding="utf-8"))[
        "environment"]["tokenizer_external_rejected"] == ["D:/bad-table"]


def test_a_missing_source_is_unmeasured_not_an_empty_hash(tmp_path):
    """缺一份就是**没测到**（`sha256=None`），而且点得出是哪一份。

    这条防的是「补一个空串充当值」：空串看着像一个哈希、能参与比较，
    读的人不会发现那一份其实根本没读到。
    """
    _make_tree(tmp_path, drop="repro_01_slicing.py")
    fp = P.readings_fingerprint(tmp_path)

    assert fp["sha256"] is None, "缺一份输入却算出了一个指纹"
    assert fp["complete"] is False
    assert fp["missing"] == ["repro_01_slicing.py"], (
        f"没指出缺的是哪一份：{fp['missing']!r}")


def test_two_calls_on_a_still_tree_agree(tmp_path):
    """树没动，两次必须一样 —— 否则门会在每个人的机器上假红一次。"""
    _make_tree(tmp_path)
    a = P.readings_fingerprint(tmp_path)
    b = P.readings_fingerprint(tmp_path)

    assert a["sha256"] is not None and a["sha256"] == b["sha256"]
    assert a["files"] == b["files"]
    assert len(a["files"]) == len(P.READING_SOURCES)


def _run_main(monkeypatch, tmp_path, fps):
    """把三条复现与对账都换成桩，只留下「指纹 → 落盘 → 退出码」这条链。"""
    seq = list(fps)
    monkeypatch.setattr(P, "readings_fingerprint", lambda *a, **k: seq.pop(0))
    monkeypatch.setattr(R, "_run_one", lambda *a, **k: (0, "（现造的正文）"))
    monkeypatch.setattr(R, "_reconcile", lambda *a, **k: (0, ()))
    monkeypatch.setattr(R, "_environment", lambda: {})
    return R.main(["--out", str(tmp_path / "rep")])


def _fp(sha):
    return {"sha256": sha, "complete": sha is not None, "missing": [],
            "files": {"README.md": "x"}, "tokenizer_table": "t"}


def test_a_tree_that_moves_under_the_run_writes_a_null_fingerprint(
        monkeypatch, tmp_path, capsys):
    """开始与结束不一致 → 退 `2`，且产物**明说这次没测到**。

    为什么不干脆不写产物：磁盘上留一份「这次没测到」的，比留一份旧的、
    看起来有效的产物好 —— 后者会被当成有效读数读走。
    """
    rc = _run_main(monkeypatch, tmp_path, [_fp("a" * 64), _fp("b" * 64)])
    out = capsys.readouterr().out

    assert rc == 2, f"读数集在跑的过程中变了，却退了 {rc} —— 该退 2（没测到）"
    assert "不成立" in out and "没测到" in out

    doc = json.loads((tmp_path / "rep.json").read_text(encoding="utf-8"))
    assert doc["run_stable"] is False
    assert doc["readings_sha256"] is None, (
        "报告不成立却写了一个指纹 —— 它会被当成有效读数读走")


def test_a_still_tree_still_reports_its_fingerprint(monkeypatch, tmp_path):
    """反向对照：两次一致时照常退原码，指纹写进产物。

    少了这一条，一个「一律退 2、一律写 null」的实现也能让上一条全绿。
    """
    rc = _run_main(monkeypatch, tmp_path, [_fp("c" * 64), _fp("c" * 64)])

    assert rc == 0, f"树没动、三条也都达到预期，却退了 {rc}"
    doc = json.loads((tmp_path / "rep.json").read_text(encoding="utf-8"))
    assert doc["run_stable"] is True
    assert doc["readings_sha256"]["start"] == doc["readings_sha256"]["end"] == "c" * 64


@pytest.mark.parametrize("sha", [None, "c" * 64])
def test_an_incomplete_tree_never_counts_as_stable(monkeypatch, tmp_path, sha):
    """开端就取不全（`sha256=None`）→ 两次「都是 None」也**不算稳定**。

    `None == None` 在 Python 里是 `True` —— 照直比会把「两次都没测到」
    判成「两次一致」。这正是本装置反复在防的那件事：没测到被当成结论。
    """
    rc = _run_main(monkeypatch, tmp_path,
                   [_fp(None), {"sha256": sha, "complete": False, "missing": [],
                                "files": {}, "tokenizer_table": None}])

    assert rc == 2, "一开始就取不全，却按稳定退了一个码"
    doc = json.loads((tmp_path / "rep.json").read_text(encoding="utf-8"))
    assert doc["run_stable"] is False
    assert doc["readings_sha256"] is None
