# 当前进展与完善方向

核查日期：2026-10-04（Asia/Shanghai）。源码基线：`local-fork` / `a252f98`，项目版本 `0.3.2`。

本文件是本次核查的当前进度入口。历史方案和实施记录保留各自时间点的事实；判断当前状态时，应结合下列复核结果。此次检查原有 20 份 Markdown 的结构、UTF-8 与本地链接，重点对照近期实施记录、当前源码、评测事件和已有测试。没有重做外部仓库调研或在线平台判题。

## 1. 结论与推荐顺序

项目已具备单个本地 dsh Worker 的 Web 题求解、结果留存、standby 提示交付和多模型线探索性评测能力。此前 D04 生产接线、D07 Compose 注入和 D08 记账修正已经进入源码，不能继续按早期审计表将它们列为完全未实现。

但目前还不能认定“运行验收与证据闭环全部完成”。本次发现一个确定的构造回归，确认评测证据判定仍有缺口，并发现 D05 live hint 的验收描述不符合原始事件顺序。

建议顺序：

1. **修复 `CliSolver` 构造回归，恢复已有真实依赖测试。**
2. **打通事件与原始产物的评测回查，统一成功语义和运行绑定。** 同批处理端口映射、事件作用域和技能指纹噪声。
3. **完成 writeup 的采集、上下文交付、文件服务和界面展示。** 仅添加截图脚本和提示词不能完成产品闭环。
4. **补 D05 live hint、重启恢复，以及 D04/D07 的运行级验收。**
5. **在统一预算和题集条件下比较单 Worker 改进。** 再决定题型提示、专项工具包和调度精简的收益。

继续保留当前 Coordinator 与独立 Flag gate。现有证据仍不足以支持优先做全量上游覆盖、多模型并行或训练。

## 2. 当前可核实的基线

| 项目 | 本次观察 |
|---|---|
| Git | 开始时工作区干净；`local-fork` 已跟踪 `origin/local-fork`；本地缓存比较为 `0 / 0`。未 fetch，不据此声称远端实时状态 |
| Docker | 可用；未发现运行中的 Muteki 容器。未发现 8000、8010、3001、3011、18200、18202、18210、18214 的监听 |
| 配置 | 单 dsh Worker，`start_workers=max_workers=1`，`race_scout=false`，bridge；planner/titler 当前为 Occamy `18214`，不是旧记录中的 Signal/Bonsai |
| 产品预算 | `wall_clock_budget=0`、`max_total_workers=0`、`cost_budget_usd=0`；按当前语义不设限。评测的 600s/1200s 不等于产品默认预算 |
| 资源配置 | Compose 已透传 D07 四键及 D04 连续失败上限；当前内存/CPU/PID 为空，required=0，连续失败上限=5 |
| 镜像 | `muteki-web:latest` 为 `4adc75bec6c2`；当前 `cli_solver.py` 与镜像中该文件 SHA-256 相同。仅验证此文件，不能扩展为整个镜像一致 |
| 测试环境 | 宿主 Python 3.14.7 缺 pytest/pydantic/httpx/dsh/fastapi；产品镜像有业务依赖，但缺 pytest |
| 结果资料 | `results.jsonl` 共 91 行，混合历史实验；`results-eval-v3.jsonl` 仅 26 行，不包含后续 D05 两场与 Occamy 七场 |

## 3. 本次新增或收窄的判断

### 3.1 必须先修：默认产物存储的初始化顺序错误

位置：[cli_solver.py](../muteki/solver/cli_solver.py)，897–908 行。

`self.artifacts = artifacts or ArtifactStore(...)` 在 903 行访问 `self._workdir`，而该属性到 908 行才赋值。只要调用方没有显式传入 `artifacts`，构造即抛出：

```text
AttributeError: 'CliSolver' object has no attribute '_workdir'
```

本次挂载当前源码，在真实依赖镜像内重跑 `tests.test_upstream_backports`，10 项中 4 项因此报错。包含有 workdir 与无 workdir 的调用。

Web 主路径在 [drivers.py](../apps/web/drivers.py) 974、1043 行显式传入 `ArtifactStore`，因此可以绕过该分支；此前 Web 跑题成功不能证明直接构造路径可用。当前镜像的该源码与工作区一致。

