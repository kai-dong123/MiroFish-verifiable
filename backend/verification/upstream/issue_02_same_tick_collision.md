# [草稿] 新 issue ②：同一拍里的两次 tool 调用会拆散「请求 / 回执」，该 agent 整轮动作消失

> 标题建议：
> **一次响应里并排的两个 tool 调用会撞进同一拍，导致 tool_calls 后面跟的不是它的回执**

---

## 环境

| | |
|---|---|
| MiroFish | `39d849138ef254f6c737ab4c4705e5545dbe31d4` |
| camel-ai | `0.2.78` |
| camel-oasis | `0.2.5` |
| Python | 3.11.9 · Windows 11 |

## 症状

`camel/agents/chat_agent.py` 的 `_record_tool_calling`（2739~2751 行）**只读一次时钟**，
再用 `+1e-6` 把回执排在请求之后。源码注释写着「纳秒精度，避免碰撞」：

```python
2739  current_time_ns = time.time_ns()
2740  base_timestamp  = current_time_ns / 1_000_000_000   # Convert to seconds
2742  self.update_memory(assist_msg, ASSISTANT, timestamp=base_timestamp)
2747  self.update_memory(func_msg,   FUNCTION,  timestamp=base_timestamp + 1e-6)
```

**那个 `1e-6` 比时钟自己的分辨率还细两三个数量级**（下面量出来本机是零点几毫秒，
即 `1e-6` 只有一拍的几百分之一）。所以它分得开**一对**请求/回执 —— 那是加在显式
值上的算术，不看钟 —— 却分不开**两次调用**：一次模型响应里并排的两个 tool 调用
前后脚读钟，**读到同一个 `T`**。

于是四条记录的时间戳是 `T、T+1e-6、T、T+1e-6`。排序键是
`(timestamp, -score)`（`memories/context_creators/score_based.py` 的
`_conversation_sort_key`）。同一时间戳上按**分数高的在前**决胜负，而分数随写入
递增（实测 `0.6561 / 0.729 / 0.81 / 0.9`，是 `0.9^n` 的衰减）——
**也就是后写的那条排到前面**：

```
REQ call_2(T) · REQ call_1(T) · RESP call_2(T+1e-6) · RESP call_1(T+1e-6)
   ↑ 带 tool_calls，紧随其后的却是另一个请求，不是它的回执
```

这串消息**不符合 OpenAI 兼容端点对 tool_calls 的要求**（`tool_calls` 之后必须紧跟
回应它的 `role="tool"`），会被以 `insufficient tool messages following tool_calls
message` 拒掉。

（**说明**：这条消息串我们没有真的发出去 —— 那需要 `LLM_API_KEY` 和真实额度。
下面复现里的「违反」判定就是照端点这条规则在本地消息串上做的，判据与端点同源。）

而异常到了上层是**被吞掉**的。`oasis/social_agent/agent.py` 的
`perform_action_by_llm`：

```python
153      except Exception as e:
154          agent_log.error(f"Agent {self.social_agent_id} error: {e}")
155          return e
```

只记一行日志，然后**把异常对象当结果返回**。于是日志里一行
`Agent xxx error: ...`，而那个 agent 这一轮**什么也没做** —— 在模拟的任何统计里
它都是「没动作」，看不出是被拒了。

> 说明：上面这条路径我们是**读源码核实的**（`oasis/social_agent/agent.py:153-155`），
> 不是从一次真实运行的日志里看到的（同样因为没有 key）。机制和本地复现是实的。

## 最小复现（自包含，不联网、不要 API key、几秒跑完）

```python
import time

from camel.agents.chat_agent import ChatAgent
from camel.memories.agent_memories import ChatHistoryMemory
from camel.memories.context_creators.score_based import ScoreBasedContextCreator
from camel.messages import FunctionCallingMessage
from camel.types import OpenAIBackendRole, RoleType, UnifiedModelType
from camel.utils import OpenAITokenCounter

counter = OpenAITokenCounter(UnifiedModelType("gpt-4o-mini"))
creator = ScoreBasedContextCreator(counter, token_limit=8000)


def bare_agent():
    agent = ChatAgent.__new__(ChatAgent)   # 不碰模型，只测写入
    agent.agent_id = "repro"
    agent._system_message = None
    agent.memory = ChatHistoryMemory(context_creator=creator)
    return agent


def record_tool_call(agent, cid, ts):
    """照着 `_record_tool_calling` 的形状（2742~2751 行）写一对记录。"""
    common = dict(role_name="Actor", role_type=RoleType.ASSISTANT,
                  meta_dict=None, content="", func_name="act",
                  tool_call_id=cid)
    agent.update_memory(FunctionCallingMessage(args={"call": cid}, **common),
                        OpenAIBackendRole.ASSISTANT, timestamp=ts)
    agent.update_memory(FunctionCallingMessage(result=f"{cid} 的结果", **common),
                        OpenAIBackendRole.FUNCTION, timestamp=ts + 1e-6)


def violations(ctx):
    """端点同一条校验：带 tool_calls 的消息，后面必须紧跟它的回执。"""
    out = []
    for i, m in enumerate(ctx):
        if m.get("tool_calls"):
            nxt = ctx[i + 1] if i + 1 < len(ctx) else None
            if not nxt or nxt.get("role") != "tool":
                out.append((i, (nxt or {}).get("role")))
    return out


def shape(ctx):
    return " → ".join("assistant+tool_calls" if m.get("tool_calls")
                      else m.get("role", "?") for m in ctx)


# 冻钟：把 time.time_ns 换成手动推进的表（camel 是 `import time`，换模块属性即可）
state = {"t": 0.0}
real_time_ns = time.time_ns
time.time_ns = lambda: int(state["t"] * 1e9)
try:
    for label, gap in (("同拍（gap=0）", 0.0), ("隔一拍（gap=1e-3）", 1e-3)):
        state["t"] = 1000.0
        agent = bare_agent()
        record_tool_call(agent, "call_1", state["t"])
        state["t"] += gap
        record_tool_call(agent, "call_2", state["t"])
        ctx = agent.memory.get_context()[0]
        print(f"\n【{label}】")
        print("  发给端点的消息串：", shape(ctx))
        v = violations(ctx)
        print("  违反「tool_calls 后必须紧跟它的回执」：",
              f"{len(v)} 处 {v}" if v else "无")

    # 真钟一拍有多宽。**按时间窗采样、取窗口内最小值**，用 time.perf_counter()
    # 计时 —— 紧凑循环跑定次数不行：循环跑完可能还没跨过一拍，读数全同；
    # 而循环自身的开销又会盖过时钟分辨率。
    time.time_ns = real_time_ns
    best, deadline, prev = None, time.perf_counter() + 0.05, real_time_ns()
    while time.perf_counter() < deadline:
        now = real_time_ns()
        d = now - prev
        if d > 0 and (best is None or d < best):
            best = d
        prev = now
    print(f"\n【真钟】连续读钟 50 ms 内，最小正步长 = {best} ns"
          f"（camel 给的排序偏移是 1000 ns）")
    print(f"  那个 1e-6 只有时钟一拍的 1/{best / 1000:.0f}"
          " —— 所以它分得开一对请求/回执（那是算术），分不开两次调用（那是读钟）")
finally:
    time.time_ns = real_time_ns
```

