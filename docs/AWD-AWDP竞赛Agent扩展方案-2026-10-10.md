# AWD/AWDP 竞赛 Agent 扩展方案

日期：2026-10-10（Asia/Shanghai）。

依据：2026-10-10 会话三轮调研结论——① YL_Phantom 项目评估与同类项目对比（AoiAWD / awd-watchbird / AWD-Predator-Framework / LingOps / e_awd_tools / Prepare-for-AWD）；② 云端 vs 本地大模型的框架选型（云端→YL_Phantom 防御模块做审计补丁管线，本地→Predator core 做工具层）；③ muteki-local 组合可行性分析（AWDP Break 是解题核原生形态，AWD 攻击需新增批量放大层）。相关既有文档：[三线Web简单题评测-2026-10-04.md](三线Web简单题评测-2026-10-04.md)、[解题能力提升方案.md](解题能力提升方案.md)、[批次4实施记录-2026-10-05.md](批次4实施记录-2026-10-05.md)（live hint 验收与重启恢复遗留）、[批次5后复核与下一步方案-2026-10-05.md](批次5后复核与下一步方案-2026-10-05.md)。

本文件**只做方案设计**，未修改任何源码、配置、依赖或部署，未启动容器、未调用模型、未跑题。

---

## 0. 结论摘要

1. **可以组合为一个覆盖 AWD + AWDP 的 agent**，以 muteki-local 为统一编排核。AWDP Break（漏洞发现→payload 构造→利用→交 flag）就是解题核的现有单实例形态；AWD 攻击 = Break 的产物参数化后批量放大；AWDP Fix 与 AWD 防御走独立工具管线，由核做编排。
2. **核心原则：LLM 只做 0→1（打样），1→N 走确定性脚本重放。** AWD flag 通常 5–10 分钟轮换一轮、靶机十几台，解题循环（单次数百秒、数十万 token）不可能作为常驻主力。模型介入点收敛为：打样、失败兜底、防御研判三处。
3. **直接扩展 muteki，不参考架构另起。** 三个硬理由：① 证据闸门（verdict v4，flag 必须回查真实 tool.result）是批量自动交 flag 场景防"幻觉 flag 刷提交"的刚需，已解决；② KB 沉淀（kbnote→AGENTS.md 投影→下轮自动生效）在多轮攻防中价值放大；③ 黑板/UI/HITL hint 通路（D05 已修复验收）就是现成的比赛指挥界面，且全链已在 27B 本地模型上验证。
4. 新增代码收敛在 `labs/awd/`（沿用 labs/nyu-ctf 惯例，实验区不碰核心），**零新依赖**（宿主 requests 2.32.5 已确认可用）。
5. **实施分支策略**（2026-10-11 定）：本方案的实施（批次 A–D 全部代码与 vendor 动作）在专用分支 `awd-extension`（自 local-fork 切出）进行，验收通过后合回 local-fork；local-fork 只收修复类与文档类提交。单批次单 commit 序列，沿用 `data/change-backups/` 冻结惯例。
6. **已知遗留修复已完成**（2026-10-11，批次 8，commit 4ebb9c2）：A1 credential_accounts env 来源 API_KEY 尾换行 strip（opencode JSONC 断根因闭环）；A2 usage rollup 覆盖率比较改 (execution_generation, seq) 元组、跨代旧 rollup 判 superseded 而非 STALE 误报（USAGE_STATS_VERSION 2→3）；A3 重启自动恢复 opt-in 落地（`MUTEKI_AUTO_RESUME` 默认关，经既有 resolve() 围栏重开代，`MUTEKI_AUTO_RESUME_STAGGER_S` 防惊群）。A3 接线层待 web-api 容器下次启动实机验收；be2/be4/be6 干净复跑与 pi 座位缺配仍开放（见 §8）。

---

## 1. 目标与范围

### 1.1 四个模式

| 模式 | 赛制 | 核心动作 | 主力组件 |
|---|---|---|---|
| AWDP-break | AWDP 攻击阶段 | 对自身实例解题→交 flag/payload | 解题核（现有）+ 模板导出（新） |
| AWD-attack | AWD | 打样一台→批量放大→按轮重放→提交 | 解题核 + 重放器（新）+ 提交适配器（新） |
| AWDP-fix | AWDP 防御 | 源码审计→patch 生成→验证→diff 提交 | Fix 管线（新，云端赛前） |
| AWD-defend | AWD 防御 | WAF/基线部署、日志研判、回滚封禁 | 外部工具层（AoiAWD / YL_Phantom 拆件）+ 研判编排（新） |

