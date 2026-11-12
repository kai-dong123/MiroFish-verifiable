# 变异测试留痕（自动生成，别手改）

> 生成时间 **2026-11-12 17:28:22** · Python 3.11.9 · `cd backend && python -m verification.mutations`

## 这份报告是什么、不是什么

**是**：一张「把被测代码改坏了、测试会不会红」的对照表 —— `README.md` 里「验过它不是恒真的」那句话的证据。

**不是**：通过率、覆盖率、质量分。这里的**红色是期望的结果**，一条红都没有才是坏消息。**别把红条数读成任何形式的得分。**

- 基线（一点没改）：**269 passed / 0 failed / 47 skipped**（= 全套 316 条），退出码 0，36.72s —— 先证明测试集本身是绿的，底下那些红才有意义。
- **「红 N 条」一律是相对基线多出来的**（扣掉基线本来就红的那些）：基线全绿时它与「原样数红条」逐字相同；基线红了时，原样的那个数也留在每条的明细里，扣没扣由读者自己核。**为什么要减这一下**：判据被污染之后照样给判定，正是这个装置盯别人的那件事（实测踩到过：基线红 2 条、靶子正好是那个文件，一条**按声明红掉**的变异被数成 3 条、判成「与声明不符」）。
- 上面这个规模**不含** `tests/test_mutation_evidence.py`（15 条）：那一组问的是「这份报告有没有过期」，而本模块每一轮都在被改坏的源码上跑 —— 它见到环境变量 `MIROFISH_MUTATION_RUN` 会跳过自己。「报告过期」由普通 `pytest` 抓，见那个文件。
- 15 个源文件跑完后：**文本哈希 一致**、**字节逐字节还原**（文本那份见 `sources` / `sources_after`；字节这一格回答的是「本机这份有没有被动过」，两件事分开记）。

## 对照表

「声明」是**材料里先写下的**数字；「实测」是这一轮跑出来的。两者不一致时**以实测为准**，并且材料要跟着改 —— 不许反过来把期望值改成漂移后的样子。

| # | 组 | 变异成什么 | 声明 | 实测（目标文件红掉） | 判定 |
|---|---|---|---|---|---|
| `G1` | 守卫 | 判据的边界写成 `>=`（顶格的消息会被误判成超限） | 至少 1 条 | **1 条** | 相符 |
| `G2` | 守卫 | 整个守卫变成空操作（开头就把活原样交回原方法） | 至少 1 条 | **13 条** | 相符 |
| `G3` | 守卫 | 变成「一律不切」（该切的那条路被永远关掉） | 至少 1 条 | **4 条** | 相符 |
| `G4` | 守卫 | 逻辑步长调到比 camel 那个 `1e-6` 还细 | 至少 1 条 | **1 条** | 相符 |
| `G5` | 守卫 | 时间戳不再往后推（拿掉严格递增那一步） | 至少 1 条 | **4 条** | 相符 |
| `G6` | 守卫 | 去掉兜底（算不出 token 时不再交回原方法，直接抛） | 至少 1 条 | **2 条** | 相符 |
| `G7` | 守卫 | `install` 不再幂等（第二次调用会套第二层补丁） | 至少 1 条 | **1 条** | 相符 |
| `G8` | 守卫 | 推了游标但不交回（回退支仍把原时间戳交给原方法） | 3 条 | **3 条** | 相符 |
| `V1` | 判词 | 判词写死（直接把结论摆在预期那一侧，不再由读数算） | 16 条 | **16 条** | 相符 |
| `V2` | 判词 | 判据的 `<` 写成 `<=`（`gap == tick` 会被算成同一拍） | 3 条 | **3 条** | 相符 |
| `V3` | 判词 | 去掉「与预期相反」那一支（与预期不符时折回预期那一侧的话术） | 3 条 | **3 条** | 相符 |
| `C1` | 引文·上半 | 行号错开一格（933 → 934） | 至少 1 条 | **1 条** | 相符 |
| `C2` | 引文·上半 | 引一个越界的行号（884 → 999999） | 至少 1 条 | **1 条** | 相符 |
| `C3` | 引文·上半 | 换成那一行没有的片段（`// 10` 写成 `// 100`） | 至少 1 条 | **1 条** | 相符 |
| `C4` | 引文·上半 | 引一个不存在的模块（`camel.memories.base` → `..._missing`） | 至少 1 条 | **1 条** | 相符 |
| `C5` | 引文·上半 | 同一行引两遍（把 env:55 那条改成 env:193，片段也跟着改成 193 行的） | 至少 1 条 | **1 条** | 相符 |
| `C6` | 引文·下半 | 把那个错引写法**植回 `camel_guards.py`**，看扫描抓不抓 | 1 条 | **1 条** | 相符 |
| `C7` | 引文·逐字块 | 逐字块里的行号错开一格（886 → 885，那一行是空行） | 1 条 | **1 条** | 相符 |
| `J1` | 裁决 | 贴界退化成「碰过这一臂或这一量的格子都算贴界」（一格贴界，整行整列降级） | 1 条 | **1 条** | 相符 |
| `J2` | 裁决·缺读数 | 把「缺读数」折进「否决」—— 正是本装置抓别人的那件事 | 4 条 | **4 条** | 相符 |
| `J3` | 裁决·恒真 | falsifier 只查在不在，**不实例化** —— 于是它永远「翻得动」 | 2 条 | **2 条** | 相符 |
| `J4` | 裁决·恒真 | **判据恒真也照退 0** —— 这张表开始装绿 | 1 条 | **1 条** | 相符 |
| `J5` | 裁决·缺读数 | **「没测到」退 1**（退成「没达到预期」）—— 正是本装置抓别人的那件事，落在自己身上 | 1 条 | **1 条** | 相符 |
| `J6` | 守卫·计数落盘 | **装守卫时不安排落盘** —— 计数照样烂在内存里，一次真跑还是什么都看不见（回到补它之前那个状态） | 1 条 | **1 条** | 相符 |
| `J7` | 裁决·端到端 | 端到端报告不在时**编一份读数**出来 —— 最容易写下的那种「补全」，而且编完那张表看着更完整 | 1 条 | **1 条** | 相符 |
| `P1` | 环境·版本钉 | 把 `tiktoken` 的锁定从 `==0.7.0` 放成 `>=0.1` | 1 条 | **1 条** | 相符 |
| `D1` | 清单·改动表 | 清单改动表里把一个数目改歪（`requirements.txt` 15 → 16） | 1 条 | **1 条** | 相符 |
| `N1` | 上游基线 | 把「这里是不是 git 仓库」那道门焊死（`_is_repo()` 恒为假） | 1 条 | **1 条** | 相符 |
| `O1` | 落点 | 汇总驱动把落点那道门摘了（`--out` 不通也照跑三个复现） | 1 条 | **1 条** | 相符 |
| `O2` | 落点 | 裁决把落点那道门摘了（判定照算，算完才发现写不出去） | 1 条 | **1 条** | 相符 |
| `O3` | 落点 | 裁决写不下去时报「没达到预期」（`2` 改成 `1`） | 1 条 | **1 条** | 相符 |
| `O4` | 落点 | 自证把落点那道门摘了 | 1 条 | **1 条** | 相符 |
| `O5` | 落点 | 端到端把落点那道门摘了（真去跑那一局，跑完才发现写不出去） | 1 条 | **1 条** | 相符 |
| `O6` | 落点 | 对账把落点那道门摘了 | 1 条 | **1 条** | 相符 |
| `O7` | 落点 | 留痕把落点那道门摘了（⚠️ 这条改的是本文件自己） | 1 条 | **1 条** | 相符 |
| `X1` | 没测到·不许折 | 汇总驱动把契约外的退出码原样放过去（`2` 那道判据形同虚设） | 1 条 | **1 条** | 相符 |
| `X2` | 没测到·不许折 | 端到端把「没跑完」判成「没达到预期」（`rc != 0` 排到前面） | 1 条 | **1 条** | 相符 |
| `X3` | 没测到·不许折 | 对账时不一致就不再把「抽不出来」升到 `2` | 1 条 | **1 条** | 相符 |
| `X4` | 没测到·不许折 | 对账的收尾退回 `elif`（两件事只能说出前一件） | 1 条 | **1 条** | 相符 |
| `X5` | 没测到·不许折 | 产物那一栏又抄了一份 `0/1/2 → 措辞`（打屏与产物分家） | 1 条 | **1 条** | 相符 |
| `X6` | 没测到·不许折 | 裁决不再查形状（「是 JSON 但结构不对」重新变成 traceback） | 1 条 | **1 条** | 相符 |
| `W1` | 展示层 | 展示层把「不可判定」印成「否决」（三态在最后一米被折成两态） | 2 条 | **2 条** | 相符 |
| `W2` | 展示层 | 展示层的闸不认 falsifier 的 `kind`（表外的种类到渲染那一刻就是 `KeyError`） | 1 条 | **1 条** | 相符 |
| `W3` | 展示层 | 展示层的闸不核用例的 `moved`（落不到任何一格的用例会从页面上静默消失） | 1 条 | **1 条** | 相符 |
| `W4` | 展示层 | 展示层的闸退回原样（判据行的 `what` / `check` 又不核了） | 1 条 | **1 条** | 相符 |
| `W5` | 展示层 | 展示层把渲染中途撞上的形状错又甩成 traceback（退 `1` —— 看着像「发现了一处折合」） | 1 条 | **1 条** | 相符 |
| `W6` | 展示层 | 展示层只说一个数（一例落两格时，页面上不再交代条目数与例数是两个数） | 1 条 | **1 条** | 相符 |
| `T1` | 读数指纹 | 空的外部目录也算有表（仓库内那份编码表被一个空目录绕过去） | 3 条 | **3 条** | 相符 |
| `T2` | 读数指纹 | 外部表只验在不在、不验内容（同名错表顶掉仓库副本） | 1 条 | **1 条** | 相符 |
| `R1` | 读数指纹 | 开始/结束双哈希的门焊成恒真（报告不成立也照常出有效指纹） | 3 条 | **3 条** | 相符 |
| `M1` | 阴性对照 | 判据退回「数红条」：基线红的是 X、这轮多红 Y 也会被减成 0 | 1 条 | **1 条** | 相符 |
| `K0` | 阴性对照 | 语义上什么都不改（只在 `STEP` 那行尾加一句注释） | 0 条 | **0 条** | 相符 |

共 **52** 处变异，其中 **52** 处的实测与声明相符。

## 逐条明细

每条的「改了什么」是**逐字节替换**（`old` → `new`），跑完立刻按字节还原。

`C6` 那条的 `+` 行被**刻意屏蔽**成上面那个占位符：那个写法一旦抄进这份报告，**报告自己就会被 `test_no_known_misquote_survives_in_our_materials` 抓红**（理由和 `README.md` 里不抄第二遍是同一条）。要看原样 —— 连同那个字面量本身 —— 去 `mutations_report.json`：后缀 `.json` 不在那条扫描的范围里。

### `G1` · 判据的边界写成 `>=`（顶格的消息会被误判成超限）