修复应在原构造层完成：先建立 workdir 状态，或用构造参数确定默认路径；保持调用方显式传入的存储不变。验收为已有 10 项回移测试恢复通过，并确认默认/显式存储的生命周期。

### 3.2 高优先级：评测证据链尚未闭环

位置：[eval_verdict.py](../labs/nyu-ctf/eval_verdict.py)、[run_challenge.py](../labs/nyu-ctf/run_challenge.py)。

已有进展：官方 Flag 不匹配不再被无条件 Gate 回退覆盖；外部多 Flag 判定已由 any 改为 all；增加了 `evidence_links` 和 `unlinked_flags`。

仍存在以下问题。本次使用当前模块的真实导入执行内存夹具，没有修改历史数据：

| 夹具 | 当前实际结果 | 缺口 |
|---|---|---|
| 无官方 Flag、只有 solved=true 终态、没有工具输出 | `verdict.solved=false`，但 harness 最终 `solved=true` | `_eval_solved()` 在无官方值时直接返回 `gate_solved`，绕过新增证据判定 |
| 预期两枚 Flag，仅一枚有输出且被 Gate 接受 | `verdict.solved=true` | Gate 路径没有检查全部预期 Flag；外部判定的 all 不覆盖此路径 |
| `run.finished` 明确 `solved=false`，但携带已在工具输出出现的 Flag | `verdict.solved=true` | 接受事件识别主要检查类型和字符串，未要求该终态明确成功 |
| 第 1 代输出 + 第 2 代接受，指定 `attempt=2` | `solved=true`、`attempt_matched=true` | 只过滤接受事件的代次，未绑定输出所属 Worker/代次 |
| Flag 只出现在 `tool.result` 的命令字段，响应不含 Flag | `verdict.solved=true` | 匹配整个事件 JSON，不仅匹配真实输出字段 |

这些是评测层的可复现缺陷，不能等同为生产 Flag gate 已被绕过，也不能据此推翻所有历史成功。

另有两个实际消费缺口：

- 评测器只读事件，没有读取 `artifact_id` 对应的原文。原始输出位于实际 Web 工作区的 `data/sessions/<run>/workspace/arts/`。本次核实 `run-22883` seq 50 引用的 `c0f036d9850d.txt` 存在且含本场 Flag，证明新落盘链至少已有真实样本。
- `run-22881` 的记录同时为 `solved=true`、`gate_accepted=false`，当前重放也无法获得输出链接；其 `workspace/arts` 没有可用原文。不能以“已修复落盘”追溯宣布旧证据恢复。

下一步应以 `(run, worker, attempt, tool call, output/artifact)` 关联证据；读取受限工作区内的原始输出，保留缺失原因；把 Gate 判定、证据复核和外部判题明确分开。最终用于能力统计的成功字段应消费同一套判据，历史 Gate 结果另留字段。

### 3.3 D05 的“运行中 live hint 已通过”需要更正

记录：[D05验收与D10绑定记录](D05验收与D10绑定记录-2026-10-04.md) 第 2 节。

本次只读重放 [run-22881 原始事件](../data/sessions/run-22881.jsonl)：

| seq | 事件 |
|---|---|
| 49 | `run.finished`，`solved=true` |
| 50 | hint `received`，发生在终态约 2.29 秒后 |
| 53 | `effect_observed`，detail 为 `standby prompt delivery confirmed` |

该证据验证的是完成后 standby 提示交付，不能验证运行中 hint 没有打断 Worker。

`run-22882` 同样先在 seq 47 预算结束，再于 seq 48 收到 hint、seq 51 确认 standby 交付。它可以支持无 winner 的 standby 分支；归档主事件流中只见一条 `run.finished`，不能按实施记录所述把“第二条终态”当作已复核证据。

本次 `docker ps` 只证明当前无 Muteki 容器，不能独立证明历史每个取消路径都正确清理。D05 应标为：**standby 交付已有证据；live hint、长 hint、进程重启恢复和取消边界仍需专项验收**。

### 3.4 D10 已有记录绑定，但尚未实现完整环境冻结

位置：[eval_env.py](../labs/nyu-ctf/eval_env.py)、[run_challenge.py](../labs/nyu-ctf/run_challenge.py) 355、463 行。

