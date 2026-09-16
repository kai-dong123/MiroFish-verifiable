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

## 这个文件有两半，核的是两件不同的事

* **上半**（`CITATIONS`）：源码那一行**还对不对**。防的是上游一升级、行号一漂，
  一叠材料静静地引用错行。
* **下半**（`KNOWN_MISQUOTES`）：**我们引的时候有没有引岔**。防的是源码纹丝不动、
  我们的材料却把它写错。这两件事不重叠 —— 上半完全管不到下半，所以下半要单独有。

下半只收**真出现过**的错，不收假想的。目前一条：曾经把 `prefix_token_len`
（943 行当场量出来的值）写成了字面量 `12`，还标成 948 行的原文。数值上对
（那个分词器下恰好是 12）、引文上错，而当时没有任何东西会因此变红。
"""

from __future__ import annotations

import functools
import importlib.machinery
import pathlib

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

    这一条是量出来的：`import oasis` 要 9.4 秒（它拖 flask 那一整套 web 栈），
    而这里需要的只是**文件里的几行字**。真去 import 的话，这条测试会让
    `pytest verification/tests` 从两秒变成十一秒 —— 一个没人愿意跑的测试
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
