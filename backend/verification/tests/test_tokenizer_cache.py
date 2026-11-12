"""编码表固化：四个方向都钉住 —— 认得出、让得对、空目录不让、断网也编得动。

**不联网。** 最后一条把 `tiktoken.load.read_file`（真正会发请求的那个函数）
换成抛异常：只要它被调用一次，测试就红。这比「跑一下 encode 看看过不过」强 ——
后者在缓存恰好是热的时候会静默地放过一次下载。
"""

from __future__ import annotations

import hashlib
import pathlib

from verification import tokenizer_cache as T


def test_vendor_table_matches_pinned_hash():
    """仓库里那份就是钉住的那份。换表 = 换读数，必须显式改常量。"""
    p = T.VENDOR_DIR / T.FILENAME
    assert p.is_file(), "仓库里没有编码表 —— P0-2 的固化没生效"
    assert T.table_sha256() == T.EXPECTED_SHA256, "表的内容和钉住的哈希对不上"


def test_vendor_table_is_marked_binary_for_git():
    """`.gitattributes` 必须把这张表按字节原样检出。

    `core.autocrlf=true` 的机器（本机就是）会把 base64 文本转成 CRLF；
    文本归一化哈希还成立，但字节数会变，报告里那个「实测字节数」就对不上了。
    """
    root = pathlib.Path(__file__).resolve().parents[3]
    attrs = (root / ".gitattributes").read_text(encoding="utf-8")
    assert "backend/verification/vendor/tiktoken/* -text" in attrs


def test_resolver_yields_to_external_dir_that_has_the_table(tmp_path, monkeypatch):
    """外部目录里**确实有表** → 让位（那是评委自己准备的缓存）。"""
    dest = tmp_path / T.FILENAME
    dest.write_bytes((T.VENDOR_DIR / T.FILENAME).read_bytes())
    monkeypatch.setenv("TIKTOKEN_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("DATA_GYM_CACHE_DIR", raising=False)

    directory, source = T.resolve()
    assert directory == tmp_path
    assert source == "external"


def test_resolver_ignores_empty_external_dir(tmp_path, monkeypatch):
    """外部目录是空的 → **不让位**，用仓库内那份。

    这条是给评委机器准备的：一个空的 `TIKTOKEN_CACHE_DIR` 不该把我们打回联网。
    """
    monkeypatch.setenv("TIKTOKEN_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("DATA_GYM_CACHE_DIR", raising=False)

    directory, source = T.resolve()
    assert directory == T.VENDOR_DIR
    assert source == "vendor"


def test_resolver_reports_missing_when_neither_side_has_it(tmp_path, monkeypatch):
    """两边都没有 → `missing`，**不补默认值**。"""
    monkeypatch.setenv("TIKTOKEN_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("DATA_GYM_CACHE_DIR", raising=False)
    monkeypatch.setattr(T, "VENDOR_DIR", tmp_path / "nope")

    directory, source = T.resolve()
    assert directory is None
    assert source == "missing"


def test_encode_does_not_download_when_cache_is_cold(monkeypatch):
    """`read_file` 一旦被调用就红 —— 证明这张表确实是本地的。"""
    import tiktoken.load

    monkeypatch.setenv("TIKTOKEN_CACHE_DIR", str(T.VENDOR_DIR))
    monkeypatch.delenv("DATA_GYM_CACHE_DIR", raising=False)

    def _boom(*args, **kwargs):
        raise AssertionError("编码表不在本地，tiktoken 去下载了")

    monkeypatch.setattr(tiktoken.load, "read_file", _boom)

    import tiktoken
    from tiktoken_ext.openai_public import o200k_base

    # `o200k_base()` 返回的是编码参数（读表就在这一步）；`Encoding` 只是把它们装起来。
    enc = tiktoken.Encoding(**o200k_base())
    assert enc.encode("hello"), "编码表读到了，但编不出 token"


def test_pinned_hash_is_the_one_tiktoken_asks_for(monkeypatch):
    """`EXPECTED_SHA256` **就是** tiktoken 自己传下去的那个串。

    这条比「我们按文本归一化算一遍、再和自己比」硬：它走的是上游**实际执行**
    的那条路，把 `o200k_base()` 传给 `load_tiktoken_bpe` 的 `expected_hash`
    截下来比对。换成桩之后不会联网 —— 桩在发请求之前就把参数接走了。
    """
    import tiktoken_ext.openai_public as O

    captured = {}
    def fake(url, expected_hash=None):
        captured["h"] = expected_hash
        return {}
    monkeypatch.setattr(O, "load_tiktoken_bpe", fake)

    O.o200k_base()
    assert captured["h"] == T.EXPECTED_SHA256, (
        "我们钉的哈希和 tiktoken 要的不是同一个 —— 上游换表了，先看读数还成不成立")


def test_vendor_table_is_byte_identical_to_the_pinned_hash():
    """仓库里那份的**字节**哈希必须等于钉住的值。

    这张表是**按字节**喂给 tiktoken 的数据文件，身份就是字节。它同时是
    LF-only，所以文本哈希此刻也相等 —— 那是这份文件的巧合，不是判据依据。
    """
    p = T.VENDOR_DIR / T.FILENAME
    raw = p.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == T.EXPECTED_SHA256
    assert b"\r\n" not in raw, (
        "仓库里这份表不是 LF-only 了 —— 先查 `.gitattributes` 的 `-text`")


def test_resolver_rejects_an_external_table_whose_content_is_wrong(tmp_path, monkeypatch):
    """外部目录里**有同名文件、但内容不对** → 不让位，退回仓库那份。

    只验「文件在不在」是不够的：tiktoken 命中缓存后会自己校验哈希，不对时
    **删掉那个文件、联网重取**。在断网机器上，那条路的终点是一次异常；而报告
    里的 `source: external` 会变成一句假话。所以闸要提前落在这里。
    """
    (tmp_path / T.FILENAME).write_bytes(b"not the table\n")
    monkeypatch.setenv("TIKTOKEN_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("DATA_GYM_CACHE_DIR", raising=False)

    directory, source = T.resolve()
    assert directory == T.VENDOR_DIR, "内容不对的外部表也被让位了"
    assert source == "vendor"

    desc = T.describe()
    assert desc["source"] == "vendor"
    assert desc["external_rejected"] == [str(tmp_path)], (
        "外部表被拒这件事必须记进报告，否则账上还是 external")


def test_pinned_bytes_are_recorded_not_a_second_criterion():
    """字节数只作记录：它由哈希完全决定，不许再加一条判据。"""
    assert isinstance(T.EXPECTED_BYTES, int) and T.EXPECTED_BYTES > 0
    desc = T.describe()
    if desc["path"] is not None:
        assert desc["bytes"] == pathlib.Path(desc["path"]).stat().st_size