- `freeze_eval_env()` 实际在运行结束、构造结果行时调用，不是第二批记录描述的“每次 run 启动时”。期间切换配置或更新镜像标签，会记录结束时环境。
- 两处调用均未传 attempt；本次核实最近 9 行 `env_binding.attempt` 全为 `null`，不是已绑定为 1。
- 模型块保存配置别名与端点，没有物理模型文件摘要、量化和推理参数；源码 commit+dirty 也不能恢复未提交的具体源码。
- 技能指纹包含 `.kbsearch-index.db` 与 `.mimosa/`。它们会使内容未改变的知识库出现指纹变化。
- `replay_eval.py` 不保留已有 `env_binding`，未写独立 verdict 版本，且 `replay_note` 仍称空 expected_flags 不置位，已经与新增 Gate-derived 逻辑不一致。

建议先在启动前生成实际选用配置的不可变绑定，再由结果行引用；传入真实 attempt。按明确清单排除运行索引，分别记录知识内容与工具状态。原始记录不覆盖，更正结果另存版本。

### 3.5 最新“快速小修”的方向成立，但 B1/B2 描述需要修正

依据：[下一步修复方案](下一步修复方案-writeup与批次-2026-10-04.md)。

- **B1 实际是端口错配。** 当前 [start.bat](../start.bat) 59–66 行选 Occamy 时设置 `PORT=18214`、`LINE=C`；[switch_line.py](../labs/nyu-ctf/switch_line.py) 的 C 指向 `8890`。当前启动器并没有引用 X4；仅添加 X4 而不改调用方不会修好。应统一启动端口与切换映射，并让切换失败中止启动，避免继续使用旧配置。
- **B2 不能直接按“无 solver_id 的首条 run.started”过滤。** `run-21289` 的两条 started 分别为 seq 6、247，两条均有 solver_id，scope 均为空。过滤后会没有起点。需要先定义 run/worker 事件语义，并为旧事件提供可解释的计时回退。当前 `replay_eval.py` 还只是复制旧 `elapsed_s`，本身没有重新计算启动耗时。
- **B3 指纹排除项确实未实现。** eval_env 与技能投影的哈希函数均遍历所有文件。

## 4. writeup 完善方案需要补齐的环节

目前有“生成复盘”入口、standby 生成文本和落盘路径；没有截图采集器、证据清单注入和图片展示闭环。

本次核实的具体边界：

1. **统一工作区路径。** `RunManager.workspace_dir()` 返回 `sessions/<run>/workspace/`；`drivers.py` 把 writeup 保存为该目录下的 `writeup.md`。最新方案与代码注释中的 `sessions/<run>/writeup.md` 少了 workspace。采集器、清单、Markdown 相对链接与下载接口应共享实际工作区定义。
2. **显式把证据清单交给模型。** `_RESPOND_WRITEUP_PROMPT` 禁止工具调用和文件系统搜索。把 JSON 放进目录并不能让模型读到它；宿主应把允许引用的图片、摘录、命令与来源标识注入该次生成上下文，或在模型正文生成后确定性附加证据章节。
3. **补齐读取与渲染。** 当前 `Conversation.tsx` 218 行直接渲染 `{text}`；Markdown 图片标记只会成为文本。后端本次查到的 FileResponse/StaticFiles 用于 UI 静态文件，没有 writeup 图片路由。需要以 run 为边界的图片/报告读取，以及 Markdown 图片渲染；不能仅检查 `writeup.md` 内是否出现图片语法。
4. **覆盖产品入口的生命周期。** 仅挂 `labs/nyu-ctf/run_challenge.py` 只能覆盖该评测脚本。普通 Web 发起的任务也需要证据采集入口。脚本中的 `stop_target()` 对 remote 题直接返回，不能把它视为统一平台销毁接口。
5. **区分执行时证据与事后重放。** 登录态、POST、一次性页面不一定能用 GET 重现；Docker 内部靶机域名也不一定从宿主可达。优先保存真实请求/响应，截图标明采集时间、来源和重放状态。采集失败应保留可解释原因，不能统一解释为实例过期。

推荐最小交付路径：

```text
真实工具输出/原始产物
  → 运行中或结束前采集证据清单与可用截图
  → 注入 writeup 上下文或确定性附录
  → 保存到同一 run workspace
  → Web 图片读取与 Markdown 展示
```

