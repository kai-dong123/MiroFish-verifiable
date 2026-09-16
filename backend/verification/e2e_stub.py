"""端到端：拿替身模型把**真入口脚本**跑一整局，把守卫的计数取回来。

    cd backend
    python -m verification.e2e_stub              # 三档臂，约 40 秒
    python -m verification.e2e_stub --keep       # 留下临时目录，方便逐字看现场

## 它补的是哪一格

`README.md` 里「运行时守卫」那一节长期写着「**接上了，但没端到端跑过** ——
那要 API key」。这一格由本文件推掉：本命令**不发一个字节的网**，也不需要 key。

## 它跑的是**真入口**，不是把管线重搭一遍

被拉起来的子进程是上游那个原样的驱动脚本：

    python scripts/run_parallel_simulation.py \\
        --config <临时目录>/simulation_config.json \\
        --reddit-only --max-rounds 1 --no-wait --guards both

也就是说 `SocialAgent`、`AgentGraph`、`OASIS env.step()`、SQLite 平台库、camel 的
工具调用环、记忆写入路径**全是真的**。被换掉的只有一样：**模型的决策**
（`stub_model.ToolStubModel` 顶掉 `ModelFactory.create`）。这条界线是本命令
全部读数的前提，读它的人必须知道。

## 为什么用 Reddit，不用 Twitter

`DefaultPlatformType.TWITTER` 的推荐系统硬依赖 HuggingFace 的
`Twitter/twhin-bert-base` 权重；离线时那个异常被 `oasis/.../platform.py` 吞掉，
推荐表**永远静默不更新**。Reddit 的 `rec_sys_reddit` 不需要任何模型。

## 为什么没有「守卫关」这条臂

`--guards off` 时守卫**根本没装**，`counters()` 恒为全 0 —— 读不出东西来。
所以三档臂**全部**是 `--guards both`，彼此之间的差别只在两个旋钮上：

| 臂 | 旋钮 | 想走到守卫的哪一支 |
|---|---|---|
| `roomy_e2e` | 一次响应一个动作，消息放得下 | 快路径写入 |
| `bigtext_e2e` | 助手消息文本 20000 字 | 「自己就超上限」的回落支 |
| `two_e2e` | 一次响应两个动作 | 同拍写入（时间戳被推） |

**`max_tokens` 不能当旋钮用。** 它同时是 `ScoreBasedContextCreator` 的上限，
收得太紧会让 `get_context()` 抛 `RuntimeError`，`chat_agent.py:2004-2007` 接住
之后直接把这一轮终止 —— agent 在能写任何东西之前就没了动作，**看起来像跑通了**。

## 这一格能诚实主张什么，不能主张什么

**能主张**：守卫的两个分支**都被真实流量走到了** —— 快路径写入走通、超限回落支
走通、同拍写入被推时间戳、动作真的落进平台库。

**不能主张**：**它不证明「守卫修好了什么」** —— 那是三条离线复现的活（它们量的是
「装上前后差多少」，本命令量的是「装上了、并且被走到了」）。它也**不证明仿真质量**，
因为模型是替身。这条界线写进了产物，不只是写在这里。

## 读数落盘靠 `atexit`，不靠改上游脚本

`camel_guards.install()` 在本进程注册一个 `atexit`，把 `counters()` 写到
`$GUARD_COUNTERS_OUT`。**文件不在就报「没测到」，不编数** —— 和 `_reconcile`
同一条纪律。在本文件之前，`counters()` 只有测试在调：谁真拿 `--guards both`
跑一整局，也拿不到任何一个数。

## 转录是**抹过**的，这一点写进了产物

上游脚本会把路径原样打出来：运行目录（`mkdtemp` 的随机后缀）、仓库位置、主目录。
这份转录要入库、仓库要公开 —— `C:\\Users\\<某人的名字>\\AppData\\Local\\Temp\\...`
既泄露构建者的本机路径，又让产物每次的字节都不一样。所以 `_redact()` 抹掉四个
具名的东西（运行目录 / `backend/` / 系统临时根 / 主目录）和行首的挂钟时间戳，
**替换名单一并写进产物**（`redaction_applied`）、并标 `transcript_redacted: true`：
**一份抹过的转录不许被当成逐字转录读。**
**读数不受影响** —— 它取自 `counters()` 落下的 JSON 与平台库的计数，
不从这段文本里抠（这与 `run_all` 那条「不解析数字」是同一条纪律）。

## 一份单独的报告，`run_all` 一个字不改

本命令落 `verification/e2e_report.json`，长成 `run_all` 报告的样子
（`results[*].readings`），由 `adjudicate.all_cells()` 一并读进去。
**不登记进 `run_all.CASES`** —— 登记进去会把汇总那个 `x/3` 变成 `x/5`，
而三条复现回答的是三个不同性质的问题，不该被稀释。端到端的读数**在就判，
不在就如实记「不可判定」**。

## 退出码（三种，不是两种）

    0   三档臂都跑完，且每档的计数与平台库都取到了
    1   有子进程**没跑成**（真要看的东西）
    2   有**没测到**的格子（计数文件没落下来 / 平台库读不到 / 超时）

`2` 和 `1` 分开，和装置其余部分同一个规矩：**「没测到」不等于「通过」，也不等于
「失败」**。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time

from . import _probe as P

HERE = pathlib.Path(__file__).resolve().parent          # backend/verification
BACKEND = HERE.parent                                   # backend/
SCRIPT = BACKEND / "scripts" / "run_parallel_simulation.py"
REPORT = HERE / "e2e_report.json"

#: 只用来过一句**非空检查**（`run_parallel_simulation.py:1026` 那句
#: 「缺少 API Key 配置」）。替身不走任何网络 —— 这个串不会被发给任何人。
#: **这条照实写进产物**：上游把「有 key」当成了「能跑」的代理，是个小疵。
PLACEHOLDER_KEY = "e2e-stub-never-sent-nowhere"

#: 播种 `random`：上游靠它挑每轮谁说话（`get_active_agents_for_round`）。
#: 本夹具的 `activity_level=1.0` 与 `agents_per_hour_min==max` 已经让选择确定，
#: 播种是第二道保险 —— 读数靠的是「同一份配置」，不是运气。
SEED = "20260917"

#: 一档一条臂。`(稳定键, 人读标签, 旋钮)`。**全部 `--guards both`**（见模块头）。
ARMS = (
    ("roomy_e2e", "基线：一次响应一个动作、消息放得下",
     {"E2E_STUB_N_CALLS": "1", "E2E_STUB_CONTENT_LEN": "40",
      "E2E_STUB_TEXT_LEN": "0"}),
    ("bigtext_e2e", "助手消息文本 20000 字：逼出「自己就超上限」的回落支",
     {"E2E_STUB_N_CALLS": "1", "E2E_STUB_CONTENT_LEN": "40",
      "E2E_STUB_TEXT_LEN": "20000"}),
    ("two_e2e", "一次响应两个动作：逼出同拍写入",
     {"E2E_STUB_N_CALLS": "2", "E2E_STUB_CONTENT_LEN": "40",
      "E2E_STUB_TEXT_LEN": "0"}),
)

#: 每档臂报哪几个量。**裸数，无单位串**（`emit_readings` 的纪律）。
METRICS = ("written_whole", "still_sliced", "timestamp_pushed", "db_posts")

#: 量的单位，只给人读。
UNITS = {"written_whole": "条（走快路径写入的记录）",
         "still_sliced": "条（自己就超上限、交回原方法切的记录）",
         "timestamp_pushed": "次（我们取读数却被推后的写入）",
         "db_posts": "条（平台 SQLite 里 post 表的行数）"}

#: 花名册。**值里有中文是故意的** —— 见 `_write_profiles`。
PROFILES = (
    {"username": "甲", "bio": "关注校园食堂", "persona": "学生",
     "mbti": "INTJ", "gender": "female", "age": 20, "country": "China"},
    {"username": "乙", "bio": "关注宿舍管理", "persona": "教职工",
     "mbti": "ENFP", "gender": "male", "age": 35, "country": "China"},
)


def _config() -> dict:
    """夹具配置。每一处取值都在把「谁会被激活」钉成确定的，不留给运气。

    * `total_simulation_hours=1` 且 `minutes_per_round=60` → 恰好 1 轮。
    * `agents_per_hour_min == max == 2` → `random.uniform(2, 2)` 恒为 2。
    * `peak_hours` / `off_peak_hours` 都空 → 倍率恒为 1.0。
    * 两个 agent 的 `activity_level=1.0` → `random.random() < 1.0` 恒真。
    * `active_hours` 含 0 —— 第 0 轮的 `simulated_hour` 就是 0。
    * `initial_posts` 空 → 平台库里每一条帖子都出自替身，没有手工注入的干扰。
    """
    return {
        "simulation_id": "e2e_stub",
        "time_config": {
            "total_simulation_hours": 1,
            "minutes_per_round": 60,
            "agents_per_hour_min": len(PROFILES),
            "agents_per_hour_max": len(PROFILES),
            "peak_hours": [],
            "off_peak_hours": [],
            "peak_activity_multiplier": 1.0,
            "off_peak_activity_multiplier": 1.0,
        },
        "agent_configs": [
            {"agent_id": i, "entity_name": p["username"],
             "active_hours": [0], "activity_level": 1.0}
            for i, p in enumerate(PROFILES)
        ],
        "event_config": {"initial_posts": []},
    }


def _write_profiles(path: pathlib.Path) -> None:
    """写花名册。**必须 `ensure_ascii=True`。**

    上游 `oasis/social_agent/agents_generator.py:574` 是
    `open(profile_path, "r")` —— **不指定编码**。中文 Windows 上默认 GBK，
    于是一份 UTF-8 的中文花名册当场 `UnicodeDecodeError`。
    `ensure_ascii=True` 把中文转成 `\\uXXXX` 转义，整份文件退化成纯 ASCII，
    GBK 也解得开。**这是绕法，不是修法** —— 上游那个缺陷照实记在产物里。

    值里故意留着中文：绕法正是要有中文才验得到，全 ASCII 的花名册绕过了缺陷、
    也就绕过了这条证据。
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(list(PROFILES), f, ensure_ascii=True, indent=2)