- 组：守卫　目标文件：`verification/tests/test_camel_guards.py`
- 声明：README「守卫：两个方向都要成立」：八处变异都变红
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 260 条、跳过 55 条，退出码 1，31.65s
- 改：`camel_guards.py`

  ```diff
  -     if own_tokens > limit:
  +     if own_tokens >= limit:
  ```

- 红掉的用例（全部）：

  - `test_boundary_is_strict_greater_not_greater_equal`

<details><summary>原样输出（末 12 行）</summary>

```
..........s..........sssssss...sssss..........F......................... [ 22%]
....................................ssssssss............................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s...................................... [ 91%]
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_camel_guards.py::test_boundary_is_strict_greater_not_greater_equal - assert 0 == 1
1 failed, 260 passed, 55 skipped in 29.80s
```

</details>

### `G2` · 整个守卫变成空操作（开头就把活原样交回原方法）

- 组：守卫　目标文件：`verification/tests/test_camel_guards.py`
- 声明：README「守卫：两个方向都要成立」：八处变异都变红
- 实测：**新增红 13 条**（目标文件）、整轮新增 13 条、绿 248 条、跳过 55 条，退出码 1，31.68s
- 改：`camel_guards.py`

  ```diff
  -     """替换 `ChatAgent.update_memory` 的那个函数。两个开关在这里读。"""
  -     original = _state["original"]
  +     """替换 `ChatAgent.update_memory` 的那个函数。两个开关在这里读。"""
  +     original = _state["original"]
  +     return original(self, message, role, timestamp)  # 变异：空操作
  ```

- 红掉的用例（全部）：

  - `test_install_is_idempotent`
  - `test_uninstall_restores_original_and_clears_counters`
  - `test_whole_write_when_message_fits`
  - `test_hands_back_when_message_itself_exceeds_limit`
  - `test_boundary_is_strict_greater_not_greater_equal`
  - `test_hands_back_pushes_clock_when_over_limit`
  - `test_hands_back_pushes_clock_when_tokens_uncomputable`
  - `test_hands_back_supplies_value_when_caller_gave_none`
  - `test_slicing_on_timestamp_off_leaves_timestamps_untouched`
  - `test_timestamp_on_slicing_off_only_moves_the_clock`
  - `test_timestamp_is_strictly_increasing_across_calls`
  - `test_explicit_pair_is_pushed_apart_but_not_counted`
  - `test_timestamp_pushed_counts_only_our_own_reads`

<details><summary>原样输出（末 12 行）</summary>

```
FAILED verification/tests/test_camel_guards.py::test_slicing_on_timestamp_off_leaves_timestamps_untouched - assert 0 == 1
FAILED verification/tests/test_camel_guards.py::test_timestamp_on_slicing_off_only_moves_the_clock - AssertionError: 第二条没被推开 —— 同拍碰撞没被修掉
assert 1234.0 >= ((1234.0 + 0.001) - 1e-09)
 +  where 0.001 = G.STEP
FAILED verification/tests/test_camel_guards.py::test_timestamp_is_strictly_increasing_across_calls - AssertionError: 1794473920.0474844 → 1794473920.0474844 没拉开一个步长
assert 1794473920.0474844 >= (1794473920.0474844 + 0.001)
 +  where 0.001 = G.STEP
FAILED verification/tests/test_camel_guards.py::test_explicit_pair_is_pushed_apart_but_not_counted - AssertionError: 回执没被推得足够远
assert (1000.000001 - 1000.0) >= (0.001 - 1e-09)
 +  where 0.001 = G.STEP
FAILED verification/tests/test_camel_guards.py::test_timestamp_pushed_counts_only_our_own_reads - assert 0 == 1
13 failed, 248 passed, 55 skipped in 29.82s
```

</details>

### `G3` · 变成「一律不切」（该切的那条路被永远关掉）

- 组：守卫　目标文件：`verification/tests/test_camel_guards.py`
- 声明：README「守卫：两个方向都要成立」：八处变异都变红
- 实测：**新增红 4 条**（目标文件）、整轮新增 4 条、绿 257 条、跳过 55 条，退出码 1，33.13s
- 改：`camel_guards.py`

  ```diff
  -     if own_tokens > limit:
  +     if False:
  ```

- 红掉的用例（全部）：

  - `test_hands_back_when_message_itself_exceeds_limit`
  - `test_boundary_is_strict_greater_not_greater_equal`
  - `test_hands_back_pushes_clock_when_over_limit`
  - `test_hands_back_supplies_value_when_caller_gave_none`

<details><summary>原样输出（末 12 行）</summary>

```
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_camel_guards.py::test_hands_back_when_message_itself_exceeds_limit - assert 0 == 1
FAILED verification/tests/test_camel_guards.py::test_boundary_is_strict_greater_not_greater_equal - assert 0 == 1
FAILED verification/tests/test_camel_guards.py::test_hands_back_pushes_clock_when_over_limit - AssertionError: 这一档本该走回退支
assert 0 == 3
 +  where 0 = len([])
FAILED verification/tests/test_camel_guards.py::test_hands_back_supplies_value_when_caller_gave_none - AssertionError: 这一档本该走回退支
assert 0 == 1
 +  where 0 = len([])
 +    where [] = <test_camel_guards.stand_in.<locals>._StandIn object at 0x0000015C4E0BEF90>.seen
4 failed, 257 passed, 55 skipped in 31.12s
```

</details>

### `G4` · 逻辑步长调到比 camel 那个 `1e-6` 还细

- 组：守卫　目标文件：`verification/tests/test_camel_guards.py`
- 声明：README「守卫：两个方向都要成立」：八处变异都变红
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 260 条、跳过 55 条，退出码 1，37.64s
- 改：`camel_guards.py`

  ```diff
  - STEP = 1e-3
  + STEP = 1e-7
  ```

- 红掉的用例（全部）：

  - `test_step_is_larger_than_camels_offset`

<details><summary>原样输出（末 12 行）</summary>

```
..........s..........sssssss...sssss.......................F............ [ 22%]
....................................ssssssss............................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s...................................... [ 91%]
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_camel_guards.py::test_step_is_larger_than_camels_offset - assert 1e-07 > (1e-06 * 100)
 +  where 1e-07 = G.STEP
1 failed, 260 passed, 55 skipped in 35.63s
```

</details>

### `G5` · 时间戳不再往后推（拿掉严格递增那一步）

- 组：守卫　目标文件：`verification/tests/test_camel_guards.py`
- 声明：README「守卫：两个方向都要成立」：八处变异都变红
- 实测：**新增红 4 条**（目标文件）、整轮新增 4 条、绿 257 条、跳过 55 条，退出码 1，37.06s
- 改：`camel_guards.py`

  ```diff
  -     if last is not None and value < last + STEP:
  -         value = last + STEP
  -     agent._ts_guard_last = value
  +     agent._ts_guard_last = value
  ```

- 红掉的用例（全部）：

  - `test_timestamp_on_slicing_off_only_moves_the_clock`
  - `test_timestamp_is_strictly_increasing_across_calls`
  - `test_explicit_pair_is_pushed_apart_but_not_counted`
  - `test_timestamp_pushed_counts_only_our_own_reads`

<details><summary>原样输出（末 12 行）</summary>

```
FAILED verification/tests/test_camel_guards.py::test_timestamp_on_slicing_off_only_moves_the_clock - AssertionError: 第二条没被推开 —— 同拍碰撞没被修掉
assert 1234.0 >= ((1234.0 + 0.001) - 1e-09)
 +  where 0.001 = G.STEP
FAILED verification/tests/test_camel_guards.py::test_timestamp_is_strictly_increasing_across_calls - AssertionError: 1794474023.0454552 → 1794474023.0454552 没拉开一个步长
assert 1794474023.0454552 >= (1794474023.0454552 + 0.001)
 +  where 0.001 = G.STEP
FAILED verification/tests/test_camel_guards.py::test_explicit_pair_is_pushed_apart_but_not_counted - AssertionError: 回执没被推得足够远
assert (1000.000001 - 1000.0) >= (0.001 - 1e-09)
 +  where 0.001 = G.STEP
FAILED verification/tests/test_camel_guards.py::test_timestamp_pushed_counts_only_our_own_reads - assert 1794474023.062748 >= (1794475023.062748 + 0.001)
 +  where 0.001 = G.STEP
4 failed, 257 passed, 55 skipped in 34.99s
```

</details>

### `G6` · 去掉兜底（算不出 token 时不再交回原方法，直接抛）

- 组：守卫　目标文件：`verification/tests/test_camel_guards.py`
- 声明：README「守卫：两个方向都要成立」：八处变异都变红
- 实测：**新增红 2 条**（目标文件）、整轮新增 2 条、绿 259 条、跳过 55 条，退出码 1，37.23s
- 改：`camel_guards.py`

  ```diff
  -     except Exception:  # noqa: BLE001
  -         # 算不出来就别自作聪明 —— 交回原方法。**但交回的时间戳仍要推过**：
  -         # 回退不等于可以绕开时钟不变式（见 `_hand_back_timestamp`）。
  -         if _state["timestamp"]:
  -             return original(self, message, role,
  -                             _hand_back_timestamp(
  -                                 self, timestamp,
  -                                 content=getattr(message, "content", None)))
  -         return original(self, message, role, timestamp)
  +     except Exception:  # noqa: BLE001
  +         raise
  ```

- 红掉的用例（全部）：

  - `test_hands_back_when_tokens_cannot_be_counted`
  - `test_hands_back_pushes_clock_when_tokens_uncomputable`

<details><summary>原样输出（末 12 行）</summary>

```
..........s..........sssssss...sssss...........F.F...................... [ 22%]
....................................ssssssss............................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s...................................... [ 91%]
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_camel_guards.py::test_hands_back_when_tokens_cannot_be_counted - RuntimeError: 模拟取不到 context creator
FAILED verification/tests/test_camel_guards.py::test_hands_back_pushes_clock_when_tokens_uncomputable - RuntimeError: 模拟取不到 context creator
2 failed, 259 passed, 55 skipped in 35.20s
```

</details>

### `G7` · `install` 不再幂等（第二次调用会套第二层补丁）

- 组：守卫　目标文件：`verification/tests/test_camel_guards.py`
- 声明：README「守卫：两个方向都要成立」：八处变异都变红
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 260 条、跳过 55 条，退出码 1，39.68s
- 改：`camel_guards.py`

  ```diff
  -     if _state["patched"]:
  -         _state["slicing"] = slicing
  -         _state["timestamp"] = timestamp
  -         return _state
  +     if False:
  +         _state["slicing"] = slicing
  +         _state["timestamp"] = timestamp
  +         return _state
  ```

- 红掉的用例（全部）：

  - `test_install_is_idempotent`

<details><summary>原样输出（末 12 行）</summary>

```
..........s..........sssssss...sssss...F................................ [ 22%]
....................................ssssssss............................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s...................................... [ 91%]
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_camel_guards.py::test_install_is_idempotent - assert <function _dispatch at 0x00000193C62BFA60> is <function stand_in.<locals>._StandIn.update_memory at 0x00000193C89B5760>
1 failed, 260 passed, 55 skipped in 37.60s
```

</details>

### `G8` · 推了游标但不交回（回退支仍把原时间戳交给原方法）