验收：在可控 Web 夹具中，保留旧方案的“首页 + 成功页至少 2 张截图”条件；同时验证页面显示、引用定位、刷新后读取、无截图说明和结束后生成。POST/会话态必须明确覆盖范围，不能以通用 GET 重放代替原始成功证据。采集超时不得阻断任务收尾。

## 5. D01–D11 当前状态

| 条目 | 复核状态 | 剩余主要工作 |
|---|---|---|
| D01 离线契约 | 未验收 | 本地端点清单、进程级禁公网要求、离线依赖与无云端回退验证 |
| D02 上下文/原文交付 | 部分完成，有构造回归 | 先修初始化，再完成 artifact 回查、读取记录和上下文预算 |
| D03 单 Worker/题型提示 | 单 Worker 已配置，模板收益未验证 | 在固定基线上逐项比较提示长度、规划调用和失败形态 |
| D04 启动失败/停滞 | 已生产接线，真实 mixin 测试通过 | 完整主循环故障注入、达到上限的终态与取消验证 |
| D05 hint/恢复 | standby 交付有事件证据 | live hint 重新验收；长 hint、重启恢复、取消边界 |
| D06 技能路由/版本 | 中文检索和投影 manifest 已实现 | 排除索引噪声、验证实际读取；受控刷新与旧副本识别 |
| D07 资源/产物 | Compose 与调用接线完成，当前无限额 | 用户指定或测量后选择限额；docker inspect、超限/清理；磁盘策略 |
| D08 用量/预算 | 本地端点分类与账本统一已有测试 | 恢复/多代次归约、Coordinator 覆盖范围和真实全链计量 |
| D09 专项工具/知识 | 有工具补齐与历史验收资料 | 本次未重跑完整镜像工具验收；根据失败样本选子包 |
| D10 评测/对照 | 四模型线探索记录，冻结与判据部分完成 | 本报告 3.2/3.4；同预算、重复、留出题与版本化重放 |
| D11 可复现交付 | Git 与跟踪分支已建立 | 模型/镜像/证据包和离线恢复演练；hash 清单不能代替备份 |

## 6. 模型进展应怎样表述

| 模型线 | 该批题数 | Gate 成功 | 预算/题 | 本次复核边界 |
|---|---:|---:|---:|---|
| Signal | 7 | 7 | 1200s | v3 中可直接由输出链接确认 5 场；另 2 场留有证据缺口。平台 7/7 属历史记录，本次未复核回执 |
| Swift | 7 | 4 | 1200s | v3 中输出链接确认 3 场，另 1 场缺口 |
| Bonsai | 7 | 4 | 1200s | v3 中输出链接确认 3 场，另 1 场缺口 |
| Occamy | 7 | 5 | 600s | 本次重放最近七场，5 场 Gate 与事件输出链接一致；LoveSQL、Knife 超时；尚无本次平台复判 |

Signal 在 v3 另有 5 场启动故障，应单列；不能把 12 场都当作模型推理样本。四线共 28 场 Web 探索运行，不等于 28 道不同题，也不等于同预算对照。

当前可保留 Signal 为求解覆盖基线候选、Occamy 为效率对照候选。不能从这批单轮小样本宣布模型排名、编排增益或未见题泛化。历史 Include 已有知识卡，应与留出题区分。

## 7. 文档阅读入口

| 用途 | 文档 |
|---|---|
| 当前核查与下一步 | 本文件；本次确认的回归和未验收项优先于历史完成表述 |
| writeup 候选设计 | [下一步修复方案](下一步修复方案-writeup与批次-2026-10-04.md)，结合本文件第 3.5、4 节修订后实施 |
| 最近实现范围 | [批次3第一批](批次3实施记录-核查第一批修复-2026-10-04.md)、[批次3第二批](批次3实施记录-第二批-D10与D06-2026-10-04.md)、[D05/D10记录](D05验收与D10绑定记录-2026-10-04.md) |
| 早期修复历史 | [批次0–1](批次0-1实施记录-2026-10-03.md)、[批次2](批次2实施记录-D07与D04-2026-10-03.md)；其中 Docker/认证阻塞是当时快照 |
| 历次审计依据 | [10月3日阶段审计](阶段审计复核与下一步方案-2026-10-03.md)、[批次0–1设计](下一步实施方案-批次0与批次1-2026-10-03.md)、[此前10月4日核查](项目进展核查与下一步优先级-2026-10-04.md)、[第二轮缺陷审计](CTF增强调研第二轮-缺陷审计-2026-10-03.md) |
| 工具与单 Worker 增强方向 | [D01–D11原方案](CTF增强实施方案-2026-10-03.md)、[仓库调研](CTF能力增强仓库调研-2026-10-03.md)、[BUUCTF_Agent建议](BUUCTF_Agent核查与改进建议-2026-10-03.md)、[9月提升方案](解题能力提升方案.md) |
| 评测历史 | [三线Web评测](三线Web简单题评测-2026-10-04.md)、[9月本地模型报告](本地模型CTF实测报告.md)；Occamy 新七场见 results.jsonl |
| 架构与版本历史 | [工作原理](工作原理.md)、[上游同步](上游同步评估-2026-10-03.md)、[差异基线](上游差异基线-2026-10-03.md)、[建仓记录](Git分支建立记录-2026-10-03.md) |

