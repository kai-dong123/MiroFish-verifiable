"""让 `verification.tests` 在两种跑法下都 import 得到 `verification`。

`python -m pytest verification/tests` 会把当前目录（`backend/`）放进 `sys.path`，
但 `pytest verification/tests` **不会** —— 而两种跑法都应该能用。所以这里自己把
`backend/` 放进去，不指望调用方式。

（这个文件同时也让本目录在 pytest 眼里是个包，收集行为更可预期。）
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(os.path.dirname(_HERE))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _no_guard_leaks():
    """每个测试前后都把守卫卸干净。

    守卫的状态是**模块级全局**的，而 `install()` 是在**类**上打补丁 —— 不清理的话
    一个测试装上的补丁会漏进下一个测试，而且漏得**静默**。这个夹具存在的理由就是
    让「测试之间不互相污染」这件事不依赖每个测试作者自觉。
    """
    from verification import camel_guards as G

    G.uninstall()
    yield
    G.uninstall()