### 1.2 明确不做（本方案范围外）

- **Pwn 题型**：解题核当前能力面是 web（BUUCTF web 7/7 基线），pwn 不在本方案。
- **非授权目标**：所有攻击能力仅在授权比赛/自建靶场使用，不内置任何面向公网目标的便利（无隧道、无 CDN 隐藏、无反溯源）。
- **多引擎蜂群复活**：单引擎单 worker 定案不变（见本地模型CTF实测报告）。
- **LLM 常驻批量攻击**：重放器不经过模型，理由见 §0.2。

---

## 2. 总体架构

```
                      ┌─ 模式路由: AWDP-break / AWD-attack / AWDP-fix / AWD-defend
  比赛编排层(新,labs/awd/) ─┤  目标网格(IP×port) + flag 经济(提交适配器/轮换倒计时/计分板轮询)
                      │
  解题核 = muteki(现有) ─── 0→1 打样: run_challenge 解题循环 + 证据闸门 + KB
  (扩展点: 模板导出)      └─ 产出: exploit 模板 JSON(新协议) + fix 建议 + KB 沉淀
                      │
  批量放大层(新) ───────── 1→N 确定性重放(纯 requests 并发,不经模型)
                          失败靶机连续≥2轮 → 回抛清单 → 解题核重打样
                      │
  防御工具层(编排) ─────── AoiAWD(Guard/Tape) 或 YL_Phantom 拆件(waf_strong/watchdog)
                          日志 → 黑板 → 本地模型研判 → HITL 确认 → 动作
                      │
  Fix 管线(新,赛前) ────── 云端 LLM 审计(OpenAI 兼容) → finding → patch → Docker 重建验证
                          → git diff 提交包；赛中离线自动不可用(降级路径见 §4.3)
                      │
  模型路由 ─────────────── 赛中: 本地栈(FULL=Signal@18210 基线 / C390=Coder390@18216 快打)
                          赛前: 云端(仅 M3 审计,只送源码) / 赛后: 复盘
```

**数据流（AWD-attack 一轮）**：轮换开始 → 重放器对全部目标执行模板 → flag 正则提取 → 去重 → 提交适配器 → 结果 JSONL 落盘进黑板；某目标连续失败 ≥2 轮 → 进回抛清单 →（打样预算允许时）解题核对该目标重跑打样 → 新模板替换。

---

## 3. 硬约束（决定方案形态）

1. **宿主 Python 3.14.7 无 pytest/pydantic/httpx**（既有核查结论）。新增宿主侧代码只用标准库 + requests（2.32.5 已实测可用）；测试用标准库 unittest 或容器内跑，不引入新依赖——沿用批次0方案确立的规则。
2. **Mimosa hook 拦 Bash 写 .py/.env**：本方案所有文件改动一律走 Write/Edit 工具（既有实践）。
3. **显存互斥、逐线串行**：模型线切换只走 `labs/nyu-ctf/switch_line.py`，不手改配置（既有用户指令）。打样期间批量层照常跑旧模板，两者不抢模型资源（批量层无模型调用）。
4. **赛中无外网**：云端管线（M3）仅赛前运行；代码层面让云端配置缺失时显式报错而非静默回退本地（沿用 D01 契约哲学）。
5. **合规**（详见 §7）：不死马/蠕虫/SSH 后门类手段**默认关闭**，以配置开关存在，启用前提是赛事规则明确允许。
6. **muteki 遗留缺陷**（详见 §8）：重启恢复不自动、rollup STALE、be2/be4/be6 干净复跑未做——列为赛前 checklist，不阻塞本方案开发。

---

## 4. 模块详细设计

### 4.1 M1 — exploit 模板导出协议（P0）

**目标**：run 解出后，从证据链自动提取成功请求序列，参数化为可重放模板。这是打样→放大的桥，全方案最关键新增件。

**设计**：

