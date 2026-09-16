"""端到端那一层自己的测试：替身模型、夹具、读数块、以及「不在」这条路。

**这些测试不跑一整局仿真。** 真跑那一局由 `python -m verification.e2e_stub`
做（约 40 秒、起三个子进程），不适合放进 1.8 秒的测试套件里。这里钉的是
**跑之前和跑之后**的那些东西 —— 它们才是最容易悄悄坏掉的部分：

* 替身**必须无状态**（`env.step()` 并发跑所有 agent，而它们共用同一个后端实例）；
* 替身**必须用真分词器**（camel 自带的那个恒返 10，守卫的判据就成了摆设）；
* 花名册**必须能过中文 Windows 的 GBK**（上游不带编码地 `open`）；
* 读数块**必须和 `emit_readings` 同形**（不同形，裁决器就抽不出来）；
* 计数取不到时**必须记「没测到」**，不许填一个 0；
* 端到端报告**不在**时，那几条断言**必须判「不可判定」**，不是静默少掉。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import pathlib
import re

import pytest

from verification import _probe as P
from verification import adjudicate as A
from verification import e2e_stub as E
from verification import stub_model as S


# --------------------------------------------------------------------------
# 替身模型：形状、无状态、真分词器
# --------------------------------------------------------------------------


def test_the_stub_answers_with_a_well_formed_tool_call():
    """吐出来的东西必须**逐字**长成 `chat_agent.py` 读的那个样子。

    那条转换点是唯一的模型输出 → 动作的关口，它读三级：
    `.choices[0].message.tool_calls[i]` → `.id` / `.function.name` /
    `.function.arguments`（**JSON 字符串**，不是 dict）。少一级，动作就没了。
    """
    model = S.ToolStubModel(content_len=7)
    resp = model._run([])
    calls = resp.choices[0].message.tool_calls
    assert calls, "没有 tool_calls —— OASIS 的动作环会当这一轮没动作"
    assert calls[0].id and calls[0].function.name == S.ACTION
    assert isinstance(calls[0].function.arguments, str), (
        "`arguments` 必须是 JSON 字符串 —— camel 那一行直接把它当字符串用")
    assert json.loads(calls[0].function.arguments) == {"content": "x" * 7}


def test_the_stub_is_stateless_under_concurrency():
    """**同一个后端实例被所有 agent 共用**（每个 agent 一个 `ModelManager`，
    但包的是同一个后端）。所以行为只能由构造参数决定 —— 谁在里头放一个
    「这次该吐第几个动作」的游标，并发下就会串味，而且串得静默。
    """
    model = S.ToolStubModel(n_calls=1, content_len=3)
    first = model._run([]).choices[0].message.tool_calls[0].function.arguments

    async def _many():
        return await asyncio.gather(*[model._arun([]) for _ in range(24)])

    got = [r.choices[0].message.tool_calls[0].function.arguments
           for r in asyncio.run(_many())]
    assert set(got) == {first}, "并发 24 次返回了不止一种结果 —— 替身有状态"


def test_the_stub_counts_tokens_with_a_real_tokenizer():
    """`token_counter` **不能**是 camel 那个 `StubTokenCounter`（恒返 10）。

    守卫的判据是 `own_tokens > token_limit`；计数恒 10 的话，那条判断对任何
    消息都为假 —— 等于守卫没装。所以这里钉两件事：长消息数出来的**远多于 10**，
    而且**越长越多**（恒返 10 的假分词器过不了后一条）。
    """
    model = S.ToolStubModel()
    counter = model.token_counter
    from camel.messages import BaseMessage
    from camel.types import OpenAIBackendRole

    def n(text):
        return counter.count_tokens_from_messages(
            [BaseMessage.make_user_message(role_name="U", content=text)
             .to_openai_message(OpenAIBackendRole.USER)])

    short, long = n("x" * 10), n("x" * 4000)
    assert short > 10 or long > 10, "数出来恒等于 10 —— 这是假分词器"
    assert long > short * 5, "越长反而没越多 —— 计数器和内容无关"


def test_the_stub_reads_its_knobs_from_the_environment(monkeypatch):
    """端到端那条命令靠环境变量把三档臂喂进来（替身活在子进程里，
    没法用函数参数传）。"""
    monkeypatch.setenv(S.ENV_N_CALLS, "2")
    monkeypatch.setenv(S.ENV_CONTENT_LEN, "123")
    monkeypatch.setenv(S.ENV_TEXT_LEN, "456")
    monkeypatch.setenv(S.ENV_MAX_TOKENS, "4000")
    m = S.from_env()
    assert (m.n_calls, m.content_len, m.text_len) == (2, 123, 456)
    assert len(m._run([]).choices[0].message.tool_calls) == 2
    assert m._run([]).choices[0].message.content == "y" * 456


def test_an_unreadable_knob_falls_back_instead_of_crashing(monkeypatch):
    """旋钮读不出数就用默认值 —— **崩在一个环境变量上不该是这一层的行为**。"""
    monkeypatch.setenv(S.ENV_N_CALLS, "两")
    assert S.from_env().n_calls == S.DEFAULT_N_CALLS


# --------------------------------------------------------------------------
# 夹具：配置要把「谁被激活」钉住，花名册要能过 GBK
# --------------------------------------------------------------------------


def test_the_config_pins_who_gets_activated():
    """三档臂报的是同一件事的不同侧面，所以**人群必须一样**。

    上游选人靠 `random`（`random.uniform` 定人数、`random.random()` 定个人）。
    夹具把这些旋钮都顶到退化值上，于是「谁被激活」不再取决于运气。
    """
    cfg = E._config()
    t = cfg["time_config"]
    assert t["agents_per_hour_min"] == t["agents_per_hour_max"] == len(E.PROFILES)
    assert t["peak_hours"] == [] and t["off_peak_hours"] == []
    assert t["peak_activity_multiplier"] == t["off_peak_activity_multiplier"] == 1.0
    assert t["total_simulation_hours"] == 1 and t["minutes_per_round"] == 60
    assert all(a["activity_level"] == 1.0 for a in cfg["agent_configs"])
    # 第 0 轮的 simulated_hour 就是 0 —— 不把 0 放进 active_hours，一个人都不会醒。
    assert all(0 in a["active_hours"] for a in cfg["agent_configs"])
    # 库里每一条帖子都该出自替身，没有手工注入的干扰。
    assert cfg["event_config"]["initial_posts"] == []


def test_the_profiles_fixture_survives_a_gbk_windows(tmp_path):
    """花名册文件必须是**纯 ASCII 字节**。

    上游 `agents_generator.py` 那句 `open(profile_path, "r")` **不指定编码**，
    中文 Windows 上默认 GBK —— 一份 UTF-8 的中文花名册当场 `UnicodeDecodeError`。
    实测过，不是推测。`ensure_ascii=True` 把中文转成转义，整份文件退化成 ASCII。

    **同时也钉住「值里真的有中文」** —— 全 ASCII 的花名册绕过了那个缺陷，
    也就绕过了这条证据。
    """
    path = tmp_path / "reddit_profiles.json"
    E._write_profiles(path)
    raw = path.read_bytes()
    assert max(raw) < 128, "花名册里有非 ASCII 字节 —— 中文 Windows 上会当场炸"
    assert json.loads(raw.decode("ascii")) == list(E.PROFILES)
    assert any(ord(ch) > 127 for p in E.PROFILES for ch in p["username"]), (
        "花名册里一个中文都没有 —— 那就验不到那个绕法了")


def test_the_child_env_blocks_the_boost_model_path(monkeypatch):
    """只认 `LLM_MODEL_NAME=stub` 还不够。

    上游 `create_model(config, use_boost=True)` **先看加速配置**：`LLM_BOOST_API_KEY`
    非空就走 `LLM_BOOST_MODEL_NAME`，而那个名字不是 `stub` —— 于是真模型被造出来、
    真请求发出去。仓库根目录的 `.env` 若配了加速 key，`load_dotenv` 就会把它塞进来。
    所以这一步是**显式清空**，不是指望 `.env` 里没有。
    """
    monkeypatch.setenv("LLM_BOOST_API_KEY", "sk-a-real-looking-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://private.example/v1")
    monkeypatch.setenv("LLM_API_KEY", "sk-another-real-key")
    monkeypatch.setenv("GUARD_COUNTERS_OUT", "keep-me")
    env = E._child_env(pathlib.Path("."), {}, pathlib.Path("c.json"))
    assert env["LLM_MODEL_NAME"] == "stub"
    assert env["LLM_BOOST_API_KEY"] == "" and env["LLM_BOOST_MODEL_NAME"] == ""
    assert env["LLM_BASE_URL"] == ""
    assert env["LLM_API_KEY"] == E.PLACEHOLDER_KEY, "把真 key 带进子进程了"
    assert env["LLM_API_KEY"] and "sk-" not in env["LLM_API_KEY"]
    assert env["GUARD_COUNTERS_OUT"] == "c.json"
    assert env["PYTHONIOENCODING"] == "utf-8"


def test_the_recorded_entry_script_hash_is_a_text_hash(tmp_path):
    """产物里记的入口脚本 sha256 **按文本算**，不按字节。

    入口脚本是受版本控制的：`core.autocrlf`（Windows 上默认开）会在 clone 时把
    它换成 CRLF。拿 `read_bytes()` 去算，记下来的就是**造这份产物那台机器的检出
    配置**，而不是脚本的内容 —— 换个人 clone 就对不上，而脚本一个字没动。
    这条与 `mutations._suite_fingerprint` 那处是同一个毛病（2026-09-17 在一个
    干净 clone 里当场红过），所以两处一起按文本算，见 `_probe.sha256_text`。
    """
    assert E._environment()["script_sha256"] == P.sha256_text(E.SCRIPT)

    # 差分对照：**同一份内容**，一份 LF 一份 CRLF —— 文本哈希不动、字节哈希会动。
    # 没有这一半，「按文本算」和「这儿碰巧两边一样」看起来是一回事。
    #
    # （两个副本都现造，不拿工作区里那个当基准：本机工作区正是 `autocrlf` 的
    # 现场，而它是**混的** —— clone 下来的文件是 CRLF、后来手写的文件是 LF。
    # 拿它当基准，这一条就变成在测「谁最后碰过哪个文件」。）
    text = E.SCRIPT.read_text(encoding="utf-8")
    lf, crlf = tmp_path / "lf.py", tmp_path / "crlf.py"
    lf.write_bytes(text.encode("utf-8"))
    crlf.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    assert P.sha256_text(lf) == P.sha256_text(crlf)
    assert hashlib.sha256(lf.read_bytes()) != hashlib.sha256(crlf.read_bytes())


# --------------------------------------------------------------------------
# 读数：取不到就是「没测到」，不许填 0
# --------------------------------------------------------------------------


def _fake_run(arm, *, counters=None, posts=None):
    return {"arm": arm, "counters": counters, "db_posts": posts,
            "timeout": False, "rc": 0, "seconds": 1.0, "body": ""}


def test_a_missing_counters_file_is_undecided_not_zero(tmp_path):
    """**取不到 ≠ 0。** 填充一个 0 等于把一次取证失败说成一个读数 ——
    而 0 恰好是「守卫装了但一次都没走到」的正常取值，两种情形会长得一模一样。
    """
    assert E._read_counters(tmp_path / "nope.json") is None
    assert E._read_counters(tmp_path) is None          # 路径是个目录
    bad = tmp_path / "bad.json"
    bad.write_text("{不是 json", encoding="utf-8")
    assert E._read_counters(bad) is None


def test_unmeasured_cells_are_declared_not_filled_in():
    payload = E._payload([_fake_run("roomy_e2e", counters=None, posts=None)])
    assert "roomy_e2e" not in payload["readings"], (
        "没测到的那档臂不该出现在读数里 —— 填一个默认值进去是编数")
    kinds = {(b["arm"], b["metric"]): b["kind"] for b in payload["boundaries"]}
    assert kinds[("roomy_e2e", "written_whole")] == P.BOUND_UNMEASURED
    assert kinds[("roomy_e2e", "db_posts")] == P.BOUND_UNMEASURED


def test_the_db_reader_returns_none_when_there_is_no_db(tmp_path):
    assert E._count_posts(tmp_path / "nope.db") is None
    empty = tmp_path / "empty.db"
    empty.write_bytes(b"")            # 有文件、不是库
    assert E._count_posts(empty) is None


# --------------------------------------------------------------------------
# 读数块：和 emit_readings 同形
# --------------------------------------------------------------------------


def _three_runs():
    return [
        _fake_run("roomy_e2e",
                  counters={"written_whole": 8, "still_sliced": 0,
                            "timestamp_pushed": 2}, posts=2),
        _fake_run("bigtext_e2e",
                  counters={"written_whole": 6, "still_sliced": 2,
                            "timestamp_pushed": 0}, posts=2),
        _fake_run("two_e2e",
                  counters={"written_whole": 12, "still_sliced": 0,
                            "timestamp_pushed": 2}, posts=4),
    ]


def test_the_readings_block_is_the_shape_emit_readings_produces():
    """块**必须**和 `_probe.emit_readings` 同形 —— 不同形，裁决器就抽不出来，
    而它抽不出来时会静静地少判几条（看上去像「这张表就这么多」）。

    做法不是比对字段名清单，而是**真走一遍取块的那条路**：按锚定分隔符拼出正文，
    用 `parse_readings` 读回来，看是不是同一份。拼法写死在 `_block_body` 里，
    所以这条测试同时钉住了那个拼法。
    """
    payload = E._payload(_three_runs())
    body = E._block_body(payload)
    assert body.count(P._READINGS_BEGIN) == 1
    assert body.count(P._READINGS_END) == 1
    assert P.parse_readings(body) == payload
    assert P.readings_sha256(body) == P.readings_sha256(body)  # 确定性
    assert P.non_gbk_chars(body) == "", "读数块里有 GBK 编不出的字（cmd 下会变 ?）"


def test_the_block_marks_the_structurally_dead_cell_as_railed():
    """回落支那档的 `timestamp_pushed` **按构造**恒为 0 —— 必须声明贴界。

    不声明的话，E5 会以「通过·采信」出现，读起来像「我们证明了回落支没有碰撞」，
    而那个计数压根不在那条支上加。
    """
    payload = E._payload(_three_runs())
    railed = {(b["arm"], b["metric"]): b["kind"] for b in payload["boundaries"]}
    assert railed[("bigtext_e2e", "timestamp_pushed")] == P.BOUND_RAILED
    assert ("bigtext_e2e", "timestamp_pushed") not in \
        [k for k, v in railed.items() if v == P.BOUND_UNMEASURED]


# --------------------------------------------------------------------------
# 转录：抹过，而且说得出抹了什么
# --------------------------------------------------------------------------


def test_the_transcript_redacts_this_machine(tmp_path):
    """转录要入库、仓库要公开 —— 本机路径和挂钟时间戳都得抹掉，
    而且**替换名单要写进产物**：一份抹过的转录不许被当成逐字转录读。
    """
    root = tmp_path / "mirofish_e2e_abcd1234"
    root.mkdir()
    text = (f"db_path {root}\\roomy_e2e\\reddit_simulation.db\n"
            f"配置文件: {E.BACKEND}\\scripts\\x.py\n"
            "[01:08:17] 环境已启动\n[01:08:18] 环境已关闭\n")
    out = E._redact(text, root)
    assert "mirofish_e2e_abcd1234" not in out
    assert str(E.BACKEND) not in out
    assert "[01:08:17]" not in out and "[01:08:18]" not in out
    assert out.count("<运行目录>") == 1 and out.count("<backend>") == 1
    assert "环境已启动" in out, "不能把正文一起抹了"


def test_the_report_says_the_transcript_was_redacted(tmp_path):
    rep = E._report(_three_runs(), "", tmp_path)
    entry = rep["results"][0]
    assert entry["transcript_redacted"] is True
    assert entry["redaction_applied"], "抹了却不说抹了什么"
    assert entry["readings"]["readings"]["two_e2e"]["db_posts"] == 4
    assert rep["not_a_pass_rate"] is True


#: 这份产物**要入库**，所以它里面一个本机路径都不许有。
#:
#: 这条**踩过一次**：转录抹干净了，`environment.cwd` 却还记着
#: `D:\open_source\...\backend` —— 抹了会话记录、漏了环境块。当时没有任何东西
#: 会因此变红，是本目录四份**别的**产物（`adjudicate` / `selfproof` / `mutations` /
#: `reconcile_selfcheck`）都记 `"backend/"` 才看出来这一个不合群。
#: 手抄的纪律会烂，所以这里把它变成机检的。
_LEAK_PATTERNS = (
    r"[A-Za-z]:\\",            # Windows 盘符绝对路径
    r"[A-Za-z]:/",
    r"AppData",
    r"mirofish_e2e_",          # 临时目录前缀
    r"[\\/]Temp[\\/]",
    r"/tmp/",
    r"/home/",
    r"/Users/",
)


def test_the_report_carries_no_machine_path_anywhere(tmp_path):
    """整份产物（不只是转录）里不许有本机路径 —— 环境块也算。"""
    rep = E._report(_three_runs(), "", tmp_path)
    blob = json.dumps(rep, ensure_ascii=False)
    hits = [p for p in _LEAK_PATTERNS if re.search(p, blob)]
    assert not hits, f"产物里带着本机路径，模式：{hits}"
    assert rep["environment"]["cwd"] == "backend/", (
        "入库的产物记相对路径 —— 与 adjudicate / selfproof / mutations / "
        "reconcile_selfcheck 四份的惯例一致")
    # 反向对照：真的把绝对路径塞回去，这台机检必须响。
    # （没有这一半，「没扫到」和「扫描器写坏了」看起来一模一样。）
    rep["environment"]["cwd"] = r"D:\open_source\mirofish-verifiable\backend"
    blob2 = json.dumps(rep, ensure_ascii=False)
    assert [p for p in _LEAK_PATTERNS if re.search(p, blob2)], "机检翻不动，等于没检"


# --------------------------------------------------------------------------
# 接进裁决器：两份报告一起读，缺一份就是「不可判定」
# --------------------------------------------------------------------------


def test_cells_from_accepts_extra_reports():
    """`cells_from` 收**几份**报告。一份一个来源，来源之间不互相知道。"""
    a = {"results": [{"readings": {"readings": {"arm_a": {"m": 1}},
                                   "boundaries": []}}]}
    b = {"results": [{"readings": {
        "readings": {"arm_b": {"m": 2}},
        "boundaries": [{"arm": "arm_b", "metric": "m", "kind": P.BOUND_RAILED,
                        "why": "凑出来的"}]}}]}
    cells, railed, _ = A.cells_from(a, b)
    assert ("arm_a", "m") in cells and cells[("arm_b", "m")] == 2
    assert ("arm_b", "m") in railed


def test_all_cells_reads_both_reports(monkeypatch):
    """**两个来源一个入口。** 两处各读一半，会出现「这份产物判了 15 条、
    那份判了 10 条」而没人发现。"""
    monkeypatch.setattr(A, "load_report", lambda *a, **k: {
        "results": [{"readings": {"readings": {"arm_a": {"m": 1}},
                                  "boundaries": []}}]})
    monkeypatch.setattr(A, "load_e2e_report", lambda *a, **k: {
        "results": [{"readings": {"readings": {"roomy_e2e": {"written_whole": 8}},
                                  "boundaries": []}}]})
    cells, _, _ = A.all_cells()
    assert cells[("arm_a", "m")] == 1 and cells[("roomy_e2e", "written_whole")] == 8


def test_a_missing_e2e_report_is_none_not_an_exception(tmp_path):
    """端到端那一路**本来就可以没跑过** —— 于是返回 `None`，不抛。

    这和三条复现那份**故意不同**：那三条的读数必须都在（不在就说明前提坏了，
    该停下来），而这一层不在是正常状态。
    """
    assert A.load_e2e_report(tmp_path / "nope.json") is None
    assert A.load_e2e_report(tmp_path) is None            # 是个目录
    bad = tmp_path / "bad.json"
    bad.write_text("不是 json", encoding="utf-8")
    assert A.load_e2e_report(bad) is None, "文件在但不是 JSON —— 这也是「没测到」"


def test_a_missing_e2e_report_makes_that_layer_undecided(tmp_path, monkeypatch):
    """**不许静默少掉几条。** 端到端报告不在时，E1–E5 必须判「不可判定」、
    带着「跑一次 e2e_stub」这条补法，而且 `trusted` 记 `None`
    （记 False 会让「不采信」虚高，记 True 等于说它可信）。

    这一条守的是整个设计的那个接缝：**「没测到」既不是通过也不是否决。**
    """
    monkeypatch.setattr(A, "load_report", lambda *a, **k: {
        "results": [{"readings": {"readings": {"arm_a": {"m": 1}},
                                  "boundaries": []}}]})
    monkeypatch.setattr(A, "load_e2e_report", lambda *a, **k: None)
    rows = A.evaluate(A.CLAIMS, *A.all_cells())
    by_id = {r["id"]: r for r in rows}
    e_ids = [c["id"] for c in A.CLAIMS if c["id"].startswith("E")]
    assert e_ids, "一条端到端断言都没有？"
    for cid in e_ids:
        assert by_id[cid]["verdict"] == A.UNDECIDED, f"{cid} 在没跑端到端时没判不可判定"
        assert by_id[cid]["trusted"] is None
        assert "e2e_stub" in by_id[cid]["to_make_decidable"], (
            f"{cid} 说了判不了，却没说怎么才能判")
    # 其余各条不受影响 —— 「缺一份报告」不该波及另一份。
    assert by_id["E1"]["detail"] == "缺 roomy_e2e.written_whole"
    assert by_id["E1"]["operands"] == ["roomy_e2e.written_whole"]


def test_the_e2e_provenance_is_recorded_either_way():
    """「没跑过」和「跑了」都要说得出是哪一种 —— 否则少了几条断言
    会被读成「这张表就这么多」。"""
    absent = A._e2e_provenance(None)
    assert absent["present"] is False and "e2e_stub" in absent["to_make_decidable"]
    got = {"generated_at": "X", "arms_missing": ["two_e2e"],
           "what_it_does_NOT_prove": "…",
           "results": [{"arms": ["roomy_e2e", "bigtext_e2e"]}]}
    present = A._e2e_provenance(got)
    assert present["present"] is True
    assert present["arms"] == ["roomy_e2e", "bigtext_e2e"]
    assert present["arms_missing"] == ["two_e2e"]
    assert present["model_is_stub"] is True, (
        "替身这件事必须跟着读数走到裁决器 —— 否则读的人会以为模型是真的")


def test_the_e2e_claims_are_wired_into_the_real_corpus():
    """E1–E5 真在判据表里、层名合法、每条都带 falsifier 与「怎么才能判」。"""
    e = [c for c in A.CLAIMS if c["id"].startswith("E")]
    assert [c["id"] for c in e] == ["E1", "E2", "E3", "E4", "E5"]
    assert all(c["layer"] == "端到端" for c in e)
    assert "端到端" in A.LAYERS
    for c in e:
        assert c["falsifier"], f"{c['id']} 没有 falsifier —— 它会被判恒真"
        assert c["undecidable_because"] and c["to_make_decidable"], (
            f"{c['id']} 的「缺什么」和「怎么才能判」必须成对")
        assert all(a.endswith("_e2e") for a, _ in c["operands"]), (
            f"{c['id']} 读了非端到端的格子 —— 层和格子对不上")
