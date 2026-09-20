"""文档里引的每一个**行号**，在这儿逐条对着装好的源码核一遍。

## 为什么值得单独一个文件

这套装置的每一份材料都在引 camel / oasis 的源码行号 —— README、两个上游 issue
草稿、守卫的注释，加起来二十几处。**判读的人会把它们和本地装的源码对一遍**，
这是最容易被逐条 diff 的地方。

而这些行号是**手抄的**。抄错一次，整套材料的可信度就跟着那一个数字走。事实上
复核时确实抓到过两处引文写岔（把 `chunk_body_limit` 的前缀减项写成了字面量
`12`），而且那时候没有任何东西会因此变红。

手抄的东西会烂，所以把它变成机检的：**行号对不上就让测试红**。
上游一升级、行号一漂，这里先响，而不是让一叠材料静静地引用错行。

## 引错的时候该怎么办

**不要**把这里期望的片段改成漂移后的样子就完事 —— 那等于让证据跟着源码走。
正确顺序是：先看那条引文在文档里的**论断**还成不成立，改论断、再改引文。
这个文件只是提醒「该去看那一条了」。

（`oasis/environment/env.py` 那四条另有 `repro_03_concurrency.py` 在运行时会
现场核一遍 —— 那一条是判据的一部分，所以两边都有。这里把全部引文收在一处，
免得散着。）

## 这个文件有四半，核的是四件不同的事

* **第一半**（`CITATIONS`）：源码那一行**还对不对**。防的是上游一升级、行号一漂，
  一叠材料静静地引用错行。
* **第二半**（`KNOWN_MISQUOTES`）：**我们引的时候有没有引岔**。防的是源码纹丝不动、
  我们的材料却把它写错。
* **第三半**（`_verbatim_blocks`）：贴出来的那几段**是不是真的逐字那几行**。
* **第四半**（块的形状）：上面三半都只管「认了标记之后」的事，这一半管**标记本身**
  —— 不认标记的块整块免检、认了标记的块还能靠一行格式写歪**把自己静默摘出去**。
  两个口子都真的漏过东西，所以要看形状而不能只看内容。

第二半只收**真出现过**的错，不收假想的。目前一条：曾经把 `prefix_token_len`
（943 行当场量出来的值）写成了字面量 `12`，还标成 948 行的原文。数值上对
（那个分词器下恰好是 12）、引文上错，而当时没有任何东西会因此变红。
"""

from __future__ import annotations

import functools
import importlib.machinery
import pathlib
import re

import pytest