- 输入：run 事件流 JSONL（`data/sessions/` 下，NDJSON）+ ArtifactStore（`<workdir>/arts`，批次5 后持久化）。
- 提取逻辑：verdict v4 已建立"accepted flag 必须回查到含该 flag 的真实 tool.result"的链条 → 从被接受的 tool.result 沿事件序号回溯，取该轮 worker 的工具调用序列 → 过滤出 HTTP 类调用（curl / python requests 工具调用）→ 解析出请求四元组（method/path/headers/body）与顺序 → 响应捕获（cookie/token）与后续引用识别。
- 模板 schema（`exploit-template/1`，JSON）：

```json
{
  "schema": "exploit-template/1",
  "source_run": "run-23529",
  "challenge": "be5-lovesql",
  "vars": { "TARGET_HOST": "", "TARGET_PORT": "80", "BASE_PATH": "/" },
  "flag_regex": "flag\\{[^}]+\\}",
  "steps": [
    { "name": "inject",  "method": "POST", "path": "{{BASE_PATH}}/login.php",
      "data": { "username": "admin'-- ", "password": "x" },
      "save": { "cookie": "$response.cookies" } },
    { "name": "extract", "method": "GET", "path": "{{BASE_PATH}}/admin.php",
      "use_cookie": "cookie", "extract_flag": true }
  ]
}
```

- 导出失败自动降级：无法解析为请求序列（如 exploit 是非 HTTP 步骤链）时，产出半成品模板 + 人工确认标记，走 HITL 补全（复用 control_adapter 的 HINT 通路，D05 已验收）。

**改动点**（全部新建）：

| 文件 | 内容 |
|---|---|
| `labs/awd/template_export.py` | 导出器：事件流+工件 → 模板 JSON；含 `--from-archive` 模式直接吃 replay_eval 归档 |
| `labs/awd/template_render.py` | 渲染器：模板+目标 → 请求序列（供 M2 与单靶机干跑） |
| `labs/awd/README.md` | schema 说明与人工补全指引 |

**验收标准**：
- V1：对 replay_eval 已归档的 Signal 7/7 各场（run-23529 等）执行 `--from-archive`，≥5/7 自动导出成功，其余有明确失败原因（非 HTTP 链/加密流量）。
- V2：导出模板经渲染器对原单靶机重放（靶机存活或本地重建），再次取到 flag。
- V3：单元测试（标准库 unittest）覆盖渲染器的变量替换/捕获引用/flag_regex 三条路径。

**风险**：worker 的 HTTP 调用是 curl 命令行形态，解析器要覆盖 `-X/-d/-b/-H/-L` 常用面与 `$(cat jar)` cookie jar 惯例（既有教训：cookie jar 须 curl -c/-b）。首版只支持解析成功的子集，其余走人工补全，不做万能解析。

### 4.2 M2 — 批量重放器 + flag 提交适配器（P0）

**目标**：对目标网格确定性并发重放模板，收集 flag，按平台配置提交；失败目标进回抛清单。

**设计**：

- 纯 requests + `ThreadPoolExecutor`，无模型调用。单目标执行 = 渲染模板 → 顺序执行 steps → 响应中 flag_regex 提取。
- 提交适配器配置化（各家 AWD 平台提交接口不同）：

```json
{
  "platform": "generic",
  "submit_url": "http://<scoreboard>/api/flag",
  "method": "POST", "field": "flag", "token": "<from-env>",
  "interval_s": 300, "dedup": true, "timeout_s": 10
}
```

- 去重与轮换：本地已提交集合按轮次窗口清空（轮换周期从配置读，M5 联动倒计时）。
- 结果落盘：每轮 `labs/awd/results/fire-<ts>.jsonl`（目标/步骤/状态/flag 哈希——**不落明文 flag 到模板目录**，明文只在黑板内存与提交记录）；可选写入黑板事件（供 UI 显示）。
- 回抛清单：目标连续 ≥2 轮失败 → `labs/awd/results/refire-<ts>.json`，格式与 `run_challenge.py` 的 target 字段对齐，人工决定是否消费（避免自动循环烧预算）。
- 限速：默认每目标并发 1、全局限速可配——AWD 规则常禁止高频扫描式请求，被判作弊得不偿失。

**改动点**（全部新建）：

| 文件 | 内容 |
|---|---|
| `labs/awd/replayer.py` | 重放器 CLI：`python replayer.py --template t.json --targets targets.txt --submit submit.json --rounds N` |
| `labs/awd/submit_adapters.py` | generic POST 适配器 + 预留 per-platform 扩展点（首版只做 generic） |
| `labs/awd/test_replayer.py` | unittest：本地 httpp.server 夹具模拟靶机与计分板 |

