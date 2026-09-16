# 变异测试留痕（自动生成，别手改）

> 生成时间 **2026-09-16 23:25:02** · Python 3.11.9 · `cd backend && python -m verification.mutations`

## 这份报告是什么、不是什么

**是**：一张「把被测代码改坏了、测试会不会红」的对照表 —— `README.md` 里「验过它不是恒真的」那句话的证据。

**不是**：通过率、覆盖率、质量分。这里的**红色是期望的结果**，一条红都没有才是坏消息。**别把红条数读成任何形式的得分。**

- 基线（一点没改）：**83 passed / 0 failed / 12 skipped**（= 全套 95 条），退出码 0，2.22s —— 先证明测试集本身是绿的，底下那些红才有意义。
- 上面这个规模**不含** `tests/test_mutation_evidence.py`（5 条）：那一组问的是「这份报告有没有过期」，而本模块每一轮都在被改坏的源码上跑 —— 它见到环境变量 `MIROFISH_MUTATION_RUN` 会跳过自己。「报告过期」由普通 `pytest` 抓，见那个文件。
- 三个源文件跑完后逐字节还原：**是**（逐文件 `sha256` 见 `mutations_report.json` 的 `sources` / `sources_after`）。

## 对照表

「声明」是**材料里先写下的**数字；「实测」是这一轮跑出来的。两者不一致时**以实测为准**，并且材料要跟着改 —— 不许反过来把期望值改成漂移后的样子。

| # | 组 | 变异成什么 | 声明 | 实测（目标文件红掉） | 判定 |
|---|---|---|---|---|---|
| `G1` | 守卫 | 判据的边界写成 `>=`（顶格的消息会被误判成超限） | 至少 1 条 | **1 条** | 相符 |
| `G2` | 守卫 | 整个守卫变成空操作（开头就把活原样交回原方法） | 至少 1 条 | **10 条** | 相符 |
| `G3` | 守卫 | 变成「一律不切」（该切的那条路被永远关掉） | 至少 1 条 | **2 条** | 相符 |
| `G4` | 守卫 | 逻辑步长调到比 camel 那个 `1e-6` 还细 | 至少 1 条 | **1 条** | 相符 |
| `G5` | 守卫 | 时间戳不再往后推（拿掉严格递增那一步） | 至少 1 条 | **4 条** | 相符 |
| `G6` | 守卫 | 去掉兜底（算不出 token 时不再交回原方法，直接抛） | 至少 1 条 | **1 条** | 相符 |
| `G7` | 守卫 | `install` 不再幂等（第二次调用会套第二层补丁） | 至少 1 条 | **1 条** | 相符 |
| `V1` | 判词 | 判词写死（直接把结论摆在预期那一侧，不再由读数算） | 16 条 | **16 条** | 相符 |
| `V2` | 判词 | 判据的 `<` 写成 `<=`（`gap == tick` 会被算成同一拍） | 3 条 | **3 条** | 相符 |
| `V3` | 判词 | 去掉「与预期相反」那一支（与预期不符时折回预期那一侧的话术） | 3 条 | **3 条** | 相符 |
| `C1` | 引文·上半 | 行号错开一格（933 → 934） | 至少 1 条 | **1 条** | 相符 |
| `C2` | 引文·上半 | 引一个越界的行号（884 → 999999） | 至少 1 条 | **1 条** | 相符 |
| `C3` | 引文·上半 | 换成那一行没有的片段（`// 10` 写成 `// 100`） | 至少 1 条 | **1 条** | 相符 |
| `C4` | 引文·上半 | 引一个不存在的模块（`camel.memories.base` → `..._missing`） | 至少 1 条 | **1 条** | 相符 |
| `C5` | 引文·上半 | 同一行引两遍（把 env:55 那条改成 env:193，片段也跟着改成 193 行的） | 至少 1 条 | **1 条** | 相符 |
| `C6` | 引文·下半 | 把那个错引写法**植回 `camel_guards.py`**，看扫描抓不抓 | 1 条 | **1 条** | 相符 |
| `K0` | 阴性对照 | 语义上什么都不改（只在 `STEP` 那行尾加一句注释） | 0 条 | **0 条** | 相符 |

