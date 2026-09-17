"""照 README 装出来的那个环境，是不是**装置量的那个环境**。

这个文件守两件在别处都没有东西守的事：

**一、`mcp` 的上界。** `camel-ai` 自己声明的是 `mcp>=1.3.0`、上界开放，pip 会解析到
mcp 2.x；而 `camel/toolkits/base.py` 的**类体里**（不是函数里、不是 `TYPE_CHECKING` 里）
有一句 `from mcp.server import FastMCP`，2.x 把这个名字搬走了，于是**只要有人走到
`camel.toolkits.base` 这个文件，就当场 ImportError**。实测：本装置用的那条导入路径
（`import camel.agents.chat_agent`）**确实会把它拉进来**，所以这不是「理论上可能」。
症状长得像「你自己的环境有问题」，而其实是依赖解析的锅 —— 这一类坏掉的东西
**不会自己告诉你它是坏的**，只会在 `import` 那一行炸给你看。

**二、版本锁定。** 整套引文（行号、常量、分支）与判据都是照着 `requirements.txt` 里
那几个版本核的。版本一变，引文表、`repro_*` 的判据、端到端那一跑的读数全都得重核 ——
所以「装的版本 == 锁的版本」本身就是一条**装置能不能用**的前提，值得钉住。

**它能证明什么、不能证明什么：** 它只证明这三件事（两个仿真内核的版本、`mcp` 的上界、
以及那个真的会炸的导入真的没炸）。它**不**证明整套环境与 README 说的完全一致 ——
那要一条一条 pin，而 README 也从没那么声称过。
"""

from __future__ import annotations

import importlib.metadata as md
import pathlib
import re
import subprocess
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent          # verification/tests
VERIFICATION = HERE.parent
BACKEND = VERIFICATION.parent
REQUIREMENTS = BACKEND / "requirements.txt"

#: 引文与判据对的那两个版本 —— 改了这里，`test_citations.py` 那张表要重核。
_CITATION_CRITICAL = ("camel-ai", "camel-oasis")

_PIN = re.compile(r"^([A-Za-z0-9_.\-]+)\s*(==|~=|>=|<=|>|<)\s*([^\s;]+)$")


def _norm(name: str) -> str:
    """PEP 503：比较包名时 `.` / `_` / `-` 是一回事。"""
    return re.sub(r"[-_.]+", "-", name).lower()


def _pins() -> dict:
    pins: dict = {}
    for raw in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        m = _PIN.match(line)
        if m:
            pins.setdefault(_norm(m.group(1)), []).append((m.group(2), m.group(3)))
    return pins


def _installed(name: str) -> str:
    try:
        return md.version(name)
    except md.PackageNotFoundError:                       # pragma: no cover
        pytest.fail(f"`{name}` 没装 —— 这个环境不是 README 说的那个环境。")


def test_the_citation_critical_versions_are_pinned_and_installed():
    """两个仿真内核必须是**精确锁定**的，而且装的正好是锁的那个。"""
    pins = _pins()
    for name in _CITATION_CRITICAL:
        entries = pins.get(name)
        assert entries, (
            f"`{name}` 在 `requirements.txt` 里没有 pin 了。"
            "整套引文（行号、常量、分支）是照着某个确切版本核的，"
            "版本放开就等于让引文随时可能变错而没人知道。")
        assert entries == [("==", entries[0][1])], (
            f"`{name}` 的 pin 不是单个 `==`：{entries} —— 改成 `==` 并写明确切版本。")
        stated = entries[0][1]
        actual = _installed(name)
        assert stated == actual, (
            f"`{name}`：`requirements.txt` 锁的是 **{stated}**，现场装的是 **{actual}**。\n"
            "要么环境不是照 README 装的，要么版本被升过 —— "
            "**两种情况都得先把引文表与判据重核一遍**，别直接把这个数字改掉。")


def test_mcp_still_has_the_upper_bound():
    """`mcp<2` 这一行是**必需的上界**，不是保守写法 —— 删了它就有人装不上。"""
    pins = _pins()
    entries = pins.get("mcp")
    assert entries, (
        "`mcp` 在 `requirements.txt` 里没有上界了。`camel-ai` 自己声明的是 "
        "`mcp>=1.3.0`、上界开放，放开这一行 pip 会解析到 mcp 2.x，"
        "然后 `from mcp.server import FastMCP` 当场 ImportError。")
    bounds = [(op, ver) for op, ver in entries if op in ("<", "<=", "~=")]
    assert bounds, f"`mcp` 只剩这些约束：{entries} —— 上界没了。"

    installed = _installed("mcp")
    major = int(installed.split(".")[0])
    assert major < 2, (
        f"现场装的是 mcp {installed}（major={major}），而这条上界是 `<2`。\n"
        "症状不是「装置算错了」，是**导入就炸**："
        "`camel/toolkits/base.py` 的类体里有一句 `from mcp.server import FastMCP`。")


def test_the_import_that_actually_breaks_still_works():
    """去把那个**真的会炸的导入**走一遍 —— 不是查版本号，是真 import。

    为什么在子进程里 import：这是一条「炸了就 ImportError」的路径，
    留在本进程里，一个半路失败的 `camel` 包会污染后面所有测试的 `sys.modules`，
    红的地方就指不到真凶了。

    为什么它**不是**恒真的：在 mcp 2.x 下这一条当场红（本装置踩过，所以才有
    `mcp<2` 那一行）。它现在绿，是因为上界在起作用 —— 这正是要守住的东西。
    """
    code = "from mcp.server import FastMCP\nimport camel.agents.chat_agent\n"
    proc = subprocess.run([sys.executable, "-c", code],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=300)
    assert proc.returncode == 0, (
        "这两行导入炸了：\n"
        "    from mcp.server import FastMCP\n"
        "    import camel.agents.chat_agent\n"
        f"--- stderr ---\n{proc.stderr}\n"
        "如果报的是 `cannot import name 'FastMCP' from 'mcp.server'`，"
        "那就是 `mcp<2` 那条上界没装上/被绕过了。")


def test_this_check_would_catch_the_breakage_it_is_about():
    """阴性对照：**把 mcp 2.x 的条件造出来**，看上面那一条会不会红。

    做法是「用完就删」：先 `import mcp.server`，再把 `FastMCP` 这个属性 `del` 掉 ——
    mcp 2.x 正是「`mcp.server` 底下没有这个名字」。删掉之后，
    `camel/toolkits/base.py` 类体里那句 `from mcp.server import FastMCP`
    就当场复现出当年那个 `ImportError`。

    为什么非要有这一条：没有它，上面那条测试**可能是恒真的** ——
    哪天 camel 把那个导入挪进函数（惰性化），它就会一直绿，
    而环境其实已经坏在别处了。「一条永远绿的检查」和没有检查是一回事，
    本装置在别处已经栽过这个跟头（变异留痕就是为这个存在的）。
    """
    code = ("import mcp.server\n"
            "del mcp.server.FastMCP\n"          # ← 这就是 2.x 的样子
            "import camel.agents.chat_agent\n")
    proc = subprocess.run([sys.executable, "-c", code],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=300)
    assert proc.returncode != 0, (
        "把 `mcp.server.FastMCP` 删掉之后，导入居然还是过了 —— "
        "那么 `test_the_import_that_actually_breaks_still_works` 守不住任何东西："
        "它绿是因为**它根本没走到那一行**，不是因为环境是对的。")
    assert "FastMCP" in proc.stderr, (
        "它确实红了，但红的原因不是我们要复现的那个：\n" + proc.stderr)
