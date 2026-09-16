"""上游 issue ① 的最小复现（紧凑版）—— 就是贴在 issue 正文里的那一份。

    python -m verification.upstream.repro_min_01_slicing   # 在 backend/ 下

不发 LLM、不要 API key、几秒跑完、结果确定。
> **首次运行要联网一次**：装置用的分词器（tiktoken）要下一份静态数据（约 3.6 MB，
> 之后走本地缓存）。这只是编码表，不是 LLM 调用 —— 但冷缓存的机器上确实要用到网。


**这是为了贴进 issue 而另写的紧凑版**，装置本体是 `../repro_01_slicing.py`
（多了前提自检、单点扰动、退出码三态、以及「没测到 != 通过」的处理）。
两份的数字必须一致 —— 改任何一边都要同步另一边，不一致就是有一边错了。
数字与 `upstream/issue_01_memory_slicing.md` 里的输出块逐字对应。
"""
import warnings

from camel.agents.chat_agent import ChatAgent
from camel.memories.agent_memories import ChatHistoryMemory
from camel.memories.context_creators.score_based import ScoreBasedContextCreator
from camel.memories.records import MemoryRecord
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
own = counter.count_tokens_from_messages([msg.to_openai_message(
    OpenAIBackendRole.USER)])

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
print("→ 原文还找得回连续片段吗：",
      "找得到" if text[:40] in "".join(
          r.memory_record.message.content or "" for r in agent.memory.retrieve()
      ) else "**找不到了**")