共 **17** 处变异，其中 **17** 处的实测与声明相符。

## 逐条明细

每条的「改了什么」是**逐字节替换**（`old` → `new`），跑完立刻按字节还原。

`C6` 那条的 `+` 行被**刻意屏蔽**成上面那个占位符：那个写法一旦抄进这份报告，**报告自己就会被 `test_no_known_misquote_survives_in_our_materials` 抓红**（理由和 `README.md` 里不抄第二遍是同一条）。要看原样 —— 连同那个字面量本身 —— 去 `mutations_report.json`：后缀 `.json` 不在那条扫描的范围里。

### `G1` · 判据的边界写成 `>=`（顶格的消息会被误判成超限）

- 组：守卫　目标文件：`verification/tests/test_camel_guards.py`
- 声明：README「守卫：两个方向都要成立」：七处变异都变红
- 实测：目标文件红 **1** 条，整轮红 **1** 条、绿 82 条、跳过 12 条，退出码 1，2.28s
- 改：`camel_guards.py`

  ```diff
  -     if own_tokens > limit:
  +     if own_tokens >= limit:
  ```

- 红掉的用例（全部）：

  - `test_boundary_is_strict_greater_not_greater_equal`

<details><summary>原样输出（末 12 行）</summary>

```
.......F.........................................ssssssssssss........... [ 75%]
.......................                                                  [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_camel_guards.py::test_boundary_is_strict_greater_not_greater_equal
1 failed, 82 passed, 12 skipped in 1.67s
```

</details>

### `G2` · 整个守卫变成空操作（开头就把活原样交回原方法）

- 组：守卫　目标文件：`verification/tests/test_camel_guards.py`
- 声明：README「守卫：两个方向都要成立」：七处变异都变红
- 实测：目标文件红 **10** 条，整轮红 **10** 条、绿 73 条、跳过 12 条，退出码 1，2.24s
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
  - `test_slicing_on_timestamp_off_leaves_timestamps_untouched`
  - `test_timestamp_on_slicing_off_only_moves_the_clock`
  - `test_timestamp_is_strictly_increasing_across_calls`
  - `test_explicit_pair_is_pushed_apart_but_not_counted`
  - `test_timestamp_pushed_counts_only_our_own_reads`

<details><summary>原样输出（末 12 行）</summary>

```
=========================== short test summary info ===========================
FAILED verification/tests/test_camel_guards.py::test_install_is_idempotent - ...
FAILED verification/tests/test_camel_guards.py::test_uninstall_restores_original_and_clears_counters
FAILED verification/tests/test_camel_guards.py::test_whole_write_when_message_fits
FAILED verification/tests/test_camel_guards.py::test_hands_back_when_message_itself_exceeds_limit
FAILED verification/tests/test_camel_guards.py::test_boundary_is_strict_greater_not_greater_equal
FAILED verification/tests/test_camel_guards.py::test_slicing_on_timestamp_off_leaves_timestamps_untouched
FAILED verification/tests/test_camel_guards.py::test_timestamp_on_slicing_off_only_moves_the_clock
FAILED verification/tests/test_camel_guards.py::test_timestamp_is_strictly_increasing_across_calls
FAILED verification/tests/test_camel_guards.py::test_explicit_pair_is_pushed_apart_but_not_counted
FAILED verification/tests/test_camel_guards.py::test_timestamp_pushed_counts_only_our_own_reads
10 failed, 73 passed, 12 skipped in 1.61s
```

</details>

### `G3` · 变成「一律不切」（该切的那条路被永远关掉）

- 组：守卫　目标文件：`verification/tests/test_camel_guards.py`
- 声明：README「守卫：两个方向都要成立」：七处变异都变红
- 实测：目标文件红 **2** 条，整轮红 **2** 条、绿 81 条、跳过 12 条，退出码 1，2.3s
- 改：`camel_guards.py`

  ```diff
  -     if own_tokens > limit:
  +     if False:
  ```

