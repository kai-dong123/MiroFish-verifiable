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

#: 四个档位。`both` 是 `slicing` + `timestamp` 的合并。
CHOICES = ("off", "slicing", "timestamp", "both")

_HELP = (
    "运行时守卫。默认 off —— **不装，行为与上游完全一致**。"
    "slicing=修「切片正反馈环」，timestamp=修「同拍碰撞」，both=两个都装。"
    "两个可独立开关：第二个失效是第一个的代价，不拆开就分不清是谁动了什么。"
    "见 verification/README.md"
)


def add_guard_argument(parser) -> None:
    """给驱动脚本的 argparse 加上 `--guards`。"""
    parser.add_argument("--guards", choices=CHOICES, default="off",
                        help=_HELP)


def install_if_requested(args, log=print) -> bool:
    """按 `args.guards` 装守卫。装了返回 True。**默认 `off` 时什么都不做。**"""
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