- 组：守卫　目标文件：`verification/tests/test_camel_guards.py`
- 声明：README「守卫：两个方向都要成立」：八处变异都变红
- 实测：**新增红 3 条**（目标文件）、整轮新增 3 条、绿 258 条、跳过 55 条，退出码 1，35.55s
- 改：`camel_guards.py`

  ```diff
  -     agent._ts_guard_last = value + span + STEP
  -     return value
  +     agent._ts_guard_last = value + span + STEP
  +     return timestamp
  ```

- 红掉的用例（全部）：

  - `test_hands_back_pushes_clock_when_over_limit`
  - `test_hands_back_pushes_clock_when_tokens_uncomputable`
  - `test_hands_back_supplies_value_when_caller_gave_none`

<details><summary>原样输出（末 12 行）</summary>

```
..........s..........sssssss...sssss............FFF..................... [ 22%]
....................................ssssssss............................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s...................................... [ 91%]
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_camel_guards.py::test_hands_back_pushes_clock_when_over_limit - AssertionError: 第一条不该被动 —— 它是往后推，不是替换
assert None == 1700000000.0
FAILED verification/tests/test_camel_guards.py::test_hands_back_pushes_clock_when_tokens_uncomputable - assert None == 1700000000.0
FAILED verification/tests/test_camel_guards.py::test_hands_back_supplies_value_when_caller_gave_none - AssertionError: 回退支把 None 原样交回去了
assert None is not None
3 failed, 258 passed, 55 skipped in 33.50s
```

</details>

### `V1` · 判词写死（直接把结论摆在预期那一侧，不再由读数算）

- 组：判词　目标文件：`verification/tests/test_repro_verdicts.py`
- 声明：README「判词」：判词写死 → 红 16 条
- 实测：**新增红 16 条**（目标文件）、整轮新增 16 条、绿 245 条、跳过 55 条，退出码 1，33.22s
- 改：`repro_02_timestamp.py`

  ```diff
  -     same = (gap / tick) < 1.0 if tick > 0 else False
  +     same = want_same
  ```

- 红掉的用例（前 15 条，共 16 条）：

  - `test_verdict_never_contradicts_its_own_numbers[True-0.0004-0.0004]`
  - `test_verdict_never_contradicts_its_own_numbers[True-0.00041-0.0004]`
  - `test_verdict_never_contradicts_its_own_numbers[True-0.001-0.0004]`
  - `test_verdict_never_contradicts_its_own_numbers[True-0.01-0.0004]`
  - `test_verdict_never_contradicts_its_own_numbers[True-0.12-0.0004]`
  - `test_verdict_never_contradicts_its_own_numbers[True-0.00101-0.001]`
  - `test_verdict_never_contradicts_its_own_numbers[True-0.00335-0.000302]`
  - `test_verdict_never_contradicts_its_own_numbers[True-0.0038-0.00034100000000000005]`
  - `test_verdict_never_contradicts_its_own_numbers[False-0.0-0.0004]`
  - `test_verdict_never_contradicts_its_own_numbers[False-0.0001-0.0004]`
  - `test_verdict_never_contradicts_its_own_numbers[False-0.00039000000000000005-0.0004]`
  - `test_verdict_never_contradicts_its_own_numbers[False-0.0-0.001]`
  - `test_verdict_never_contradicts_its_own_numbers[False-0.00099-0.001]`
  - `test_the_actual_regression_is_reported_not_smoothed`
  - `test_opposite_direction_of_surprise_is_also_reported`

<details><summary>原样输出（末 12 行）</summary>

```
assert not True
 +  where True = _asserts_cross('跨拍 → 误打误撞免疫')
FAILED verification/tests/test_repro_verdicts.py::test_verdict_never_contradicts_its_own_numbers[False-0.00099-0.001] - AssertionError: gap=0.00099 < tick=0.001 却是「跨拍」判词：'跨拍 → 误打误撞免疫'
assert not True
 +  where True = _asserts_cross('跨拍 → 误打误撞免疫')
FAILED verification/tests/test_repro_verdicts.py::test_the_actual_regression_is_reported_not_smoothed - AssertionError: 没报出与预期不符：'同拍 → 碰撞才发生'
assert '与预期相反' in '同拍 → 碰撞才发生'
FAILED verification/tests/test_repro_verdicts.py::test_opposite_direction_of_surprise_is_also_reported - AssertionError: 没报出与预期不符：'跨拍 → 误打误撞免疫'
assert '与预期相反' in '跨拍 → 误打误撞免疫'
FAILED verification/tests/test_repro_verdicts.py::test_zero_tick_does_not_explode - AssertionError: 量不到一拍却当成符合预期：'同拍 → 碰撞才发生'
assert '与预期相反' in '同拍 → 碰撞才发生'
16 failed, 245 passed, 55 skipped in 31.35s
```

</details>

### `V2` · 判据的 `<` 写成 `<=`（`gap == tick` 会被算成同一拍）

- 组：判词　目标文件：`verification/tests/test_repro_verdicts.py`
- 声明：README「判词」：`<` 写成 `<=` → 红 3 条
- 实测：**新增红 3 条**（目标文件）、整轮新增 3 条、绿 258 条、跳过 55 条，退出码 1，33.18s
- 改：`repro_02_timestamp.py`

  ```diff
  -     same = (gap / tick) < 1.0 if tick > 0 else False
  +     same = (gap / tick) <= 1.0 if tick > 0 else False
  ```

- 红掉的用例（全部）：

  - `test_verdict_never_contradicts_its_own_numbers[True-0.0004-0.0004]`
  - `test_verdict_never_contradicts_its_own_numbers[False-0.0004-0.0004]`
  - `test_boundary_gap_equal_to_tick_counts_as_crossed`

<details><summary>原样输出（末 12 行）</summary>

```
=========================== short test summary info ===========================
FAILED verification/tests/test_repro_verdicts.py::test_verdict_never_contradicts_its_own_numbers[True-0.0004-0.0004] - AssertionError: gap=0.0004 >= tick=0.0004 却是「同拍」判词：'同拍 → 碰撞才发生'
assert not True
 +  where True = _asserts_same('同拍 → 碰撞才发生')
FAILED verification/tests/test_repro_verdicts.py::test_verdict_never_contradicts_its_own_numbers[False-0.0004-0.0004] - AssertionError: gap=0.0004 >= tick=0.0004 却是「同拍」判词：'**同一拍**（与预期相反）'
assert not True
 +  where True = _asserts_same('**同一拍**（与预期相反）')
FAILED verification/tests/test_repro_verdicts.py::test_boundary_gap_equal_to_tick_counts_as_crossed - AssertionError: assert '**同一拍**（与预期相反）' == '跨拍 → 误打误撞免疫'
  
  - 跨拍 → 误打误撞免疫
  + **同一拍**（与预期相反）
3 failed, 258 passed, 55 skipped in 31.28s
```

</details>

### `V3` · 去掉「与预期相反」那一支（与预期不符时折回预期那一侧的话术）

- 组：判词　目标文件：`verification/tests/test_repro_verdicts.py`
- 声明：README「判词」：去掉「与预期相反」那一支 → 红 3 条
- 实测：**新增红 3 条**（目标文件）、整轮新增 3 条、绿 258 条、跳过 55 条，退出码 1，32.9s
- 改：`repro_02_timestamp.py`

  ```diff
  -     n = gap / tick if tick > 0 else float("nan")
  -     return ("**同一拍**（与预期相反）" if same
  -             else f"**跨到 {n:,.0f} 拍**（与预期相反）")
  +     return ("同拍 → 碰撞才发生" if same
  +             else "跨拍 → 误打误撞免疫")
  ```

- 红掉的用例（全部）：

  - `test_the_actual_regression_is_reported_not_smoothed`
  - `test_opposite_direction_of_surprise_is_also_reported`
  - `test_zero_tick_does_not_explode`

<details><summary>原样输出（末 12 行）</summary>

```
....................................ssssssss............................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.FF...F..........................s...................................... [ 91%]
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_repro_verdicts.py::test_the_actual_regression_is_reported_not_smoothed - AssertionError: 没报出与预期不符：'跨拍 → 误打误撞免疫'
assert '与预期相反' in '跨拍 → 误打误撞免疫'
FAILED verification/tests/test_repro_verdicts.py::test_opposite_direction_of_surprise_is_also_reported - AssertionError: 没报出与预期不符：'同拍 → 碰撞才发生'
assert '与预期相反' in '同拍 → 碰撞才发生'
FAILED verification/tests/test_repro_verdicts.py::test_zero_tick_does_not_explode - AssertionError: 量不到一拍却当成符合预期：'跨拍 → 误打误撞免疫'
assert '与预期相反' in '跨拍 → 误打误撞免疫'
3 failed, 258 passed, 55 skipped in 31.00s
```

</details>

### `C1` · 行号错开一格（933 → 934）

- 组：引文·上半　目标文件：`verification/tests/test_citations.py`
- 声明：README「引文：文档里的行号不许腐烂」：上半五处变异都红
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 260 条、跳过 55 条，退出码 1，32.81s
- 改：`test_citations.py`

  ```diff
  - ("camel.agents.chat_agent", 933,
  + ("camel.agents.chat_agent", 934,
  ```

- 红掉的用例（全部）：

  - `test_cited_line_still_says_what_we_say_it_says[camel.agents.chat_agent-934-base_chunk_size`

<details><summary>原样输出（末 12 行）</summary>

```
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s...................................... [ 91%]
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_citations.py::test_cited_line_still_says_what_we_say_it_says[camel.agents.chat_agent-934-base_chunk_size = max(1, remaining_budget) // 10-camel_guards / README \xa7\u2460\uff1a\u6b8b\u4f59\u9884\u7b97\u5148\u88ab //10 \u780d\u4e00\u5200] - AssertionError: 
  camel.agents.chat_agent:934 对不上了。
    期望含：'base_chunk_size = max(1, remaining_budget) // 10'
    实为　：''
    这条引文支持的是：camel_guards / README §①：残余预算先被 //10 砍一刀
    **先看那个论断还成不成立**，别只把期望值改成漂移后的样子。
assert 'base_chunk_size = max(1, remaining_budget) // 10' in ''
1 failed, 260 passed, 55 skipped in 30.96s
```

</details>

### `C2` · 引一个越界的行号（884 → 999999）

- 组：引文·上半　目标文件：`verification/tests/test_citations.py`
- 声明：README「引文：文档里的行号不许腐烂」：上半五处变异都红
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 260 条、跳过 55 条，退出码 1，33.72s
- 改：`test_citations.py`

  ```diff
  - ("camel.agents.chat_agent", 884,
  + ("camel.agents.chat_agent", 999999,
  ```

- 红掉的用例（全部）：

  - `test_cited_line_still_says_what_we_say_it_says[camel.agents.chat_agent-999999-remaining_budget`

<details><summary>原样输出（末 12 行）</summary>

