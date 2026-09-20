# [草稿] 新 issue ①：记忆写入把一条消息切成 270 块，token 实增 18.5 倍

> 标题建议：
> **记忆写入：一条只占窗口 7% 的消息被切成一块一个 token，记忆膨胀 18.5 倍**

---

## 环境

| | |
|---|---|
| MiroFish | `39d849138ef254f6c737ab4c4705e5545dbe31d4` |
| camel-ai | `0.2.78`（`backend/requirements.txt` pin 的就是这个） |
| camel-oasis | `0.2.5` |
| Python | 3.11.9 · Windows 11 |

## 症状

跑模拟时 camel 自己会刷这种告警，一条消息一行：

```
WARNING - Message with 277 tokens exceeds remaining budget of 133. Slicing into smaller chunks.
```

`Slicing into smaller chunks` 听着像正常的分块。实际发生的是：**那条 277 token 的
消息被切成了 270 条记录**，而且原文从此找不回连续片段。

对 MiroFish 使用者的后果有两个，都是钱和结果的问题：

* **上下文被自己的碎片挤满**。该 agent 后续拿到的「历史」是几百条一个 token 的残片，
  而不是它自己说过的话 —— 记忆等于没了。而这是个**正反馈**：记忆满 → 残余预算小 →
  切得更碎 → 记忆更满。
* **token 消耗成倍上涨**。每块还各带一个十几 token 的前缀，实测一条 277 token 的
  消息实增 **5130 token（18.5 倍）**。

> 说明：这个 issue 里**没有端到端跑过 MiroFish**（那需要 `LLM_API_KEY` 和真实额度）。
> 机制与离线复现是实打实测出来的，上面两条用户可见后果是据此推断的。如果维护者
> 需要端到端证据，我们可以配合补。

## 最小复现（自包含，不发 LLM 请求、不要 API key、几秒跑完）

（唯一要用到网的地方：分词器的编码表首次使用要下一张几 MB 的静态表，之后走缓存。它不是 LLM 调用。）

```python
import warnings

from camel.agents.chat_agent import ChatAgent
from camel.memories.agent_memories import ChatHistoryMemory
from camel.memories.context_creators.score_based import ScoreBasedContextCreator
from camel.messages import BaseMessage
from camel.types import OpenAIBackendRole, UnifiedModelType
from camel.utils import OpenAITokenCounter

TOKEN_LIMIT = 4000
counter = OpenAITokenCounter(UnifiedModelType("gpt-4o-mini"))
creator = ScoreBasedContextCreator(counter, token_limit=TOKEN_LIMIT)

# 真造一个 ChatAgent 需要模型后端；这里要测的是**写入决策**，与模型无关，
# 所以用 __new__ 绕过 __init__。update_memory 只用到下面这三个属性。
agent = ChatAgent.__new__(ChatAgent)
agent.agent_id = "repro"
agent._system_message = None
agent.memory = ChatHistoryMemory(context_creator=creator)

warnings.simplefilter("ignore")


def raw_tokens():
    return sum(counter.count_tokens_from_messages(
        [r.memory_record.to_openai_message()])
        for r in agent.memory.retrieve())


# 1) 把记忆灌到「截断已经启动」—— 也就是切片分支的前提状态
filler = BaseMessage.make_user_message(role_name="User", content="填 " + "x" * 1200)
while raw_tokens() <= TOKEN_LIMIT:
    agent.update_memory(filler, OpenAIBackendRole.USER)

_, ctx_tokens = agent.memory.get_context()
remaining_budget = max(0, TOKEN_LIMIT - ctx_tokens)
base_chunk_size = max(1, remaining_budget) // 10
prefix_token_len = len(counter.encode("[chunk 1/1000 of a long message]\n"))
chunk_body_limit = max(1, base_chunk_size - prefix_token_len)

# 2) 写一条**相对整个窗口很小、但超过残余预算**的消息
text = "".join(f"记录{i}，" for i in range(90))
msg = BaseMessage.make_user_message(role_name="User", content=text)
own = counter.count_tokens_from_messages(
    [msg.to_openai_message(OpenAIBackendRole.USER)])

before_n, before_t = len(agent.memory.retrieve()), raw_tokens()
agent.update_memory(msg, OpenAIBackendRole.USER)
after_n, after_t = len(agent.memory.retrieve()), raw_tokens()

print(f"上限                        {TOKEN_LIMIT}")
print(f"截断后上下文 token           {ctx_tokens}")
print(f"remaining_budget            {remaining_budget}")
print(f"base_chunk_size             {base_chunk_size}")
print(f"prefix_token_len            {prefix_token_len}")
print(f"chunk_body_limit            {chunk_body_limit}")
print(f"待写消息自己的 token         {own}   （「放得下」= {own} <= {TOKEN_LIMIT}）")
print(f"写入前 记录数/实际 token     {before_n} / {before_t}")
print(f"写入后 记录数/实际 token     {after_n} / {after_t}")
print(f"→ 一条消息变成 {after_n - before_n} 条记录，"
      f"token 实增 {after_t - before_t}（{(after_t - before_t) / max(own, 1):.1f} 倍）")
```

