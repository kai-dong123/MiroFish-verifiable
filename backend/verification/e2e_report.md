# 端到端读数：替身模型 · 真入口脚本

生成时间：2026-09-20T23:13:02

> 这一份**不是通过率**，没有分母。三档臂装的是同一套守卫，
> 差别只在两个受控旋钮上。它回答的是「守卫的分支有没有被真实流量走到」。

## 这三档臂是什么

| 臂 | 旋钮 | 想走到守卫的哪一支 | 耗时 |
|---|---|---|---|
| `roomy_e2e` | 基线：一次响应一个动作、消息放得下 | `{"E2E_STUB_N_CALLS": "1", "E2E_STUB_CONTENT_LEN": "40", "E2E_STUB_TEXT_LEN": "0"}` | 10.7 秒 |
| `bigtext_e2e` | 助手消息文本 20000 字：逼出「自己就超上限」的回落支 | `{"E2E_STUB_N_CALLS": "1", "E2E_STUB_CONTENT_LEN": "40", "E2E_STUB_TEXT_LEN": "20000"}` | 15.8 秒 |
| `two_e2e` | 一次响应两个动作：逼出同拍写入 | `{"E2E_STUB_N_CALLS": "2", "E2E_STUB_CONTENT_LEN": "40", "E2E_STUB_TEXT_LEN": "0"}` | 11.9 秒 |

全部 `--guards both`。**没有「守卫关」这条臂** —— 不装守卫时
`counters()` 恒为全 0，读不出东西。守卫「装上前后差多少」那件事由三条
离线复现回答，不是这里。

## 读数

```json
{
  "arms": {
    "bigtext_e2e": "助手消息文本 20000 字：逼出「自己就超上限」的回落支",
    "roomy_e2e": "基线：一次响应一个动作、消息放得下",
    "two_e2e": "一次响应两个动作：逼出同拍写入"
  },
  "boundaries": [
    {
      "arm": "bigtext_e2e",
      "kind": "贴界",
      "metric": "timestamp_pushed",
      "why": "这一格**按构造**恒为 0：`timestamp_pushed` 只在快路径写入那支累加，而这档臂走的正是回落支。它分不出「有没有碰撞」。"
    }
  ],
  "note": "模型是**替身**（`stub_model.ToolStubModel`），其余全真：真 SocialAgent、真 AgentGraph、真 OASIS env.step()、真记忆写入路径、真平台 SQLite。三档臂**全部** `--guards both` —— 没有「守卫关」这条臂，因为不装守卫时 `counters()` 恒为全 0，读不出东西。本命令主张的是「守卫的两个分支都被真实流量走到了」，**不主张「守卫修好了什么」**（那是三条离线复现的活），也不主张仿真质量。发过 LLM 请求：0 次（`LLM_API_KEY` 只是个过非空检查的占位串）。",
  "readings": {
    "bigtext_e2e": {
      "db_posts": 2,
      "still_sliced": 2,
      "timestamp_pushed": 0,
      "written_whole": 6
    },
    "roomy_e2e": {
      "db_posts": 2,
      "still_sliced": 0,
      "timestamp_pushed": 2,
      "written_whole": 8
    },
    "two_e2e": {
      "db_posts": 4,
      "still_sliced": 0,
      "timestamp_pushed": 2,
      "written_whole": 12
    }
  },
  "repro": "端到端（替身模型 · 真入口脚本 · Reddit）",
  "units": {
    "db_posts": "条（平台 SQLite 里 post 表的行数）",
    "still_sliced": "条（自己就超上限、交回原方法切的记录）",
    "timestamp_pushed": "次（我们取读数却被推后的写入）",
    "written_whole": "条（走快路径写入的记录）"
  }
}
```

- 读数块在正文里的 `sha256`：`a20e25bac0920f2dbf6d9fba6ab4135281119073fd4e38761bca68c69863fc08`

## 边界（照实说）

1. **模型是替身，其余全真。** 真 `SocialAgent`、真 `AgentGraph`、真
   `OASIS env.step()`、真记忆写入路径、真平台 SQLite。
2. **不证明「守卫修好了什么」** —— 那是三条离线复现的活。
3. **不证明仿真质量**，也不证明真 LLM 下的行为。
4. `LLM_API_KEY` 只是个**过一句非空检查**的占位串（`run_parallel_simulation.py:1026`），
   替身不发一个字节的网。上游把「有 key」当成「能跑」的代理，是个小疵。