### 实测输出

```text
【同拍（gap=0）】
  发给端点的消息串： assistant+tool_calls → assistant+tool_calls → tool → tool
  违反「tool_calls 后必须紧跟它的回执」： 1 处 [(0, 'assistant')]

【隔一拍（gap=1e-3）】
  发给端点的消息串： assistant+tool_calls → tool → assistant+tool_calls → tool
  违反「tool_calls 后必须紧跟它的回执」： 无

【真钟】连续读钟 50 ms 内，最小正步长 = 436700 ns（camel 给的排序偏移是 1000 ns）
  那个 1e-6 只有时钟一拍的 1/437 —— 所以它分得开一对请求/回执（那是算术），分不开两次调用（那是读钟）
                         ^^^^^^ 这两行每次跑都不一样，见下
```

（前两块是**冻钟**，逐位可复现 —— 换台机器也是这个输出。
**最后那块是真钟，那个步长是测量值**：同一台机器上多次测到 0.30 ~ 1.00 ms 不等，
中位数 0.37 —— 最小步长本身是个随机量，随调度变，所以上面那个 `436700` / `1/437`
换个时间跑就不是这两个数（下一次跑可能是 `443300` / `1/443`，再下一次又是别的）。
**结论不依赖它的具体数值**，只用到「它比 `1e-6` 大两三个数量级」这一点。）

## 这不是边缘情况

两次 `_record_tool_calling` 是在**同一个模型响应的 tool_calls 循环里连着调**的，
中间**没有 I/O** —— 两次读钟之间只隔着几次 Python 调用。
所以「同拍」不是小概率事件，是**常态**。

一个实测佐证：在**记忆已经灌满**的前提下量（这是最不利的一种情形 —— 每次写入还得
连带做一轮驱逐），7 次运行里有 5 次两次调用之间的真实间隔量出来是 **0.00 ms**
（低于时钟分辨率），即落在**同一拍**；另外 2 次跨到十来拍（0.80 / 3.35 / 3.80 ms）。
换句话说：**同拍是多数情形，不是保证** —— 时钟分辨率有多细、这一拍恰好有多宽，
本来就随调度变。我们没把这句写成「必然」，因为它不是。

（这一段的数是在**满记忆**这个最重的前提下量的；记忆没满时写入更快，间隔只会更小。
但「更快」我们**没有端到端量过**，这里只是据机制推断，不作为证据。）

顺带说明一个容易看岔的地方：记忆没满的时候，写入很快，这个碰撞本来就碰得到；
记忆满了以后，记忆写入的另一个问题（见 issue ①）会把一次写入撑到 **一百多毫秒
（折合上百拍，实测 106.8 ~ 122.7 ms）**，两次调用于是必然跨出很远 —— ① 反而
**遮住**了 ②。把 ① 修掉（我们做的就是这件事），间隔掉回**拍的量级**，
② 才有机会暴露出来。

## 建议

「加一个常数保证顺序」这个做法在这里是失效的，因为常数**加在一个读数上，
而读数本身的分辨率不够**。要让顺序真的成立，需要的是**不依赖读数的**单调性，
比如：

* 给记忆写入维护一个单调递增的序号，排序键用它做第一关键字；或
* 记录时读**一次**钟，同一次响应内的所有调用按调用下标递推时间戳
  （`base + i * step`），而不是各读各的钟。

请维护者定哪种合适 —— 我们不确定上游对「同一次响应的多个 tool 调用必须保持次序」
这一点有没有明确规格，所以不敢替上游选。

## 我们这边的处置

我们在自己的 fork 里包了一层**运行时守卫**：写入时若发现取到的读数没有比上一次
至少前进一个逻辑步长（`1e-3`，比 `1e-6` 大得多，又远小于任何真实间隔），就把它
推后到上一次 + 一个步长。装上前 / 装上后的消息串就是上面那张表里的两行。

守卫与它的离线复现都在 `backend/verification/`，一条命令跑完，不需要 API key。