- 红掉的用例（全部）：

  - `test_hands_back_when_message_itself_exceeds_limit`
  - `test_boundary_is_strict_greater_not_greater_equal`

<details><summary>原样输出（末 12 行）</summary>

```
......FF.........................................ssssssssssss........... [ 75%]
.......................                                                  [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_camel_guards.py::test_hands_back_when_message_itself_exceeds_limit
FAILED verification/tests/test_camel_guards.py::test_boundary_is_strict_greater_not_greater_equal
2 failed, 81 passed, 12 skipped in 1.63s
```

</details>

### `G4` · 逻辑步长调到比 camel 那个 `1e-6` 还细

- 组：守卫　目标文件：`verification/tests/test_camel_guards.py`
- 声明：README「守卫：两个方向都要成立」：七处变异都变红
- 实测：目标文件红 **1** 条，整轮红 **1** 条、绿 82 条、跳过 12 条，退出码 1，2.19s
- 改：`camel_guards.py`

  ```diff
  - STEP = 1e-3
  + STEP = 1e-7
  ```

- 红掉的用例（全部）：

  - `test_step_is_larger_than_camels_offset`

<details><summary>原样输出（末 12 行）</summary>

```
.................F...............................ssssssssssss........... [ 75%]
.......................                                                  [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_camel_guards.py::test_step_is_larger_than_camels_offset
1 failed, 82 passed, 12 skipped in 1.56s
```

</details>

### `G5` · 时间戳不再往后推（拿掉严格递增那一步）