```
..........s..........sssssss...sssss................................F... [ 22%]
....................................ssssssss............................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s...................................... [ 91%]
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_citations.py::test_cited_line_still_says_what_we_say_it_says[camel.agents.chat_agent-999999-remaining_budget = max(0, token_limit - ctx_tokens)-README \xa7\u2460 / camel_guards\uff1a\u6b8b\u4f59\u9884\u7b97\u7528\u7684\u662f**\u622a\u65ad\u540e**\u7684 ctx_tokens] - AssertionError: camel.agents.chat_agent 只有 4385 行，却引了第 999999 行 —— 上游大概动过了。这条引文支持的是：README §① / camel_guards：残余预算用的是**截断后**的 ctx_tokens
assert 999999 <= 4385
 +  where 4385 = len(['# ========= Copyright 2023-2024 @ CAMEL-AI.org. All Rights Reserved. =========', '# Licensed under the Apache Licens...e License.', '# You may obtain a copy of the License at', '#', '#     http://www.apache.org/licenses/LICENSE-2.0', ...])
1 failed, 260 passed, 55 skipped in 31.81s
```

</details>

### `C3` · 换成那一行没有的片段（`// 10` 写成 `// 100`）

- 组：引文·上半　目标文件：`verification/tests/test_citations.py`
- 声明：README「引文：文档里的行号不许腐烂」：上半五处变异都红
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 260 条、跳过 55 条，退出码 1，34.14s
- 改：`test_citations.py`

  ```diff
  - "base_chunk_size = max(1, remaining_budget) // 10",
  + "base_chunk_size = max(1, remaining_budget) // 100",
  ```

- 红掉的用例（全部）：

  - `test_cited_line_still_says_what_we_say_it_says[camel.agents.chat_agent-933-base_chunk_size`

<details><summary>原样输出（末 12 行）</summary>

```
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s...................................... [ 91%]
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_citations.py::test_cited_line_still_says_what_we_say_it_says[camel.agents.chat_agent-933-base_chunk_size = max(1, remaining_budget) // 100-camel_guards / README \xa7\u2460\uff1a\u6b8b\u4f59\u9884\u7b97\u5148\u88ab //10 \u780d\u4e00\u5200] - AssertionError: 
  camel.agents.chat_agent:933 对不上了。
    期望含：'base_chunk_size = max(1, remaining_budget) // 100'
    实为　：'base_chunk_size = max(1, remaining_budget) // 10'
    这条引文支持的是：camel_guards / README §①：残余预算先被 //10 砍一刀
    **先看那个论断还成不成立**，别只把期望值改成漂移后的样子。
assert 'base_chunk_size = max(1, remaining_budget) // 100' in '        base_chunk_size = max(1, remaining_budget) // 10'
1 failed, 260 passed, 55 skipped in 32.23s
```

</details>

### `C4` · 引一个不存在的模块（`camel.memories.base` → `..._missing`）

- 组：引文·上半　目标文件：`verification/tests/test_citations.py`
- 声明：README「引文：文档里的行号不许腐烂」：上半五处变异都红
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 259 条、跳过 56 条，退出码 1，34.05s
- 改：`test_citations.py`

  ```diff
  - ("camel.memories.base", 143,
  + ("camel.memories.base_missing", 143,
  ```

- 红掉的用例（全部）：

  - `test_every_citation_module_is_reachable`

<details><summary>原样输出（末 12 行）</summary>

```
..........s..........sssssss...sssss.................................... [ 22%]
.........s...........F..............ssssssss............................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s...................................... [ 91%]
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_citations.py::test_every_citation_module_is_reachable - AssertionError: 这些模块取不到，对应的引文等于没核：['camel.memories.base_missing']
assert not ['camel.memories.base_missing']
1 failed, 259 passed, 56 skipped in 32.16s
```

</details>

### `C5` · 同一行引两遍（把 env:55 那条改成 env:193，片段也跟着改成 193 行的）

- 组：引文·上半　目标文件：`verification/tests/test_citations.py`
- 声明：README「引文：文档里的行号不许腐烂」：上半五处变异都红
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 260 条、跳过 55 条，退出码 1，34.68s
- 改：`test_citations.py`

  ```diff
  - ("oasis.environment.env", 55,
  + ("oasis.environment.env", 193,
  ```

- 改：`test_citations.py`

  ```diff
  - "semaphore: int = 128",
  + "await asyncio.gather(*tasks)",
  ```

- 红掉的用例（全部）：

  - `test_no_duplicate_citations`

<details><summary>原样输出（末 12 行）</summary>

```
..........s..........sssssss...sssss.................................... [ 22%]
......................F.............ssssssss............................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s...................................... [ 91%]
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_citations.py::test_no_duplicate_citations - AssertionError: 重复的引文：{('oasis.environment.env', 193)}
assert not {('oasis.environment.env', 193)}
1 failed, 260 passed, 55 skipped in 32.81s
```

</details>

### `C6` · 把那个错引写法**植回 `camel_guards.py`**，看扫描抓不抓

- 组：引文·下半　目标文件：`verification/tests/test_citations.py`
- 声明：README「引文」：下半把那个写法植回 `camel_guards.py`，当场红
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 260 条、跳过 55 条，退出码 1，33.9s
- 改：`camel_guards.py`

  ```diff
  - base_chunk_size - prefix_token_len
  + ＜那个被引错的字面量，本报告不抄＞
  ```

- 红掉的用例（全部）：

  - `test_no_known_misquote_survives_in_our_materials[base_chunk_size\\s*-\\s*12-base_chunk_size`

<details><summary>原样输出（末 12 行）</summary>

```
.........................F..........ssssssss............................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s...................................... [ 91%]
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_citations.py::test_no_known_misquote_survives_in_our_materials[base_chunk_size\\s*-\\s*12-base_chunk_size - prefix_token_len\uff08948 \u884c\uff1b\u90a3\u4e2a\u51cf\u6570\u662f 943 \u884c**\u91cf**\u51fa\u6765\u7684\uff09-\u628a\u300c\u524d\u7f00\u957f\u5ea6\u300d\u8fd9\u4e2a\u5f53\u573a\u91cf\u51fa\u6765\u7684\u503c\u5199\u6b7b\u6210\u4e86\u5b57\u9762\u91cf 12\uff0c\u8fd8\u6807\u6210 948 \u884c\u7684\u539f\u6587 \u2014\u2014 \u6570\u503c\u4e0a\u5bf9\uff08gpt-4o-mini \u4e0b\u6070\u597d\u662f 12\uff09\uff0c**\u5f15\u6587\u4e0a\u9519**\uff1a\u6362\u4e2a\u5206\u8bcd\u5668\u5c31\u4e0d\u662f 12] - AssertionError: 
  材料里出现了已知的错引：
    camel_guards.py:14  `chunk_body_limit = max(1, ＜那个被引错的字面量，本报告不抄＞)`（948 行，
    正确的写法：base_chunk_size - prefix_token_len（948 行；那个减数是 943 行**量**出来的）
    出过的事：把「前缀长度」这个当场量出来的值写死成了字面量 12，还标成 948 行的原文 —— 数值上对（gpt-4o-mini 下恰好是 12），**引文上错**：换个分词器就不是 12
assert not ['camel_guards.py:14  `chunk_body_limit = max(1, ＜那个被引错的字面量，本报告不抄＞)`（948 行，']
1 failed, 260 passed, 55 skipped in 32.01s
```

</details>

### `C7` · 逐字块里的行号错开一格（886 → 885，那一行是空行）

- 组：引文·逐字块　目标文件：`verification/tests/test_citations.py`
- 声明：README「引文」：标了行号的逐字块，行号错了当场红
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 260 条、跳过 55 条，退出码 1，33.84s
- 改：`README.md`

  ```diff
  - if current_tokens <= remaining_budget:                         # 886
  + if current_tokens <= remaining_budget:                         # 885
  ```

- 红掉的用例（全部）：

  - `test_verbatim_blocks_match_upstream_line_for_line[-camel.agents.chat_agent-0]`

<details><summary>原样输出（末 12 行）</summary>

```
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_citations.py::test_verbatim_blocks_match_upstream_line_for_line[-camel.agents.chat_agent-0] - AssertionError: 
  README.md 里贴着的那一行，和 camel.agents.chat_agent:885 **对不上**。
    材料里：'if current_tokens <= remaining_budget:'
    上游是：''
    这一行既不在 `CITATIONS` 表里、也不在 `KNOWN_MISQUOTES` 里，只有这个逐字块在管它。
    **先看那段话的论断还成不成立**；要是这行本来就不是原文，把它改成原文，别把行号改成让它对得上的样子。
assert 'if current_t...ining_budget:' == ''
  
  + if current_tokens <= remaining_budget:
1 failed, 260 passed, 55 skipped in 31.81s
```

</details>

### `J1` · 贴界退化成「碰过这一臂或这一量的格子都算贴界」（一格贴界，整行整列降级）

- 组：裁决　目标文件：`verification/tests/test_adjudicate.py`
- 声明：README「裁决：三种结果不是两种」：贴界按单元格判，退化成乘积当场红
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 260 条、跳过 55 条，退出码 1，33.43s
- 改：`adjudicate.py`

  ```diff
  -         hits = [f"{a}.{m}" for a, m in c["operands"] if (a, m) in railed]
  +         _arms = {a for a, _ in railed}
  +         _mets = {m for _, m in railed}
  +         hits = [f"{a}.{m}" for a, m in c["operands"]
  +                 if (a, m) in railed or a in _arms or m in _mets]
  ```

- 红掉的用例（全部）：

  - `test_railing_is_judged_per_cell_not_by_the_product_of_two_sets`

<details><summary>原样输出（末 12 行）</summary>

```
.F........s..........sssssss...sssss.................................... [ 22%]
....................................ssssssss............................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s...................................... [ 91%]
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_adjudicate.py::test_railing_is_judged_per_cell_not_by_the_product_of_two_sets - KeyError: ('B', 'x')
1 failed, 260 passed, 55 skipped in 31.58s
```

</details>

### `J2` · 把「缺读数」折进「否决」—— 正是本装置抓别人的那件事

- 组：裁决·缺读数　目标文件：`verification/tests/test_adjudicate.py`
- 声明：README「裁决」：缺读数判不可判定，折进「否决」当场红
- 实测：**新增红 4 条**（目标文件）、整轮新增 5 条、绿 256 条、跳过 55 条，退出码 1，33.65s
- 改：`adjudicate.py`

  ```diff
  - "check": c["check"], "verdict": UNDECIDED,
  + "check": c["check"], "verdict": FAIL_,  # 变异：没测到就当没通过
  ```

- 红掉的用例（全部）：

  - `test_the_first_real_assertion_is_not_vacuous`
  - `test_a_reading_that_is_not_there_is_undecided_not_failed`
  - `test_every_falsifier_result_the_checker_can_emit_is_renderable`
  - `test_undecided_is_not_counted_as_vacuous`
  - `test_a_missing_e2e_report_makes_that_layer_undecided`

<details><summary>原样输出（末 12 行）</summary>

```
        'T23': '可翻面',
    }
FAILED verification/tests/test_adjudicate.py::test_undecided_is_not_counted_as_vacuous - AssertionError: assert '否决' == '不可判定'
  
  - 不可判定
  + 否决
FAILED verification/tests/test_e2e_stub.py::test_a_missing_e2e_report_makes_that_layer_undecided - AssertionError: E1 在没跑端到端时没判不可判定
assert '否决' == '不可判定'
  
  - 不可判定
  + 否决
5 failed, 256 passed, 55 skipped in 31.71s
```