#: (模块, 行号, 该行**必须包含**的片段, 这个行号被引在哪 / 用来支持什么论断)
#:
#: 片段取的是那一行的**结构特征**（不是整行），这样上游改个空格、改个变量名
#: 里的一个词不至于误报，但**行号漂了、或者那一行换了意思**一定报。
CITATIONS = (
    # ---- camel：切片正反馈环（①）---------------------------------------
    ("camel.agents.chat_agent", 884,
     "remaining_budget = max(0, token_limit - ctx_tokens)",
     "README §① / camel_guards：残余预算用的是**截断后**的 ctx_tokens"),
    ("camel.agents.chat_agent", 886,
     "if current_tokens <= remaining_budget:",
     "README §①：放得下就直接写、不切（这不满足才走切片）"),
    ("camel.agents.chat_agent", 933,
     "base_chunk_size = max(1, remaining_budget) // 10",
     "camel_guards / README §①：残余预算先被 //10 砍一刀"),
    ("camel.agents.chat_agent", 942,
     'sample_prefix = "[chunk 1/1000 of a long message]\\n"',
     "README §①：每块前缀长这样"),
    ("camel.agents.chat_agent", 943,
     "prefix_token_len = len(token_counter.encode(sample_prefix))",
     "README §① / camel_guards：前缀长度是**量出来的**，不是字面量 12"),
    ("camel.agents.chat_agent", 948,
     "chunk_body_limit = max(1, base_chunk_size - prefix_token_len)",
     "README §① / camel_guards：正文容量落到下界 max(1, …)"),
    ("camel.agents.chat_agent", 951,
     "num_chunks = math.ceil(len(all_token_ids) / chunk_body_limit)",
     "README §①：条数由正文容量算出来"),
    # ---- camel：同拍碰撞（②）-------------------------------------------
    ("camel.agents.chat_agent", 2739,
     "current_time_ns = time.time_ns()",
     "README §② / issue ②：**只读这一次**钟"),
    ("camel.agents.chat_agent", 2740,
     "base_timestamp = current_time_ns / 1_000_000_000",
     "README §② / issue ②：换算成秒"),
    ("camel.agents.chat_agent", 2747,
     "self.update_memory(",
     "README §② / issue ②：回执那一笔"),
    ("camel.agents.chat_agent", 2750,
     "timestamp=base_timestamp + 1e-6",
     "README §② / issue ②：那个**比时钟一拍还细**的 1e-6"),
    # ---- camel：另外两处被引到的 ----------------------------------------
    ("camel.agents.chat_agent", 847,
     "def _write_single_record(",
     "camel_guards：整条写入那几行与它等价（它是闭包，取不到）"),
    ("camel.agents.chat_agent", 859,
     "base_ts = (",
     "tests/test_camel_guards：timestamp 为 None 时 camel 自己读钟"),
    ("camel.memories.base", 143,
     "def get_context(self)",
     "repro_02：判据拿的就是 get_context() 返回的那串消息"),
    # ---- oasis：并发次序（③）与异常被吞 ---------------------------------
    ("oasis.social_agent.agent", 153,
     "except Exception as e:",
     "issue ②：异常在这一层被接住"),
    ("oasis.social_agent.agent", 154,
     'agent_log.error(f"Agent {self.social_agent_id} error: {e}")',
     "issue ②：只记一行日志"),
    ("oasis.social_agent.agent", 155,
     "return e",
     "issue ②：**把异常对象当结果返回**，该 agent 这一轮等于没动作"),
    ("oasis.environment.env", 55,
     "semaphore: int = 128",
     "repro_03 / comment_751_759：并发上限的默认值"),
    ("oasis.environment.env", 70,
     "self.llm_semaphore = asyncio.Semaphore(semaphore)",
     "repro_03 / comment_751_759：把它造成信号量"),
    ("oasis.environment.env", 127,
     "async with self.llm_semaphore:",
     "repro_03 / comment_751_759：`_perform_llm_action` 在这里排队"),
    ("oasis.environment.env", 193,
     "await asyncio.gather(*tasks)",
     "repro_03 / comment_751_759：所有 agent 的动作并发执行"),
    # ---- camel/oasis：端到端那一跑引到的 --------------------------------
    ("camel.agents.chat_agent", 468,
     "self.model_backend = ModelManager(",
     "README §端到端 / e2e_stub：每个 agent 各包一个 ModelManager —— "
     "**包的是同一个后端实例**，所以替身必须无状态"),
    ("camel.agents.chat_agent", 2004,
     "except RuntimeError as e:",
     "README §端到端：max_tokens 同时是上下文上限，收紧它在这里被接住"),
    ("camel.agents.chat_agent", 2006,
     '"max_tokens_exceeded"',
     "README §端到端：接住之后**直接把这一轮终止** —— agent 静默无动作，"
     "看起来像跑通了。所以 max_tokens 不能当旋钮用"),
    ("oasis.social_agent.agents_generator", 574,
     'with open(profile_path, "r") as file:',
     "e2e_stub：**不指定编码** —— 中文 Windows 上默认 GBK，"
     "读 UTF-8 花名册当场 UnicodeDecodeError（上游缺陷，本命令绕开）"),
)