**验收标准**：
- V1：docker 本地起 3 个同源实例（用既有本地题镜像），一键 fire → 3/3 flag 收集并提交到 mock 计分板，去重生效（重复 flag 只提交一次）。
- V2：改靶机 flag 模拟轮换 → 下一轮重放取到新 flag 并提交。
- V3：注入 1 个故障目标 → 连续 2 轮失败后出现在回抛清单，其余目标不受影响。

**风险**：靶机非严格同源（per-team 差异/路径随机化）→ 模板 vars 容错 + 失败回抛兜底，重放器对单目标失败不重试超过 2 次。

### 4.3 M3 — AWDP Fix 管线（P1）

**目标**：赛前对赛题源码自动审计→生成 patch→验证→产出 AWDP 提交格式（git diff）。

**设计**（云端 LLM 审计管线，选型依据见"依据"段②）：

1. 源码解包 → 目录树 + 按文件分块（大文件按函数粗分）。
2. 云端审计：OpenAI 兼容接口，配置 `MUTEKI_CLOUD_AUDIT_BASE_URL/MODEL/API_KEY`（缺失时显式报错，不静默回退，沿用 D01 契约）。送审内容 = 源码 + 目录结构，**严禁包含 flag、队伍信息、网络拓扑**（§7）。
3. finding 结构与知识库同构：知识库拷贝 YL_Phantom 防御模块 `fix_library.json`（15 类漏洞规则）至 `labs/awd/kb/fix_library.json`（来源与许可注明），作为 few-shot 与 finding schema 模板。
4. patch 生成：LLM 按 finding 产 unified diff → 本地 Docker 重建靶机（复用既有 compose/镜像设施）→ 双向验证：原 exploit 模板重放**不再取到 flag** + 业务冒烟 check **通过**（防 LLM 幻觉补丁把业务打挂——AWD 场景 WAF 误拦 check 即掉分的同款教训）。
5. 产出：`labs/awd/fixout/<challenge>/`（finding.json / patch.diff / 验证记录），patch.diff 即 AWDP 提交格式。

**降级路径**：云端不可用（赛中/无 key）→ 本地 27B 审计（预期质量下调，只报高危类，finding 须人工确认后才进 patch 生成）。

**改动点**：`labs/awd/fix_pipeline.py`（流程编排）、`labs/awd/audit_prompts/`（审计/补丁两套 prompt）、`labs/awd/kb/fix_library.json`（拷入）、`labs/awd/verify_patch.py`（重建+双向验证）。

**验收标准**：
- V1：3 类已知漏洞样本（SQLi / 文件上传 / 反序列化，取自本地已有题源码）→ 管线闭环 → patch 验证双向通过。
- V2：送审 payload 断言测试——payload 内容不含 flag 样式串（`flag{` 检查）与配置中的 token 值。
- V3：拔掉云端配置 → 显式报错（无静默回退），降级开关行为符合本节定义。

**风险**：云端审计质量依赖模型与 prompt，首轮以"已知漏洞样本召回率"量化（目标 3/3 类别命中），不追求零误报——误报由 patch 验证环节兜底。

### 4.4 M4 — AWD 防御编排（P1）

**目标**：AWD-defend 模式下，把外部防御工具的日志接进黑板，本地模型研判，HITL 确认后执行动作。

**设计**：

- 工具层不重造：防御主力用 **AoiAWD**（防御侧成熟度最高，Guard 文件监控/Tape 流量/日志分析台）或 **YL_Phantom 拆件**（`waf_strong.php` + `watchdog.sh`，轻量；其 `.waf.log` 经既有 OpsTab fetch_traffic 通路拉取）。muteki 侧只做**摄取与编排**。
- 摄取：`labs/awd/defend.py` 拉取/监听日志文件 → 归一化为黑板事件（攻击 IP/命中规则/目标文件）。
- 研判：本地模型（走既有 worker 通路或简化单次调用）对聚合事件输出建议，**动作白名单**：`restore_baseline`（备份回滚）/ `ban_ip` / `restart_service` / `alert_only`。
- HITL：所有动作默认需人工确认（复用 D05 已验收的 HINT/DIRECTIVE 投递通路），配置 `MUTEKI_AWD_DEFEND_AUTO=0` 默认关闭全自动。
- **持久化类攻击手段（不死马/蠕虫/SSH 后门）不在防御编排内**，见 §7。

