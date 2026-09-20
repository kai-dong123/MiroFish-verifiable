# 变异测试留痕（自动生成，别手改）

> 生成时间 **2026-09-20 23:53:09** · Python 3.11.9 · `cd backend && python -m verification.mutations`

## 这份报告是什么、不是什么

**是**：一张「把被测代码改坏了、测试会不会红」的对照表 —— `README.md` 里「验过它不是恒真的」那句话的证据。

**不是**：通过率、覆盖率、质量分。这里的**红色是期望的结果**，一条红都没有才是坏消息。**别把红条数读成任何形式的得分。**

- 基线（一点没改）：**207 passed / 0 failed / 47 skipped**（= 全套 254 条），退出码 0，29.8s —— 先证明测试集本身是绿的，底下那些红才有意义。
- **「红 N 条」一律是相对基线多出来的**（扣掉基线本来就红的那些）：基线全绿时它与「原样数红条」逐字相同；基线红了时，原样的那个数也留在每条的明细里，扣没扣由读者自己核。**为什么要减这一下**：判据被污染之后照样给判定，正是这个装置盯别人的那件事（实测踩到过：基线红 2 条、靶子正好是那个文件，一条**按声明红掉**的变异被数成 3 条、判成「与声明不符」）。
- 上面这个规模**不含** `tests/test_mutation_evidence.py`（15 条）：那一组问的是「这份报告有没有过期」，而本模块每一轮都在被改坏的源码上跑 —— 它见到环境变量 `MIROFISH_MUTATION_RUN` 会跳过自己。「报告过期」由普通 `pytest` 抓，见那个文件。
- 13 个源文件跑完后逐字节还原：**是**（逐文件 `sha256` 见 `mutations_report.json` 的 `sources` / `sources_after`）。

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
| `K0` | 阴性对照 | 语义上什么都不改（只在 `STEP` 那行尾加一句注释） | 0 条 | **0 条** | 相符 |

共 **41** 处变异，其中 **41** 处的实测与声明相符。

## 逐条明细

每条的「改了什么」是**逐字节替换**（`old` → `new`），跑完立刻按字节还原。

`C6` 那条的 `+` 行被**刻意屏蔽**成上面那个占位符：那个写法一旦抄进这份报告，**报告自己就会被 `test_no_known_misquote_survives_in_our_materials` 抓红**（理由和 `README.md` 里不抄第二遍是同一条）。要看原样 —— 连同那个字面量本身 —— 去 `mutations_report.json`：后缀 `.json` 不在那条扫描的范围里。

### `G1` · 判据的边界写成 `>=`（顶格的消息会被误判成超限）

- 组：守卫　目标文件：`verification/tests/test_camel_guards.py`
- 声明：README「守卫：两个方向都要成立」：七处变异都变红
- 实测：目标文件红 **1** 条（相对基线多红的），整轮红 **1** 条、绿 198 条、跳过 55 条，退出码 1，27.43s
- 改：`camel_guards.py`

  ```diff
  -     if own_tokens > limit:
  +     if own_tokens >= limit:
  ```

- 红掉的用例（全部）：

  - `test_boundary_is_strict_greater_not_greater_equal`

<details><summary>原样输出（末 12 行）</summary>

```
..........s.........sssssss...sssss..........F.......................... [ 28%]
................................ssssssss................................ [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s...............                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_camel_guards.py::test_boundary_is_strict_greater_not_greater_equal
1 failed, 198 passed, 55 skipped in 24.22s
```

</details>

### `G2` · 整个守卫变成空操作（开头就把活原样交回原方法）

- 组：守卫　目标文件：`verification/tests/test_camel_guards.py`
- 声明：README「守卫：两个方向都要成立」：七处变异都变红
- 实测：目标文件红 **10** 条（相对基线多红的），整轮红 **10** 条、绿 189 条、跳过 55 条，退出码 1，27.95s
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
10 failed, 189 passed, 55 skipped in 24.76s
```

</details>

### `G3` · 变成「一律不切」（该切的那条路被永远关掉）

- 组：守卫　目标文件：`verification/tests/test_camel_guards.py`
- 声明：README「守卫：两个方向都要成立」：七处变异都变红
- 实测：目标文件红 **2** 条（相对基线多红的），整轮红 **2** 条、绿 197 条、跳过 55 条，退出码 1，27.78s
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
..........s.........sssssss...sssss.........FF.......................... [ 28%]
................................ssssssss................................ [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s...............                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_camel_guards.py::test_hands_back_when_message_itself_exceeds_limit
FAILED verification/tests/test_camel_guards.py::test_boundary_is_strict_greater_not_greater_equal
2 failed, 197 passed, 55 skipped in 24.45s
```

</details>

### `G4` · 逻辑步长调到比 camel 那个 `1e-6` 还细