@functools.lru_cache(maxsize=None)
def _read(module: str) -> list:
    """把那个模块的**源码文本**读出来 —— **不 import 它**。

    这一条是量出来的：`import oasis` 要九秒上下（它拖 flask 那一整套 web 栈，
    本机两次 9.2 / 8.7 秒），而这里需要的只是**文件里的几行字**。真去 import 的话，
    光这一个文件就从 **0.06 秒**变成十秒量级 —— 一个没人愿意跑的测试
    和没有测试是一样的下场。

    `PathFinder.find_spec` 只查路径、不执行模块（实测 0.000 秒），够用。
    """
    parts = module.split(".")
    spec = importlib.machinery.PathFinder.find_spec(parts[0])
    if spec is None or not spec.submodule_search_locations:
        raise ImportError(f"找不到 {parts[0]} 的位置")
    path = pathlib.Path(list(spec.submodule_search_locations)[0]).joinpath(*parts[1:])
    if path.is_dir():                       # 包：读它的 __init__
        path = path / "__init__.py"
    else:
        path = path.with_suffix(".py")
    return path.read_text(encoding="utf-8").splitlines()


def _source(module: str) -> list:
    """取模块的源码行。取不到就 skip —— 环境没装不是「引错了」。"""
    try:
        return _read(module)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"取不到 {module}（{exc.__class__.__name__}）—— 没测到，不算引错")


@pytest.mark.parametrize("module,lineno,fragment,why", CITATIONS)
def test_cited_line_still_says_what_we_say_it_says(module, lineno, fragment, why):
    """那一行的内容必须还是我们引的那个样子。"""
    lines = _source(module)

    assert 0 < lineno <= len(lines), (
        f"{module} 只有 {len(lines)} 行，却引了第 {lineno} 行 —— "
        f"上游大概动过了。这条引文支持的是：{why}")

    actual = lines[lineno - 1]
    assert fragment in actual, (
        f"\n{module}:{lineno} 对不上了。\n"
        f"  期望含：{fragment!r}\n"
        f"  实为　：{actual.strip()!r}\n"
        f"  这条引文支持的是：{why}\n"
        f"  **先看那个论断还成不成立**，别只把期望值改成漂移后的样子。")


def test_every_citation_module_is_reachable():
    """引文表里不能有一个取不到的模块 —— 否则那条 citation 是空过的。"""
    missing = sorted({m for m, _, _, _ in CITATIONS if _source_or_none(m) is None})
    assert not missing, f"这些模块取不到，对应的引文等于没核：{missing}"


def _source_or_none(module: str):
    try:
        return _read(module)
    except Exception:  # noqa: BLE001
        return None


def test_no_duplicate_citations():
    """同一行引两遍要合并 —— 免得改了上面那条、漏了下面那条。"""
    seen = [(m, n) for m, n, _, _ in CITATIONS]
    dupes = {k for k in seen if seen.count(k) > 1}
    assert not dupes, f"重复的引文：{dupes}"


# --------------------------------------------------------------------------
# 另一半：**我们自己的材料**里有没有错引
# --------------------------------------------------------------------------
#
# 上面那组核的是「源码那一行还对不对」；这一组核的是「我们引的时候有没有引岔」。
# 两件事不一样，而上面那组**管不到**下面这件事 —— 源码可以纹丝不动，我们的材料
# 照样能把它写错。

#: 已经在材料里**真出现过**的错引。每一条都曾经写在某份材料里、并且当时
#: **没有任何东西会因此变红** —— 是人工复核才抓到的。
#:
#: (错的样子（正则）, 对的样子, 出过什么事)
KNOWN_MISQUOTES = (
    (r"base_chunk_size\s*-\s*12",
     "base_chunk_size - prefix_token_len（948 行；那个减数是 943 行**量**出来的）",
     "把「前缀长度」这个当场量出来的值写死成了字面量 12，还标成 948 行的原文 —— "
     "数值上对（gpt-4o-mini 下恰好是 12），**引文上错**：换个分词器就不是 12"),
)

