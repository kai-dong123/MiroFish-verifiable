"""变异机器**自己的簿记** —— 还原、journal、锁、判据口径。

这个文件**不**写 `MU._MUTATION_ENV` 自跳过：`M1` 的靶子就是它 —— 那条变异
把「新增红条」退回「数红条」，只有这里会红。别把它并进
`test_mutation_evidence.py`：那个文件在变异轮整组跳过，`M1` 会永远红不了。

这里的测试**不碰仓库里的源码**：还原/journary/锁都在 `tmp_path` 上做，唯一
一个走 `main()` 的用例把 `MUTATIONS` / `BACKEND` / `_touched` / `_run_pytest`
全换成了替身。原因见 `test_only_never_touches_the_committed_reports`。
"""

from __future__ import annotations

import base64
import hashlib
import json
import pathlib

import pytest

from verification import mutations as MU


def _write_journal(path: pathlib.Path, mid: str, files: dict) -> None:
    """按 `_journal_write` 的格式手写一份 journal（不走真实路径的 `_rel`）。"""
    doc = {
        "mutation": mid,
        "written_at": "X",
        "files": {
            str(p): {
                "sha256": hashlib.sha256(b).hexdigest(),
                "bytes_b64": base64.b64encode(b).decode("ascii"),
            }
            for p, b in files.items()
        },
    }
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


def test_apply_and_revert_preserve_bytes_for_both_line_endings(tmp_path):
    """LF 与 CRLF 两份 fixture 都要**按原字节**回到原样。

    不能拿仓库里的真文件测：CI 是 Linux，checkout 出来全是 LF —— 那种测试在
    CI 上永远绿，等于没测。这里自己造两份。
    """
    for name, nl in (("lf.py", "\n"), ("crlf.py", "\r\n")):
        p = tmp_path / name
        original = nl.join(["x = 1", "y = 2", ""]).encode("utf-8")
        p.write_bytes(original)

        backups: dict = {}
        MU._apply([{"file": str(p), "old": "x = 1", "new": "x = 11"}], backups)
        assert p.read_bytes() != original
        assert MU._revert(backups) is True
        assert p.read_bytes() == original, f"{name} 还原后字节变了（换行被改写？）"


def test_newly_red_counts_ids_not_counts():
    """基线红的是 X、这一轮多红一条 Y —— 计数差是 0，集合差是 1。

    旧的计数口径会把 `expect=0` 的阴性对照读成「相符」：`0 == 0`。这正是
    「红了几条」和「多红了哪几条」的区别。
    """
    baseline = {"failed_ids": ["t.py::test_x"]}
    res = {"failed_ids": ["t.py::test_x", "t.py::test_y"]}

    assert MU._newly_red(res, baseline) == ["t.py::test_y"]
    assert MU._delta({"failed": 2, "failed_by_file": {"t.py": 2}},
                     {"failed": 1, "failed_by_file": {"t.py": 1}}, "t.py") == (1, 1), (
        "计数列本身没变 —— 它照实记「原样减基线」")
    assert MU._verdict(True, len(MU._newly_red(res, baseline)), 0) is False, (
        "阴性对照被计数差读成了「相符」")


def test_a_crashed_journal_with_intact_files_is_cleared_with_a_note(
        tmp_path, monkeypatch, capsys):
    """文件都还是原样 → 静默清掉，但**要打印一行**（静默成功也是一种静默）。"""
    f = tmp_path / "a.py"
    f.write_bytes(b"ok\n")
    j = tmp_path / "journal.json"
    monkeypatch.setattr(MU, "JOURNAL", j)
    _write_journal(j, "X1", {f: b"ok\n"})

    MU._recover_interrupted_journal()

    assert not j.exists()
    assert "文件已是原状，已清除" in capsys.readouterr().out