</details>

### `J3` · falsifier 只查在不在，**不实例化** —— 于是它永远「翻得动」

- 组：裁决·恒真　目标文件：`verification/tests/test_adjudicate.py`
- 声明：README「裁决·非空泛」：falsifier 必须实例化，只查在不在当场红
- 实测：**新增红 2 条**（目标文件）、整轮新增 2 条、绿 259 条、跳过 55 条，退出码 1，35.38s
- 改：`adjudicate.py`

  ```diff
  -             if after[cid]["verdict"] != base[cid]["verdict"]:
  +             if True:  # 变异：声明了就算数，不去试它
  ```

- 红掉的用例（全部）：

  - `test_a_claim_that_no_single_change_can_flip_is_not_trusted`
  - `test_a_claim_whose_falsifier_does_not_bite_is_vacuous`

<details><summary>原样输出（末 12 行）</summary>

```
  
  Full diff:
    [
  -     '恒真',
  +     '可翻面',
    ]
FAILED verification/tests/test_adjudicate.py::test_a_claim_whose_falsifier_does_not_bite_is_vacuous - AssertionError: 把 B.z 改成 0 → 由 通过 变为 通过
assert '可翻面' == '恒真'
  
  - 恒真
  + 可翻面
2 failed, 259 passed, 55 skipped in 33.39s
```

</details>

### `J4` · **判据恒真也照退 0** —— 这张表开始装绿

- 组：裁决·恒真　目标文件：`verification/tests/test_adjudicate.py`
- 声明：README「裁决：恒真就不许退 0」：判据恒真时退出码必须非 0
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 260 条、跳过 55 条，退出码 1，34.78s
- 改：`adjudicate.py`

  ```diff
  -         return 1
  -     return 0
  - 
  - 
  - if __name__ == "__main__":
  +         return 0  # 变异：有恒真判据也当表是好的
  +     return 0
  + 
  + 
  + if __name__ == "__main__":
  ```

- 红掉的用例（全部）：

  - `test_a_vacuous_claim_makes_the_table_refuse_to_exit_green`

<details><summary>原样输出（末 12 行）</summary>

```
..........s.........Fsssssss...sssss.................................... [ 22%]
....................................ssssssss............................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s...................................... [ 91%]
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_adjudicate.py::test_a_vacuous_claim_makes_the_table_refuse_to_exit_green - AssertionError: 判据恒真时退出码是 0 —— 该是 1（表生成了，但有东西白写）
assert 0 == 1
1 failed, 260 passed, 55 skipped in 32.87s
```

</details>

### `J5` · **「没测到」退 1**（退成「没达到预期」）—— 正是本装置抓别人的那件事，落在自己身上

- 组：裁决·缺读数　目标文件：`verification/tests/test_adjudicate.py`
- 声明：README「退出码：三种不是两种」：前提不成立退 2，折成 1 当场红
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 260 条、跳过 55 条，退出码 1，34.24s
- 改：`adjudicate.py`

  ```diff
  -         print(f"\n○ 没测到：{e}")
  -         return 2
  +         print(f"\n○ 没测到：{e}")
  +         return 1  # 变异：折成「没达到预期」
  ```

- 红掉的用例（全部）：

  - `test_no_report_is_undecided_and_gets_no_traceback`

<details><summary>原样输出（末 12 行）</summary>

```
..........s......F...sssssss...sssss.................................... [ 22%]
....................................ssssssss............................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s...................................... [ 91%]
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_adjudicate.py::test_no_report_is_undecided_and_gets_no_traceback - AssertionError: 报告不在时退出码是 1 —— 该是「没测到」的 2
assert 1 == 2
1 failed, 260 passed, 55 skipped in 32.31s
```

</details>

### `J6` · **装守卫时不安排落盘** —— 计数照样烂在内存里，一次真跑还是什么都看不见（回到补它之前那个状态）

- 组：守卫·计数落盘　目标文件：`verification/tests/test_camel_guards.py`
- 声明：README「守卫端到端」：装了守卫就得安排落盘，拿掉当场红
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 260 条、跳过 55 条，退出码 1，34.04s
- 改：`camel_guards.py`

  ```diff
  -     _state["patched"] = True
  -     _arrange_counters_dump()
  +     _state["patched"] = True  # 变异：不安排落盘
  ```

- 红掉的用例（全部）：

  - `test_install_arranges_to_dump_counters_at_exit`

<details><summary>原样输出（末 12 行）</summary>

```
  
  Right contains one more item: (<function dump_counters at 0x000001910FD47CE0>, 'somewhere/guard_counters.json')
  
  Full diff:
  + []
  - [
  -     (
  -         <function dump_counters at 0x000001910FD47CE0>,
  -         'somewhere/guard_counters.json',
  -     ),
  - ]
1 failed, 260 passed, 55 skipped in 32.10s
```

</details>

### `J7` · 端到端报告不在时**编一份读数**出来 —— 最容易写下的那种「补全」，而且编完那张表看着更完整

- 组：裁决·端到端　目标文件：`verification/tests/test_e2e_stub.py`
- 声明：README「裁决：三种结果不是两种」：端到端读数缺了要判不可判定，编一份补上当场红
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 260 条、跳过 55 条，退出码 1，35.19s
- 改：`adjudicate.py`

  ```diff
  -     if not path.is_file():
  -         return None
  -     try:
  +     if not path.is_file():
  +         # 变异：没跑过就编一份读数 —— 于是那五条照判「通过」
  +         return {"results": [{"readings": {
  +             "readings": {
  +                 "roomy_e2e": {"written_whole": 1, "still_sliced": 0,
  +                               "timestamp_pushed": 1, "db_posts": 1},
  +                 "bigtext_e2e": {"written_whole": 1, "still_sliced": 1,
  +                                "timestamp_pushed": 0, "db_posts": 1},
  +                 "two_e2e": {"written_whole": 2, "still_sliced": 0,
  +                             "timestamp_pushed": 1, "db_posts": 2}},
  +             "boundaries": []}}]}
  +     try:
  ```

- 红掉的用例（全部）：

  - `test_a_missing_e2e_report_is_none_not_an_exception`

<details><summary>原样输出（末 12 行）</summary>

```
..........s..........sssssss...sssss.................................... [ 22%]
....................................ssssssss......................F..... [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s...................................... [ 91%]
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_e2e_stub.py::test_a_missing_e2e_report_is_none_not_an_exception - AssertionError: assert {'results': [{'readings': {'boundaries': [], 'readings': {'bigtext_e2e': {'db_posts': 1, 'still_sliced': 1, 'timestamp...: 1, 'written_whole': 1}, 'two_e2e': {'db_posts': 2, 'still_sliced': 0, 'timestamp_pushed': 1, 'written_whole': 2}}}}]} is None
 +  where {'results': [{'readings': {'boundaries': [], 'readings': {'bigtext_e2e': {'db_posts': 1, 'still_sliced': 1, 'timestamp...: 1, 'written_whole': 1}, 'two_e2e': {'db_posts': 2, 'still_sliced': 0, 'timestamp_pushed': 1, 'written_whole': 2}}}}]} = <function load_e2e_report at 0x000001F332D33240>((WindowsPath('C:/Users/user/AppData/Local/Temp/pytest-of-user/pytest-2419/test_a_missing_e2e_report_is_n0') / 'nope.json'))
 +    where <function load_e2e_report at 0x000001F332D33240> = A.load_e2e_report
1 failed, 260 passed, 55 skipped in 33.21s
```

</details>

### `P1` · 把 `tiktoken` 的锁定从 `==0.7.0` 放成 `>=0.1`

- 组：环境·版本钉　目标文件：`verification/tests/test_environment_pins.py`
- 声明：环境版本钉：直接依赖被放成开区间 → 当场红
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 268 条、跳过 47 条，退出码 1，38.33s
- 改：`requirements.txt`

  ```diff
  - tiktoken==0.7.0
  + tiktoken>=0.1
  ```

- 红掉的用例（全部）：

  - `test_tiktoken_is_pinned_even_though_it_arrives_transitively`

<details><summary>原样输出（末 12 行）</summary>

```
  
  Full diff:
    [
        (
  -         '==',
  ?          ^
  +         '>=',
  ?          ^
            '0.1',
        ),
    ]
1 failed, 268 passed, 47 skipped in 36.45s
```

</details>

### `D1` · 清单改动表里把一个数目改歪（`requirements.txt` 15 → 16）

- 组：清单·改动表　目标文件：`verification/tests/test_docs_claims.py`
- 声明：清单第一节：改动数目和现场 diff 对不上 → 当场红
- 实测：**新增红 1 条**（目标文件）、整轮新增 2 条、绿 267 条、跳过 47 条，退出码 1，36.14s
- 改：`开源及第三方资源使用清单.md`

  ```diff
  - | 15 行插入 |
  + | 16 行插入 |
  ```

- 红掉的用例（全部）：

  - `test_the_diff_numbers_match_a_live_diff`
  - `test_notice_states_the_same_numbers_as_the_inventory`

<details><summary>原样输出（末 12 行）</summary>

```
.........................................F.............................. [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s............................F......... [ 91%]
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_docs_claims.py::test_the_diff_numbers_match_a_live_diff - AssertionError: 对上游的改动数目对不上了：
    backend/requirements.txt：清单写 16 插入 / 0 删除，现场是 15 插入 / 0 删除
  量法写在表头：`git diff --numstat --ignore-all-space <基线>`。
assert not ['  backend/requirements.txt：清单写 16 插入 / 0 删除，现场是 15 插入 / 0 删除']
FAILED verification/tests/test_upstream_baseline.py::test_notice_states_the_same_numbers_as_the_inventory - AssertionError: 《清单》说 `backend/requirements.txt` 是 `+16`，而 `NOTICE` 里找不到这个数 —— 两份副本分家了，改一处必须改另一处。
assert '`+16`' in 'mirofish-verifiable —— MiroFish 的可验证性 fork\n================================================\n本项目基于开源项目 MiroFish 进行二次...\n\n本仓库另新增一份 `NOTICE`（即本文件）。改动均在本 fork 的工作期内完成（2026-09-16 起）；\n上表「最后改动」一栏是各文件最后一次改动的提交日期（`git log -1 --date=short`）。\n'
2 failed, 267 passed, 47 skipped in 34.23s
```

</details>

### `N1` · 把「这里是不是 git 仓库」那道门焊死（`_is_repo()` 恒为假）

- 组：上游基线　目标文件：`verification/tests/test_upstream_baseline.py`
- 声明：上游基线：门恒假 → 本仓里那条阴性对照当场红（**本仓明明在仓库里，却被判成不是**）
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 256 条、跳过 59 条，退出码 1，31.51s
- 改：`test_upstream_baseline.py`

  ```diff
  -     return out.returncode == 0 and out.stdout.strip() == "true"
  +     return False  # 变异：门永远关着
  ```

- 红掉的用例（全部）：

  - `test_the_repo_check_is_not_vacuous`

<details><summary>原样输出（末 12 行）</summary>

