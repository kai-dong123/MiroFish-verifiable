"""verification —— 让 MiroFish 类仿真的输出变得**可判定**的装置。

见 `README.md`。跑全部：`python -m verification.run_all`。
"""

import sys


def _harden_streams() -> None:
    """给标准输出/错误加一层兜底：**编不出的字符降级，不要让程序崩**。

    上游已经知道 Windows 有这个坑（`scripts/run_parallel_simulation.py` 开头
    在改 I/O 编码），但它只在**一个入口脚本**里做了；从别处进来还是会撞上。
    这里做的是补漏，不是替换上游的做法。

    **注意这里不强制 UTF-8。** 中文 Windows 的 cmd 默认代码页是 GBK，
    硬写 UTF-8 会让所有中文变成乱码 —— 那比崩掉更难排查。所以：保持原有编码，
    只把**编不出的那些字符**降级成 `?`。配套地，`_probe.py` 里只用 GBK
    也编得出的记号，两条一起才真的挡住这件事。

    对已经设过的流是空操作，可重复调用。
    """
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(errors="replace")
            except (ValueError, OSError):  # 流已关闭或不可重配
                pass


_harden_streams()