5. 花名册必须 `ensure_ascii` 写：上游 `agents_generator.py:574` 的
   `open(profile_path, "r")` 不带编码，中文 Windows 上下默认 GBK，
   读 UTF-8 的中文花名册当场 `UnicodeDecodeError`。**任何中文 Windows
   用户走 Reddit 路径都会撞上。** 这是绕法，不是修法。

## 环境

| 项 | 值 |
|---|---|
| `python` | 3.11.9 |
| `cwd` | backend/ |
| `entry` | scripts/run_parallel_simulation.py |
| `platform_type` | REDDIT |
| `guards` | both |
| `seed` | 20260917 |
| `camel_ai` | 0.2.78 |
| `camel_oasis` | 0.2.5 |
| `script_sha256` | caaee04c0d0089e60d51d42ffd27f192879d16d442ca0e6f4b19dbe85b82d35f |

## 转录（**抹过，不是逐字**）

> 被抹掉的只有这台机器的痕迹和行首的挂钟时间戳，逐条如下：

> - 运行目录 → `<运行目录>`
> - backend/ → `<backend>`
> - 系统临时根 → `<临时根>`
> - 主目录 → `<主目录>`
> - 行首 [HH:MM:SS] 日志时间戳 → 去掉

> **读数和它是两条路**：读数取自 `counters()` 落下的 JSON 与平台库的
> 计数，不从这段文本里抠 —— 所以抹痕不影响上面任何一个数。