- 组：守卫　目标文件：`verification/tests/test_camel_guards.py`
- 声明：README「守卫：两个方向都要成立」：七处变异都变红
- 实测：目标文件红 **4** 条，整轮红 **4** 条、绿 79 条、跳过 12 条，退出码 1，2.24s
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
...........F..FFF................................ssssssssssss........... [ 75%]
.......................                                                  [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_camel_guards.py::test_timestamp_on_slicing_off_only_moves_the_clock
FAILED verification/tests/test_camel_guards.py::test_timestamp_is_strictly_increasing_across_calls
FAILED verification/tests/test_camel_guards.py::test_explicit_pair_is_pushed_apart_but_not_counted
FAILED verification/tests/test_camel_guards.py::test_timestamp_pushed_counts_only_our_own_reads
4 failed, 79 passed, 12 skipped in 1.65s
```

</details>

### `G6` · 去掉兜底（算不出 token 时不再交回原方法，直接抛）

- 组：守卫　目标文件：`verification/tests/test_camel_guards.py`
- 声明：README「守卫：两个方向都要成立」：七处变异都变红
- 实测：目标文件红 **1** 条，整轮红 **1** 条、绿 82 条、跳过 12 条，退出码 1，2.26s
- 改：`camel_guards.py`

  ```diff
  -     except Exception:  # noqa: BLE001
  -         # 算不出来就别自作聪明 —— 交回原方法。
  -         if _state["timestamp"]:
  -             _note_timestamp(self, timestamp)
  -         return original(self, message, role, timestamp)
  +     except Exception:  # noqa: BLE001
  +         raise
  ```

- 红掉的用例（全部）：

  - `test_hands_back_when_tokens_cannot_be_counted`

<details><summary>原样输出（末 12 行）</summary>

```
........F........................................ssssssssssss........... [ 75%]
.......................                                                  [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_camel_guards.py::test_hands_back_when_tokens_cannot_be_counted
1 failed, 82 passed, 12 skipped in 1.58s
```

</details>

### `G7` · `install` 不再幂等（第二次调用会套第二层补丁）

- 组：守卫　目标文件：`verification/tests/test_camel_guards.py`
- 声明：README「守卫：两个方向都要成立」：七处变异都变红
- 实测：目标文件红 **1** 条，整轮红 **1** 条、绿 82 条、跳过 12 条，退出码 1，2.17s
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
F................................................ssssssssssss........... [ 75%]
.......................                                                  [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_camel_guards.py::test_install_is_idempotent - ...
1 failed, 82 passed, 12 skipped in 1.58s
```

</details>

### `V1` · 判词写死（直接把结论摆在预期那一侧，不再由读数算）

- 组：判词　目标文件：`verification/tests/test_repro_verdicts.py`
- 声明：README「判词」：判词写死 → 红 16 条
- 实测：目标文件红 **16** 条，整轮红 **16** 条、绿 67 条、跳过 12 条，退出码 1，2.22s
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
FAILED verification/tests/test_repro_verdicts.py::test_verdict_never_contradicts_its_own_numbers[True-0.00101-0.001]
FAILED verification/tests/test_repro_verdicts.py::test_verdict_never_contradicts_its_own_numbers[True-0.00335-0.000302]
FAILED verification/tests/test_repro_verdicts.py::test_verdict_never_contradicts_its_own_numbers[True-0.0038-0.00034100000000000005]
FAILED verification/tests/test_repro_verdicts.py::test_verdict_never_contradicts_its_own_numbers[False-0.0-0.0004]
FAILED verification/tests/test_repro_verdicts.py::test_verdict_never_contradicts_its_own_numbers[False-0.0001-0.0004]
FAILED verification/tests/test_repro_verdicts.py::test_verdict_never_contradicts_its_own_numbers[False-0.00039000000000000005-0.0004]
FAILED verification/tests/test_repro_verdicts.py::test_verdict_never_contradicts_its_own_numbers[False-0.0-0.001]
FAILED verification/tests/test_repro_verdicts.py::test_verdict_never_contradicts_its_own_numbers[False-0.00099-0.001]
FAILED verification/tests/test_repro_verdicts.py::test_the_actual_regression_is_reported_not_smoothed
FAILED verification/tests/test_repro_verdicts.py::test_opposite_direction_of_surprise_is_also_reported
FAILED verification/tests/test_repro_verdicts.py::test_zero_tick_does_not_explode
16 failed, 67 passed, 12 skipped in 1.59s
```

</details>

### `V2` · 判据的 `<` 写成 `<=`（`gap == tick` 会被算成同一拍）

- 组：判词　目标文件：`verification/tests/test_repro_verdicts.py`
- 声明：README「判词」：`<` 写成 `<=` → 红 3 条
- 实测：目标文件红 **3** 条，整轮红 **3** 条、绿 80 条、跳过 12 条，退出码 1，2.14s
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
.................................................ssssssssssss....F...... [ 75%]
......F.............F..                                                  [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_repro_verdicts.py::test_verdict_never_contradicts_its_own_numbers[True-0.0004-0.0004]
FAILED verification/tests/test_repro_verdicts.py::test_verdict_never_contradicts_its_own_numbers[False-0.0004-0.0004]
FAILED verification/tests/test_repro_verdicts.py::test_boundary_gap_equal_to_tick_counts_as_crossed
3 failed, 80 passed, 12 skipped in 1.54s
```

</details>

### `V3` · 去掉「与预期相反」那一支（与预期不符时折回预期那一侧的话术）

- 组：判词　目标文件：`verification/tests/test_repro_verdicts.py`
- 声明：README「判词」：去掉「与预期相反」那一支 → 红 3 条
- 实测：目标文件红 **3** 条，整轮红 **3** 条、绿 80 条、跳过 12 条，退出码 1，2.28s
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
.................................................ssssssssssss........... [ 75%]
................FF...F.                                                  [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_repro_verdicts.py::test_the_actual_regression_is_reported_not_smoothed
FAILED verification/tests/test_repro_verdicts.py::test_opposite_direction_of_surprise_is_also_reported
FAILED verification/tests/test_repro_verdicts.py::test_zero_tick_does_not_explode
3 failed, 80 passed, 12 skipped in 1.68s
```

</details>

### `C1` · 行号错开一格（933 → 934）

- 组：引文·上半　目标文件：`verification/tests/test_citations.py`
- 声明：README「引文：文档里的行号不许腐烂」：上半五处变异都红
- 实测：目标文件红 **1** 条，整轮红 **1** 条、绿 82 条、跳过 12 条，退出码 1，2.23s
- 改：`test_citations.py`

  ```diff
  - ("camel.agents.chat_agent", 933,
  + ("camel.agents.chat_agent", 934,
  ```

- 红掉的用例（全部）：

  - `test_cited_line_still_says_what_we_say_it_says[camel.agents.chat_agent-934-base_chunk_size`

<details><summary>原样输出（末 12 行）</summary>

```
.........................F.......................ssssssssssss........... [ 75%]
.......................                                                  [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_citations.py::test_cited_line_still_says_what_we_say_it_says[camel.agents.chat_agent-934-base_chunk_size = max(1, remaining_budget) // 10-camel_guards / README \xa7\u2460\uff1a\u6b8b\u4f59\u9884\u7b97\u5148\u88ab //10 \u780d\u4e00\u5200]
1 failed, 82 passed, 12 skipped in 1.65s
```

</details>

### `C2` · 引一个越界的行号（884 → 999999）

- 组：引文·上半　目标文件：`verification/tests/test_citations.py`
- 声明：README「引文：文档里的行号不许腐烂」：上半五处变异都红
- 实测：目标文件红 **1** 条，整轮红 **1** 条、绿 82 条、跳过 12 条，退出码 1，2.14s
- 改：`test_citations.py`

  ```diff
  - ("camel.agents.chat_agent", 884,
  + ("camel.agents.chat_agent", 999999,
  ```

- 红掉的用例（全部）：

  - `test_cited_line_still_says_what_we_say_it_says[camel.agents.chat_agent-999999-remaining_budget`

<details><summary>原样输出（末 12 行）</summary>

```
.......................F.........................ssssssssssss........... [ 75%]
.......................                                                  [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_citations.py::test_cited_line_still_says_what_we_say_it_says[camel.agents.chat_agent-999999-remaining_budget = max(0, token_limit - ctx_tokens)-README \xa7\u2460 / camel_guards\uff1a\u6b8b\u4f59\u9884\u7b97\u7528\u7684\u662f**\u622a\u65ad\u540e**\u7684 ctx_tokens]
1 failed, 82 passed, 12 skipped in 1.53s
```

</details>

### `C3` · 换成那一行没有的片段（`// 10` 写成 `// 100`）

- 组：引文·上半　目标文件：`verification/tests/test_citations.py`
- 声明：README「引文：文档里的行号不许腐烂」：上半五处变异都红
- 实测：目标文件红 **1** 条，整轮红 **1** 条、绿 82 条、跳过 12 条，退出码 1，2.15s
- 改：`test_citations.py`

  ```diff
  - "base_chunk_size = max(1, remaining_budget) // 10",
  + "base_chunk_size = max(1, remaining_budget) // 100",
  ```

- 红掉的用例（全部）：

  - `test_cited_line_still_says_what_we_say_it_says[camel.agents.chat_agent-933-base_chunk_size`

<details><summary>原样输出（末 12 行）</summary>

```
.........................F.......................ssssssssssss........... [ 75%]
.......................                                                  [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_citations.py::test_cited_line_still_says_what_we_say_it_says[camel.agents.chat_agent-933-base_chunk_size = max(1, remaining_budget) // 100-camel_guards / README \xa7\u2460\uff1a\u6b8b\u4f59\u9884\u7b97\u5148\u88ab //10 \u780d\u4e00\u5200]
1 failed, 82 passed, 12 skipped in 1.55s
```

</details>

### `C4` · 引一个不存在的模块（`camel.memories.base` → `..._missing`）

- 组：引文·上半　目标文件：`verification/tests/test_citations.py`
- 声明：README「引文：文档里的行号不许腐烂」：上半五处变异都红
- 实测：目标文件红 **1** 条，整轮红 **1** 条、绿 81 条、跳过 13 条，退出码 1，2.15s
- 改：`test_citations.py`

  ```diff
  - ("camel.memories.base", 143,
  + ("camel.memories.base_missing", 143,
  ```

- 红掉的用例（全部）：

  - `test_every_citation_module_is_reachable`

<details><summary>原样输出（末 12 行）</summary>

```
....................................s.......F....ssssssssssss........... [ 75%]
.......................                                                  [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_citations.py::test_every_citation_module_is_reachable
1 failed, 81 passed, 13 skipped in 1.53s
```

</details>

### `C5` · 同一行引两遍（把 env:55 那条改成 env:193，片段也跟着改成 193 行的）

- 组：引文·上半　目标文件：`verification/tests/test_citations.py`
- 声明：README「引文：文档里的行号不许腐烂」：上半五处变异都红
- 实测：目标文件红 **1** 条，整轮红 **1** 条、绿 82 条、跳过 12 条，退出码 1，2.16s
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
.............................................F...ssssssssssss........... [ 75%]
.......................                                                  [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_citations.py::test_no_duplicate_citations - As...
1 failed, 82 passed, 12 skipped in 1.57s
```

</details>

### `C6` · 把那个错引写法**植回 `camel_guards.py`**，看扫描抓不抓

- 组：引文·下半　目标文件：`verification/tests/test_citations.py`
- 声明：README「引文」：下半把那个写法植回 `camel_guards.py`，当场红
- 实测：目标文件红 **1** 条，整轮红 **1** 条、绿 82 条、跳过 12 条，退出码 1，2.11s
- 改：`camel_guards.py`

  ```diff
  - base_chunk_size - prefix_token_len
  + ＜那个被引错的字面量，本报告不抄＞
  ```

- 红掉的用例（全部）：

  - `test_no_known_misquote_survives_in_our_materials[base_chunk_size\\s*-\\s*12-base_chunk_size`

<details><summary>原样输出（末 12 行）</summary>

```
................................................Fssssssssssss........... [ 75%]
.......................                                                  [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_citations.py::test_no_known_misquote_survives_in_our_materials[base_chunk_size\\s*-\\s*12-base_chunk_size - prefix_token_len\uff08948 \u884c\uff1b\u90a3\u4e2a\u51cf\u6570\u662f 943 \u884c**\u91cf**\u51fa\u6765\u7684\uff09-\u628a\u300c\u524d\u7f00\u957f\u5ea6\u300d\u8fd9\u4e2a\u5f53\u573a\u91cf\u51fa\u6765\u7684\u503c\u5199\u6b7b\u6210\u4e86\u5b57\u9762\u91cf 12\uff0c\u8fd8\u6807\u6210 948 \u884c\u7684\u539f\u6587 \u2014\u2014 \u6570\u503c\u4e0a\u5bf9\uff08gpt-4o-mini \u4e0b\u6070\u597d\u662f 12\uff09\uff0c**\u5f15\u6587\u4e0a\u9519**\uff1a\u6362\u4e2a\u5206\u8bcd\u5668\u5c31\u4e0d\u662f 12]
1 failed, 82 passed, 12 skipped in 1.53s
```

</details>

### `K0` · 语义上什么都不改（只在 `STEP` 那行尾加一句注释）

- 组：阴性对照　目标文件：`verification/tests/test_camel_guards.py`
- 声明：本模块自己的纪律：不做任何语义改动的编辑，一条都不许红
- 实测：目标文件红 **0** 条，整轮红 **0** 条、绿 83 条、跳过 12 条，退出码 0，2.12s
- 改：`camel_guards.py`

  ```diff
  - STEP = 1e-3
  + STEP = 1e-3  # 阴性对照：这行不该有行为差异
  ```

- 一条都没红 —— 这正是这一条**期望**的结果。

<details><summary>原样输出（末 12 行）</summary>

```
.................................................ssssssssssss........... [ 75%]
.......................                                                  [100%]
83 passed, 12 skipped in 1.51s
```

</details>

## 结论

**17 处变异全部按声明变红，基线全绿，源文件逐字节还原。** 这份测试集不是恒真的 —— 它有**会被改坏**的地方，而那些地方都被盯着。
