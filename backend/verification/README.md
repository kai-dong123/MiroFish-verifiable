# verification —— 让仿真输出变得**可判定**的装置

这个目录不属于上游 MiroFish。它是这个 fork 加的东西，回答的是一个上游没回答的问题：

> MiroFish 能演出一份**很像结论**的报告，**但没有任何机制告诉你它可不可信**。

这里放的**不是**「一套让仿真更准的方法」，也不是「一套测试」。它是一组
**运行时守卫**加一组**离线复现**：守卫能在你不该相信的时候让你别信（说不出来
就明说说不出来），复现能让你亲手把每一个结论跑出来看。

---

## 装与跑

```bash
cd backend
pip install -r requirements.txt      # 装置依赖的 camel / oasis 也在里面
python -m verification.run_all
```

**不要 API key、不要 Zep、不联网、不花钱。** 几十秒跑完。

预期看到：三条复现各自打印它量到的数，结尾一张汇总，退出码 `0`。
退出码有三种，见下。

### 只想跑一条

```bash
python -m verification.repro_01_slicing        # 切片正反馈环
python -m verification.repro_02_timestamp      # 同拍碰撞
python -m verification.repro_03_concurrency    # 并发次序（边界，不修）
```

### 把守卫接进真跑

守卫**默认不装** —— 不装时行为与上游逐字一致，这是刻意的（没有「不装」那一版，
就无从对比）。三个真跑入口都有 `--guards`：

```bash
python scripts/run_parallel_simulation.py --config your_config.json --guards off
python scripts/run_parallel_simulation.py --config your_config.json --guards slicing
python scripts/run_parallel_simulation.py --config your_config.json --guards timestamp
python scripts/run_parallel_simulation.py --config your_config.json --guards both
```

**两个守卫可以分开开，这是这个目录存在的主要理由。** 第二个失效是第一个的代价
（见下），焊在一起就分不清是谁动了什么。

---

## 退出码：**三种，不是两种**

| 码 | 含义 |
|---|---|
| `0` | 三条都达到预期 |
| `1` | 有任意一条**没达到预期** —— 这是真的要看的东西 |
| `2` | 有任意一条**没测到**（缺依赖、源码对不上……） |

`2` 和 `1` 分开是刻意的：**「没测到」不等于「通过」，也不等于「失败」。**
一个装置如果把「没跑起来」报成绿色，它后面所有的绿色都不值钱了。

---

## 三条各自在说什么

### ① 切片正反馈环 —— `repro_01_slicing.py`

`camel/agents/chat_agent.py` 的 `update_memory`（884 / 933 / 948 行）：

```
remaining_budget = max(0, token_limit - ctx_tokens)     # ctx_tokens 是**截断后**的
base_chunk_size  = max(1, remaining_budget) // 10
chunk_body_limit = max(1, base_chunk_size - 12)         # 12 是给块前缀留的扣减
```

截断干的事就是把上下文填到贴着上限，所以 `remaining_budget` **按构造就远小于
待写的消息**；它还要再被 `//10` 和 `-12` 砍两刀。于是**一条完全放得下的消息
被切成一块一个 token**，每块还各带一个十几 token 的前缀。

实测（上限 4000）：一条 **277 token** 的消息 → **270 条记录、实增 5130 token
（18.5 倍）**，原文被撕得找不回连续的「记录开始」。而这是个正反馈环：
记忆满 → 残余预算小 → 切片 → 膨胀 → 记忆更满。

装上守卫后：**1 条记录、实增 277 token、原文完整**。

判据是机检的，不看叙述：**这条消息自己 ≤ 上限，却仍然被切了** → 不是必要的切分。
「预算只是紧」本该交给 `ScoreBasedContextCreator` 去驱逐旧记录，camel 把两种
情形合并进了同一个条件。

### ② 同拍碰撞 —— `repro_02_timestamp.py`

`_record_tool_calling`（2739~2751 行）**只读一次时钟**，用 `+1e-6` 把回执排在
请求之后，注释写着「纳秒精度，避免碰撞」。但**那个 `1e-6` 比时钟自己的分辨率还细
两三个数量级**（脚本第一节现场量出本机 `time.time_ns()` 的最小步长，半毫秒量级）。

所以它分得开**一对**请求/回执（那是加在显式值上的算术，不看钟），却分不开
**两次调用**：一次模型响应里并排的两个 tool 调用前后脚读钟，**读到同一个 `T`**。
四条记录的时间戳成了 `T、T+1e-6、T、T+1e-6`，而排序键 `(timestamp, -score)`
在相等处按**分数高的在前**决胜负 —— 也就是**后写的那条排到前面**：

```
assistant_B(T) · assistant_A(T) · func_B(T+1e-6) · func_A(T+1e-6)
   ↑ 带 tool_calls     ↑ 紧随其后的却是另一个 assistant，不是它的回执
```

端点回 400 `insufficient tool messages following tool_calls message`，而上层只记
一行 `Agent ... error` 就继续跑 —— **该 agent 这一轮的动作整条消失**。

判据直接对**发给 API 的那串消息**做 API 的同一条校验（`memory.get_context()`
返回的就是它）：凡带 `tool_calls` 的消息，紧随其后的必须是回应它的 `role="tool"`。

> ⚠️ 第一节那个步长是**量出来的**，每次运行会有出入（同一台机器上见过
> 0.5 ~ 1.0 ms）—— 它随系统调度变，是测量值不是常数。**结论不依赖它的具体数值**，
> 只用到「它比 `1e-6` 大两三个数量级」这一点。
>
> 与之相对：**第二节那张表**用的是冻钟，每次运行逐位相同；**第三节的两个毫秒数**
> 也是量出来的（同样是物理时钟给的），会有出入 —— 但「切片没修 ≈ 200 拍、
> 切片修了 ≈ 0 拍」差着两个数量级，**判定「跨拍 / 同拍」这一条是稳的**，
> 抖不出那个区间。