def _write_config(path: pathlib.Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_config(), f, ensure_ascii=False, indent=2)


def _child_env(tmp: pathlib.Path, arm_knobs: dict,
               counters_path: pathlib.Path) -> dict:
    """子进程的环境。**把「跑真模型」这条路彻底堵死**，不只靠一个名字。

    `LLM_MODEL_NAME=stub` 是替身唯一的触发词（见 `attach.py`）。但上游
    `create_model(config, use_boost=True)` 会**先看加速配置**：只要
    `LLM_BOOST_API_KEY` 非空，它就走 `LLM_BOOST_MODEL_NAME` 那条路 ——
    而那个名字不是 `stub`，于是真模被造出来、真请求发出去。仓库根目录的 `.env`
    若配了加速 key，`load_dotenv` 就会把它塞进来。所以这里把三个加速变量**显式
    清空**，而不是指望 `.env` 里没有。
    """
    return {
        **os.environ,
        "LLM_MODEL_NAME": "stub",
        "LLM_API_KEY": PLACEHOLDER_KEY,
        # `LLM_BASE_URL` 也清掉：上游会把它打出来（`create_model` 那句
        # `base_url={...}`），而这份转录是要入库的 —— 一个私有的接口地址
        # 不该因为 `.env` 里配过就跟着进公开仓库。
        "LLM_BASE_URL": "",
        "LLM_BOOST_API_KEY": "",
        "LLM_BOOST_BASE_URL": "",
        "LLM_BOOST_MODEL_NAME": "",
        "E2E_STUB_SEED": SEED,
        "GUARD_COUNTERS_OUT": str(counters_path),
        # 管道读写不该受控制台代码页影响（`run_all._run_one` 同一条纪律）。
        "PYTHONIOENCODING": "utf-8",
        **arm_knobs,
    }


