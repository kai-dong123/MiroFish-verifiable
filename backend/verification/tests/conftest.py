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


@pytest.fixture
def requires_a_real_tokenizer():
    """本机取不到分词器时，把这格记成**没测到**（跳过），不记成失败。

    需要它的测试有一个共同前提：得有一个**真分词器**（`ToolStubModel` 构造时
    就建 `OpenAITokenCounter`；它还负责数出「一条消息到底多少 token」）。
    而那份编码表**首次使用要联网下一次**（约 3.6 MB，落在临时目录里）——
    没网、或者临时缓存被清过时取不到。

    取不到时**没有条件判**，与「判了为假」是两件事。这两件事混起来，正是本装置
    立身要反对的那一格（`_probe.tokenizer_or_none` 的文档里记着那次翻车：
    缺读数被折成「没达到预期」）。所以在这一层也要分清 —— 报「没测到」。

    **为什么是运行时部件而不是 `skipif`。** `tokenizer_or_none()` 在取不到时
    会打一行中文解释；`skipif` 是在**收集期**求值的，那行字会打在任何测试的
    捕获之外（GBK 控制台上正是会崩的那种场合）。放在夹具里就和别的测试一样，
    发生在 pytest 的捕获之内。
    """
    from verification import _probe as P

    if P.tokenizer_or_none() is None:
        pytest.skip("本机取不到分词器（编码表没下过 / 临时缓存被清过）"
                    " —— 这一格没测到，不是没达到预期")
    yield
