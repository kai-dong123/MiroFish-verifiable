"""在驱动脚本入口装上 camel 运行时守卫；**装不上就退出，不裸奔**。

`--no-guards` 是唯一的显式关断开关：默认硬失败，只有调用方明确要求时才跳过。
这个取舍是刻意的 —— 守卫失效如果只打印一行提示，仿真会照常跑、只是悄悄
退回未修补的行为，而这正是这两个缺陷本身的形状。
"""
from __future__ import annotations

import sys


def install_guards_or_exit() -> None:
    if "--no-guards" in sys.argv:
        sys.argv.remove("--no-guards")
        print("[camel_guards] --no-guards：守卫未安装（裸奔）")
        return
    try:
        import camel_guards
    except ImportError as exc:
        raise SystemExit(
            "camel_guards.py 必须与本脚本同目录；"
            "确实要裸奔请显式加 --no-guards。") from exc
    camel_guards.install()