**这条失效是①的代价，脚本第三节把它量了出来：**

| | 两次 tool 调用的真实间隔 | 后果 |
|---|---|---|
| 切片没修 | **115 ms（≈198 拍）** | 跨拍 → 误打误撞免疫 |
| 切片修了 | **0 ms（同拍）** | 碰撞才发生 |

切片没修时写一次回执要落几百条记录、花好几毫秒，两次调用必然跨拍；切片的修复
**全部目的就是让写入变快** —— 快进同一拍，碰撞才开始发生。

### ③ 并发次序 —— `repro_03_concurrency.py`（**边界，不修**）

这一条和上面两条同等重要，它不是「没做的东西」，是**划出来的边界**。

上游 issue #751 / #759：同一份输入跑两次跑出不同人群（弃权率 9.5% vs 60.0%），
温度设 0 也一样。成因在 `oasis/environment/env.py`：

```
 55   semaphore: int = 128
 70   self.llm_semaphore = asyncio.Semaphore(semaphore)
127   async with self.llm_semaphore:              # _perform_llm_action
193   await asyncio.gather(*tasks)                # 所有 agent 的动作并发执行
```

（脚本第一节会**在真实源码里逐行核对**这几行；对不上就报「没测到」，不报「通过」。
MiroFish 的驱动脚本把并发数设成 **30**，也是从脚本里读出来的，不是记的。）

**谁的 LLM 先返回，谁的动作就先落库** —— 落库次序决定 `post_id` 的分配，进而决定
后续交互指向哪条帖子。而次序取决于网络快慢，那是程序管不到的量。

脚本量出两件事：

* **次序是「耗时」的确定函数**：耗时全相同时跑两遍，次序逐位相同。
  **乱的不是事件循环，是喂给它的耗时。**
* **灵敏度极低**：把一个 agent 拖慢 **1 微秒**，落库次序就变了。
  而两次真实 LLM 调用的耗时差是毫秒到秒量级 —— **根本没有安全余量。**

**为什么不能靠「排个序」修掉**：要让这一层逐字可复现，就得把 agent 的动作串行化；
而并发正是这个仿真跑得动的前提。**换来的确定性和花掉的时间，是取舍，不是对错。**

所以装置的立场是：**这一层不承诺可复现，只承诺可检出。**

---

## 三个守卫是什么关系

```
camel_guards.install(target=None, slicing=True, timestamp=True)
camel_guards.set_flags(slicing=..., timestamp=...)   # 只改开关，不重装
camel_guards.uninstall()
camel_guards.counters()
```

替换的是 `ChatAgent.update_memory` **一个方法，一处补丁**，两个开关在这里读。
`target` 是给测试用的注入口：传一个替身类就能在不碰 camel、不发 LLM 的前提下把
「该拦的拦、该切的不切」两个方向都测到。被替换的原方法留在内部、
`uninstall()` 可完整还原，`install()` **幂等**。

计数（`counters()`）落进调用方的产物：

| 名字 | 含义 |
|---|---|
| `written_whole` | 整条写入的次数 |
| `still_sliced` | 消息**自己**就超上限、必须切才交回原方法的次数 |
| `timestamp_pushed` | 我们自己取读数、却被推后的次数 |

⚠️ **`timestamp_pushed` 不是「撞窗口的次数」，别那样读它。** camel 显式给的
请求/回执那一对**几乎总会被推**（它的 `1e-6` 小于一个步长），那是把次序撑开、
不是撞上。这个计数只回答「有多少次读数是靠逻辑时钟补救的」。

---

## 版本

本目录里引的源码行号，是对着 **`camel-ai==0.2.78`** 与 **`camel-oasis==0.2.5`**
写的 —— 而 `backend/requirements.txt` 里 pin 的正是这两个版本。所以
`pip install -r requirements.txt` 装出来的，**就是文档里引的那一份源码**，
行号能对得上，`repro_03` 第一节也是照着这个前提去逐行核对的。

（`repro_03` 核对不上会报「没测到」并给退出码 `2`，不会报「通过」。）

## 已知边界

* **装置只对 MiroFish 类 · camel-oasis 系仿真实例有效**，**不承诺支持任意框架**。
  这是边界，不是缺陷：两个守卫改的是 `camel.agents.chat_agent.ChatAgent` 的
  运行时行为，判据也建立在这条调用链上。
* **第 3 层（端到端）不执行，只划界** —— 见上。
* **`repro_03` 不证明 MiroFish 端到端不可复现。** 那要真跑、要 API key，而且
  「跑两次不一样」本身也不构成证明。它只说明这一层的次序由什么决定、为什么钉不住。
* 上游 web 半边**硬依赖 Zep Cloud**（`zep-cloud`、`ZEP_API_KEY`），没有 key 跑不起来。
  三个缺陷全在 OASIS/camel 路径上，而 `scripts/run_*_simulation.py` 不 import `app/`，
  所以本目录**完全不需要 Zep**。

---

## 目录

```
verification/
  camel_guards.py       两个运行时守卫（一处补丁、两个独立开关）
  attach.py             接到上游驱动脚本上的那两行胶水
  _probe.py             离线探针的共享底座（裸 agent / 灌满 / 冻钟 / 打印）
  repro_01_slicing.py   ① 切片正反馈环
  repro_02_timestamp.py ② 同拍碰撞
  repro_03_concurrency.py ③ 并发次序（边界）
  run_all.py            一条命令跑三个
```