### 实测输出

```text
2026-09-16 21:04:56,435 - camel.camel.agents.chat_agent - WARNING - Message with 160 tokens exceeds remaining budget of 0. Slicing into smaller chunks.
2026-09-16 21:04:56,551 - camel.camel.memories.context_creators.score_based - WARNING - Context truncation performed: before=6907, after=3867, limit=4000
2026-09-16 21:04:56,660 - camel.camel.memories.context_creators.score_based - WARNING - Context truncation performed: before=6907, after=3867, limit=4000
2026-09-16 21:04:56,660 - camel.camel.agents.chat_agent - WARNING - Message with 277 tokens exceeds remaining budget of 133. Slicing into smaller chunks.
上限                        4000
截断后上下文 token           3867
remaining_budget            133
base_chunk_size             13
prefix_token_len            12
chunk_body_limit            1
待写消息自己的 token         277   （「放得下」= 277 <= 4000）
写入前 记录数/实际 token     178 / 6907
写入后 记录数/实际 token     448 / 12037
→ 一条消息变成 270 条记录，token 实增 5130（18.5 倍）
→ 原文还找得回连续片段吗： **找不到了**
```

## 根因

`camel/agents/chat_agent.py` 的 `update_memory`（方法在 **818** 行起；下面几行的行号对 `0.2.78`）：

```python
# 逐字引自 camel.agents.chat_agent
remaining_budget = max(0, token_limit - ctx_tokens)            # 884
if current_tokens <= remaining_budget:                         # 886
    _write_single_record(message, role, base_ts)               # 887
    return                                                     # 888
base_chunk_size = max(1, remaining_budget) // 10               # 933
sample_prefix = "[chunk 1/1000 of a long message]\n"           # 942
prefix_token_len = len(token_counter.encode(sample_prefix))    # 943
chunk_body_limit = max(1, base_chunk_size - prefix_token_len)  # 948
num_chunks = math.ceil(len(all_token_ids) / chunk_body_limit)  # 951
```

（884 行的 `ctx_tokens` 是**截断后**的；888 与 933 之间略去的部分与本论断无关。）

`ctx_tokens` 来自 `self.memory.get_context()`，而截断干的事就是**把上下文填到贴着上限**
（上面日志里 `before=6907, after=3867, limit=4000`）。所以走到 933 行时
`remaining_budget` 已经被挤得很小，再被 `// 10` 和减前缀两刀砍完，
`chunk_body_limit` 落到 `max(1, …)` 那个下界 —— **1**。

**这个下界被命中的范围比「预算很紧」宽得多。** 把实测的 `prefix_token_len = 12`
代进去：只要 `remaining_budget < 140`，`chunk_body_limit` 就恒为 1。也就是说，
**在 4000 的窗口里残余预算低于 140 token 时，每一条被切的消息都变成一块一个 token**。
上面那次 `remaining_budget` 是 133 —— 刚过线。

## 为什么这不是「预算紧」该有的行为

`remaining_budget` 小的时候，正确的处置是**驱逐旧记录** —— 这正是
`ScoreBasedContextCreator` 存在的理由，它在 `get_context()` 里已经在做截断了。
把「消息自己放不进整个窗口」和「消息放不进当下的残余额度」合并进同一个
`if`（886 行），再对后者套用一个为前者设计的切块公式，结果是**在一条消息完全
可以整条留下的时候把它毁掉**。

一个可以当判据的说法：**这条消息自己（277）远小于窗口（4000），却仍然被切片。**
这种切分不是必要的。

## 建议

按「谁该让步」来分，有两种都说得通的改法，请维护者定：

1. **缩小切片分支的适用范围**：只有 `current_tokens > token_limit`（消息自己就放不下）
   才切片；`token_limit` 装得下、只是残余额度不够的，整条写入，把腾地方交给
   context creator。
2. **修 `chunk_body_limit` 的下界**：`max(1, …)` 会在算出来是负数或 0 时落到 1，
   这是最坏的一种退化。可以让它在算出来太小时**放弃切片**（退回整条写入），
   而不是切成一块一 token。

我们不敢替上游定哪个对 —— 两个函数的预期行为没有写在文档里，而我们对 MiroFish
的调用姿势未必是上游设想的唯一姿势。

## 我们这边的处置

我们在自己的 fork 里包了一层**运行时守卫**，不改 `site-packages`：写入前先算这条
消息自己值多少 token，**≤ 上限就整条写入**；只有它自己就超上限时才交回原方法去切。
同一份输入下 270 条 / 5130 token 变成 **1 条 / 277 token**，原文完整。

守卫与它的离线复现（就是上面这份，加上前提自检和单点扰动）都在
`backend/verification/`，一条命令跑完，不需要 API key。如果维护者想要，我们可以
把它整理成一个 PR；如果不想要，这个 issue 本身也够定位问题了。