**改动点**：`labs/awd/defend.py`（摄取+研判+执行器）、动作执行器对 AoiAWD / YL_Phantom 各一个薄适配（首版只做 YL_Phantom waf_ban + 基线回滚两条）。

**验收标准**：
- V1：测试环境注入模拟攻击流量 → WAF 日志被摄取为黑板事件（字段齐全）。
- V2：研判产出结构化建议（白名单之一）→ 确认后动作在测试靶机执行成功（如 IP 封禁后该 IP 403）。
- V3：`AUTO=0` 下无确认不执行任何动作（断言测试）。

**风险**：研判是辅助而非决策——动作面刻意收窄为四条白名单，宁可漏处理不可误动作（WAF 误拦 check 掉分 > 慢一拍封禁）。

### 4.5 M5 — 计分板监控与轮换倒计时（P2）

**目标**：计分板轮询 + flag 轮换倒计时进黑板 UI，为重放节奏提供时钟。

**设计**：`labs/awd/scoreboard.py` 扩展 poll 模式（只读分数/轮次接口）→ 黑板事件 → `apps/web` 增只读卡片（最小改动，不动 UI 框架）。倒计时与 M2 的轮次窗口同源（同一配置项），避免两处时钟漂移。

**验收**：mock 计分板下轮询、分数变化、倒计时归零触发一轮 fire 提示（事件流可见）。UI 展示为加分项非门槛。

### 4.6 YL_Phantom 组件引入设计（仅方案，2026-10-11 增补，未实施）

**来源**：Wwlsyl/YL_Phantom@main（快照 commit 4d93a47，2026-10-10 抓取）。**仓库未附 LICENSE**——默认保留作者权利，vendor 树仅限内部授权赛事用途，README 须注明来源 URL + commit 哈希 + 此许可注记；对外传播前移除该树或另行取得作者许可。

**vendor 布局**（`labs/awd/vendor/ylphantom/`，保留原相对目录结构——不改一行源码即可用）：

```
labs/awd/vendor/ylphantom/
├── 攻击模块/   mix_attack.py  batch_runner.py  dfunc_bypass.py
│              phpggc_wrapper.py  rsa_crypto.py  rsa_crypto 依赖件
│              flag_hunter_config.json  known_flags.json
├── 防御模块/   auto_fix.py  patch_deploy.py  fix_library.json
└── 上传靶机/   waf_strong.php  waf_ban.php  waf_admin.php
               watchdog.php  watchdog.sh  target_monitor.php
               tinyfilemanager.php  rsa_agent.php（引入前人工审读，见下）
```

保留原结构的理由（2026-10-10 代码级核查结论）：`auto_fix.py` 以 `dirname(dirname(__file__))` 为 BASE 定位 `防御模块/fix_library.json`；`phpggc_wrapper.py` 定位 `../第三方工具/phpggc`（缺席时返回 'php not found' 优雅降级）；`mix_attack.py` 同目录 import `rsa_crypto`。整树拷贝后三个模块的内部路径依赖全部成立。

**引入映射**（组件 → 模块接入点 → 批次）：