```
..........s..........sssssss...sssss.................................... [ 22%]
....................................ssssssss............................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s........................ssF..ss....... [ 91%]
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_upstream_baseline.py::test_the_repo_check_is_not_vacuous - AssertionError: 本仓（D:\open_source\B-装置\mirofish-verifiable）居然被判成「不是 git 仓库」——那么上面那条祖先检查在**本仓里也永远是跳过的**，等于没跑。
assert False
 +  where False = _is_repo()
1 failed, 256 passed, 59 skipped in 29.62s
```

</details>

### `O1` · 汇总驱动把落点那道门摘了（`--out` 不通也照跑三个复现）

- 组：落点　目标文件：`verification/tests/test_repro_verdicts.py`
- 声明：落点：门被摘掉 → 「坏落点要在动手之前退」当场红
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 260 条、跳过 55 条，退出码 1，75.7s
- 改：`run_all.py`

  ```diff
  -         rc = P.refuse_out_path(f"{args.out}.md", f"{args.out}.json")
  +         rc = None  # 变异：落点这道门形同虚设
  ```

- 红掉的用例（全部）：

  - `test_run_all_refuses_a_bad_out_place_before_running_the_repros`

<details><summary>原样输出（末 12 行）</summary>

```
    
      3/3 条达到预期
      √ 达到预期       对账（两份材料报的是不是同一组数）
    
      以上都是无 LLM 调用、无 API key、结果确定 —— 换台机器结论应当一样。
      （前提是分词器那份静态编码表拿得到 —— 仓库里带了一份，外部缓存有表时让位给外部，两边都没有才要联网下一份。）
      取不到时上面会明确写「没测到」，**不会**把没跑成的记成「没达到预期」 —— 缺读数不是结论。
      对账单独列在汇总里，**不并进那个 x/3** —— 它不是第四个复现，
      它管的是「装置和准备发出去的草稿有没有走岔」。
    
    ○ 没测到：报告写不下去（FileNotFoundError: [Errno 2] No such file or directory: 'C:\\Users\\user\\AppData\\Local\\Temp\\pytest-of-user\\pytest-2423\\test_run_all_refuses_a_bad_out0\\没有这个目录\\x.md'）—— 三条复现的判定都在上面，但**这一份报告没落成**。
1 failed, 260 passed, 55 skipped in 73.74s (0:01:13)
```

</details>

### `O2` · 裁决把落点那道门摘了（判定照算，算完才发现写不出去）

- 组：落点　目标文件：`verification/tests/test_adjudicate.py`
- 声明：落点：裁决那道门被摘掉 → 当场红
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 260 条、跳过 55 条，退出码 1，33.55s
- 改：`adjudicate.py`

  ```diff
  -     rc = P.refuse_out_path(args.json, args.md)
  +     rc = None  # 变异：落点这道门形同虚设
  ```

- 红掉的用例（全部）：

  - `test_a_bad_place_stops_both_entry_points_before_they_compute`

<details><summary>原样输出（末 12 行）</summary>

```
..........s..........sssssss...sssssF................................... [ 22%]
....................................ssssssss............................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s...................................... [ 91%]
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_adjudicate.py::test_a_bad_place_stops_both_entry_points_before_they_compute - AssertionError: 得说清是**落点**的问题，不是读数的问题
assert '落点' in '\n○ 没测到：**报告不是用这棵树跑的**：报告记的结束指纹是 `187a945ab58f…`，现在这棵树是 `651f548484a4…`。变的是：README.md、_probe.py、tokenizer_cache.py。\n  重跑一次 `python -m verification.run_all` 再判。如果你**就是要**判那份旧报告（比如核对归档），加 `--allow-source-mismatch` —— 那是显式地在说「我知道它不是这棵树」。\n'
1 failed, 260 passed, 55 skipped in 31.65s
```

</details>

### `O3` · 裁决写不下去时报「没达到预期」（`2` 改成 `1`）

- 组：落点　目标文件：`verification/tests/test_adjudicate.py`
- 声明：落点：写不下去时折成 `1` → 当场红（`1` 会把人指去查判据）
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 260 条、跳过 55 条，退出码 1，33.31s
- 改：`adjudicate.py`

  ```diff
  -               "表算出来了，但**这一份产物没落成**。")
  -         return 2
  +               "表算出来了，但**这一份产物没落成**。")
  +         return 1  # 变异：把「没落成」报成「没达到预期」
  ```

- 红掉的用例（全部）：

  - `test_a_write_that_fails_anyway_is_still_not_measured`

<details><summary>原样输出（末 12 行）</summary>

```
..........s..........sssssss...sssss.F.................................. [ 22%]
....................................ssssssss............................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s...................................... [ 91%]
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_adjudicate.py::test_a_write_that_fails_anyway_is_still_not_measured - AssertionError: 裁决：写不下去时退了 `1` —— 该退 `2`（没测到）
assert 1 == 2
1 failed, 260 passed, 55 skipped in 31.44s
```

</details>

### `O4` · 自证把落点那道门摘了

- 组：落点　目标文件：`verification/tests/test_adjudicate.py`
- 声明：落点：自证那道门被摘掉 → 当场红
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 260 条、跳过 55 条，退出码 1，34.36s
- 改：`selfproof.py`

  ```diff
  -     rc = P.refuse_out_path(args.json, args.md)
  +     rc = None  # 变异：落点这道门形同虚设
  ```

- 红掉的用例（全部）：

  - `test_a_bad_place_stops_both_entry_points_before_they_compute`

<details><summary>原样输出（末 12 行）</summary>

```
..........s..........sssssss...sssssF................................... [ 22%]
....................................ssssssss............................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s...................................... [ 91%]
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_adjudicate.py::test_a_bad_place_stops_both_entry_points_before_they_compute - KeyError: 'meta'
1 failed, 260 passed, 55 skipped in 32.39s
```

</details>

### `O5` · 端到端把落点那道门摘了（真去跑那一局，跑完才发现写不出去）

- 组：落点　目标文件：`verification/tests/test_repro_verdicts.py`
- 声明：落点：端到端那道门被摘掉 → 当场红
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 260 条、跳过 55 条，退出码 1，35.32s
- 改：`e2e_stub.py`

  ```diff
  -     rc = P.refuse_out_path(args.out,
  -                            str(pathlib.Path(args.out).with_suffix(".md")))
  +     rc = None  # 变异：落点这道门形同虚设
  +     _ = (args.out, str(pathlib.Path(args.out).with_suffix('.md')))
  ```

- 红掉的用例（全部）：

  - `test_the_other_three_entry_points_refuse_a_bad_out_place_too`

<details><summary>原样输出（末 12 行）</summary>

```
..........s..........sssssss...sssss.................................... [ 22%]
....................................ssssssss............................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s...F.................................. [ 91%]
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_repro_verdicts.py::test_the_other_three_entry_points_refuse_a_bad_out_place_too - AssertionError: 门在动手之前就该退 —— 它不该被走到
1 failed, 260 passed, 55 skipped in 33.31s
```

</details>

### `O6` · 对账把落点那道门摘了

- 组：落点　目标文件：`verification/tests/test_repro_verdicts.py`
- 声明：落点：对账那道门被摘掉 → 当场红
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 260 条、跳过 55 条，退出码 1，32.91s
- 改：`reconcile_selfcheck.py`

  ```diff
  -     rc = P.refuse_out_path(args.json, args.md)
  +     rc = None  # 变异：落点这道门形同虚设
  ```

- 红掉的用例（全部）：

  - `test_the_other_three_entry_points_refuse_a_bad_out_place_too`

<details><summary>原样输出（末 12 行）</summary>

```
..........s..........sssssss...sssss.................................... [ 22%]
....................................ssssssss............................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s...F.................................. [ 91%]
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_repro_verdicts.py::test_the_other_three_entry_points_refuse_a_bad_out_place_too - AssertionError: 门在动手之前就该退 —— 它不该被走到
1 failed, 260 passed, 55 skipped in 31.03s
```

</details>

### `O7` · 留痕把落点那道门摘了（⚠️ 这条改的是本文件自己）

- 组：落点　目标文件：`verification/tests/test_repro_verdicts.py`
- 声明：落点：留痕那道门被摘掉 → 当场红
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 260 条、跳过 55 条，退出码 1，33.16s
- 改：`mutations.py`

  ```diff
  -         rc = P.refuse_out_path(args.json, args.md)
  -         if rc is not None:
  -             return rc
  +         rc = None  # 变异：落点这道门形同虚设
  +         if rc is not None:
  +             return rc
  ```

- 红掉的用例（全部）：

  - `test_the_other_three_entry_points_refuse_a_bad_out_place_too`

<details><summary>原样输出（末 12 行）</summary>

```
..........s..........sssssss...sssss.................................... [ 22%]
....................................ssssssss............................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s...F.................................. [ 91%]
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_repro_verdicts.py::test_the_other_three_entry_points_refuse_a_bad_out_place_too - AssertionError: 门在动手之前就该退 —— 它不该被走到
1 failed, 260 passed, 55 skipped in 31.31s
```

</details>

### `X1` · 汇总驱动把契约外的退出码原样放过去（`2` 那道判据形同虚设）

- 组：没测到·不许折　目标文件：`verification/tests/test_repro_verdicts.py`
- 声明：没测到：被信号杀死的复现不许记成「达到预期」→ 当场红
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 260 条、跳过 55 条，退出码 1，33.43s
- 改：`run_all.py`

  ```diff
  - 
  -     if rc not in (0, 1, 2):
  - 
  + 
  +     if False:  # 变异：契约外的退出码放它过去
  + 
  ```

- 红掉的用例（全部）：

  - `test_an_out_of_contract_exit_code_is_not_measured`

<details><summary>原样输出（末 12 行）</summary>

```
..........s..........sssssss...sssss.................................... [ 22%]
....................................ssssssss............................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
................................Fs...................................... [ 91%]
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_repro_verdicts.py::test_an_out_of_contract_exit_code_is_not_measured - AssertionError: 契约外的退出码 `7` 被译成了 `7` —— 「没跑完」必须是 `2`
assert 7 == 2
1 failed, 260 passed, 55 skipped in 31.56s
```

</details>

### `X2` · 端到端把「没跑完」判成「没达到预期」（`rc != 0` 排到前面）

- 组：没测到·不许折　目标文件：`verification/tests/test_e2e_stub.py`
- 声明：没测到：负退出码 / argparse 的 `2` 不许判成「没达到预期」→ 当场红
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 260 条、跳过 55 条，退出码 1，33.31s
- 改：`e2e_stub.py`

  ```diff
  - 
  -     if run["rc"] not in (0, 1):
  - 
  + 
  +     if False:  # 变异：契约外的退出码放它过去
  + 
  ```

- 红掉的用例（全部）：

  - `test_an_arm_that_never_finished_is_undecided_not_failed`

<details><summary>原样输出（末 12 行）</summary>

```
..........s..........sssssss...sssss.................................... [ 22%]
....................................ssssssss...........F................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s...................................... [ 91%]
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_e2e_stub.py::test_an_arm_that_never_finished_is_undecided_not_failed - AssertionError: 信号杀死
assert 1 == 2
 +  where 2 = E.ARM_UNMEASURED
1 failed, 260 passed, 55 skipped in 31.43s
```