#: 会被扫的材料。**不含本目录** —— 上面那些正则就写在这儿，扫自己等于自投罗网。
_SCAN_SUFFIXES = (".py", ".md", ".txt")
_SKIP_DIRS = {"__pycache__", "tests", ".git"}


def _materials() -> list:
    """把 `verification/` 下**会被人读到**的文本文件都列出来。"""
    root = pathlib.Path(__file__).resolve().parent.parent
    out = []
    for path in sorted(root.rglob("*")):
        if path.suffix not in _SCAN_SUFFIXES or not path.is_file():
            continue
        if _SKIP_DIRS & set(path.relative_to(root).parts):
            continue
        out.append(path)
    return out


def test_the_misquote_scan_covers_the_materials():
    """先证明这个扫描**不是空转** —— 否则下面那条测的是空气。"""
    files = _materials()
    assert files, "一个文件都没扫到，这个扫描是空的"
    names = {f.name for f in files}
    for must in ("README.md", "repro_01_slicing.py", "camel_guards.py"):
        assert must in names, f"这份材料没被扫到：{must}（扫描范围写窄了）"


def test_the_misquote_patterns_actually_match_the_wrong_form():
    """先证明这几条正则**真能命中**它们要抓的那个写法。

    否则「没命中」和「这缺陷不存在」就分不开了 —— 而这两件事完全不同。
    """
    import re as _re

    for pattern, right, _story in KNOWN_MISQUOTES:
        assert _re.search(pattern, "    chunk_body_limit = max(1, base_chunk_size - 12)"), (
            f"这条正则抓不到它要抓的写法：{pattern!r}")
        assert not _re.search(pattern, right), (
            f"这条正则连**正确**的写法也抓 —— 那它会天天误报：{pattern!r}")


@pytest.mark.parametrize("pattern,right,story", KNOWN_MISQUOTES)
def test_no_known_misquote_survives_in_our_materials(pattern, right, story):
    """那个错引过一次的写法，不许在任何材料里留下第二份。"""
    import re as _re

    hits = []
    for path in _materials():
        for i, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1):
            if _re.search(pattern, line):
                hits.append(f"{path.name}:{i}  {line.strip()}")
    assert not hits, (
        "\n材料里出现了已知的错引：\n  " + "\n  ".join(hits) +
        f"\n  正确的写法：{right}\n  出过的事：{story}")


# --------------------------------------------------------------------------
# 第三件事：**贴出来的那几段源码，是不是真的**逐字那几行
# --------------------------------------------------------------------------
#
# 上面两半管的都不是这件事。上半核的是「引文表里那条 citation 对不对」，
# 下半抓的是「一个**已知的**错引写法有没有留下第二份」。可材料里还有第三种东西：
#
#     ```python
#     # 逐字引自 camel.agents.chat_agent
#     remaining_budget = max(0, token_limit - ctx_tokens)   # 884
#     ```
#
# 一行一行贴着上游源码、旁边标着行号，**看着就是原文**。可它既不在 `CITATIONS`
# 里（那是一张表，不是代码块），也不在 `KNOWN_MISQUOTES` 里（那是**已经犯过**的
# 那一个具体写法）—— 于是**没有任何东西会去核它**。
#
# 这不是假想。写这一套的时候就出过：README §① 那段九行代码里，有一行是把 **942 行
# 的字面量拼进了 943 行的表达式**。数值上照样对、读起来比真的还顺，可上游**根本
# 没有那一行**。而这正是本文件开头说的那件事 —— 引文会烂，手抄的引文一定会烂。
#
# 所以给这种块加一个**认得出的标记**：围栏第一行写 `# 逐字引自 <模块>`，
# 之后每行写成 `代码  # <行号>`。认了这个标记，就得**逐字**对得上上游第 N 行。

_VERBATIM_MARK = "# 逐字引自 "
_VERBATIM_LINE = r"^(?P<code>.*?)\s{2,}#\s*(?P<lineno>\d+)\s*$"


