"""把 tiktoken 的编码表固化进仓库，并决定这次运行用哪一份。

`tiktoken` 的编码表是**首次使用时下载**的一份静态数据（`o200k_base`，实测
3,613,922 字节）。缓存冷的时候，`run_all` 只能报「没测到」—— 而切片那一整节的
数字（270 条 / 5130 token）**全部依赖这张表给出的真 token 数**。

这里做三件事：

1. **认表**：文件名取表的 URL 的 sha1（tiktoken 自己就是这么缓存的），内容哈希
   钉在 `EXPECTED_SHA256`；
2. **选目录**：外部 `TIKTOKEN_CACHE_DIR` / `DATA_GYM_CACHE_DIR` 里**已经有这张表**
   时让位给外部；否则用仓库内那份 `verification/vendor/tiktoken/`；两边都没有才
   交回 tiktoken 的默认缓存（那意味着要联网，报告里会记成 `missing`/`default`）；
3. **落环境变量**：tiktoken 在**调用时**读这两个变量，所以在包导入时设一次就够。

**为什么必须在包导入时设。** `stub_model.py` 在 `__init__` 里就建
`OpenAITokenCounter`，比 `_probe.py` 更早；设晚一步就绕不过去。而
`os.environ` 是进程级的，晚设还会让已经构造好的对象继续用旧目录。

**为什么空的外部目录不能让位。** 评委机器上很可能已经有一个空的
`TIKTOKEN_CACHE_DIR`；照单全收就等于把仓库内那份绕过去、退回联网。所以判据是
「那个目录里**确实有这张表**」，不是「那个变量被设过」。
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import tempfile

#: 表在 OpenAI 的公开地址。**文件名不是随便起的** —— tiktoken 用它的 sha1 当缓存名。
URL = "https://openaipublic.blob.core.windows.net/encodings/o200k_base.tiktoken"
FILENAME = hashlib.sha1(URL.encode("utf-8")).hexdigest()

#: 钉住的内容哈希 —— **就是 tiktoken `o200k_base()` 传给 `load_tiktoken_bpe`
#: 的 `expected_hash`（按字节算）。测试里用捕获桩把它截下来逐字比对，不手抄。
#: 换表 = 换读数，必须显式改这个常量并重跑全部产物。
EXPECTED_SHA256 = "446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d"

#: 实测字节数。**只作记录，不作判据** —— 判据是 `EXPECTED_SHA256`（字节）。
#: 字节数由哈希完全决定；再加一条「字节数对不对」只是同一个性质的第二个结论，
#: 屏幕上和产物里多一个可能不一致的答案。
EXPECTED_BYTES = 3_613_922

VENDOR_DIR = pathlib.Path(__file__).resolve().parent / "vendor" / "tiktoken"

_state: dict = {"dir": None, "source": "unresolved", "rejected": []}


def _external_dirs() -> list[pathlib.Path]:
    """外部缓存目录，按 tiktoken 自己的优先顺序；**排除仓库内那份**。

    排除是为了不让 `ensure()` 自己写进去的值反过来被认成「外部」。
    """
    out = []
    for key in ("TIKTOKEN_CACHE_DIR", "DATA_GYM_CACHE_DIR"):
        value = os.environ.get(key)
        if not value:
            continue
        p = pathlib.Path(value)
        try:
            if p.resolve() == VENDOR_DIR:
                continue
        except OSError:  # 路径不合法时按「不是仓库内」处理
            pass
        out.append(p)
    return out


def _has_table(directory: pathlib.Path) -> bool:
    """**有这张表** = 文件在、而且字节与 `EXPECTED_SHA256` 一致。

    只验「文件在不在」不够：tiktoken 命中缓存后会自己校验哈希，不一致时
    **删掉那个文件、联网重取**。那条路在断网机器上会变成一次异常，而且报告里
    的 `source: external` 会是一句假话。闸要提前落在这里。
    """
    p = directory / FILENAME
    from . import _probe as P          # 延迟导入：本模块被包导入时还轮不到 _probe
    return p.is_file() and P.sha256_bytes(p) == EXPECTED_SHA256


def resolve() -> tuple[pathlib.Path | None, str]:
    """这次该用哪个目录：`(目录, 来源)`。来源是 `external` / `vendor` / `missing`。

    **不让位给空目录**（理由见模块头）。外部目录里有表、且**内容对得上**时才让位
    —— 那是评委自己准备好的缓存。内容不对的目录会被记进 `rejected`，由
    `describe()` 写进报告：账上不能一边退回仓库、一边还写着 `external`。
    """
    rejected = []
    for d in _external_dirs():
        if _has_table(d):
            _state["rejected"] = rejected
            return d, "external"
        if (d / FILENAME).is_file():
            rejected.append(str(d))     # 有同名文件，但内容不是钉住的那份
    _state["rejected"] = rejected
    if _has_table(VENDOR_DIR):
        return VENDOR_DIR, "vendor"
    return None, "missing"


def ensure() -> dict:
    """解析一次并写进环境变量。**幂等**，包导入时调用。"""
    directory, source = resolve()
    if directory is not None:
        os.environ["TIKTOKEN_CACHE_DIR"] = str(directory)
        _state["dir"], _state["source"] = directory, source
    else:
        _state["dir"], _state["source"] = None, "missing"
    return dict(_state)


def table_path() -> pathlib.Path | None:
    """**实际**那份表的路径；一份都没有返回 `None`。

    会顺手看一眼 tiktoken 的默认缓存：如果这次运行已经联网下过，报告里至少要
    能记下「用的是下载来的那份」，而不是假装没有表。
    """
    directory, _ = resolve()
    if directory is not None:
        return directory / FILENAME
    default = pathlib.Path(tempfile.gettempdir()) / "data-gym-cache" / FILENAME
    return default if default.is_file() else None


def table_sha256() -> str | None:
    """表的**字节**哈希；没有表返回 `None`（**不补默认值**）。

    这张表的身份就是字节：它是按字节喂给 tiktoken 的数据文件。原先这里按文本
    归一化算 —— 与 `EXPECTED_SHA256`（tiktoken 的字节哈希）恰好相等，只因为
    仓库里那份是 LF-only。那是一处**靠巧合成立的一致性**，现在消掉。
    """
    p = table_path()
    if p is None:
        return None
    from . import _probe as P          # 延迟导入：这里只需要那个纯函数

    return P.sha256_bytes(p)


def describe() -> dict:
    """给 `run_all` 的环境一节用。路径只作信息，哈希才是判据。

    `external_rejected` 记「有同名文件但内容不对」的外部目录 —— 它可能为空。
    这一格必须留在报告里：只退回仓库、不说为什么，读者会以为外部缓存根本没设。
    """
    directory, source = resolve()
    p = directory / FILENAME if directory is not None else None
    if p is None:
        default = pathlib.Path(tempfile.gettempdir()) / "data-gym-cache" / FILENAME
        if default.is_file():
            p, source = default, "default"   # tiktoken 自己下到了默认缓存
    if p is None:
        source = "missing"
    from . import _probe as P          # 延迟导入：这里只需要那个纯函数
    return {
        "source": source,
        "path": str(p) if p is not None else None,
        "sha256": P.sha256_bytes(p) if p is not None else None,
        "bytes": p.stat().st_size if p is not None else None,
        "external_rejected": list(_state["rejected"]),
    }