</details>

### `X3` · 对账时不一致就不再把「抽不出来」升到 `2`

- 组：没测到·不许折　目标文件：`verification/tests/test_repro_verdicts.py`
- 声明：没测到：有一边抽不出来就必须退 `2`，不许被那处不一致顶掉 → 当场红
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 260 条、跳过 55 条，退出码 1，34.6s
- 改：`run_all.py`

  ```diff
  - 
  -         rc = 2
  - 
  + 
  +         rc = 2 if not rc else rc  # 变异：不一致时不升 2
  + 
  ```

- 红掉的用例（全部）：

  - `test_a_missing_number_does_not_disappear_behind_a_mismatch`

<details><summary>原样输出（末 12 行）</summary>

```
..........s..........sssssss...sssss.................................... [ 22%]
....................................ssssssss............................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s.....F................................ [ 91%]
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_repro_verdicts.py::test_a_missing_number_does_not_disappear_behind_a_mismatch - AssertionError: 退了 `1`。有一项**根本没量到**时必须退 `2`：`1` 的意思是「量到了但对不上」，读者会去找一个并不存在的对不上
assert 1 == 2
1 failed, 260 passed, 55 skipped in 32.69s
```

</details>

### `X4` · 对账的收尾退回 `elif`（两件事只能说出前一件）

- 组：没测到·不许折　目标文件：`verification/tests/test_repro_verdicts.py`
- 声明：没测到：「没量到」和「对不上」必须各自说一遍 → 当场红
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 260 条、跳过 55 条，退出码 1，34.16s
- 改：`run_all.py`

  ```diff
  - 
  -     if n_bad:
  - 
  + 
  +     elif n_bad:  # 变异：两件事只能说出前一件
  + 
  ```

- 红掉的用例（全部）：

  - `test_a_missing_number_does_not_disappear_behind_a_mismatch`

<details><summary>原样输出（末 12 行）</summary>

```
..........s..........sssssss...sssss.................................... [ 22%]
....................................ssssssss............................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s.....F................................ [ 91%]
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_repro_verdicts.py::test_a_missing_number_does_not_disappear_behind_a_mismatch - AssertionError: 两处不一致，正文却只说了「没测到」—— 更硬的那个事实不该被盖住
assert '对不上' in '                装置      草稿      对账\n  ------------  --------  --------  ---------\n  ① 新增记录数  277       277       √ 一...  999       × **不一致**\n  ② 同拍违反数  0         ○ 抽不到  ○ 没测到\n\n  ○ 这几项有一边抽不出来：② 同拍违反数（草稿） —— **这不是「一致」，是没测到**。多半是输出格式改过了。'
1 failed, 260 passed, 55 skipped in 32.26s
```

</details>

### `X5` · 产物那一栏又抄了一份 `0/1/2 → 措辞`（打屏与产物分家）

- 组：没测到·不许折　目标文件：`verification/tests/test_repro_verdicts.py`
- 声明：没测到：措辞表只许有一份 → 抄第二份当场红
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 260 条、跳过 55 条，退出码 1，33.98s
- 改：`run_all.py`

  ```diff
  - 
  -     verdicts = VERDICTS
  - 
  + 
  +     verdicts = {0: "达到预期", 1: "没达到预期", 2: "没达到预期"}  # 变异：又抄了一份表
  + 
  ```

- 红掉的用例（全部）：

  - `test_the_verdict_wording_lives_in_exactly_one_table`

<details><summary>原样输出（末 12 行）</summary>

```
..........s..........sssssss...sssss.................................... [ 22%]
....................................ssssssss............................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s......F............................... [ 91%]
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_repro_verdicts.py::test_the_verdict_wording_lives_in_exactly_one_table - AssertionError: `0/1/2 → 措辞` 的表有 2 张：[['达到预期', '没达到预期', '没测到'], ['达到预期', '没达到预期', '没达到预期']] —— 同一份语义抄了第二遍。屏幕和产物会各说各的，而且不会报错
assert 2 == 1
 +  where 2 = len([['达到预期', '没达到预期', '没测到'], ['达到预期', '没达到预期', '没达到预期']])
1 failed, 260 passed, 55 skipped in 32.10s
```

</details>

### `X6` · 裁决不再查形状（「是 JSON 但结构不对」重新变成 traceback）

- 组：没测到·不许折　目标文件：`verification/tests/test_adjudicate.py`
- 声明：没测到：读得成 JSON 不等于结构对 → 当场红
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 260 条、跳过 55 条，退出码 1，34.5s
- 改：`adjudicate.py`

  ```diff
  - 
  -     why = _report_shape_problem(rep)
  - 
  + 
  +     why = None  # 变异：形状不查了
  + 
  ```

- 红掉的用例（全部）：

  - `test_a_report_that_is_readable_json_but_wrongly_shaped_is_refused`

<details><summary>原样输出（末 12 行）</summary>

```
..........s........F.sssssss...sssss.................................... [ 22%]
....................................ssssssss............................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s...................................... [ 91%]
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_adjudicate.py::test_a_report_that_is_readable_json_but_wrongly_shaped_is_refused - Failed: DID NOT RAISE <class 'verification.adjudicate.AdjudicationError'>
1 failed, 260 passed, 55 skipped in 32.63s
```

</details>

### `W1` · 展示层把「不可判定」印成「否决」（三态在最后一米被折成两态）

- 组：展示层　目标文件：`verification/tests/test_viewer.py`
- 声明：展示层：把「不可判定」印成「否决」→ 当场红 2 条
- 实测：**新增红 2 条**（目标文件）、整轮新增 2 条、绿 259 条、跳过 55 条，退出码 1，33.4s
- 改：`viewer.py`

  ```diff
  -     vshow = r["verdict"]
  - 
  +     vshow = (A.FAIL_ if r["verdict"] == A.UNDECIDED
  +              else r["verdict"])  # 变异：没测到说成不成立
  + 
  ```

- 红掉的用例（全部）：

  - `test_undecided_rows_never_render_as_denied`
  - `test_the_verdict_on_screen_matches_the_verdict_in_the_artifact`

<details><summary>原样输出（末 12 行）</summary>

```
  
  Full diff:
    {
  -     '不可判定',
  +     '否决',
    }
FAILED verification/tests/test_viewer.py::test_the_verdict_on_screen_matches_the_verdict_in_the_artifact - AssertionError: B5 产物里是「不可判定」，行内那格印的是「否决」
assert '否决' == '不可判定'
  
  - 不可判定
  + 否决
2 failed, 259 passed, 55 skipped in 31.55s
```

</details>

### `W2` · 展示层的闸不认 falsifier 的 `kind`（表外的种类到渲染那一刻就是 `KeyError`）

- 组：展示层　目标文件：`verification/tests/test_viewer.py`
- 声明：展示层：闸不核 falsifier 的种类 → 当场红 1 条
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 260 条、跳过 55 条，退出码 1，33.5s
- 改：`viewer.py`

  ```diff
  -         _require("kind" in f, f"falsifier {f['id']!r} 里没有 `kind`")
  - 
  +         # 变异：`kind` 那两道核对摘掉
  + 
  ```

- 改：`viewer.py`

  ```diff
  -         _require(f["kind"] in A.FALSIFIER_MARKS,
  -                  f"falsifier {f['id']!r} 的种类 {f['kind']!r} 不在 "
  -                  "`adjudicate.FALSIFIER_MARKS` 那张表里")
  - 
  + 
  ```

- 红掉的用例（全部）：

  - `test_a_falsifier_kind_outside_the_one_table_is_refused`

<details><summary>原样输出（末 12 行）</summary>

```
..........s..........sssssss...sssss.................................... [ 22%]
....................................ssssssss............................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s...................................... [ 91%]
................F...........                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_viewer.py::test_a_falsifier_kind_outside_the_one_table_is_refused - Failed: DID NOT RAISE <class 'verification.viewer.ViewerError'>
1 failed, 260 passed, 55 skipped in 31.65s
```

</details>

### `W3` · 展示层的闸不核用例的 `moved`（落不到任何一格的用例会从页面上静默消失）

- 组：展示层　目标文件：`verification/tests/test_viewer.py`
- 声明：展示层：闸不核用例落在哪一格 → 静默少一块却退 0，当场红 1 条
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 260 条、跳过 55 条，退出码 1，33.65s
- 改：`viewer.py`

  ```diff
  -         _require(c["moved"], f"用例 {c['id']} 的 `moved` 是空的 —— 它会从页面上静默消失")
  -         for v in c["moved"].values():
  -             _require(v in S.GRIDS,
  -                      f"用例 {c['id']} 说它落到了 {v!r}，而五格是 {list(S.GRIDS)}")
  - 
  +         # 变异：这一例落没落在某一格上，不核了
  + 
  ```

- 红掉的用例（全部）：

  - `test_a_case_that_lands_in_no_grid_is_refused`

<details><summary>原样输出（末 12 行）</summary>

```
..........s..........sssssss...sssss.................................... [ 22%]
....................................ssssssss............................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s...................................... [ 91%]
.................F..........                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_viewer.py::test_a_case_that_lands_in_no_grid_is_refused - Failed: DID NOT RAISE <class 'verification.viewer.ViewerError'>
1 failed, 260 passed, 55 skipped in 31.81s
```

</details>

### `W4` · 展示层的闸退回原样（判据行的 `what` / `check` 又不核了）

- 组：展示层　目标文件：`verification/tests/test_viewer.py`
- 声明：展示层：闸不核渲染器要读的那两格 → 当场红 1 条
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 260 条、跳过 55 条，退出码 1，33.47s
- 改：`viewer.py`

  ```diff
  -         for key in ("id", "layer", "verdict", "trusted", "values", "what", "check"):
  - 
  +         for key in ("id", "layer", "verdict", "trusted", "values"):
  + 
  ```

- 红掉的用例（全部）：

  - `test_a_cell_the_renderer_reads_is_a_cell_the_gate_checks`

<details><summary>原样输出（末 12 行）</summary>

```
..........s..........sssssss...sssss.................................... [ 22%]
....................................ssssssss............................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s...................................... [ 91%]
...............F............                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_viewer.py::test_a_cell_the_renderer_reads_is_a_cell_the_gate_checks - Failed: DID NOT RAISE <class 'verification.viewer.ViewerError'>
1 failed, 260 passed, 55 skipped in 31.61s
```

</details>

### `W5` · 展示层把渲染中途撞上的形状错又甩成 traceback（退 `1` —— 看着像「发现了一处折合」）

- 组：展示层　目标文件：`verification/tests/test_viewer.py`
- 声明：展示层：闸外那点余地上的形状错不许折成「发现」→ 当场红 1 条
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 260 条、跳过 55 条，退出码 1，33.1s
- 改：`viewer.py`

  ```diff
  -     except (KeyError, TypeError, IndexError, AttributeError) as e:
  -         # 上面那道闸兜不住的一半：产物长成了**还没想到的**那种样子，渲染当场撞上。
  -         # 这不许按「发现了一处折合」退 `1` 走出去 —— 页面上**一个字都没有**，
  -         # 一句「展示层发现了 1 处折合」会是凭空报出来的发现（口径同 `run_all`：
  -         # 「没测到」既不是通过，也不是失败）。闸已经按「读什么就核什么」补齐，
  -         # 这一条是给闸外面剩下的那点余地留的。
  -         print(f"\n○ 没测到：渲染到一半撞上 {e.__class__.__name__}: {e} —— "
  -               "页面上一个字都没有，既不是「通过」，也不是「发现了一处折合」。")
  -         return 2
  - 
  + 
  ```