def _verbatim_blocks() -> list:
    """把材料里所有**认了标记**的代码块抽出来：`[(文件, 模块, [(行号, 那行代码), …])]`。"""
    import re as _re

    out = []
    fence = _re.compile(r"```[^\n]*\n(.*?)```", _re.S)
    for path in _materials():
        if path.suffix != ".md":
            continue
        text = path.read_text(encoding="utf-8")
        for block in fence.findall(text):
            body = block.splitlines()
            if not body or not body[0].startswith(_VERBATIM_MARK):
                continue
            module = body[0][len(_VERBATIM_MARK):].strip()
            rows = []
            for line in body[1:]:
                m = _re.match(_VERBATIM_LINE, line)
                if m:
                    rows.append((int(m.group("lineno")), m.group("code").strip()))
            out.append((path, module, rows))
    return out


def test_the_verbatim_blocks_are_actually_found():
    """先证明这个扫描**不是空转**：现在确实有块认了这个标记。

    没认标记的块它一个字都不看。要是哪天标记被删光了、或者写法改了，
    下面那条会**一条都不报** —— 而「没报」和「都对」长得一模一样。
    """
    blocks = _verbatim_blocks()
    assert blocks, ("一个认标记的逐字块都没有 —— 那下面的检查是空转的。"
                    f"标记写法：围栏第一行 `{_VERBATIM_MARK}<模块>`，"
                    f"之后每行 `代码  # <行号>`")
    total = sum(len(rows) for _, _, rows in blocks)
    assert total >= 5, f"认了标记的块一共只核到 {total} 行，太少了，看看是不是漏抽了"


@pytest.mark.parametrize("path,module,rows", _verbatim_blocks(),
                         ids=lambda v: v if isinstance(v, str) else "")
def test_verbatim_blocks_match_upstream_line_for_line(path, module, rows):
    """标了 `# N` 的那一行，就必须**逐字**是上游第 N 行。

    对不上只有两种解释：上游动了（那这条引文该去看一眼，顺带想想论断还成不成立），
    或者**我们贴的那段本来就不是原文**（那更严重 —— 它看着像原文）。
    两种都要人去看，所以这里只负责当场红。
    """
    lines = _source(module)
    for lineno, code in rows:
        assert 0 < lineno <= len(lines), (
            f"{path.name} 引了 {module}:{lineno}，而它只有 {len(lines)} 行")
        actual = lines[lineno - 1].strip()
        assert code == actual, (
            f"\n{path.name} 里贴着的那一行，和 {module}:{lineno} **对不上**。\n"
            f"  材料里：{code!r}\n"
            f"  上游是：{actual!r}\n"
            f"  这一行既不在 `CITATIONS` 表里、也不在 `KNOWN_MISQUOTES` 里，"
            f"只有这个逐字块在管它。\n"
            f"  **先看那段话的论断还成不成立**；要是这行本来就不是原文，"
            f"把它改成原文，别把行号改成让它对得上的样子。")


# --------------------------------------------------------------------------
# 第四件事：**块本身的形状** —— 上面三半管的都是「认了标记之后」的事
# --------------------------------------------------------------------------
#
# 标记是**自己写的**。这留下了两个口子，两个都真的漏过东西：
#
# ① **不认标记就整块免检。** 把行号写在**前面**（`884  remaining_budget = …`）
#    比写在后面更像原文，可 `_verbatim_blocks` 只认「围栏第一行是标记」，
#    于是这种块一个字都不核。2026-09-20 查出来材料里这么活着**三处**
#    （README 的 `env.py` 块、`comment_751_759.md` 的同一块、issue ② 的 oasis 块）。
#    其中 `env.py:55` 的引文还**漏了个逗号**（上游是 `semaphore: int = 128,`）——
#    `CITATIONS` 用的是「必须包含」的子串比对，逗号漏了它不响。
#
# ② **认了标记，行却可以被静默跳过。** 一行要是没写成 `代码  # 行号`（比如
#    `# 2740` 前面只留了一个空格），`_verbatim_blocks` 只是 `if m:` 不成立、
#    **跳过去**，那一行就从机检里消失了，而测试照样绿。写这一节的时候就踩了。
#
# 所以下面两条**不看引文内容、只看块的形状**。内容是第三半在管。

_FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.S)
_QUOTE_HEAD = re.compile(r"^\s*\d{2,}\s+\S")


def _all_blocks() -> list:
    """材料里**所有**代码块（认不认标记都在）：`[(文件, 首行, 块体行表)]`。"""
    out = []
    for path in _materials():
        if path.suffix != ".md":
            continue
        for block in _FENCE.findall(path.read_text(encoding="utf-8")):
            body = block.splitlines()
            if body:
                out.append((path, body[0].strip(), body))
    return out


def _lines_without_a_number(body: list) -> list:
    """块体里**没写成 `代码  # 行号`** 的非空行（首行那个标记不算）。"""
    return [ln for ln in body[1:] if ln.strip() and not re.match(_VERBATIM_LINE, ln)]


def _looks_like_a_quote(body: list) -> bool:
    """首行是不是「行号 代码」—— 也就是「看着像原文」的那种写法。"""
    return bool(body) and bool(_QUOTE_HEAD.match(body[0]))


def test_every_line_inside_a_claimed_block_carries_a_line_number():
    """认了标记的块里，**每一行都得带行号** —— 格式写歪的行会被静默跳过。

    跳过不是「报错」，是那一行**从机检里消失**，而测试照绿 ——
    正是本文件开头说的那件事换了个地方发生。
    """
    bad = []
    for path, head, body in _all_blocks():
        if not head.startswith(_VERBATIM_MARK):
            continue
        bad += [f"{path.name}：{ln!r}" for ln in _lines_without_a_number(body)]
    assert not bad, (
        "认了标记的块里，下面这几行**没写成** `代码  # 行号`，"
        "于是被静默跳过、根本没被核：\n  " + "\n  ".join(bad)
        + f"\n格式要求：代码 + **两个以上空格** + `# 行号`（`{_VERBATIM_LINE}`）")


def test_a_line_numbered_quote_block_is_never_left_unclaimed():
    """长得像引文的块（首行是「行号 代码」）**必须认标记**，否则红。

    不认标记就没有任何东西核它 —— 而它看上去比认了标记的那种更像原文。
    """
    bad = [f"{path.name}：{head!r}" for path, head, body in _all_blocks()
           if _looks_like_a_quote(body) and not head.startswith(_VERBATIM_MARK)]
    assert not bad, (
        "下面这些块**长得像引文**（行号在前），却没有 `# 逐字引自 <模块>` 那一行，"
        "所以机检看不见它们：\n  " + "\n  ".join(bad)
        + "\n要么转成 `代码  # 行号` 再加标记行，要么把内容挪出代码块。")


def test_the_two_block_shape_checks_can_actually_go_red():
    """反向对照：上面那两条**不是恒真的** —— 喂坏的进去要能抓出来。

    没有这一条，上面两条完全可能是**恒过**的（正则写歪、条件取反、写成了
    `assert True`），而「没报」和「都对」长得一模一样。
    """
    good = ["# 逐字引自 m", "code()          # 12", "    x = 1       # 13"]
    assert _lines_without_a_number(good) == [], "真格式喂进去也说不对，上面那条是假绿"
    assert _lines_without_a_number(
        ["# 逐字引自 m", "code() # 12"]) == ["code() # 12"], "只隔一个空格也算漏"

    assert not _looks_like_a_quote(["# 逐字引自 m", "code  # 12"]), "认了标记的不该算伪引文"
    assert _looks_like_a_quote([" 884   remaining_budget = 1"]), "行号在前的不认出来"
    assert not _looks_like_a_quote(["37.1 / 37.8 / 37.8 秒"]), "纯读数不该被误判"
    assert not _looks_like_a_quote([""]), "空块不该被误判"