| YL_Phantom 组件 | 接入点 | 用途 | 批次 |
|---|---|---|---|
| `mix_attack.py` + `rsa_crypto.py` + `rsa_agent.php` | M2 加密通道模式 | 混淆 UA + RSA 加密 webshell 通道批量攻击（对已落壳目标）；提交端改造对接 M2 submit_adapters | B |
| `batch_runner.py` | M2 备选执行器 | auto-awd 风格 CLI 批量 exp + 提交（模板重放不适配的自定义 exp 场景） | B |
| `dfunc_bypass.py` | 解题核工具层注册 | disable_functions 绕过检测（14 函数五分类：direct/extension/ld_preload/vuln/memory） | B |
| `auto_fix.py` + `fix_library.json` | M3 审计管线规则引擎前置 | 15 类漏洞正则初筛（SQLi/RCE/eval/上传/LFI/XSS/SSRF/SSTI/反序列化/python/java）；finding 结构与 M3 schema 同构，LLM 只接手正则漏报的部分 | B |
| `patch_deploy.py` | M3 patch 部署器参考实现 | 补丁生成模板（php-waf 等）+ webshell/SSH 部署通路 | B |
| `waf_strong.php` + `waf_ban.php` + `waf_admin.php` | M4 防御工具层主力 | HMAC-SHA256 签名防篡改 + fail-closed（配置损坏即 403）WAF 引擎、IP 黑名单 CLI | C |
| `watchdog.php` / `watchdog.sh` | M4 防御工具层 | inotify 文件监控 + 连接监控，日志进黑板 | C |
| `target_monitor.php` | M4（可选） | 靶机监控页 | C |
| `phpggc_wrapper.py` | 解题核工具层（需自备 phpggc + php） | PHP 反序列化链生成 | C（可选） |
| `tinyfilemanager.php` | **默认不部署** | 自身是强能力文件面板、暴露面大；仅当 M4 需要远端文件管理且经 HITL 确认时启用 | C |

**排除项（红线，永不引入，§7.2 的具体化）**：`immortal_shell.php`（不死马）、`.creep.php` / `.creep.dat` / `creep_rsa.php` / `creep_rsa_ae.php`（蠕虫通道与蠕虫 shell）、`.waf.dat` / `.waf.dat.php`（运行期密钥配置，属生成物非代码）、`rsa_keys.json`（若快照中出现）。`rsa_agent.php`（3729B，RSA 加密 webshell 服务端）在引入前必须人工审读全文：确认无持久化/自复制行为方可入 vendor 树，否则归入排除项。

**允许的改造点**（vendor 原则：可读可测、不维护分叉，除以下三处外不改源码）：
1. `mix_attack` 提交端对接 M2 `submit_adapters`（替换内置 submit_url 直连）；
2. `auto_fix`/`patch_deploy` 输出对接 M3 finding schema（`fix_library.json` 同构，预期天然兼容）；
3. `batch_runner` 的 targets 装载对接 M2 目标网格格式。

**验收标准**：
- V1 冒烟：攻击/防御模块全部 py 文件宿主 import 通过（唯一三方依赖 requests 已在位）；`fix_library.json`/`known_flags.json` 解析通过；php 文件 `php -l` 校验（php 缺席时降级为标记结构检查）。
- V2 功能：M2 经 `batch_runner` 跑通一次 mock 计分板提交；`dfunc_bypass` 对本地题镜像完成一次检测出报告。
- V3 红线断言：vendor 树文件名集合不含 immortal/creep 模式（可写成 CI/测试断言 `test_vendor_redline.py`）。

**风险**：① 作者自述"存在些 bug"——逐模块冒烟后按模块取舍，不指望整体可用；② `main.py`/`main_work.py` 双入口分叉——只取三个独立模块目录，主程序（tkinter GUI）不引入；③ 无 LICENSE（见开头注记）；④ 组件面向 PHP 栈，Java/Python 靶机照旧无覆盖（§1.2 已声明）。

---

## 5. 批次划分与端到端演练

| 批次 | 内容 | 前置 | 端到端验收 |
|---|---|---|---|
| **A（P0）** | M1 + M2：模板导出协议 + 重放器/提交适配器 | 归档证据可用（已具备） | **模拟 AWD 局**：本地 docker 起 3 个同源实例 → 解题核打样解出 1 台（FULL 线）→ 模板导出 → fire 3/3 → mock 计分板收齐去重 → 改 flag 轮换 1 轮重放成功 |
| **B（P1）** | M3：AWDP Fix 管线 | 批次 A 的模板（双向验证需要 exploit） | 3 类已知漏洞样本闭环（§4.3 V1–V3） |
| **C（P1）** | M4：AWD 防御编排 | 批次 A（复用黑板/通路） | 模拟攻击注入 → 研判 → 确认 → 动作（§4.4 V1–V3） |
| **D（P2）** | M5：计分板/倒计时 | 批次 A | §4.5 验收 |

每批次开工前沿用仓库惯例：`data/change-backups/` 下建批次目录，采集将改文件副本 + SHA-256 清单（批次0 惯例）。批次 A/B 各自独立可回滚，C/D 依赖 A 的基础设施但不改其代码。

---

## 6. 模型路由与资源配置

