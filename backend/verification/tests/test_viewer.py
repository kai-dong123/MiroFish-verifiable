"""展示层：三态在一屏之内**等宽等重**并排，而且**不许被折成两态**。

按重要性排，这个文件钉三件事：

1. **三态不许互相折合** —— `不可判定` 既不是「通过」也不是「否决」；`trusted is None`
   既不是 `True` 也不是 `False`。渲染器只要把其中一态印成另一态，这一页就在说假话，
   而它**看起来照样完整**。这一组的头一条配**负例**：把渲染结果里的 `不可判定`
   一律替换成 `否决`（就是变异 `W1` 干的那件事），同一条判据必须当场翻脸 ——
   不翻脸就说明它写的是「屏幕上没有某个字」，不是「这一格没被折」。
2. **不合成比率、不显示耗时** —— 三个计数各是各的，页面里不许出现 `%`、`d/d`、
   `seconds`。这是本装置公开声明过的一条（`not_a_pass_rate`），页面自己也把
   「没有分母」写出来，而不是留着两个数让人自己去除。
3. **零 JavaScript、零外部引用、先转义再排版** —— 没有一个 `<script>`、没有一个
   `on*=`、没有一个外链；产物里要是带着 `<script>alert(1)</script>`，页面上必须
   变成 `&lt;script&gt;`。
4. **闸要拦住渲染器真会读的每一格** —— 形状不对就**不许走到渲染那一步**。这一组是
   踩出来的：闸原先只核到「判据行有没有 `verdict`」，而渲染时还会读 `what` / `check`、
   falsifier 的 `kind`、用例的 `moved`；缺了那一格，异常冒到顶就是退出码 `1`，而 `1`
   的意思是「渲染完成了，而且**发现了一件事**」—— **「没测到」被报成了「发现了一处
   折合」**。每一条都两问：问闸（当场抛 `ViewerError`）、再问入口（退 `2`、不落盘）。

前两组拿**入库那份产物 deepcopy 之后改几格**来测（不依赖某一次运行）；
最后一组读**入库的那两份**跑真正的入口，退出码三态各测一条。

**这个文件是变异 `W1` 的靶子** —— 所以它**不**写 `MU._MUTATION_ENV` 自跳过、也
**不**进 `_CANNOT_BE_MUTATION_TARGET` 的豁免名单。`W1` 把 `不可判定` 印成 `否决`，
这里必须当场红；红不起来，这个文件就是恒真的。
"""

from __future__ import annotations

import copy
import json
import pathlib
import re

import pytest

from verification import adjudicate as A
from verification import selfproof as S
from verification import viewer as V

HERE = pathlib.Path(__file__).resolve().parent          # verification/tests
VERIFICATION = HERE.parent
BACKEND = VERIFICATION.parent
VIEWER = VERIFICATION / "viewer.py"

ADJ_JSON = VERIFICATION / "adjudication_report.json"
SP_JSON = VERIFICATION / "selfproof_report.json"

TITLE = "测试用标题"

_RERUN = ("重新跑一次：`cd backend && python -m verification.adjudicate`、"
          "`python -m verification.selfproof`")

#: 夹具要把这五条从「通过」改成「不可判定」。选它们是因为它们正是**端到端**那一层，
#: 而这批读数里那一层本来就有一条缺读数（`B5`）—— 端到端最接近「量不到」，
#: 改成不可判定是最不勉强的造法。
_FLIP = ("E1", "E2", "E3", "E4", "E5")