def _run_arm(stable: str, knobs: dict, root: pathlib.Path,
             timeout: int) -> dict:
    """跑一档臂，返回 `(子进程退出码, 正文, 计数, 库里的帖子数)`。

    每档臂一个**自己的目录**：`run_parallel_simulation.py:1538` 把
    `simulation_dir` 定成配置文件的所在目录，平台库、日志、IPC 目录全落在那里。
    合用一个目录的话，三档臂的库会互相覆盖。
    """
    tmp = root / stable
    tmp.mkdir(parents=True, exist_ok=True)
    _write_config(tmp / "simulation_config.json")
    _write_profiles(tmp / "reddit_profiles.json")
    counters_path = tmp / "guard_counters.json"
    db_path = tmp / "reddit_simulation.db"

    cmd = [sys.executable, str(SCRIPT),
           "--config", str(tmp / "simulation_config.json"),
           "--reddit-only", "--max-rounds", "1", "--no-wait",
           "--guards", "both"]
    t0 = time.time()
    timed_out = False
    try:
        proc = subprocess.run(cmd, cwd=str(tmp), capture_output=True,
                              env=_child_env(tmp, knobs, counters_path),
                              timeout=timeout)
        rc = proc.returncode
        raw = proc.stdout + b"\n" + proc.stderr
    except subprocess.TimeoutExpired as exc:
        # 超时**不是**「没达到预期」，是「没测到」—— 上层据此报 2。
        timed_out = True
        rc = None
        raw = (exc.stdout or b"") + b"\n" + (exc.stderr or b"")
    body = raw.decode("utf-8", errors="replace")
    seconds = round(time.time() - t0, 1)

    return {"arm": stable, "tmp": tmp, "rc": rc, "timeout": timed_out,
            "body": body, "seconds": seconds,
            "counters": _read_counters(counters_path),
            "db_posts": _count_posts(db_path),
            "counters_path": counters_path, "db_path": db_path}