| 用途 | 模型/线 | 端口 | 说明 |
|---|---|---|---|
| 打样（解题核） | FULL 线 Signal IQ3_XXS 双卡 K4 | 18210 | 7/7 基线，质量优先 |
| 快打/简单题打样 | C390 线 Coder390-Q4LynnStyle（thinking 可选） | 18216 | 速度快（多数题 ≤111s），长枚举缺口已知，LoveSQL 类题回落 FULL 线 |
| 防御研判（M4） | 同打样线，简化单次调用 | — | 低频，不与打样同时抢线 |
| 云端审计（M3，赛前） | 外部 API | — | 只送源码；key 走环境变量，不入库 |
| 批量重放（M2） | **无模型** | — | 确定性脚本 |

切换一律 `switch_line.py`。比赛机资源：模型 9.7–11.4G 显存 + web-api/worker 容器 + docker 实例，**赛前在目标比赛机规格上实测一轮批次 A 演练**作为资源门槛。

---

## 7. 合规与安全红线

1. 仅用于授权比赛与自建靶场；不提供面向非授权目标的任何便利能力。
2. **持久化攻击手段（不死马/蠕虫/SSH 后门）默认不存在于本方案**；YL_Phantom 组件引入以 §4.6 的映射与排除项为准——防御/运维/攻击模块可 vendor，`immortal_shell` 与 `creep` 系列永不引入。如某赛事规则明确允许且用户要求，另立配置开关并单独评审——默认路径永远是没有。
3. flag 与提交记录不出比赛内网；M3 云端管线仅赛前运行，送审内容经断言测试（§4.3 V2）。
4. 重放器默认限速；自动化提交频率遵守平台规则，避免触发反作弊。
5. 每次实战使用前过一遍「赛事规则核对单」：自动化程度限制 / 允许的攻击手段 / 提交频率 / 工具白名单。

---

## 8. 与既有遗留项的关系（赛前 checklist，不阻塞开发）

| 遗留项 | 状态（2026-10-11 批次 8 后） | 剩余动作 |
|---|---|---|
| 重启恢复不自动 | **已修（opt-in）**：`MUTEKI_AUTO_RESUME` + 既有 resolve() 围栏，commit 4ebb9c2 | web-api 容器下次启动实机验收一次（冻结 run 自动重开） |
| rollup STALE 告警 | **已修**：覆盖率比较改 (gen, seq) 元组，跨代旧 rollup 记 note 不再误报 | 无（同代 STALE 保持告警，属真实缺口） |
| credential_accounts API_KEY 尾换行 | **已修**：env 来源 strip + 空值防护，opencode JSONC 断裂根因闭环 | 无 |
| be2/be4/be6 干净复跑（bridge 修复后预计严格✓） | 开放 | 批次 A 演练顺带复跑（需模型+靶机在线） |
| pi/opencode 座位缺配 | 开放（不用即无影响） | 保持禁用；启用 pi 座位前先查因 |
| worker 镜像 zcode-ctf3 与仓库同步 | 开放 | 批次 A 开工前重建核对一次 |
| Mimosa 完整审计 | 开放（scanner_enobufs，两次 commit hook 均未出完整结论） | 空闲期重跑 `security_scan` |

---

## 9. 回滚与证据冻结

- 每批次：`data/change-backups/batchX-awd-<日期>/`（文件副本 + SHA-256 manifest）。
- 本方案全部新增文件位于 `labs/awd/`，不修改 muteki 核心源码；唯一可能的例外是批次 D 的 apps/web 只读卡片，改动前单独冻结。
- 证据：验收产生的 results/事件流按既有惯例归档，不覆盖历史 results-eval-v3 口径。

---

## 10. 下一步

1. 用户确认本方案（尤其 §7 红线与 §5 批次顺序）。
2. **切实施分支**：`git checkout -b awd-extension`（自 local-fork@4ebb9c2 之后），批次 A 开工——先 M1（template_export + 7/7 归档回放导出），验收 V1–V3 后进 M2；YL_Phantom vendor（§4.6）随批次 B/C 落地，vendor 时先做 V1 冒烟与 `rsa_agent.php` 人工审读。
3. 批次 A 演练通过后，用真实 AWD 平台（自建或公开练习赛）做一次全流程实测，回填本方案"风险"小节；验收分支合回 local-fork。