- 红掉的用例（全部）：

  - `test_an_unforeseen_shape_is_not_measured_not_a_finding`

<details><summary>原样输出（末 12 行）</summary>

```
..........s..........sssssss...sssss.................................... [ 22%]
....................................ssssssss............................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s...................................... [ 91%]
..................F.........                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_viewer.py::test_an_unforeseen_shape_is_not_measured_not_a_finding - KeyError: '某一格'
1 failed, 260 passed, 55 skipped in 31.25s
```

</details>

### `W6` · 展示层只说一个数（一例落两格时，页面上不再交代条目数与例数是两个数）

- 组：展示层　目标文件：`verification/tests/test_viewer.py`
- 声明：展示层：一例落两格却不交代 → 一个数被当成另一个数，当场红 1 条
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 260 条、跳过 55 条，退出码 1，33.46s
- 改：`viewer.py`

  ```diff
  -     if shown != total:
  -         multi = "、".join(c["id"] for c in sp["cases"]
  -                           if len([g for g in S.GRIDS if g in c["moved"].values()]) > 1)
  -         saying += (f"；下面<strong>按格陈列</strong>共 <strong>{shown}</strong> 条 —— "
  -                    f"比上面多出的 {shown - total} 条，是<strong>一例同时落了两格</strong>"
  -                    f"（{_esc(multi)} 同时动了两个断言）。"
  -                    "<strong>条目数与例数是两个数，不是一回事</strong>")
  - 
  +     # 变异：只报例数，条目数不提了
  + 
  ```

- 红掉的用例（全部）：

  - `test_the_page_says_both_counts_when_one_case_lands_in_two_grids`

<details><summary>原样输出（末 12 行）</summary>

```
..........s..........sssssss...sssss.................................... [ 22%]
....................................ssssssss............................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s...................................... [ 91%]
...................F........                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_viewer.py::test_the_page_says_both_counts_when_one_case_lands_in_two_grids - AssertionError: 页面上没交代「一例可以落两格」
assert '一例同时落了两格' in '<!doctype html>\n<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,ini...染，整页<strong>没有一行 JavaScript、没有一个外部引用</strong>；不判定、不重跑、不发任何请求。它是<strong>展示层</strong>，不是装置的一部分。</footer></body></html>\n'
1 failed, 260 passed, 55 skipped in 31.58s
```

</details>

### `T1` · 空的外部目录也算有表（仓库内那份编码表被一个空目录绕过去）

- 组：读数指纹　目标文件：`verification/tests/test_tokenizer_cache.py`
- 声明：读数指纹：空外部目录压过仓库副本／报成 missing → 当场红 3 条
- 实测：**新增红 3 条**（目标文件）、整轮新增 3 条、绿 258 条、跳过 55 条，退出码 1，33.82s
- 改：`tokenizer_cache.py`

  ```diff
  -     return p.is_file() and P.sha256_bytes(p) == EXPECTED_SHA256
  +     return True  # 变异：空目录也算有表
  ```

- 红掉的用例（全部）：

  - `test_resolver_ignores_empty_external_dir`
  - `test_resolver_reports_missing_when_neither_side_has_it`
  - `test_resolver_rejects_an_external_table_whose_content_is_wrong`

<details><summary>原样输出（末 12 行）</summary>

```
....................................ssssssss............................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s................FF...F................ [ 91%]
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_tokenizer_cache.py::test_resolver_ignores_empty_external_dir - AssertionError: assert WindowsPath('C:/Users/user/AppData/Local/Temp/pytest-of-user/pytest-2442/test_resolver_ignores_empty_ex0') == WindowsPath('D:/open_source/B-装置/mirofish-verifiable/backend/verification/vendor/tiktoken')
 +  where WindowsPath('D:/open_source/B-装置/mirofish-verifiable/backend/verification/vendor/tiktoken') = T.VENDOR_DIR
FAILED verification/tests/test_tokenizer_cache.py::test_resolver_reports_missing_when_neither_side_has_it - AssertionError: assert WindowsPath('C:/Users/user/AppData/Local/Temp/pytest-of-user/pytest-2442/test_resolver_reports_missing_0') is None
FAILED verification/tests/test_tokenizer_cache.py::test_resolver_rejects_an_external_table_whose_content_is_wrong - AssertionError: 内容不对的外部表也被让位了
assert WindowsPath('C:/Users/user/AppData/Local/Temp/pytest-of-user/pytest-2442/test_resolver_rejects_an_exter0') == WindowsPath('D:/open_source/B-装置/mirofish-verifiable/backend/verification/vendor/tiktoken')
 +  where WindowsPath('D:/open_source/B-装置/mirofish-verifiable/backend/verification/vendor/tiktoken') = T.VENDOR_DIR
3 failed, 258 passed, 55 skipped in 31.93s
```

</details>

### `T2` · 外部表只验在不在、不验内容（同名错表顶掉仓库副本）

- 组：读数指纹　目标文件：`verification/tests/test_tokenizer_cache.py`
- 声明：读数指纹：内容不对的外部表被让位 → 当场红 1 条
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 260 条、跳过 55 条，退出码 1，32.95s
- 改：`tokenizer_cache.py`

  ```diff
  -     return p.is_file() and P.sha256_bytes(p) == EXPECTED_SHA256
  +     return p.is_file()  # 变异：只看在不在，不验内容
  ```

- 红掉的用例（全部）：

  - `test_resolver_rejects_an_external_table_whose_content_is_wrong`

<details><summary>原样输出（末 12 行）</summary>

```
..........s..........sssssss...sssss.................................... [ 22%]
....................................ssssssss............................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s.....................F................ [ 91%]
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_tokenizer_cache.py::test_resolver_rejects_an_external_table_whose_content_is_wrong - AssertionError: 内容不对的外部表也被让位了
assert WindowsPath('C:/Users/user/AppData/Local/Temp/pytest-of-user/pytest-2443/test_resolver_rejects_an_exter0') == WindowsPath('D:/open_source/B-装置/mirofish-verifiable/backend/verification/vendor/tiktoken')
 +  where WindowsPath('D:/open_source/B-装置/mirofish-verifiable/backend/verification/vendor/tiktoken') = T.VENDOR_DIR
1 failed, 260 passed, 55 skipped in 31.09s
```

</details>

### `R1` · 开始/结束双哈希的门焊成恒真（报告不成立也照常出有效指纹）

- 组：读数指纹　目标文件：`verification/tests/test_run_all_fingerprint.py`
- 声明：读数指纹：树在跑的过程中被改过却退 0 → 当场红 3 条
- 实测：**新增红 3 条**（目标文件）、整轮新增 3 条、绿 258 条、跳过 55 条，退出码 1，33.37s
- 改：`run_all.py`

  ```diff
  -         run_stable = (readings_start.get("sha256") is not None
  -                       and readings_start["sha256"] == readings_end.get("sha256"))
  +         run_stable = True  # 变异：指纹门形同虚设
  ```

- 红掉的用例（全部）：

  - `test_a_tree_that_moves_under_the_run_writes_a_null_fingerprint`
  - `test_an_incomplete_tree_never_counts_as_stable[None]`
  - `test_an_incomplete_tree_never_counts_as_stable[cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc]`

<details><summary>原样输出（末 12 行）</summary>

```
....................................ssssssss............................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s.........F.FF......................... [ 91%]
............................                                             [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_run_all_fingerprint.py::test_a_tree_that_moves_under_the_run_writes_a_null_fingerprint - AssertionError: 读数集在跑的过程中变了，却退了 0 —— 该退 2（没测到）
assert 0 == 2
FAILED verification/tests/test_run_all_fingerprint.py::test_an_incomplete_tree_never_counts_as_stable[None] - AssertionError: 一开始就取不全，却按稳定退了一个码
assert 0 == 2
FAILED verification/tests/test_run_all_fingerprint.py::test_an_incomplete_tree_never_counts_as_stable[cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc] - AssertionError: 一开始就取不全，却按稳定退了一个码
assert 0 == 2
3 failed, 258 passed, 55 skipped in 31.53s
```

</details>

### `M1` · 判据退回「数红条」：基线红的是 X、这轮多红 Y 也会被减成 0

- 组：阴性对照　目标文件：`verification/tests/test_mutation_harness.py`
- 声明：阴性对照：集合差退回计数差 → 新加的「红的是另一条」测试红 1 条
- 实测：**新增红 1 条**（目标文件）、整轮新增 1 条、绿 260 条、跳过 55 条，退出码 1，33.55s
- 改：`mutations.py`

  ```diff
  -     return [i for i in (res.get("failed_ids") or ()) if i not in base]
  +     return list(res.get("failed_ids") or ())  # 变异：退回数红条
  ```

- 红掉的用例（全部）：

  - `test_newly_red_counts_ids_not_counts`

<details><summary>原样输出（末 12 行）</summary>

```
=========================== short test summary info ===========================
FAILED verification/tests/test_mutation_harness.py::test_newly_red_counts_ids_not_counts - AssertionError: assert ['t.py::test_...t.py::test_y'] == ['t.py::test_y']
  
  At index 0 diff: 't.py::test_x' != 't.py::test_y'
  Left contains one more item: 't.py::test_y'
  
  Full diff:
    [
  +     't.py::test_x',
        't.py::test_y',
    ]
1 failed, 260 passed, 55 skipped in 31.68s
```

</details>

### `K0` · 语义上什么都不改（只在 `STEP` 那行尾加一句注释）

- 组：阴性对照　目标文件：`verification/tests/test_camel_guards.py`
- 声明：本模块自己的纪律：不做任何语义改动的编辑，一条都不许红
- 实测：**新增红 0 条**（目标文件）、整轮新增 0 条、绿 261 条、跳过 55 条，退出码 0，33.32s
- 改：`camel_guards.py`

  ```diff
  - STEP = 1e-3
  + STEP = 1e-3  # 阴性对照：这行不该有行为差异
  ```

- 一条都没红 —— 这正是这一条**期望**的结果。

<details><summary>原样输出（末 12 行）</summary>

```
..........s..........sssssss...sssss.................................... [ 22%]
....................................ssssssss............................ [ 45%]
......sssssssssssssss.......ssssssssssssssssss.......................... [ 68%]
.................................s...................................... [ 91%]
............................                                             [100%]
261 passed, 55 skipped in 31.44s
```

</details>

## 结论

**52 处变异全部按声明对上（其中 `K0` 是阴性对照：按声明**一条都不该红**），基线全绿，源文件逐字节还原。** 这份测试集不是恒真的 —— 它有**会被改坏**的地方，而那些地方都被盯着；反过来，也有地方**被盯着「改了却什么都不该红」**：那处证明红是**冲着这个缺陷**红的，而不是改一行字就红。