def _read_counters(path: pathlib.Path):
    """取计数。**取不到返回 `None` —— 不返回一个全是 0 的默认值。**

    全 0 和「没测到」是两回事：前者是「守卫装了但一次都没走到」，后者是
    「计数根本没落下来」。把后者填成前者，等于把一次取证失败说成一个读数。
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _count_posts(db_path: pathlib.Path):
    """平台库里 post 表的行数。**读不到返回 `None`**（同 `_read_counters`）。"""
    if not db_path.is_file():
        return None
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        return con.execute("select count(*) from post").fetchone()[0]
    except sqlite3.Error:
        return None
    finally:
        con.close()


def _redact(text: str, root: pathlib.Path) -> str:
    """把**这台机器**的痕迹从转录里抹掉，并把换行归一。

    **这不是装饰，是必须的。** 上游脚本会把路径原样打出来：运行目录
    （`mkdtemp` 的随机后缀）、仓库位置、主目录。这份转录要入库、仓库要公开，
    而 `C:\\Users\\<某人的名字>\\AppData\\Local\\Temp\\...` 既泄露了构建者的
    本机路径，又让产物每次跑出来的字节都不一样（D-21 踩过两次的那个坑）。

    抹掉的是**四个具名的替换**，逐条列在下面 —— 有名单就能核，不是「大概洗一下」：

    * 本次的运行目录 → `<运行目录>`
    * 本仓库的 `backend/` → `<backend>`
    * 系统临时根 → `<临时根>`
    * 主目录 → `<主目录>`
    * 行首的 `[HH:MM:SS] ` 日志时间戳 → 去掉（那是**挂钟**，每次跑都不一样）

    **抹不掉、也不装抹掉的**：耗时那类秒数（`0.6秒`）和报告自己的
    `generated_at` —— 它们本来就每次不同，这里照实留着，由「判过期只看脚本
    sha、不看文件字节」那条纪律兜着（见 `tests/test_adjudicate.py`）。
    `transcript_redacted: true` 连同这段替换名单一起写进产物：**一份抹过的
    转录不许被当成逐字转录读。**
    """
    import re as _re

    for needle, tag in ((str(root), "<运行目录>"),
                        (str(BACKEND), "<backend>"),
                        (tempfile.gettempdir(), "<临时根>"),
                        (os.path.expanduser("~"), "<主目录>")):
        if needle:
            text = text.replace(needle, tag)
            text = text.replace(needle.replace("\\", "/"), tag)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return _re.sub(r"(?m)^\[\d{2}:\d{2}:\d{2}\] ?", "", text)


#: 抹过的替换名单。写进产物，供人逐条核。
REDACTION_LIST = ("运行目录 → `<运行目录>`", "backend/ → `<backend>`",
                  "系统临时根 → `<临时根>`", "主目录 → `<主目录>`",
                  "行首 [HH:MM:SS] 日志时间戳 → 去掉")


def _payload(runs: list) -> dict:
    """把三档臂的读数拼成 `_probe.emit_readings` 那一种块。

    **缺的格子不补数**：那档臂没取到的量，既不出现在 `readings` 里，也在
    `boundaries` 里记一条 `未测量` 加原因。于是裁决器把依赖它的判据判成
    「不可判定」，而不是拿一个 0 去判。
    """
    readings, boundaries = {}, []
    for run in runs:
        stable = run["arm"]
        vals, c = {}, run["counters"]
        if c:
            for m in ("written_whole", "still_sliced", "timestamp_pushed"):
                if m in c:
                    vals[m] = c[m]
        else:
            for m in ("written_whole", "still_sliced", "timestamp_pushed"):
                boundaries.append(P._boundary((
                    stable, m, P.BOUND_UNMEASURED,
                    "计数文件没落下来（`$GUARD_COUNTERS_OUT` 是空的）—— "
                    "这档臂跑没跑到守卫，无从谈起。")))
        if run["db_posts"] is not None:
            vals["db_posts"] = run["db_posts"]
        else:
            boundaries.append(P._boundary((
                stable, "db_posts", P.BOUND_UNMEASURED,
                "平台库读不到 —— 没有这一格就判不了「动作有没有真落进平台」。")))
        if vals:
            readings[stable] = vals

    # **一条贴界声明**，是读源码 + 实测得出来的、不是凑的：`timestamp_pushed`
    # 只在**快路径**里加（`camel_guards._next_timestamp`），走回落支的那种消息
    # **按构造**一次都计不到。所以「回落支那档的 `timestamp_pushed`」这一格
    # 机制上恒为 0 —— 它分不出「那档有没有发生碰撞」，不该被那样读。
    big = readings.get("bigtext_e2e", {})
    if "still_sliced" in big and "timestamp_pushed" in big:
        boundaries.append(P._boundary((
            "bigtext_e2e", "timestamp_pushed", P.BOUND_RAILED,
            "这一格**按构造**恒为 0：`timestamp_pushed` 只在快路径写入那支累加，"
            "而这档臂走的正是回落支。它分不出「有没有碰撞」。",
        )))

    arms = {stable: label for stable, label, _ in ARMS}
    return {
        "repro": "端到端（替身模型 · 真入口脚本 · Reddit）",
        "arms": arms,
        "readings": readings,
        "units": dict(UNITS),
        "boundaries": boundaries,
        "note": ("模型是**替身**（`stub_model.ToolStubModel`），其余全真：真 "
                 "SocialAgent、真 AgentGraph、真 OASIS env.step()、真记忆写入路径、"
                 "真平台 SQLite。三档臂**全部** `--guards both` —— 没有「守卫关」"
                 "这条臂，因为不装守卫时 `counters()` 恒为全 0，读不出东西。"
                 "本命令主张的是「守卫的两个分支都被真实流量走到了」，"
                 "**不主张「守卫修好了什么」**（那是三条离线复现的活），"
                 "也不主张仿真质量。"
                 "发过 LLM 请求：0 次（`LLM_API_KEY` 只是个过非空检查的占位串）。"),
    }


def _block_body(payload: dict) -> str:
    """把块序列化成**带锚定分隔符的正文**，和 `emit_readings` 逐字同形。

    `readings_sha256` 算的是「这一块在这段正文里的哈希」，所以这里必须走一遍
    真的序列化，而不是另算一个哈希 —— 否则那个 sha 和它声称的东西对不上。
    """
    return "\n".join([
        P._READINGS_BEGIN,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        P._READINGS_END,
    ])


def _report(runs: list, digest_note: str, root: pathlib.Path) -> dict:
    """落一份和 `run_all` 报告同形的机读件 —— 于是 `cells_from` 原样能读。"""
    payload = _payload(runs)
    body = _block_body(payload)
    ok = all(r["rc"] == 0 and not r["timeout"] for r in runs)
    missing = [r["arm"] for r in runs
               if not r["counters"] or r["db_posts"] is None]
    verdicts = {True: "达到预期", False: "没测到"}
    transcript = "\n\n".join(
        f"===== 臂 {r['arm']}（{r['seconds']} 秒"
        f"{'，超时' if r['timeout'] else ''}，退出码 {r['rc']}）=====\n"
        + _redact(r["body"], root)
        for r in runs) + "\n\n===== 读数 =====\n" + body

    entry = {"n": 1, "module": "verification.e2e_stub",
             "what": "端到端：替身模型驱真入口脚本跑一整局，取守卫的计数",
             "nature": "端到端·模型是替身",
             "returncode": 0 if ok else 2,
             "verdict": verdicts[bool(ok)],
             "arms": [r["arm"] for r in runs],
             "arm_seconds": {r["arm"]: r["seconds"] for r in runs},
             "readings": payload,
             "readings_missing": False,
             "readings_sha256": P.readings_sha256(body),
             "transcript_redacted": True,
             "transcript_note": (
                 "这段转录**抹过**，不是逐字：见 `redaction_applied`。"
                 "抹的是这台机器的痕迹（运行目录、仓库位置、主目录）与行首的"
                 "挂钟时间戳。**读数和它是两条路**：读数取自 `counters()` 落下的"
                 "JSON 与平台库的计数，不从这段文本里抠。"),
             "redaction_applied": list(REDACTION_LIST),
             "transcript": transcript}

    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "not_a_pass_rate": True,
        "what_this_is": (
            "一份**端到端**的读数：替身模型（不发网）顶掉模型的决策，驱动上游那个"
            "原样的 `scripts/run_parallel_simulation.py` 跑一整局，把运行时守卫的"
            "计数与平台库的行数取回来。"),
        "what_this_is_NOT": (
            "不是通过率，没有分母。三档臂都装同一套守卫，彼此之间的差别只是两个"
            "受控旋钮 —— 它判的是「守卫的分支有没有被走到」，不是「守卫好不好」。"),
        "what_it_does_NOT_prove": (
            "**它不证明「守卫修好了什么」** —— 那是三条离线复现的活：那三条量的是"
            "「装上前后差多少」，本命令量的是「装上了、并且被真实流量走到了」。"
            "它也**不证明仿真质量**：模型是替身，关于「真 LLM 下行为如何」一个字"
            "都不主张。另有一条照实说：`db_posts` 数的是**平台库里的行数**，"
            "不是「动作有多合理」。"),
        "environment": _environment(),
        "results": [entry],
        "arms_missing": missing,
        "digest_note": digest_note,
        "summary": {"arms_total": len(runs), "arms_missing": len(missing),
                    "worst_returncode": 0 if ok else 2},
    }


def _environment() -> dict:
    """这批读数是用什么跑的。取不到的如实写「未知」，不猜。

    `cwd` 记**相对**路径，和 `adjudicate` / `selfproof` / `mutations` /
    `reconcile_selfcheck` 四份产物的惯例一致 —— 因为**这份产物是要入库的**，
    绝对路径会把造它那台机器的目录布局钉进公开仓库（`run_all` 的产物记绝对
    路径，但它被 gitignore 挡着，那条不冲突）。
    """
    env = {"python": sys.version.split()[0], "cwd": "backend/",
           "entry": "scripts/run_parallel_simulation.py",
           "platform_type": "REDDIT", "guards": "both", "seed": SEED}
    for key, mod in (("camel_ai", "camel"), ("camel_oasis", "oasis")):
        try:
            env[key] = getattr(__import__(mod), "__version__", "未知")
        except Exception:  # noqa: BLE001
            env[key] = "未知"
    try:
        env["script_sha256"] = hashlib.sha256(
            SCRIPT.read_bytes()).hexdigest()
    except OSError:
        env["script_sha256"] = None
    return env


def _markdown(report: dict) -> str:
    """人读的那一份。**不解析数字** —— 数字在读数块里，抄得走。"""
    e = report["results"][0]
    md = ["# 端到端读数：替身模型 · 真入口脚本", "",
          f"生成时间：{report['generated_at']}", "",
          "> 这一份**不是通过率**，没有分母。三档臂装的是同一套守卫，",
          "> 差别只在两个受控旋钮上。它回答的是「守卫的分支有没有被真实流量走到」。", "",
          "## 这三档臂是什么", "",
          "| 臂 | 旋钮 | 想走到守卫的哪一支 | 耗时 |",
          "|---|---|---|---|"]
    for stable, label, knobs in ARMS:
        md.append(f"| `{stable}` | {label} | "
                  f"`{json.dumps(knobs, ensure_ascii=False)}` | "
                  f"{e['arm_seconds'].get(stable, '—')} 秒 |")
    md += ["", "全部 `--guards both`。**没有「守卫关」这条臂** —— 不装守卫时",
           "`counters()` 恒为全 0，读不出东西。守卫「装上前后差多少」那件事由三条",
           "离线复现回答，不是这里。", "",
           "## 读数", "", "```json",
           json.dumps(e["readings"], ensure_ascii=False, indent=2,
                      sort_keys=True),
           "```", "",
           f"- 读数块在正文里的 `sha256`：`{e['readings_sha256']}`", "",
           "## 边界（照实说）", "",
           "1. **模型是替身，其余全真。** 真 `SocialAgent`、真 `AgentGraph`、真",
           "   `OASIS env.step()`、真记忆写入路径、真平台 SQLite。",
           "2. **不证明「守卫修好了什么」** —— 那是三条离线复现的活。",
           "3. **不证明仿真质量**，也不证明真 LLM 下的行为。",
           "4. `LLM_API_KEY` 只是个**过一句非空检查**的占位串"
           "（`run_parallel_simulation.py:1026`），",
           "   替身不发一个字节的网。上游把「有 key」当成「能跑」的代理，是个小疵。",
           "5. 花名册必须 `ensure_ascii` 写：上游 `agents_generator.py:574` 的",
           "   `open(profile_path, \"r\")` 不带编码，中文 Windows 上下默认 GBK，",
           "   读 UTF-8 的中文花名册当场 `UnicodeDecodeError`。**任何中文 Windows",
           "   用户走 Reddit 路径都会撞上。** 这是绕法，不是修法。", "",
           "## 环境", "", "| 项 | 值 |", "|---|---|"]
    for k, v in report["environment"].items():
        md.append(f"| `{k}` | {v if v is not None else '未知'} |")
    md += ["", "## 转录（**抹过，不是逐字**）", "",
           "> 被抹掉的只有这台机器的痕迹和行首的挂钟时间戳，逐条如下：", ""]
    for item in e["redaction_applied"]:
        md.append(f"> - {item}")
    md += ["", "> **读数和它是两条路**：读数取自 `counters()` 落下的 JSON 与平台库的",
           "> 计数，不从这段文本里抠 —— 所以抹痕不影响上面任何一个数。", "",
           "```text", e["transcript"], "```", ""]
    return "\n".join(md) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="端到端：替身模型驱真入口脚本跑一整局，取守卫的计数")
    ap.add_argument("--keep", action="store_true",
                    help="保留临时目录（默认跑完就删）")
    ap.add_argument("--arm", default=None,
                    help="只跑这一档臂（调试用；正常别加）")
    ap.add_argument("--timeout", type=int, default=600,
                    help="每档臂的超时秒数（默认 600）")
    ap.add_argument("--out", default=str(REPORT),
                    help="报告落点（默认 verification/e2e_report.json）")
    args = ap.parse_args()

    arms = [a for a in ARMS if args.arm in (None, a[0])]
    if not arms:
        print(f"没有这一档臂：{args.arm!r}；可选 {[a[0] for a in ARMS]}")
        return 2

    print("=" * 66)
    print("端到端：替身模型驱真入口脚本跑一整局")
    print("=" * 66)
    print("模型是替身（不发一个字节的网、不要 key），其余全真：")
    print("真 SocialAgent / 真 AgentGraph / 真 OASIS env.step() / 真平台 SQLite。")
    print("这条命令**不主张「守卫修好了什么」**——那是三条离线复现的活。")
    print()

    root = pathlib.Path(tempfile.mkdtemp(prefix="mirofish_e2e_"))
    print(f"临时目录：{root}")
    print()
    runs = []
    try:
        for stable, label, knobs in arms:
            print("-" * 66)
            print(f"· {stable}：{label}")
            print("-" * 66)
            run = _run_arm(stable, knobs, root, args.timeout)
            runs.append(run)
            if run["timeout"]:
                print(f"  ○ 没测到：{args.timeout} 秒没跑完，已中断")
            elif run["rc"] != 0:
                print(f"  × 子进程退出码 {run['rc']} —— 它的输出在转录里")
            else:
                print(f"  √ 跑完（{run['seconds']} 秒）")
            c = run["counters"]
            if c is None:
                print("  ○ 计数没落下来（`$GUARD_COUNTERS_OUT` 是空的）"
                      "—— 报「没测到」，不编数")
            else:
                print("  计数：" + "、".join(
                    f"{k}={c[k]}" for k in ("written_whole", "still_sliced",
                                            "timestamp_pushed") if k in c))
            print(f"  平台库帖子数："
                  + ("读不到" if run["db_posts"] is None
                     else str(run["db_posts"])))
            print()

        report = _report(runs, "", root)
        out = pathlib.Path(args.out)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8", newline="\n")
        md_path = out.with_suffix(".md")
        md_text = _markdown(report)
        md_path.write_text(md_text, encoding="utf-8", newline="\n")

        # 读数块里的字符必须 GBK 编得出：中文 Windows 的 cmd 下编不出的会被
        # `__init__._harden_streams()` 降级成 `?`，那是**无声的数据损坏**。
        unsafe = P.non_gbk_chars(_block_body(_payload(runs)))
        if unsafe:
            print(f"  ⚠ 读数块里有 GBK 编不出的字符：{unsafe!r}")
            print("    中文 Windows 的 cmd 下它们会变成 `?` —— 本目录的记号"
                  "只用 GBK 编得出的字，正是为了这件事。")

        print("=" * 66)
        print("汇总")
        print("=" * 66)
        for r in runs:
            got = r["counters"] and r["db_posts"] is not None
            print(f"  {'√ 达到预期' if got and r['rc'] == 0 else '○ 没测到':<12}"
                  f"{r['arm']}")
        print()
        print("  这不是通过率，也没有分母：三档臂装的是**同一套守卫**，")
        print("  差别只在两个受控旋钮上。它回答的是「守卫的分支有没有被走到」。")
        print("  守卫「装上前后差多少」由三条离线复现回答，不是这里。")
        print()
        print(f"  报告已落盘：{out.resolve()}")
        print(f"              {md_path.resolve()}")
        rc = 0
        for r in runs:
            if r["timeout"] or r["rc"] != 0:
                rc = max(rc, 1)
            elif r["counters"] is None or r["db_posts"] is None:
                rc = max(rc, 2)
        return rc
    finally:
        if args.keep:
            print(f"\n  临时目录保留：{root}")
        else:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