def test_a_crashed_journal_with_a_changed_file_refuses_and_points_at_recovery(
        tmp_path, monkeypatch):
    """有文件对不上 → 一个都不碰，指出文件与恢复命令。"""
    f = tmp_path / "a.py"
    f.write_bytes(b"bad\n")
    j = tmp_path / "journal.json"
    monkeypatch.setattr(MU, "JOURNAL", j)
    _write_journal(j, "X2", {f: b"ok\n"})

    with pytest.raises(MU.MutationPremiseError) as exc:
        MU._recover_interrupted_journal()

    assert "git checkout --" in str(exc.value)
    assert f.read_bytes() == b"bad\n", "拒绝的时候不许碰文件"


def test_recover_needs_yes_and_then_restores_bytes(tmp_path, monkeypatch):
    """`--recover` 先报差异、要 `--yes` 才写；写回的是**原字节**。"""
    f = tmp_path / "a.py"
    f.write_bytes(b"bad\n")
    j = tmp_path / "journal.json"
    monkeypatch.setattr(MU, "JOURNAL", j)
    monkeypatch.setattr(MU, "LOCK", tmp_path / ".lock")
    _write_journal(j, "X3", {f: b"ok\n"})

    assert MU._recover_cli(False) == 2
    assert f.read_bytes() == b"bad\n"
    assert MU._recover_cli(True) == 0
    assert f.read_bytes() == b"ok\n"
    assert not j.exists()


def test_the_lock_refuses_a_second_run_without_touching_anything(tmp_path, monkeypatch):
    """第二个 `run()` 必须**在动手之前**被挡下：不进 journal、不碰源码。"""
    monkeypatch.setattr(MU, "LOCK", tmp_path / ".lock")
    monkeypatch.setattr(MU, "JOURNAL", tmp_path / "journal.json")

    with MU._MutationLock():
        with pytest.raises(MU.MutationPremiseError):
            MU.run(only={"K0"})

    assert not (tmp_path / "journal.json").exists()


def test_only_never_touches_the_committed_reports(tmp_path, monkeypatch):
    """`--only` 不落产物 —— 这条性质原先只写在注释里，没有测试钉住。

    它防的不是现在的代码，是**将来有人把 `if only is None:` 删掉**：
    那一次手敲 `--only T1` 会把入库的 50 条报告覆盖成 1 条，而屏幕上一切正常。

    这里把整条链路换成替身，不动仓库源码，也不写那两份产物。
    """
    report = MU.HERE / "mutations_report.json"
    markdown = MU.HERE / "MUTATIONS.md"
    before = (report.read_bytes(), markdown.read_bytes())

    src = tmp_path / "t.py"
    src.write_text("A = 1\n", encoding="utf-8")
    fake_mut = [{
        "id": "K0", "group": "x", "what": "替身", "target": str(src),
        "edits": [{"file": str(src), "old": "A = 1", "new": "A = 2"}],
        "expect_failed": 0, "claim": "",
    }]
    fake_run = {"measured": True, "timed_out": False, "returncode": 0,
                "failed": 0, "passed": 1, "skipped": 0, "errors": 0,
                "failed_ids": [], "failed_by_file": {}, "seconds": 0.0,
                "raw_tail": ""}
    monkeypatch.setattr(MU, "MUTATIONS", fake_mut)
    monkeypatch.setattr(MU, "_touched", lambda: {src})
    monkeypatch.setattr(MU, "_rel", lambda p: str(p))
    monkeypatch.setattr(MU, "BACKEND", tmp_path)
    monkeypatch.setattr(MU, "LOCK", tmp_path / ".lock")
    monkeypatch.setattr(MU, "JOURNAL", tmp_path / "journal.json")
    monkeypatch.setattr(MU, "_run_pytest", lambda label: dict(fake_run))

    assert MU.main(["--only", "K0"]) == 0
    assert (report.read_bytes(), markdown.read_bytes()) == before, (
        "`--only` 把入库的完整报告覆盖了")