## 8. 本次验证与变更边界

已执行：

- `git status --short --branch`、`git log`、`git rev-list --left-right --count origin/local-fork...HEAD`：工作区基线干净、本地缓存无差异。
- 原有 20 份文档严格 UTF-8 解码与相对 Markdown 链接检查：通过；未访问外部链接。
- `docker compose config --format json`：退出码 0；只展示指定配置键和端口，没有输出完整环境配置。
- `docker ps`、端口监听检查：未发现 Muteki 服务运行；仅作当前状态观察。
- 宿主以下命令：**162 项通过，退出码 0**。出现一次未关闭 socket 的 ResourceWarning；技能来源缺失警告属于测试夹具。

```powershell
$env:TEMP='D:\AI\muteki-local\data'
$env:TMP='D:\AI\muteki-local\data'
$env:PYTHONDONTWRITEBYTECODE='1'
& 'D:\AI\muteki-local\.venv\Scripts\python.exe' -X utf8 -B -m unittest `
  tests.test_a03_free_text_sealing tests.test_usage_reduce tests.test_eval_verdict `
  tests.test_cost_pricing tests.test_worker_resources tests.test_dispatch_failure_governor `
  tests.test_ctf_kbsearch tests.test_ctf_tools tests.test_batch1_audit_fixes `
  tests.test_eval_env tests.test_worker_skills_projection
```

真实依赖环境验证命令如下：**18 项中 14 项通过、4 项报错，退出码 1**。其中第一批 D04/D08 的 8 项全通过，回移 10 项中 4 项触发第 3.1 节回归。不能表述为测试全绿。

```powershell
docker run --rm --pull never --network none --read-only --tmpfs /tmp `
  --mount 'type=bind,src=D:\AI\muteki-local\muteki,dst=/audit/muteki,readonly' `
  --mount 'type=bind,src=D:\AI\muteki-local\apps,dst=/audit/apps,readonly' `
  --mount 'type=bind,src=D:\AI\muteki-local\tests,dst=/audit/tests,readonly' `
  --mount 'type=bind,src=D:\AI\muteki-local\skills,dst=/audit/skills,readonly' `
  --workdir /audit --env PYTHONPATH=/audit --env PYTHONDONTWRITEBYTECODE=1 `
  --entrypoint /app/.venv/bin/python 4adc75bec6c2 -B -m unittest `
  tests.container_batch1_audit_fixes tests.test_upstream_backports -v
```

另执行了第 3.2 节五个评测内存夹具、v3/最近九场原始事件复核、指定产物回查、镜像源码哈希比对。历史 `run-20670.jsonl` SHA-256 仍为 `b9c70ff22f25e05974d3fa4cc615003681ed1fab1cb9eacc1e4f275cc80c62b3`。

本次持久变更仅新增本文件，没有修改业务源码、现有文档、运行配置或历史结果。临时测试使用项目内临时目录与自动移除的隔离容器。

未运行：完整 pytest（宿主与镜像均缺依赖）、UI 构建/浏览器验收、真实模型与靶场求解、平台提交、D04 主循环故障注入、资源超限、D05 live hint/重启恢复、网络隔离、离线恢复包验收。没有安装依赖、切模型、启动常驻服务或提交/推送 Git。

仍需为后续实施明确的输入：允许端点及离线强度、资源/产物上限、留出题与重复次数、评测总预算。它们不影响先修本次确认的确定性回归；本报告没有从旧样本推导新的绝对阈值。
