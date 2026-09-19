"""上游 issue ② 的最小复现（紧凑版）—— 就是贴在 issue 正文里的那一份。

    python -m verification.upstream.repro_min_02_timestamp   # 在 backend/ 下

不发 LLM、不要 API key、几秒跑完。
> **首次运行要联网一次**：装置用的分词器（tiktoken）要下一张几 MB 的静态表，
> 之后走本地缓存。这只是编码表，不是 LLM 调用 —— 但冷缓存的机器上确实要用到网。
情形 A 用冻钟，所以逐位可复现；
情形 B 量的是物理时钟，数字每次会有出入（结论只用到量级）。

**这是为了贴进 issue 而另写的紧凑版**，装置本体是 `../repro_02_timestamp.py`。
两份的数字必须一致 —— 改任何一边都要同步另一边。
数字与 `upstream/issue_02_same_tick_collision.md` 里的输出块逐字对应。
"""
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
    agent = ChatAgent.__new__(ChatAgent)
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
    """API 的同一条校验：带 tool_calls 的消息，后面必须紧跟它的回执。"""
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
    # 情形 A：两次 tool 调用**落点相差小于 camel 那个 1e-6 偏移** vs 相差大于它。
    #
    # 第二臂的 `1e-3` 是**偏移的一千倍**（不是「时钟的一拍」）—— 这个区别是量出来的：
    # 判据的分界是**那个偏移**，不是时钟刻度。写成「隔一拍」在 Windows 上碰巧等价
    # （那边一拍零点几毫秒，比偏移粗），换到刻度比偏移细的机器上就名不副实了
    # （Linux 实测一拍 100 ns，`1e-3` 是它的**一万拍**）。间隔按偏移写，与宿主机无关。
    # 详见 `../repro_02_timestamp.py` 的「单点扰动」一节。
    for label, gap in (("同拍（gap=0）", 0.0), ("跨过那个偏移（gap=1e-3）", 1e-3)):
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

    # 情形 B：真钟一拍有多宽。**按时间窗采样、取窗口内最小值**，用
    # time.perf_counter() 计时 —— 紧凑循环跑定次数不行：循环跑完可能还没跨过
    # 一拍照样读数全同，而循环自身的开销又会盖过时钟分辨率。
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
    # 这一行**必须分两种情况写**：刻度比 1000 ns 细的机器上 `best / 1000` 小于 1，
    # 写成 `1/{比值:,.0f}` 会印出「1/0」—— 一个看着像除零、其实只是四舍五入的假象。
    if best >= 1000:
        print(f"  那个 1e-6 只有时钟一拍的 1/{best / 1000:.0f}"
              " —— 所以它分得开一对请求/回执（那是算术），分不开两次调用（那是读钟）")
    else:
        print(f"  那个 1e-6 反倒比时钟一拍还粗 {1000 / best:.1f} 倍"
              " —— 两种机器上它都分不开两次挨得太近的调用（那是读钟）")
finally:
    time.time_ns = real_time_ns