- 组：守卫　目标文件：`verification/tests/test_camel_guards.py`
- 声明：README「守卫：两个方向都要成立」：七处变异都变红
- 实测：目标文件红 **1** 条（相对基线多红的），整轮红 **1** 条、绿 198 条、跳过 55 条，退出码 1，27.74s
- 改：`camel_guards.py`

  ```diff
  - STEP = 1e-3
  + STEP = 1e-7
  ```

- 红掉的用例（全部）：

  - `test_step_is_larger_than_camels_offset`

<details><summary>原样输出（末 12 行）</summary>

```
..........s.........sssssss...sssss....................F................ [ 28%]
................................ssssssss................................ [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s...............                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_camel_guards.py::test_step_is_larger_than_camels_offset
1 failed, 198 passed, 55 skipped in 24.61s
```

</details>

### `G5` · 时间戳不再往后推（拿掉严格递增那一步）

- 组：守卫　目标文件：`verification/tests/test_camel_guards.py`
- 声明：README「守卫：两个方向都要成立」：七处变异都变红
- 实测：目标文件红 **4** 条（相对基线多红的），整轮红 **4** 条、绿 195 条、跳过 55 条，退出码 1，28.16s
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
..........s.........sssssss...sssss..............F..FFF................. [ 28%]
................................ssssssss................................ [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s...............                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_camel_guards.py::test_timestamp_on_slicing_off_only_moves_the_clock
FAILED verification/tests/test_camel_guards.py::test_timestamp_is_strictly_increasing_across_calls
FAILED verification/tests/test_camel_guards.py::test_explicit_pair_is_pushed_apart_but_not_counted
FAILED verification/tests/test_camel_guards.py::test_timestamp_pushed_counts_only_our_own_reads
4 failed, 195 passed, 55 skipped in 24.97s
```

</details>

### `G6` · 去掉兜底（算不出 token 时不再交回原方法，直接抛）

- 组：守卫　目标文件：`verification/tests/test_camel_guards.py`
- 声明：README「守卫：两个方向都要成立」：七处变异都变红
- 实测：目标文件红 **1** 条（相对基线多红的），整轮红 **1** 条、绿 198 条、跳过 55 条，退出码 1，27.51s
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
..........s.........sssssss...sssss...........F......................... [ 28%]
................................ssssssss................................ [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s...............                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_camel_guards.py::test_hands_back_when_tokens_cannot_be_counted
1 failed, 198 passed, 55 skipped in 24.33s
```

</details>

### `G7` · `install` 不再幂等（第二次调用会套第二层补丁）

- 组：守卫　目标文件：`verification/tests/test_camel_guards.py`
- 声明：README「守卫：两个方向都要成立」：七处变异都变红
- 实测：目标文件红 **1** 条（相对基线多红的），整轮红 **1** 条、绿 198 条、跳过 55 条，退出码 1，28.28s
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
..........s.........sssssss...sssss...F................................. [ 28%]
................................ssssssss................................ [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s...............                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_camel_guards.py::test_install_is_idempotent - ...
1 failed, 198 passed, 55 skipped in 25.07s
```

</details>

### `V1` · 判词写死（直接把结论摆在预期那一侧，不再由读数算）

- 组：判词　目标文件：`verification/tests/test_repro_verdicts.py`
- 声明：README「判词」：判词写死 → 红 16 条
- 实测：目标文件红 **16** 条（相对基线多红的），整轮红 **16** 条、绿 183 条、跳过 55 条，退出码 1，27.51s
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
16 failed, 183 passed, 55 skipped in 24.72s
```

</details>

### `V2` · 判据的 `<` 写成 `<=`（`gap == tick` 会被算成同一拍）

- 组：判词　目标文件：`verification/tests/test_repro_verdicts.py`
- 声明：README「判词」：`<` 写成 `<=` → 红 3 条
- 实测：目标文件红 **3** 条（相对基线多红的），整轮红 **3** 条、绿 196 条、跳过 55 条，退出码 1，20.47s
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
..........s.........sssssss...sssss..................................... [ 28%]
................................ssssssss................................ [ 56%]
..sssssssssssssssssssssssssssssssss....F............F.............F..... [ 85%]
......................s...............                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_repro_verdicts.py::test_verdict_never_contradicts_its_own_numbers[True-0.0004-0.0004]
FAILED verification/tests/test_repro_verdicts.py::test_verdict_never_contradicts_its_own_numbers[False-0.0004-0.0004]
FAILED verification/tests/test_repro_verdicts.py::test_boundary_gap_equal_to_tick_counts_as_crossed
3 failed, 196 passed, 55 skipped in 18.38s
```

</details>

### `V3` · 去掉「与预期相反」那一支（与预期不符时折回预期那一侧的话术）

- 组：判词　目标文件：`verification/tests/test_repro_verdicts.py`
- 声明：README「判词」：去掉「与预期相反」那一支 → 红 3 条
- 实测：目标文件红 **3** 条（相对基线多红的），整轮红 **3** 条、绿 196 条、跳过 55 条，退出码 1，24.93s
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
..........s.........sssssss...sssss..................................... [ 28%]
................................ssssssss................................ [ 56%]
..sssssssssssssssssssssssssssssssss...........................FF...F.... [ 85%]
......................s...............                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_repro_verdicts.py::test_the_actual_regression_is_reported_not_smoothed
FAILED verification/tests/test_repro_verdicts.py::test_opposite_direction_of_surprise_is_also_reported
FAILED verification/tests/test_repro_verdicts.py::test_zero_tick_does_not_explode
3 failed, 196 passed, 55 skipped in 21.86s
```

</details>

### `C1` · 行号错开一格（933 → 934）

- 组：引文·上半　目标文件：`verification/tests/test_citations.py`
- 声明：README「引文：文档里的行号不许腐烂」：上半五处变异都红
- 实测：目标文件红 **1** 条（相对基线多红的），整轮红 **1** 条、绿 198 条、跳过 55 条，退出码 1，24.14s
- 改：`test_citations.py`

  ```diff
  - ("camel.agents.chat_agent", 933,
  + ("camel.agents.chat_agent", 934,
  ```

- 红掉的用例（全部）：

  - `test_cited_line_still_says_what_we_say_it_says[camel.agents.chat_agent-934-base_chunk_size`

<details><summary>原样输出（末 12 行）</summary>

```
..........s.........sssssss...sssss...............................F..... [ 28%]
................................ssssssss................................ [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s...............                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_citations.py::test_cited_line_still_says_what_we_say_it_says[camel.agents.chat_agent-934-base_chunk_size = max(1, remaining_budget) // 10-camel_guards / README \xa7\u2460\uff1a\u6b8b\u4f59\u9884\u7b97\u5148\u88ab //10 \u780d\u4e00\u5200]
1 failed, 198 passed, 55 skipped in 22.05s
```

</details>

### `C2` · 引一个越界的行号（884 → 999999）

- 组：引文·上半　目标文件：`verification/tests/test_citations.py`
- 声明：README「引文：文档里的行号不许腐烂」：上半五处变异都红
- 实测：目标文件红 **1** 条（相对基线多红的），整轮红 **1** 条、绿 198 条、跳过 55 条，退出码 1，20.86s
- 改：`test_citations.py`

  ```diff
  - ("camel.agents.chat_agent", 884,
  + ("camel.agents.chat_agent", 999999,
  ```

- 红掉的用例（全部）：

  - `test_cited_line_still_says_what_we_say_it_says[camel.agents.chat_agent-999999-remaining_budget`

<details><summary>原样输出（末 12 行）</summary>

```
..........s.........sssssss...sssss.............................F....... [ 28%]
................................ssssssss................................ [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s...............                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_citations.py::test_cited_line_still_says_what_we_say_it_says[camel.agents.chat_agent-999999-remaining_budget = max(0, token_limit - ctx_tokens)-README \xa7\u2460 / camel_guards\uff1a\u6b8b\u4f59\u9884\u7b97\u7528\u7684\u662f**\u622a\u65ad\u540e**\u7684 ctx_tokens]
1 failed, 198 passed, 55 skipped in 18.52s
```

</details>

### `C3` · 换成那一行没有的片段（`// 10` 写成 `// 100`）

- 组：引文·上半　目标文件：`verification/tests/test_citations.py`
- 声明：README「引文：文档里的行号不许腐烂」：上半五处变异都红
- 实测：目标文件红 **1** 条（相对基线多红的），整轮红 **1** 条、绿 198 条、跳过 55 条，退出码 1，28.76s
- 改：`test_citations.py`

  ```diff
  - "base_chunk_size = max(1, remaining_budget) // 10",
  + "base_chunk_size = max(1, remaining_budget) // 100",
  ```

- 红掉的用例（全部）：

  - `test_cited_line_still_says_what_we_say_it_says[camel.agents.chat_agent-933-base_chunk_size`

<details><summary>原样输出（末 12 行）</summary>

```
..........s.........sssssss...sssss...............................F..... [ 28%]
................................ssssssss................................ [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s...............                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_citations.py::test_cited_line_still_says_what_we_say_it_says[camel.agents.chat_agent-933-base_chunk_size = max(1, remaining_budget) // 100-camel_guards / README \xa7\u2460\uff1a\u6b8b\u4f59\u9884\u7b97\u5148\u88ab //10 \u780d\u4e00\u5200]
1 failed, 198 passed, 55 skipped in 25.65s
```

</details>

### `C4` · 引一个不存在的模块（`camel.memories.base` → `..._missing`）

- 组：引文·上半　目标文件：`verification/tests/test_citations.py`
- 声明：README「引文：文档里的行号不许腐烂」：上半五处变异都红
- 实测：目标文件红 **1** 条（相对基线多红的），整轮红 **1** 条、绿 197 条、跳过 56 条，退出码 1，27.05s
- 改：`test_citations.py`

  ```diff
  - ("camel.memories.base", 143,
  + ("camel.memories.base_missing", 143,
  ```

- 红掉的用例（全部）：

  - `test_every_citation_module_is_reachable`

<details><summary>原样输出（末 12 行）</summary>

```
..........s.........sssssss...sssss..................................... [ 28%]
.....s...........F..............ssssssss................................ [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s...............                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_citations.py::test_every_citation_module_is_reachable
1 failed, 197 passed, 56 skipped in 24.85s
```

</details>

### `C5` · 同一行引两遍（把 env:55 那条改成 env:193，片段也跟着改成 193 行的）

- 组：引文·上半　目标文件：`verification/tests/test_citations.py`
- 声明：README「引文：文档里的行号不许腐烂」：上半五处变异都红
- 实测：目标文件红 **1** 条（相对基线多红的），整轮红 **1** 条、绿 198 条、跳过 55 条，退出码 1，22.94s
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
..........s.........sssssss...sssss..................................... [ 28%]
..................F.............ssssssss................................ [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s...............                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_citations.py::test_no_duplicate_citations - As...
1 failed, 198 passed, 55 skipped in 20.59s
```

</details>

### `C6` · 把那个错引写法**植回 `camel_guards.py`**，看扫描抓不抓

- 组：引文·下半　目标文件：`verification/tests/test_citations.py`
- 声明：README「引文」：下半把那个写法植回 `camel_guards.py`，当场红
- 实测：目标文件红 **1** 条（相对基线多红的），整轮红 **1** 条、绿 198 条、跳过 55 条，退出码 1，24.38s
- 改：`camel_guards.py`

  ```diff
  - base_chunk_size - prefix_token_len
  + ＜那个被引错的字面量，本报告不抄＞
  ```

- 红掉的用例（全部）：

  - `test_no_known_misquote_survives_in_our_materials[base_chunk_size\\s*-\\s*12-base_chunk_size`

<details><summary>原样输出（末 12 行）</summary>

```
..........s.........sssssss...sssss..................................... [ 28%]
.....................F..........ssssssss................................ [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s...............                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_citations.py::test_no_known_misquote_survives_in_our_materials[base_chunk_size\\s*-\\s*12-base_chunk_size - prefix_token_len\uff08948 \u884c\uff1b\u90a3\u4e2a\u51cf\u6570\u662f 943 \u884c**\u91cf**\u51fa\u6765\u7684\uff09-\u628a\u300c\u524d\u7f00\u957f\u5ea6\u300d\u8fd9\u4e2a\u5f53\u573a\u91cf\u51fa\u6765\u7684\u503c\u5199\u6b7b\u6210\u4e86\u5b57\u9762\u91cf 12\uff0c\u8fd8\u6807\u6210 948 \u884c\u7684\u539f\u6587 \u2014\u2014 \u6570\u503c\u4e0a\u5bf9\uff08gpt-4o-mini \u4e0b\u6070\u597d\u662f 12\uff09\uff0c**\u5f15\u6587\u4e0a\u9519**\uff1a\u6362\u4e2a\u5206\u8bcd\u5668\u5c31\u4e0d\u662f 12]
1 failed, 198 passed, 55 skipped in 21.13s
```

</details>

### `C7` · 逐字块里的行号错开一格（886 → 885，那一行是空行）

- 组：引文·逐字块　目标文件：`verification/tests/test_citations.py`
- 声明：README「引文」：标了行号的逐字块，行号错了当场红
- 实测：目标文件红 **1** 条（相对基线多红的），整轮红 **1** 条、绿 198 条、跳过 55 条，退出码 1，20.85s
- 改：`README.md`

  ```diff
  - if current_tokens <= remaining_budget:                         # 886
  + if current_tokens <= remaining_budget:                         # 885
  ```

- 红掉的用例（全部）：

  - `test_verbatim_blocks_match_upstream_line_for_line[-camel.agents.chat_agent-0]`

<details><summary>原样输出（末 12 行）</summary>

```
..........s.........sssssss...sssss..................................... [ 28%]
.......................F........ssssssss................................ [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s...............                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_citations.py::test_verbatim_blocks_match_upstream_line_for_line[-camel.agents.chat_agent-0]
1 failed, 198 passed, 55 skipped in 18.99s
```

</details>

### `J1` · 贴界退化成「碰过这一臂或这一量的格子都算贴界」（一格贴界，整行整列降级）

- 组：裁决　目标文件：`verification/tests/test_adjudicate.py`
- 声明：README「裁决：三种结果不是两种」：贴界按单元格判，退化成乘积当场红
- 实测：目标文件红 **1** 条（相对基线多红的），整轮红 **1** 条、绿 198 条、跳过 55 条，退出码 1，22.11s
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
.F........s.........sssssss...sssss..................................... [ 28%]
................................ssssssss................................ [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s...............                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_adjudicate.py::test_railing_is_judged_per_cell_not_by_the_product_of_two_sets
1 failed, 198 passed, 55 skipped in 18.95s
```

</details>

### `J2` · 把「缺读数」折进「否决」—— 正是本装置抓别人的那件事

- 组：裁决·缺读数　目标文件：`verification/tests/test_adjudicate.py`
- 声明：README「裁决」：缺读数判不可判定，折进「否决」当场红
- 实测：目标文件红 **4** 条（相对基线多红的），整轮红 **5** 条、绿 194 条、跳过 55 条，退出码 1，27.51s
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
F...F....FsF........sssssss...sssss..................................... [ 28%]
................................ssssssss.......................F........ [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s...............                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_adjudicate.py::test_the_first_real_assertion_is_not_vacuous
FAILED verification/tests/test_adjudicate.py::test_a_reading_that_is_not_there_is_undecided_not_failed
FAILED verification/tests/test_adjudicate.py::test_every_falsifier_result_the_checker_can_emit_is_renderable
FAILED verification/tests/test_adjudicate.py::test_undecided_is_not_counted_as_vacuous
FAILED verification/tests/test_e2e_stub.py::test_a_missing_e2e_report_makes_that_layer_undecided
5 failed, 194 passed, 55 skipped in 24.45s
```

</details>

### `J3` · falsifier 只查在不在，**不实例化** —— 于是它永远「翻得动」

- 组：裁决·恒真　目标文件：`verification/tests/test_adjudicate.py`
- 声明：README「裁决·非空泛」：falsifier 必须实例化，只查在不在当场红
- 实测：目标文件红 **2** 条（相对基线多红的），整轮红 **2** 条、绿 197 条、跳过 55 条，退出码 1，27.78s
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
..F....F..s.........sssssss...sssss..................................... [ 28%]
................................ssssssss................................ [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s...............                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_adjudicate.py::test_a_claim_that_no_single_change_can_flip_is_not_trusted
FAILED verification/tests/test_adjudicate.py::test_a_claim_whose_falsifier_does_not_bite_is_vacuous
2 failed, 197 passed, 55 skipped in 24.33s
```

</details>

### `J4` · **判据恒真也照退 0** —— 这张表开始装绿

- 组：裁决·恒真　目标文件：`verification/tests/test_adjudicate.py`
- 声明：README「裁决：恒真就不许退 0」：判据恒真时退出码必须非 0
- 实测：目标文件红 **1** 条（相对基线多红的），整轮红 **1** 条、绿 198 条、跳过 55 条，退出码 1，22.8s
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
..........s........Fsssssss...sssss..................................... [ 28%]
................................ssssssss................................ [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s...............                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_adjudicate.py::test_a_vacuous_claim_makes_the_table_refuse_to_exit_green
1 failed, 198 passed, 55 skipped in 20.51s
```

</details>

### `J5` · **「没测到」退 1**（退成「没达到预期」）—— 正是本装置抓别人的那件事，落在自己身上

- 组：裁决·缺读数　目标文件：`verification/tests/test_adjudicate.py`
- 声明：README「退出码：三种不是两种」：前提不成立退 2，折成 1 当场红
- 实测：目标文件红 **1** 条（相对基线多红的），整轮红 **1** 条、绿 198 条、跳过 55 条，退出码 1，20.32s
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
..........s......F..sssssss...sssss..................................... [ 28%]
................................ssssssss................................ [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s...............                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_adjudicate.py::test_no_report_is_undecided_and_gets_no_traceback
1 failed, 198 passed, 55 skipped in 18.07s
```

</details>

### `J6` · **装守卫时不安排落盘** —— 计数照样烂在内存里，一次真跑还是什么都看不见（回到补它之前那个状态）

- 组：守卫·计数落盘　目标文件：`verification/tests/test_camel_guards.py`
- 声明：README「守卫端到端」：装了守卫就得安排落盘，拿掉当场红
- 实测：目标文件红 **1** 条（相对基线多红的），整轮红 **1** 条、绿 198 条、跳过 55 条，退出码 1，26.84s
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
..........s.........sssssss...sssss......................F.............. [ 28%]
................................ssssssss................................ [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s...............                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_camel_guards.py::test_install_arranges_to_dump_counters_at_exit
1 failed, 198 passed, 55 skipped in 23.47s
```

</details>

### `J7` · 端到端报告不在时**编一份读数**出来 —— 最容易写下的那种「补全」，而且编完那张表看着更完整

- 组：裁决·端到端　目标文件：`verification/tests/test_e2e_stub.py`
- 声明：README「裁决：三种结果不是两种」：端到端读数缺了要判不可判定，编一份补上当场红
- 实测：目标文件红 **1** 条（相对基线多红的），整轮红 **1** 条、绿 198 条、跳过 55 条，退出码 1，22.05s
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
..........s.........sssssss...sssss..................................... [ 28%]
................................ssssssss......................F......... [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s...............                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_e2e_stub.py::test_a_missing_e2e_report_is_none_not_an_exception
1 failed, 198 passed, 55 skipped in 19.74s
```

</details>

### `P1` · 把 `tiktoken` 的锁定从 `==0.7.0` 放成 `>=0.1`

- 组：环境·版本钉　目标文件：`verification/tests/test_environment_pins.py`
- 声明：环境版本钉：直接依赖被放成开区间 → 当场红
- 实测：目标文件红 **1** 条（相对基线多红的），整轮红 **1** 条、绿 206 条、跳过 47 条，退出码 1，24.94s
- 改：`requirements.txt`

  ```diff
  - tiktoken==0.7.0
  + tiktoken>=0.1
  ```

- 红掉的用例（全部）：

  - `test_tiktoken_is_pinned_even_though_it_arrives_transitively`

<details><summary>原样输出（末 12 行）</summary>

```
..........s.........sssssss...sssss..................................... [ 28%]
........................................................................ [ 56%]
F.sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s...............                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_environment_pins.py::test_tiktoken_is_pinned_even_though_it_arrives_transitively
1 failed, 206 passed, 47 skipped in 21.76s
```

</details>

### `D1` · 清单改动表里把一个数目改歪（`requirements.txt` 15 → 16）

- 组：清单·改动表　目标文件：`verification/tests/test_docs_claims.py`
- 声明：清单第一节：改动数目和现场 diff 对不上 → 当场红
- 实测：目标文件红 **1** 条（相对基线多红的），整轮红 **2** 条、绿 205 条、跳过 47 条，退出码 1，27.53s
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
..........s.........sssssss...sssss..................................... [ 28%]
.....................................F.................................. [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s............F..                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_docs_claims.py::test_the_diff_numbers_match_a_live_diff
FAILED verification/tests/test_upstream_baseline.py::test_notice_states_the_same_numbers_as_the_inventory
2 failed, 205 passed, 47 skipped in 23.65s
```

</details>

### `N1` · 把「这里是不是 git 仓库」那道门焊死（`_is_repo()` 恒为假）

- 组：上游基线　目标文件：`verification/tests/test_upstream_baseline.py`
- 声明：上游基线：门恒假 → 本仓里那条阴性对照当场红（**本仓明明在仓库里，却被判成不是**）
- 实测：目标文件红 **1** 条（相对基线多红的），整轮红 **1** 条、绿 194 条、跳过 59 条，退出码 1，22.31s
- 改：`test_upstream_baseline.py`

  ```diff
  -     return out.returncode == 0 and out.stdout.strip() == "true"
  +     return False  # 变异：门永远关着
  ```

- 红掉的用例（全部）：

  - `test_the_repo_check_is_not_vacuous`

<details><summary>原样输出（末 12 行）</summary>

```
..........s.........sssssss...sssss..................................... [ 28%]
................................ssssssss................................ [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s........ssF..ss                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_upstream_baseline.py::test_the_repo_check_is_not_vacuous
1 failed, 194 passed, 59 skipped in 20.30s
```

</details>

### `O1` · 汇总驱动把落点那道门摘了（`--out` 不通也照跑三个复现）

- 组：落点　目标文件：`verification/tests/test_repro_verdicts.py`
- 声明：落点：门被摘掉 → 「坏落点要在动手之前退」当场红
- 实测：目标文件红 **1** 条（相对基线多红的），整轮红 **1** 条、绿 198 条、跳过 55 条，退出码 1，61.74s
- 改：`run_all.py`

  ```diff
  -         rc = P.refuse_out_path(f"{args.out}.md", f"{args.out}.json")
  +         rc = None  # 变异：落点这道门形同虚设
  ```

- 红掉的用例（全部）：

  - `test_run_all_refuses_a_bad_out_place_before_running_the_repros`

<details><summary>原样输出（末 12 行）</summary>

```
..........s.........sssssss...sssss..................................... [ 28%]
................................ssssssss................................ [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s..F............                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_repro_verdicts.py::test_run_all_refuses_a_bad_out_place_before_running_the_repros
1 failed, 198 passed, 55 skipped in 58.51s
```

</details>

### `O2` · 裁决把落点那道门摘了（判定照算，算完才发现写不出去）

- 组：落点　目标文件：`verification/tests/test_adjudicate.py`
- 声明：落点：裁决那道门被摘掉 → 当场红
- 实测：目标文件红 **1** 条（相对基线多红的），整轮红 **1** 条、绿 198 条、跳过 55 条，退出码 1，26.79s
- 改：`adjudicate.py`

  ```diff
  -     rc = P.refuse_out_path(args.json, args.md)
  +     rc = None  # 变异：落点这道门形同虚设
  ```

- 红掉的用例（全部）：

  - `test_a_bad_place_stops_both_entry_points_before_they_compute`

<details><summary>原样输出（末 12 行）</summary>

```
..........s.........sssssss...sssssF.................................... [ 28%]
................................ssssssss................................ [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s...............                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_adjudicate.py::test_a_bad_place_stops_both_entry_points_before_they_compute
1 failed, 198 passed, 55 skipped in 23.51s
```

</details>

### `O3` · 裁决写不下去时报「没达到预期」（`2` 改成 `1`）

- 组：落点　目标文件：`verification/tests/test_adjudicate.py`
- 声明：落点：写不下去时折成 `1` → 当场红（`1` 会把人指去查判据）
- 实测：目标文件红 **1** 条（相对基线多红的），整轮红 **1** 条、绿 198 条、跳过 55 条，退出码 1，26.64s
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
..........s.........sssssss...sssss.F................................... [ 28%]
................................ssssssss................................ [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s...............                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_adjudicate.py::test_a_write_that_fails_anyway_is_still_not_measured
1 failed, 198 passed, 55 skipped in 23.38s
```

</details>

### `O4` · 自证把落点那道门摘了

- 组：落点　目标文件：`verification/tests/test_adjudicate.py`
- 声明：落点：自证那道门被摘掉 → 当场红
- 实测：目标文件红 **1** 条（相对基线多红的），整轮红 **1** 条、绿 198 条、跳过 55 条，退出码 1，27.38s
- 改：`selfproof.py`

  ```diff
  -     rc = P.refuse_out_path(args.json, args.md)
  +     rc = None  # 变异：落点这道门形同虚设
  ```

- 红掉的用例（全部）：

  - `test_a_bad_place_stops_both_entry_points_before_they_compute`

<details><summary>原样输出（末 12 行）</summary>

```
..........s.........sssssss...sssssF.................................... [ 28%]
................................ssssssss................................ [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s...............                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_adjudicate.py::test_a_bad_place_stops_both_entry_points_before_they_compute
1 failed, 198 passed, 55 skipped in 24.02s
```

</details>

### `O5` · 端到端把落点那道门摘了（真去跑那一局，跑完才发现写不出去）

- 组：落点　目标文件：`verification/tests/test_repro_verdicts.py`
- 声明：落点：端到端那道门被摘掉 → 当场红
- 实测：目标文件红 **1** 条（相对基线多红的），整轮红 **1** 条、绿 198 条、跳过 55 条，退出码 1，27.55s
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
..........s.........sssssss...sssss..................................... [ 28%]
................................ssssssss................................ [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s...F...........                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_repro_verdicts.py::test_the_other_three_entry_points_refuse_a_bad_out_place_too
1 failed, 198 passed, 55 skipped in 24.06s
```

</details>

### `O6` · 对账把落点那道门摘了

- 组：落点　目标文件：`verification/tests/test_repro_verdicts.py`
- 声明：落点：对账那道门被摘掉 → 当场红
- 实测：目标文件红 **1** 条（相对基线多红的），整轮红 **1** 条、绿 198 条、跳过 55 条，退出码 1，26.93s
- 改：`reconcile_selfcheck.py`

  ```diff
  -     rc = P.refuse_out_path(args.json, args.md)
  +     rc = None  # 变异：落点这道门形同虚设
  ```

- 红掉的用例（全部）：

  - `test_the_other_three_entry_points_refuse_a_bad_out_place_too`

<details><summary>原样输出（末 12 行）</summary>

```
..........s.........sssssss...sssss..................................... [ 28%]
................................ssssssss................................ [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s...F...........                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_repro_verdicts.py::test_the_other_three_entry_points_refuse_a_bad_out_place_too
1 failed, 198 passed, 55 skipped in 23.61s
```

</details>

### `O7` · 留痕把落点那道门摘了（⚠️ 这条改的是本文件自己）

- 组：落点　目标文件：`verification/tests/test_repro_verdicts.py`
- 声明：落点：留痕那道门被摘掉 → 当场红
- 实测：目标文件红 **1** 条（相对基线多红的），整轮红 **1** 条、绿 198 条、跳过 55 条，退出码 1，26.7s
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
..........s.........sssssss...sssss..................................... [ 28%]
................................ssssssss................................ [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s...F...........                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_repro_verdicts.py::test_the_other_three_entry_points_refuse_a_bad_out_place_too
1 failed, 198 passed, 55 skipped in 23.71s
```

</details>

### `X1` · 汇总驱动把契约外的退出码原样放过去（`2` 那道判据形同虚设）

- 组：没测到·不许折　目标文件：`verification/tests/test_repro_verdicts.py`
- 声明：没测到：被信号杀死的复现不许记成「达到预期」→ 当场红
- 实测：目标文件红 **1** 条（相对基线多红的），整轮红 **1** 条、绿 198 条、跳过 55 条，退出码 1，29.09s
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
..........s.........sssssss...sssss..................................... [ 28%]
................................ssssssss................................ [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
.....................Fs...............                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_repro_verdicts.py::test_an_out_of_contract_exit_code_is_not_measured
1 failed, 198 passed, 55 skipped in 26.17s
```

</details>

### `X2` · 端到端把「没跑完」判成「没达到预期」（`rc != 0` 排到前面）

- 组：没测到·不许折　目标文件：`verification/tests/test_e2e_stub.py`
- 声明：没测到：负退出码 / argparse 的 `2` 不许判成「没达到预期」→ 当场红
- 实测：目标文件红 **1** 条（相对基线多红的），整轮红 **1** 条、绿 198 条、跳过 55 条，退出码 1，29.87s
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
..........s.........sssssss...sssss..................................... [ 28%]
................................ssssssss...........F.................... [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s...............                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_e2e_stub.py::test_an_arm_that_never_finished_is_undecided_not_failed
1 failed, 198 passed, 55 skipped in 26.68s
```

</details>

### `X3` · 对账时不一致就不再把「抽不出来」升到 `2`

- 组：没测到·不许折　目标文件：`verification/tests/test_repro_verdicts.py`
- 声明：没测到：有一边抽不出来就必须退 `2`，不许被那处不一致顶掉 → 当场红
- 实测：目标文件红 **1** 条（相对基线多红的），整轮红 **1** 条、绿 198 条、跳过 55 条，退出码 1，28.2s
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
..........s.........sssssss...sssss..................................... [ 28%]
................................ssssssss................................ [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s.....F.........                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_repro_verdicts.py::test_a_missing_number_does_not_disappear_behind_a_mismatch
1 failed, 198 passed, 55 skipped in 24.85s
```

</details>

### `X4` · 对账的收尾退回 `elif`（两件事只能说出前一件）

- 组：没测到·不许折　目标文件：`verification/tests/test_repro_verdicts.py`
- 声明：没测到：「没量到」和「对不上」必须各自说一遍 → 当场红
- 实测：目标文件红 **1** 条（相对基线多红的），整轮红 **1** 条、绿 198 条、跳过 55 条，退出码 1，28.56s
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
..........s.........sssssss...sssss..................................... [ 28%]
................................ssssssss................................ [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s.....F.........                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_repro_verdicts.py::test_a_missing_number_does_not_disappear_behind_a_mismatch
1 failed, 198 passed, 55 skipped in 25.20s
```

</details>

### `X5` · 产物那一栏又抄了一份 `0/1/2 → 措辞`（打屏与产物分家）

- 组：没测到·不许折　目标文件：`verification/tests/test_repro_verdicts.py`
- 声明：没测到：措辞表只许有一份 → 抄第二份当场红
- 实测：目标文件红 **1** 条（相对基线多红的），整轮红 **1** 条、绿 198 条、跳过 55 条，退出码 1，27.32s
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
..........s.........sssssss...sssss..................................... [ 28%]
................................ssssssss................................ [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s......F........                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_repro_verdicts.py::test_the_verdict_wording_lives_in_exactly_one_table
1 failed, 198 passed, 55 skipped in 25.13s
```

</details>

### `X6` · 裁决不再查形状（「是 JSON 但结构不对」重新变成 traceback）

- 组：没测到·不许折　目标文件：`verification/tests/test_adjudicate.py`
- 声明：没测到：读得成 JSON 不等于结构对 → 当场红
- 实测：目标文件红 **1** 条（相对基线多红的），整轮红 **1** 条、绿 198 条、跳过 55 条，退出码 1，22.08s
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
..........s.......F.sssssss...sssss..................................... [ 28%]
................................ssssssss................................ [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s...............                                   [100%]
=========================== short test summary info ===========================
FAILED verification/tests/test_adjudicate.py::test_a_report_that_is_readable_json_but_wrongly_shaped_is_refused
1 failed, 198 passed, 55 skipped in 19.97s
```

</details>

### `K0` · 语义上什么都不改（只在 `STEP` 那行尾加一句注释）

- 组：阴性对照　目标文件：`verification/tests/test_camel_guards.py`
- 声明：本模块自己的纪律：不做任何语义改动的编辑，一条都不许红
- 实测：目标文件红 **0** 条（相对基线多红的），整轮红 **0** 条、绿 199 条、跳过 55 条，退出码 0，23.27s
- 改：`camel_guards.py`

  ```diff
  - STEP = 1e-3
  + STEP = 1e-3  # 阴性对照：这行不该有行为差异
  ```

- 一条都没红 —— 这正是这一条**期望**的结果。

<details><summary>原样输出（末 12 行）</summary>

```
..........s.........sssssss...sssss..................................... [ 28%]
................................ssssssss................................ [ 56%]
..sssssssssssssssssssssssssssssssss..................................... [ 85%]
......................s...............                                   [100%]
199 passed, 55 skipped in 21.92s
```

</details>

## 结论

**41 处变异全部按声明对上（其中 `K0` 是阴性对照：按声明**一条都不该红**），基线全绿，源文件逐字节还原。** 这份测试集不是恒真的 —— 它有**会被改坏**的地方，而那些地方都被盯着；反过来，也有地方**被盯着「改了却什么都不该红」**：那处证明红是**冲着这个缺陷**红的，而不是改一行字就红。