@pytest.fixture(scope="module")
def adj() -> dict:
    if not ADJ_JSON.is_file():
        pytest.fail(f"裁决的产物不在：{ADJ_JSON.name}。{_RERUN}")
    return json.loads(ADJ_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def sp() -> dict:
    if not SP_JSON.is_file():
        pytest.fail(f"自证的产物不在：{SP_JSON.name}。{_RERUN}")
    return json.loads(SP_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def undecided(adj) -> dict:
    """一份**三态都在**的产物：把 `_FLIP` 那五条从「通过」改成「不可判定」。

    这批真实读数里只有 `B5`/`B8` 两条不可判定（`否决` 是 0 条），一屏之内看不出
    「另一种结果长什么样」。造一份不改变任何读数、只改结果的副本来测渲染器。
    """
    d = copy.deepcopy(adj)
    n = 0
    for r in d["rows"]:
        if r["id"] in _FLIP:
            assert r["verdict"] == A.PASS_, (
                f"{r['id']} 原本不是「{A.PASS_}」（是 {r['verdict']}）—— "
                "夹具的前提变了，改 `_FLIP` 之前先看清这批读数")
            r["verdict"] = A.UNDECIDED
            r["trusted"] = None
            r["no_trust_because"] = []
            r["tainted_by_railing"] = []
            r["undecidable_because"] = "夹具造的：读数里没有这一格"
            r["to_make_decidable"] = "夹具造的"
            n += 1
    assert n == len(_FLIP)
    d["summary"]["by_verdict"] = {A.PASS_: 8, A.FAIL_: 0, A.UNDECIDED: 7}
    return d


# ---------------------------------------------------------------------------
# 小工具：从页面里把某一行的那一段抠出来 / 只改一格
# ---------------------------------------------------------------------------

_CLAIM_HEAD = re.compile(
    r'<details class="claim" data-verdict="([^"]*)" data-layer="[^"]*">'
    r'<summary><span class="cid">([^<]*)</span>')


def _verdicts_of(html: str, cid: str) -> list[str]:
    """页面上 id 是 `cid` 的那些 `<details>` 各自带的结果。**一个 id 只该出现一次。**"""
    return [m.group(1) for m in _CLAIM_HEAD.finditer(html) if m.group(2) == cid]


def _summary_of(html: str, cid: str) -> str:
    """id 是 `cid` 那一行的**行内那一段**（`<summary>` 里，展开前的可见部分）。"""
    i = html.index(f'<span class="cid">{cid}</span>')
    return html[i:html.index("</summary>", i)]


def _dump(tmp_path, name: str, obj: dict) -> str:
    p = tmp_path / name
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return str(p)


def _undecided_ids(doc: dict) -> list[str]:
    return [r["id"] for r in doc["rows"] if r["verdict"] == A.UNDECIDED]


# ---------------------------------------------------------------------------
# 一、三态不许互相折合
# ---------------------------------------------------------------------------

def test_the_fixture_really_carries_the_three_states(undecided, adj):
    """**先自证这个文件不是空的。** 夹具真的造出了三种结果吗？

    只有两种结果的一屏，测不出「第三态有没有被折进前两态」—— 底下那些绿就都不算数。
    """
    三 = {A.PASS_, A.FAIL_, A.UNDECIDED}
    assert set(undecided["summary"]["by_verdict"]) == 三
    assert undecided["summary"]["by_verdict"] == {A.PASS_: 8, A.FAIL_: 0, A.UNDECIDED: 7}
    got = {r["verdict"] for r in undecided["rows"]}
    assert got <= 三, f"夹具里出现了三态之外的结果：{got - 三}"
    assert len(got) >= 2, f"夹具里只剩一种结果（{got}）—— 测不出「折合」这件事"
    assert set(adj["summary"]["by_verdict"]) == 三, "入库那份的 summary 就不是三态各一格"


def test_undecided_rows_never_render_as_denied(undecided, sp):
    """**核心那一条**：判「不可判定」的行，`data-verdict` 就得是「不可判定」。

    这是 `W1` 要撞的那面墙 —— 把这一格印成「否决」，屏幕上看着更整齐，
    而它把一个**没量到**的东西说成了一个**量到了、不成立**的东西。
    """
    ids = _undecided_ids(undecided)
    assert len(ids) == 7, f"夹具里不可判定只有 {len(ids)} 条，这条测试量不到东西"
    page = V.render_html(undecided, sp, TITLE)
    for cid in ids:
        got = _verdicts_of(page, cid)
        assert got, f"{cid} 那一行根本没渲染出来"
        assert set(got) == {A.UNDECIDED}, (
            f"{cid} 在产物里判的是「{A.UNDECIDED}」，页面上却印成了 {got} —— **三态被折了**")
        assert A.FAIL_ not in got, f"{cid} 被判成了「{A.FAIL_}」：没测到不等于不成立"


def test_the_verdict_on_screen_matches_the_verdict_in_the_artifact(undecided, sp):
    """**行内那格**（`<span class="cv">`）也得等于产物里的结果，不只是 `data-verdict`。

    两处任一处被折，这一条就红 —— 上面那条只盯属性，属性对了字形还能是另一个结果。
    """
    page = V.render_html(undecided, sp, TITLE)
    for r in undecided["rows"]:
        seg = _summary_of(page, r["id"])
        m = re.search(r'<span class="cv">(\S+) (\S+)</span>', seg)
        assert m, f"{r['id']} 那一行没有结果那格"
        assert m.group(2) == r["verdict"], (
            f"{r['id']} 产物里是「{r['verdict']}」，行内那格印的是「{m.group(2)}」")
        assert _verdicts_of(page, r["id"]) == [r["verdict"]], (
            f"{r['id']} 的属性那格和产物对不上")


def test_folding_undecided_into_denied_is_caught(undecided, sp):
    """**证上面那两条不是恒真的。**

    把页面里每一处 `不可判定` 都替换成 `否决` —— 这就是变异 `W1` 的形状（把
    「没量到」印成一个合法的别的值）。上面两条用的判据必须**当场翻脸**；
    不翻脸，就说明它们量的是「屏幕上没有某个字」，而不是「这一格没被折」。
    """
    ids = _undecided_ids(undecided)
    page = V.render_html(undecided, sp, TITLE)
    folded = page.replace(A.UNDECIDED, A.FAIL_)
    assert folded != page, "替换一个都没命中 —— 页面里压根没有这个结果，这条测试是空的"
    for cid in ids:
        got = _verdicts_of(folded, cid)
        assert got, f"{cid} 折叠之后那一行不见了"
        assert A.FAIL_ in got, (
            f"{cid} 折叠之后没有被读成「{A.FAIL_}」—— 上面那条判据在这个形状下**不翻脸**，"
            "它不是检查")
        assert set(got) != {A.UNDECIDED}


def test_trusted_none_is_not_rendered_as_false(undecided, sp):
    """`trusted is None` 走**第三路**：判不了**不是**「不采信」。

    折成 `False` 会让「不采信」虚高，折成 `True` 又等于替它背书 ——
    两个方向都是把没量到的东西说成了量到的。
    """
    page = V.render_html(undecided, sp, TITLE)
    for cid in _undecided_ids(undecided):
        seg = _summary_of(page, cid)
        assert "t-none" in seg, f"{cid} 那一行的采信格不是「判不了」那一路"
        assert "t-false" not in seg, f"{cid} 的采信格画成了「不采信」那一路"
        assert "不是「不采信」" in seg, (
            f"{cid} 那一行没有把「判不了 ≠ 不采信」说出来")
        assert "<strong>不采信</strong>" not in seg


def test_the_three_verdicts_are_rendered_with_equal_weight(adj, sp):
    """三态**等宽等重**：三格是同一个模板渲出来的，谁也不比谁显眼。

    这一页的全部主张就是三态并列；要是哪一态被加粗、放大、染成红绿，
    那一眼看过去就有一个「主结果」了 —— 而这里恰恰没有主结果。
    """
    page = V.render_html(adj, sp, TITLE)
    cells = re.findall(r'<div class="state">(.*?)</div>', page, re.S)
    assert len(cells) == 3, f"三态计数条该有三格，实际 {len(cells)} 格"
    # 去掉字形 / 名字 / 计数这三处**本来就该不同**的地方，剩下必须逐字相同。
    skeleton = {re.sub(r">[^<]*<", "><", c) for c in cells}
    assert len(skeleton) == 1, f"三格不是同一个模板：{skeleton}"
    assert "repeat(3,1fr)" in page, "三格不是等宽的"
    for v in (A.PASS_, A.FAIL_, A.UNDECIDED):
        assert v in page, f"三态里的「{v}」在页面上找不到"


# ---------------------------------------------------------------------------
# 二、不合成比率、不显示耗时
# ---------------------------------------------------------------------------

def test_the_page_does_not_manufacture_a_ratio(adj, sp):
    """三个计数各是各的 —— 页面上不许出现 `%`，也不许出现 `d/d` 这种合成。

    判不了的既不算通过也不算否决，所以**没有分母**。这一句页面自己说了出来，
    而不是留着两个数让人自己去除。
    """
    page = V.render_html(adj, sp, TITLE)
    assert "%" not in page, "页面上出现了百分号"
    bad = re.findall(r"\b\d+\s*/\s*\d+\b", page)
    assert not bad, f"页面上出现了比值写法：{bad}"
    assert "没有分母" in page, "页面没有把「没有分母」这句话写出来"


def test_no_timing_is_rendered(adj, sp):
    """产物里有 `seconds` 这一栏，但**这一页不读它**。

    读它就会把「这台机器当时多忙」摆到评委面前，而那跟结论没有关系
    （README 的「装与跑」里对同一个数说过同一句话）。判据落在**源码**上：
    这个字段的名字在展示层里一次都不出现 —— 那比「这一屏里没看见」结实，
    「耗时」两个字在产物自己的措辞里是有的（`为什么判不了` 那一段），
    所以页面上量不准，得量在它读不读那个字段上。
    """
    src = VIEWER.read_text(encoding="utf-8")
    assert "seconds" not in src, "展示层引用了 `seconds` 这一栏 —— 它把耗时读进来了"
    page = V.render_html(adj, sp, TITLE)
    # 它印的是**产物什么时候生成的**，不是跑它花了多久。
    assert adj["generated_at"] in page and sp["generated_at"] in page
    dur = adj["seconds"]
    assert f"{dur:g} 秒" not in page and f"{dur:g}s" not in page, "页面上出现了耗时读数"


def test_no_markdown_leaks_into_the_page(adj, sp):
    """产物里的 markdown 要**变成排版**，不能原样落进 HTML。

    `FALSIFIER_MARKS` 的取值自带 markdown（`× **恒真**`）、`_show()` 也带 ——
    漏一处，屏幕上就是一对裸星号。
    """
    page = V.render_html(adj, sp, TITLE)
    assert "**" not in page, "页面上留下了裸的 `**`"
    assert "`" not in page, "页面上留下了裸的反引号"
    assert "<strong>" in page and "<code>" in page, (
        "一处都没有变换成功 —— 那上面两条空过是因为压根没有 markdown 可漏")


# ---------------------------------------------------------------------------
# 三、零 JavaScript、零外部引用、先转义再排版
# ---------------------------------------------------------------------------

def test_the_viewer_has_no_javascript_at_all(adj, sp):
    """整页**没有一行 JavaScript** —— 报告 §2.3 写着本装置「无常驻进程」。

    所以筛选、展开、下钻全部由 `<details>` 与 CSS 完成；没有脚本，
    也就没有「脚本跑失败了页面看着还是对的」这一种坏法。
    """
    page = V.render_html(adj, sp, TITLE)
    low = page.lower()
    assert "<script" not in low
    assert "<noscript" not in low
    assert "javascript:" not in low
    handlers = re.findall(r"\son[a-z]+\s*=", page, re.I)
    assert not handlers, f"页面上有内联事件处理器：{handlers}"


def test_the_viewer_makes_no_external_request(adj, sp):
    """没有一个外链、没有一张外图、没有一次 `@import`。

    这一页要能在**断网**的机器上照常打开 —— 演示时正是这么用的。
    """
    page = V.render_html(adj, sp, TITLE)
    assert not re.search(r"https?:", page), "页面上有绝对 URL"
    assert not re.search(r"\b(src|href)\s*=", page, re.I), "页面上有 src/href"
    assert "@import" not in page
    assert "url(" not in page
    low = page.lower()
    assert "<link" not in low and "<img" not in low and "<iframe" not in low


def test_the_viewer_neither_runs_nor_calls_anything(adj, sp):
    """源码里**没有**起子进程 / 连 socket / 发请求的东西。

    上面那条量的是这一份渲染结果；这一条量的是**这一类结果** ——
    今天没有外链，不代表下一个改动不会加一个。
    """
    src = VIEWER.read_text(encoding="utf-8")
    for bad in ("subprocess", "socket", "urllib", "requests", "httpx"):
        assert bad not in src, f"展示层里出现了 {bad!r} —— 它只该读两份产物"


def test_the_page_escapes_what_the_artifacts_say(adj, sp):
    """**负例**：产物里带着 `<script>` 时，页面上必须是转义之后的文本。

    先转义、再做那两条行内变换 —— 顺序反了就是注入。这是这一页唯一的
    「输入不是我们自己写的」的地方。
    """
    d = copy.deepcopy(adj)
    d["what_this_is"] = "带尖括号的 <script>alert(1)</script> 与一对 `反引号`"
    page = V.render_html(d, sp, TITLE)
    assert "<script>alert" not in page, "产物里那段没有被转义，直接进了 HTML"
    assert "&lt;script&gt;" in page, "转义之后应当留下 `&lt;script&gt;` 这段文本"
    assert "<code>反引号</code>" in page, "转义之后那两条行内变换应当照常生效"


def test_the_viewer_reuses_the_single_falsifier_table():
    """**阴性对照**：`FALSIFIER_MARKS` / `GRIDS` 的字面量在这份源码里**一份都不许有**。

    `selfproof.py` 就因为另抄了一张 `0/1/2 → 措辞` 的表，在 Linux 上抛过一次
    `KeyError`（报告 §7.5）—— 同一个字面量抄两份，迟早只说两种话。
    """
    src = VIEWER.read_text(encoding="utf-8")
    for literal in ("√ 翻得动", "通过·采信", "复现一"):
        assert literal not in src, (
            f"展示层里出现了 {literal!r} 这个字面量 —— 它该从 adjudicate / selfproof 取")
    assert "A.FALSIFIER_MARKS" in src, "没有复用那一张表"
    assert "S.GRIDS" in src, "没有复用五格的名字"


# ---------------------------------------------------------------------------
# 四、入口：三态各一条，外加落点那道门
# ---------------------------------------------------------------------------

def test_a_pair_that_reads_cleanly_renders_and_exits_zero(capsys, tmp_path):
    """干净的一对：读到、落成、展示层自己没看出问题 —— 退 `0`。"""
    out = tmp_path / "board.html"
    rc = V.main(["--out", str(out)])
    got, _ = capsys.readouterr()
    assert rc == 0, f"干净的一对没退 0（{rc}）：{got}"
    assert out.is_file() and out.stat().st_size > 2000
    assert "这不是分数" in got
    assert A.UNDECIDED in got, "打屏那几行没把「不可判定」单列出来"


def test_the_clean_pair_produces_no_findings(adj, sp):
    """**阴性对照**：干净的一对，`findings()` 必须是空表。

    不空的话，底下两条「造一处矛盾就报得出来」等于没有对照 —— 一个永远报问题的
    检查，报不报都一样。
    """
    assert V.findings(adj, sp) == []


def test_a_missing_artifact_is_not_measured_not_a_failure(capsys, tmp_path, sp):
    """产物不在 = **没测到**（`2`），不是「没达到预期」（`1`）。

    `1` 会把人指去查判据 —— 而这时候一条判据都没读到。
    """
    out = tmp_path / "board.html"
    rc = V.main(["--adj", str(tmp_path / "absent.json"), "--sp", str(SP_JSON),
                 "--out", str(out)])
    got, _ = capsys.readouterr()
    assert rc == 2
    assert "没测到" in got
    assert not out.exists()


def test_an_output_path_that_cannot_be_written_exits_two_before_reading(capsys, tmp_path):
    """**落点那道门开在读取之前** —— 前提再全，写不出去也等于一条都没量到。

    两个输入都**故意指向不存在的文件**：要是先读，屏幕上会是「读不到产物」；
    实际该看到的是落点那句话。这就是「先问一句」的机器可核形式。
    """
    rc = V.main(["--adj", str(tmp_path / "absent.json"),
                 "--sp", str(tmp_path / "absent.json"),
                 "--out", str(tmp_path / "no_such_dir" / "board.html")])
    got, _ = capsys.readouterr()
    assert rc == 2, f"落点不通该退 2（没测到），实际退了 {rc}"
    assert "落点" in got
    assert "读不到产物" not in got, "它先读了输入 —— 落点那道门开晚了"


def test_a_row_broken_into_two_states_is_reported(capsys, tmp_path, adj, sp):
    """某条判「不可判定」却带着一个采信值 —— **三态被折成两态了**，退 `1`。

    `1` 在这里的意思是「渲染是好的，但展示层自己看出了一件事」，与
    `adjudicate` 用 `1` 报「判据恒真」同构。
    """
    broken = copy.deepcopy(adj)
    victim = next(r for r in broken["rows"] if r["verdict"] == A.UNDECIDED)
    victim["trusted"] = False
    found = V.findings(broken, sp)
    assert any(victim["id"] in x for x in found), f"没报出来：{found}"
    assert "折成两态" in " ".join(found)
    rc = V.main(["--adj", _dump(tmp_path, "adj.json", broken), "--sp", str(SP_JSON),
                 "--out", str(tmp_path / "board.html")])
    got, _ = capsys.readouterr()
    assert rc == 1, f"发现了折合却退了 {rc}"
    assert "折合" in got


def test_two_artifacts_disagreeing_on_one_claim_are_reported(capsys, tmp_path, adj, sp):
    """两份产物对同一条判据的说法不一致 —— 也退 `1`，并把那条**点名**。"""
    other = copy.deepcopy(sp)
    victim = other["base"][0]["id"]
    for b in other["base"]:
        if b["id"] == victim:
            b["verdict"] = A.FAIL_ if b["verdict"] != A.FAIL_ else A.PASS_
    found = V.findings(adj, other)
    assert any(victim in x for x in found), f"{victim} 的不一致没报出来：{found}"
    rc = V.main(["--adj", str(ADJ_JSON), "--sp", _dump(tmp_path, "sp.json", other),
                 "--out", str(tmp_path / "board.html")])
    got, _ = capsys.readouterr()
    assert rc == 1
    assert victim in got


def test_a_report_missing_a_key_is_not_rendered(capsys, tmp_path, adj, sp):
    """形状不对就**别渲染** —— 一张渲染到一半的表比没有表更坏。退 `2`。"""
    d = copy.deepcopy(adj)
    del d["rows"][0]["verdict"]
    with pytest.raises(V.ViewerError):
        V.check_shape(d, sp)
    rc = V.main(["--adj", _dump(tmp_path, "adj.json", d), "--sp", str(SP_JSON),
                 "--out", str(tmp_path / "board.html")])
    got, _ = capsys.readouterr()
    assert rc == 2
    assert "没测到" in got
    assert not (tmp_path / "board.html").exists()


# ---------------------------------------------------------------------------
# 三之二、闸要拦住**渲染器真会读的每一格**
# ---------------------------------------------------------------------------
#
# 这一组是踩出来的，不是想出来的。闸原先只核到「判据行有没有 `verdict`」，而渲染时
# 还会**下标读** `what` / `check` / `values` / `trusted`、falsifier 的 `kind`、
# 用例的 `moved`。缺了那一格，渲染当场 `KeyError`，异常一路冒到顶 —— 退出码 `1`，
# 而 `1` 在本模块里的定义是「渲染完成了，而且展示层**发现了一件事**」。
# **「没测到」被报成了「发现了一处折合」**，正是本装置盯着别人的那一族。
#
# 每条都**两问**：问闸（`check_shape` 当场抛 `ViewerError`），再问入口（退 `2`、
# 一个字都不落盘）。只问入口不够 —— `main` 里另有一张网也会让它退 `2`，于是
# 「闸拦住了」与「没拦住、网接住了」在退出码上长得一模一样，而形状不对本来就
# 不该走到渲染那一步；只问闸也不够：闸抛异常不等于那条路真接住了它。

def test_the_judgments_that_are_in_the_artifacts_pass_the_gate(adj, sp):
    """**反向对照**：入库那两份产物必须过闸。

    少了这一条，下面那一组可以用「一律拒收」通过 —— 那样闸拦住的不是「形状不对」，
    是「有一个产物」。上面那条 `test_the_default_output_is_not_inside_the_repository`
    同族：一个只有一种输出的检查，不是检查。
    """
    V.check_shape(adj, sp)          # 不抛就是过


def test_a_cell_the_renderer_reads_is_a_cell_the_gate_checks(adj, sp, tmp_path, capsys):
    """渲染器下标读的每一格，闸都得核过 —— 逐格删一次，闸当场说话、入口退 `2`。

    口径一句话：**读什么就核什么**。`what` 与 `check` 原先正是在渲染那一刻才第一次
    被读到的那两格 —— 闸没核、渲染照读。
    """
    for key in ("what", "check", "values", "trusted"):
        broken = copy.deepcopy(adj)
        del broken["rows"][0][key]
        with pytest.raises(V.ViewerError, match=f"`{key}`"):
            V.check_shape(broken, sp)
        out = tmp_path / f"board_{key}.html"
        rc = V.main(["--adj", _dump(tmp_path, f"adj_no_{key}.json", broken),
                     "--sp", str(SP_JSON), "--out", str(out)])
        got, _ = capsys.readouterr()
        assert rc == 2, f"判据行少了 `{key}`，入口却退了 {rc}"
        assert "没测到" in got, got
        assert not out.exists(), (
            f"少了 `{key}` 还是渲染出了一张表 —— 一张渲染到一半的表比没有表更坏")


def test_a_falsifier_kind_outside_the_one_table_is_refused(adj, sp, tmp_path, capsys):
    """`kind` 缺了、或不在 `adjudicate.FALSIFIER_MARKS` 里 —— 那是**没有字形**的一格。

    字形表只有一份（渲染约定 2：本文件不另抄），所以闸核的不是「有没有 `kind`」，
    是「这个种类在不在那张表里」。少了它，渲染到那一行就是 `KeyError`：
    traceback、退出码 `1`，看着像「发现了一处折合」。
    """
    missing = copy.deepcopy(adj)
    del missing["falsifiers"][0]["kind"]
    with pytest.raises(V.ViewerError, match="`kind`"):
        V.check_shape(missing, sp)

    unknown = copy.deepcopy(adj)
    unknown["falsifiers"][0]["kind"] = "表外的种类"
    with pytest.raises(V.ViewerError, match="FALSIFIER_MARKS"):
        V.check_shape(unknown, sp)

    out = tmp_path / "board_kind.html"
    rc = V.main(["--adj", _dump(tmp_path, "adj_kind.json", unknown),
                 "--sp", str(SP_JSON), "--out", str(out)])
    got, _ = capsys.readouterr()
    assert rc == 2, f"表外的种类退了 {rc} —— `1` 的意思是「发现了一处折合」"
    assert "没测到" in got, got
    assert not out.exists()


def test_a_case_that_lands_in_no_grid_is_refused(adj, sp, tmp_path, capsys):
    """用例是**按「它落到了哪一格」陈列**的 —— 落不到任何一格的用例会静默消失。

    页眉那句「（15 例）」取自 `cases` 的长度，与渲染出来的条数无关：一例匹配不到格，
    页面就少一行、退出码照样 `0`，而页眉照样报总数。**「静默少一块」比「拒绝渲染」坏**，
    所以缺 `moved`、空 `moved`、指到表外的格，三样都算形状不对。
    """
    for how, wreck in (("缺", lambda c: c.pop("moved")),
                       ("空", lambda c: c.__setitem__("moved", {})),
                       ("指到表外", lambda c: c.__setitem__("moved", {"B1": "没有这一格"}))):
        broken = copy.deepcopy(sp)
        wreck(broken["cases"][0])
        with pytest.raises(V.ViewerError):
            V.check_shape(adj, broken)
        out = tmp_path / "board_case.html"
        rc = V.main(["--adj", str(ADJ_JSON), "--sp", _dump(tmp_path, "sp_bad.json", broken),
                     "--out", str(out)])
        got, _ = capsys.readouterr()
        assert rc == 2, f"`moved` {how}了，入口却退了 {rc}"
        assert "没测到" in got, got
        assert not out.exists()


def test_an_unforeseen_shape_is_not_measured_not_a_finding(adj, sp, tmp_path, capsys,
                                                          monkeypatch):
    """闸外面剩下的那点余地：渲染**中途**撞上一个没预料到的形状。

    它不许按「发现了一处折合」走出去 —— 页面上一个字都没有，一句「展示层发现了
    1 处折合」会是**凭空报出来的发现**。口径与 `run_all` 逐字相同：**「没测到」
    既不是通过，也不是失败。**

    这里把渲染器换成一个当场抛 `KeyError` 的替身：闸再全，也穷举不完
    「产物还能长成什么样」—— 所以要有一条接得住的网，而且它得说清楚自己接住的是什么。
    """
    def boom(*a, **k):
        raise KeyError("某一格")

    monkeypatch.setattr(V, "render_html", boom)
    out = tmp_path / "board_net.html"
    rc = V.main(["--adj", str(ADJ_JSON), "--sp", str(SP_JSON), "--out", str(out)])
    got, _ = capsys.readouterr()
    assert rc == 2, (f"撞上没预料到的形状却退了 {rc} —— `1` 的意思"
                     "是「渲染完成了，而且发现了一件事」")
    assert "没测到" in got, got
    assert "发现了一处折合" in got, "没把「这不是发现」说出来，读者会把 2 读成别的"
    assert not out.exists()


#: 按格陈列时**条目数**与**例数**是两个数：这一批里落了两格的那个用例。
_TWO_GRIDS_CASE = "P2"


def test_the_page_says_both_counts_when_one_case_lands_in_two_grids(adj, sp):
    """一例落两格 → 条目数多于例数。**两个数都得说出来。**

    这批里 `P2` 同时动了 `B1` 与 `B2`，所以按格陈列时它出现两次：产物 **15 例**、
    页面 **16 条**。页眉只说「（15 例）」的话，读者数一遍条目就会读出一个**不存在**
    的不一致（同族的毛病：一个数被当成了另一个数）。
    """
    page = V.render_html(adj, sp, TITLE)
    entries = page.count('<div class="case">')
    total = len(sp["cases"])
    assert entries == 16 and total == 15 and entries > total, (
        f"这批产物的形状变了（条目 {entries}、例 {total}）—— 先看清再改这条")
    assert "一例同时落了两格" in page, "页面上没交代「一例可以落两格」"
    assert f"共 <strong>{entries}</strong> 条" in page, "条目数没有被说出来"
    assert f"（{total} 例）" in page, "例数那一句不见了 —— 两个数要都在"


def test_no_such_sentence_when_every_case_lands_in_one_grid(adj, sp):
    """**反向对照**：每例只落一格时，那句「一例同时落了两格」不许出现。

    少了这一条，上面那一条可以用「这句话永远印在页面上」通过。
    """
    one_grid = copy.deepcopy(sp)
    victim = next(c for c in one_grid["cases"] if c["id"] == _TWO_GRIDS_CASE)
    assert len(victim["moved"]) == 2, (
        f"夹具的前提变了（`{_TWO_GRIDS_CASE}` 不再落两格）—— 改这条之前先看清这批产物")
    k, v = next(iter(victim["moved"].items()))
    victim["moved"] = {k: v}

    page = V.render_html(adj, one_grid, TITLE)
    assert page.count('<div class="case">') == len(one_grid["cases"]), (
        "每例只落一格时条目数应当**等于**例数")
    assert "一例同时落了两格" not in page
    assert f"共 <strong>{len(one_grid['cases'])}</strong> 条" not in page


def test_stdout_mode_writes_nothing_and_keeps_the_summary_off_the_page(capsys, tmp_path):
    """`--stdout` 时页面走标准输出、**汇总走标准错误**，仓库里不留东西。"""
    before = {p.name for p in VERIFICATION.iterdir()}
    rc = V.main(["--stdout"])
    got, err = capsys.readouterr()
    assert rc == 0
    assert got.startswith("<!doctype html>")
    assert not re.search(r"^→ ", got, re.M), "批量模式不该打印落点"
    assert "这不是分数" not in got, "汇总混进了页面"
    assert "这不是分数" in err, "汇总应当走标准错误"
    assert {p.name for p in VERIFICATION.iterdir()} == before, "落盘落进仓库了"


def test_the_default_output_is_not_inside_the_repository():
    """默认落点**在系统临时目录** —— 仓库里多一个未跟踪文件会被 `git status` 看见。

    这里刻意**不断言那个绝对路径的字面值**（跨平台会不成立）：
    只断言它不在仓库里、文件名是那一个。
    """
    out = V.DEFAULT_OUT.resolve()
    assert BACKEND.resolve() not in out.parents, f"默认落点在仓库里：{out}"
    assert out.name == "verification_viewer.html"


def test_the_four_ways_to_dig_in_are_all_here_without_javascript(adj, sp):
    """四个交互**全由 HTML/CSS 完成** —— 每一条判据一个 `<details>`、五格各一个、
    两排 `radio`、两轴各一组 `:has()` 规则。
    """
    page = V.render_html(adj, sp, TITLE)
    assert page.count('<details class="claim"') == len(adj["rows"])
    assert page.count('<details class="grid"') == len(S.GRIDS)
    assert page.count('<input type="radio"') == 4 + (1 + len(A.LAYERS))
    assert page.count("body:has(#vf-") == 3, "三态筛选少了轴"
    assert page.count("body:has(#lf-") == len(A.LAYERS), "层筛选少了轴"
    for g in S.GRIDS:
        assert g in page, f"五格里的「{g}」在页面上找不到"
