"""把守卫接到上游驱动脚本上的那一小段胶水（三个入口共用一份）。

上游三个 `scripts/run_*_simulation.py` 的入口结构是一样的，所以这一段抽出来，
**每个入口只多两行**，而不是各抄十行。改动越小越好查：

    from verification.attach import add_guard_argument, install_if_requested
    add_guard_argument(parser)          # 加 --guards 选项
    ...
    install_if_requested(args, log=log_manager.info)

（两个入口要先把 `backend/` 放进 `sys.path`，见各脚本里的那一行。）

**默认是 `off`：不装，行为与上游逐字一致。** 这一点是刻意的 —— 一个能让你
对比「装与不装」的装置，默认状态必须是「不装」，否则就没有对比可言。
"""

from __future__ import annotations

import os

#: 四个档位。`both` 是 `slicing` + `timestamp` 的合并。
CHOICES = ("off", "slicing", "timestamp", "both")

#: 替身模型的触发词。**没有新开命令行选项** —— 上游 `create_model()` 本来就把
#: `LLM_MODEL_NAME` 当 `model_type` 直接传给 `ModelFactory.create`
#: （`run_parallel_simulation.py:1015` 与 `:1034`），所以「模型叫 stub」就是它
#: 唯一需要的信号。不写这个名字，本文件一个字都不参与。
STUB_MODEL_NAME = "stub"

#: 让 `random` 可复现。`get_active_agents_for_round` 用 `random` 挑每轮谁说话
#: （`run_parallel_simulation.py:1063-1080`），不播种的话同一份配置两遍跑出不同
#: 的人群 —— 而读数的意义就靠「同一份配置」。
ENV_SEED = "E2E_STUB_SEED"

_HELP = (
    "运行时守卫。默认 off —— **不装，行为与上游完全一致**。"
    "slicing=修「切片正反馈环」，timestamp=修「同拍碰撞」，both=两个都装。"
    "两个可独立开关：第二个失效是第一个的代价，不拆开就分不清是谁动了什么。"
    "见 verification/README.md"
)

_STUB_PATCHED = False


def add_guard_argument(parser) -> None:
    """给驱动脚本的 argparse 加上 `--guards`。"""
    parser.add_argument("--guards", choices=CHOICES, default="off",
                        help=_HELP)


def install_stub_model_if_named(log=print) -> bool:
    """`LLM_MODEL_NAME=stub` 时，把模型工厂接管过来造替身。装了返回 True。

    **只认这一个名字。** 其余任何模型名，`ModelFactory.create` 原样不动 ——
    所以这个函数在正常跑真模型的那条路上是**彻底惰性**的。

    为什么要接管工厂、而不是改上游那句 `create_model()`：那是上游的文件，改它
    就得多背一份 diff。接管工厂是**一个条件分支**，位置清楚、可整段摘掉。
    """
    global _STUB_PATCHED
    if _STUB_PATCHED or os.environ.get("LLM_MODEL_NAME") != STUB_MODEL_NAME:
        return False

    import random

    import camel.models.model_factory as factory

    from . import stub_model

    original = factory.ModelFactory.create

    def create(model_platform=None, model_type=None, **kw):
        if model_type == STUB_MODEL_NAME:
            return stub_model.from_env()
        return original(model_platform=model_platform,
                        model_type=model_type, **kw)

    factory.ModelFactory.create = staticmethod(create)
    _STUB_PATCHED = True

    seed = os.environ.get(ENV_SEED)
    if seed:
        random.seed(int(seed))
    try:
        log(f"替身模型已接管: model_type={STUB_MODEL_NAME!r}"
            + (f", random.seed({seed})" if seed else ""))
    except Exception:  # noqa: BLE001
        print(f"替身模型已接管: {STUB_MODEL_NAME!r}")
    return True


def install_if_requested(args, log=print) -> bool:
    """按 `args.guards` 装守卫。装了返回 True。**默认 `off` 时什么都不做。**

    替身模型那一支与 `--guards` **无关**：它由 `LLM_MODEL_NAME` 决定，所以放在
    这个早退分支**之前** —— 只想拿替身跑一局、一个守卫都不装，也是合法的用法。
    """
    install_stub_model_if_named(log=log)

    spec = getattr(args, "guards", "off")
    if spec not in CHOICES or spec == "off":
        return False
    from . import camel_guards

    camel_guards.install(slicing=spec in ("slicing", "both"),
                         timestamp=spec in ("timestamp", "both"))
    try:
        log(f"运行时守卫已装: {spec}")
    except Exception:  # noqa: BLE001  日志后端出问题不该拦住装守卫
        print(f"运行时守卫已装: {spec}")
    return True