```text
===== 臂 roomy_e2e（10.7 秒，退出码 0）=====
[Reddit] 初始化...
[通用LLM] model=stub, base_url=默认...
{'user_profile': '自由撰稿人', 'mbti': 'INTJ', 'gender': 'female', 'age': 20, 'country': 'China'}
{'user_profile': '产品经理', 'mbti': 'ENFP', 'gender': 'male', 'age': 35, 'country': 'China'}
db_path <运行目录>\roomy_e2e\reddit_simulation.db
[Reddit] 环境已启动
[Reddit] 模拟循环完成! 耗时: 0.6秒, 总动作: 2
模拟进程已退出

替身模型已接管: model_type='stub', random.seed(20260917)
运行时守卫已装: both
============================================================
OASIS 双平台并行模拟
配置文件: <运行目录>\roomy_e2e\simulation_config.json
模拟ID: e2e_stub
等待命令模式: 禁用
============================================================
模拟参数:
  - 总模拟时长: 1小时
  - 每轮时间: 60分钟
  - 配置总轮数: 1
  - 最大轮数限制: 1
  - Agent数量: 2
日志结构:
  - 主日志: simulation.log
  - Twitter动作: twitter/actions.jsonl
  - Reddit动作: reddit/actions.jsonl
============================================================
[Reddit] 初始化...
[Reddit] 环境已启动
[Reddit] 模拟循环完成! 耗时: 0.6秒, 总动作: 2
============================================================
模拟循环完成! 总耗时: 1.6秒
[Reddit] 环境已关闭
============================================================
全部完成!
日志文件:
  - <运行目录>\roomy_e2e\simulation.log
  - <运行目录>\roomy_e2e\twitter\actions.jsonl
  - <运行目录>\roomy_e2e\reddit\actions.jsonl
============================================================


===== 臂 bigtext_e2e（15.8 秒，退出码 0）=====
[Reddit] 初始化...
[通用LLM] model=stub, base_url=默认...
{'user_profile': '自由撰稿人', 'mbti': 'INTJ', 'gender': 'female', 'age': 20, 'country': 'China'}
{'user_profile': '产品经理', 'mbti': 'ENFP', 'gender': 'male', 'age': 35, 'country': 'China'}
db_path <运行目录>\bigtext_e2e\reddit_simulation.db
[Reddit] 环境已启动
2026-09-20 23:12:45,964 - camel.camel.agents.chat_agent - WARNING - Message with 5007 tokens exceeds remaining budget of 3722. Slicing into smaller chunks.
2026-09-20 23:12:47,914 - camel.camel.agents.chat_agent - WARNING - Message with 5007 tokens exceeds remaining budget of 3718. Slicing into smaller chunks.
[Reddit] 模拟循环完成! 耗时: 4.5秒, 总动作: 2
模拟进程已退出

替身模型已接管: model_type='stub', random.seed(20260917)
运行时守卫已装: both
============================================================
OASIS 双平台并行模拟
配置文件: <运行目录>\bigtext_e2e\simulation_config.json
模拟ID: e2e_stub
等待命令模式: 禁用
============================================================
模拟参数:
  - 总模拟时长: 1小时
  - 每轮时间: 60分钟
  - 配置总轮数: 1
  - 最大轮数限制: 1
  - Agent数量: 2
日志结构:
  - 主日志: simulation.log
  - Twitter动作: twitter/actions.jsonl
  - Reddit动作: reddit/actions.jsonl
============================================================
[Reddit] 初始化...
[Reddit] 环境已启动
[Reddit] 模拟循环完成! 耗时: 4.5秒, 总动作: 2
============================================================
模拟循环完成! 总耗时: 5.4秒
[Reddit] 环境已关闭
============================================================
全部完成!
日志文件:
  - <运行目录>\bigtext_e2e\simulation.log
  - <运行目录>\bigtext_e2e\twitter\actions.jsonl
  - <运行目录>\bigtext_e2e\reddit\actions.jsonl
============================================================


===== 臂 two_e2e（11.9 秒，退出码 0）=====
[Reddit] 初始化...
[通用LLM] model=stub, base_url=默认...
{'user_profile': '自由撰稿人', 'mbti': 'INTJ', 'gender': 'female', 'age': 20, 'country': 'China'}
{'user_profile': '产品经理', 'mbti': 'ENFP', 'gender': 'male', 'age': 35, 'country': 'China'}
db_path <运行目录>\two_e2e\reddit_simulation.db
[Reddit] 环境已启动
[Reddit] 模拟循环完成! 耗时: 0.6秒, 总动作: 4
模拟进程已退出

替身模型已接管: model_type='stub', random.seed(20260917)
运行时守卫已装: both
============================================================
OASIS 双平台并行模拟
配置文件: <运行目录>\two_e2e\simulation_config.json
模拟ID: e2e_stub
等待命令模式: 禁用
============================================================
模拟参数:
  - 总模拟时长: 1小时
  - 每轮时间: 60分钟
  - 配置总轮数: 1
  - 最大轮数限制: 1
  - Agent数量: 2
日志结构:
  - 主日志: simulation.log
  - Twitter动作: twitter/actions.jsonl
  - Reddit动作: reddit/actions.jsonl
============================================================
[Reddit] 初始化...
[Reddit] 环境已启动
[Reddit] 模拟循环完成! 耗时: 0.6秒, 总动作: 4
============================================================
模拟循环完成! 总耗时: 1.6秒
[Reddit] 环境已关闭
============================================================
全部完成!
日志文件:
  - <运行目录>\two_e2e\simulation.log
  - <运行目录>\two_e2e\twitter\actions.jsonl
  - <运行目录>\two_e2e\reddit\actions.jsonl
============================================================


===== 读数 =====
--- 读数 BEGIN（机器可读；由本复现自己打出，人读上面那几张表）---
{
  "arms": {
    "bigtext_e2e": "助手消息文本 20000 字：逼出「自己就超上限」的回落支",
    "roomy_e2e": "基线：一次响应一个动作、消息放得下",
    "two_e2e": "一次响应两个动作：逼出同拍写入"
  },
  "boundaries": [
    {
      "arm": "bigtext_e2e",
      "kind": "贴界",
      "metric": "timestamp_pushed",
      "why": "这一格**按构造**恒为 0：`timestamp_pushed` 只在快路径写入那支累加，而这档臂走的正是回落支。它分不出「有没有碰撞」。"
    }
  ],
  "note": "模型是**替身**（`stub_model.ToolStubModel`），其余全真：真 SocialAgent、真 AgentGraph、真 OASIS env.step()、真记忆写入路径、真平台 SQLite。三档臂**全部** `--guards both` —— 没有「守卫关」这条臂，因为不装守卫时 `counters()` 恒为全 0，读不出东西。本命令主张的是「守卫的两个分支都被真实流量走到了」，**不主张「守卫修好了什么」**（那是三条离线复现的活），也不主张仿真质量。发过 LLM 请求：0 次（`LLM_API_KEY` 只是个过非空检查的占位串）。",
  "readings": {
    "bigtext_e2e": {
      "db_posts": 2,
      "still_sliced": 2,
      "timestamp_pushed": 0,
      "written_whole": 6
    },
    "roomy_e2e": {
      "db_posts": 2,
      "still_sliced": 0,
      "timestamp_pushed": 2,
      "written_whole": 8
    },
    "two_e2e": {
      "db_posts": 4,
      "still_sliced": 0,
      "timestamp_pushed": 2,
      "written_whole": 12
    }
  },
  "repro": "端到端（替身模型 · 真入口脚本 · Reddit）",
  "units": {
    "db_posts": "条（平台 SQLite 里 post 表的行数）",
    "still_sliced": "条（自己就超上限、交回原方法切的记录）",
    "timestamp_pushed": "次（我们取读数却被推后的写入）",
    "written_whole": "条（走快路径写入的记录）"
  }
}
--- 读数 END ---
```

