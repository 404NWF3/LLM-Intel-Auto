# WP1-1 `intel_agents` 技术要点与 3 分钟答辩讲稿

## 1. 文档用途

这份材料面向不了解项目细节的评委，目标是把 `backend/agents/intel_agents` 讲清楚。

- 第一部分：技术要点整理
- 第二部分：3 分钟展示讲稿
- 第三部分：5 页以内展示提纲

以下内容严格以当前代码实现为准，重点锚定：

- `backend/agents/intel_agents/orchestrator/graph.py`
- `backend/agents/intel_agents/orchestrator/nodes.py`
- `backend/agents/intel_agents/orchestrator/runtime.py`

必要时补充 `agents/`、`services/`、`tools/`、`subgraphs/` 下的实现细节。

## 2. 一句话概括

`intel_agents` 不是一个简单的“安全情报爬虫”，而是一个基于 `LangGraph` 的有状态多智能体情报生产线。它会先规划去哪里找情报，再并行采集多源数据，把原始文本转成结构化攻击知识，做语义去重、AI BOM 组件映射和 STIX 图谱构建，最后根据覆盖缺口决定下一轮还要补采什么，并输出可运营的告警候选。

## 3. 技术要点整理

### 3.1 系统定位

从代码和目录结构看，WP1-1 `intel_agents` 解决的是“AI 安全情报的持续生产”问题，核心目标不是抓取网页，而是形成一条可闭环、可恢复、可演进的情报管线。

它的最终产物不是一堆原始文章，而是几类更适合后续系统消费的结构化资产：

- 标准化攻击情报对象
- 去重后的稳定攻击记录
- AI BOM 组件影响映射
- STIX 2.1 兼容的攻击图谱
- 覆盖缺口分析结果和补采计划
- 告警候选与运行审计信息

### 3.2 技术要点 1：有状态编排，而不是脚本串联

`orchestrator/graph.py` 里定义了整条主流程，底层用的是 `LangGraph StateGraph`。这意味着系统不是“函数顺序调用”，而是“带状态的图编排”。

关键点有 5 个：

1. `WP11GraphState` 是全局状态中枢。  
   它不仅保存 `run_id`、`run_mode`、`run_status`，还保存采集游标、LLM 审计、标准化结果、去重结果、覆盖缺口、告警候选、错误记录和已完成节点列表。

2. 主流程是明确的阶段化流水线。  
   默认主线是：
   `load_runtime_context -> supervisor_plan -> dispatch_collection -> 并行采集 -> store_raw_records -> assess_collection_yield -> reflect_search_strategy -> parse_and_standardize -> semantic_dedup_and_merge -> resolve_ai_bom -> build_stix_graph -> score_confidence_and_novelty -> refresh_coverage_view -> coverage_gap_analysis -> weak_signal_mining -> generate_alerts -> finalize_run`

3. 采集阶段用了 `Send API fan-out` 并行展开。  
   `dispatch_collection` 后不会只走一个采集器，而是把任务分发给结构化源、代码源、论文源、社区源、公告源几个 collector 节点并行执行，提高吞吐量。

4. 路由是条件驱动的。  
   比如 `reflect_search_strategy` 会根据 `reflection_needed` 决定是回到采集阶段，还是进入标准化阶段；`coverage_gap_analysis` 会根据 `gap_fill_needed` 决定是否回到 `supervisor_plan` 发起一轮定向补采。

5. 运行时具备 checkpoint、恢复和跳过已完成节点的能力。  
   `Phase1GraphRuntime` 提供 `invoke()`、`get_state()`、`recover()`、`prepare_recovered_state()`、`invoke_live_run()`、`invoke_stub_run()` 等接口。恢复时可以选择从指定节点继续，甚至只重放部分 `query_run_id`。

这部分的价值在于：系统已经具备“长流程智能体”的基本工程形态，而不是一次性脚本。

### 3.3 技术要点 2：多源采集不是简单抓网页，而是带调度策略的异构采集

多源采集能力主要落在：

- `services/source_registry.py`
- `services/source_scheduler.py`
- `tools/source_fetch_tools.py`
- `crews/source_collection_crew.py`
- `crews/crew_collaboration.py`

从当前代码看，第一波默认接入的源包括：

- `nvd`
- `github_advisories`
- `github_discussions`
- `arxiv`
- `reddit`
- `hackernews`
- `cisa_kev`
- `mitre_attack`
- `vendor_advisories`
- `huggingface`

这里有 4 个值得向评委强调的点。

第一，它有 source registry，而不是把源写死在一堆 if-else 里。  
每个源都带有 `source_type`、`adapter_name`、`base_uri`、`default_qps`、`default_max_results`、`default_time_window_days`、分页方式、鉴权方式等元数据，所以系统天然适合继续扩展新源。

第二，它会根据 query intent 做请求计划，而不是所有源都用同一个搜索词。  
`SourceFetchToolbox` 里有 intent-aware request plan，会记录原始查询、转换后查询、请求 profile 和 query tokens。

第三，它的调度器有生产级的稳态控制。  
`SourceScheduler` 已经实现了：

- 限流节流
- 重试和指数退避
- circuit breaker 断路器
- cursor 分页和游标续跑
- `live / hybrid / stub` 运行模式

第四，它支持一个“可选的协同层”。  
`CrewCollaborationService` 在 CrewAI 可用时可以做轻量任务协调，不可用时也会自动回退到确定性的 fallback 方案，所以这个协同层不是单点依赖。

### 3.4 技术要点 3：系统有两个真正的闭环

这套智能体最有说服力的地方，不是它会采集，而是它会根据结果调整自己。

#### 闭环一：低产出或高噪声时，自我反思并改写查询

对应链路是：

`collect_*_sources -> store_raw_records -> assess_collection_yield -> reflect_search_strategy -> dispatch_collection`

`assess_collection_yield_node` 会产出一组遥测信号，例如：

- `result_count`
- `parsed_count`
- `duplicate_count`
- `novelty_yield`
- `noise_ratio`
- `source_mismatch`

随后 `SearchReflectionAgent` 会判断这轮采集是：

- 低召回
- 高噪声
- 源不匹配
- 还是已经接近饱和

如果需要重试，系统会直接改写 `collection_plan` 中对应 source plan 的：

- `query_text`
- `query_intent`
- `rewrite_reason`
- `query_provenance`

而且这些反馈不会只活在当前运行里。  
`QueryFeedbackMemoryService` 会把反馈记录下来，供后续运行继续参考。这就让系统不只是“本轮纠错”，而是在做跨轮次经验积累。

#### 闭环二：覆盖不足时，自动生成下一轮定向补采任务

对应链路是：

`refresh_coverage_view -> coverage_gap_analysis -> supervisor_plan -> dispatch_collection`

这里的核心逻辑是：

1. `CoverageReadModelService` 先从稳定攻击记录里构建覆盖视图。  
   它会看 taxonomy、source、component family、vendor/model family 等维度。

2. `GapScoringService` 再把这些覆盖视图转成“缺口候选”。  
   它会计算 gap score、source diversity gap、component coverage gap、corroboration gap、severity pressure、estimated ROI 等指标。

3. `CoverageAnalystAgent` 最后决定哪些缺口值得补。  
   它会输出：

- 是否发起 gap fill
- 推荐去哪几个源补
- 推荐用什么 query
- 推荐用什么 query intent

然后 Supervisor 会基于这些 dispatch plans 重新规划下一轮采集。  
这意味着系统已经不是“采一次就结束”，而是会围绕知识覆盖率做主动补全。

### 3.5 技术要点 4：中间不是简单清洗，而是一条完整的情报生产线

#### 1. 原始数据入库和落盘

`RawIngestFlow` 负责把采集结果转成可追踪的原始记录，包括：

- payload 落盘
- manifest / audit 记录
- 可选 DB 持久化
- 过期 payload 清理

它解决的是“原始证据可追溯”的问题。

#### 2. LLM + 规则融合的标准化

`StandardizerAgent` 不是只做文本摘要，而是把异构原始记录转成统一的 `StandardizedIntelDTO`。  
它的策略是：

- 优先走 LLM 抽取
- 再用规则校验和融合
- LLM 不可用时，根据策略决定是否降级到规则路径

输出里已经包含：

- 规范化后的攻击名称和描述
- taxonomy 标签
- 严重性线索
- `bom_mentions`
- 证据片段
- 字段级置信度

#### 3. 语义去重与稳定攻击记录沉淀

`semantic_dedup_and_merge_node` 背后是一条多阶段去重流水线：

- 内容哈希和近重复判断
- 向量召回
- 规则先验判断
- LLM merge judge
- adjudicator 融合裁决

其中 `AttackSignatureMemory` 用本地嵌入式 Qdrant 做语义记忆，不需要额外部署独立向量服务。  
`DedupMemoryService` 则负责把去重后的稳定记录和审计信息持久化下来。

这一层的意义是把“多篇文章在讲同一件攻击”压缩成“一个稳定攻击实体”。

#### 4. AI BOM 组件映射和 reviewer 复核

这部分由 `orchestrator/subgraphs/ai_bom_graph.py` 串起来，主线实际上是：

- `resolve_bom`
- `review_bom`
- `persist_bom`

也就是说，当前默认主路径里，BOM 的解析、复核和持久化已经在子图里完成。  
虽然主图里也注册了 `review_ai_bom_resolution` 节点，但默认线性路径并不会在 `resolve_ai_bom` 之后再走一次这个节点，因此答辩时应按“子图路径”讲解，而不是把它说成主线上额外独立的一步。

具体来说：

- `ComponentResolutionService` 先做候选组件召回
- `BomMapperAgent` 再结合上下文做最终解析
- `BomResolutionReviewerAgent` 对解析结果进行二次复核
- 不够确定的结果会被送进 review queue，而不是被强行自动发布

这一步的价值，是把“攻击影响了哪个模型、框架或组件”从文本描述变成结构化关系。

#### 5. STIX 2.1 图谱构建

STIX 可以向评委解释成“安全知识图谱交换格式”。

当前实现里，STIX 构建由 `orchestrator/subgraphs/stix_graph.py` 和 `services/stix_graph_service.py` 负责，大致流程是：

- 先从标准化后的攻击对象中构造抽取 payload
- 再由 LLM extractor 和 reviewer 生成图草稿
- 然后做规则级校验
- 校验通过后再 materialize 成真正的 STIX bundle
- 最后持久化到数据库

而且这里不是“LLM 一次输出就直接入库”。  
代码里明确做了：

- draft validation
- review decision
- publication status 判定
- 失败时降级到 review queue

所以这更像“可审计的图谱生产线”，而不是“把 LLM 输出直接当真”。

### 3.6 技术要点 5：它不仅产出情报，还能产出运营视角

采集和结构化完成之后，系统还做了 3 类运营分析。

#### 1. 置信度与新颖度打分

`ConfidenceScoringService` 会综合 source quality、去重结果、BOM 解析质量等信号，对情报做可信度与新颖度评估。

#### 2. 覆盖视图构建

`CoverageReadModelService` 会把稳定攻击记录转换成更适合运营分析的 read model，例如：

- taxonomy-component-source 视图
- vendor-model-source 视图
- recent attack summary

#### 3. 告警候选生成

`generate_alerts_node` 目前主要根据两类信号生成告警候选：

- 覆盖缺口 ROI 很高
- source drift 被检测到

也就是说，系统在当前阶段已经具备“情报生产 + 运营提示”的雏形。

### 3.7 技术要点 6：工程可靠性设计比较完整

评委如果问“这个东西是不是只在 Demo 环境能跑”，可以重点讲下面几项。

#### 1. LLM profile pool 和路由预设

`tools/llm_client_factory.py` 不是直接绑一个模型，而是实现了：

- profile pool
- route preset
- 结构化输出校验
- 最大并发预算
- cooldown 冷却
- 失败分类和切换

这说明系统在设计上已经考虑了模型切换、失败恢复和成本/能力分层。

#### 2. resume hint 和恢复能力

部分节点如果因为 LLM 调用失败而中断，会生成 `resume_hint`，提示从哪个节点继续、建议调什么参数、哪些 profile 已经尝试过。  
这对长流程系统非常关键，因为它避免了“一处失败，全局重来”。

#### 3. 可测试的运行模式

运行时不仅支持 live，也支持：

- `stub`
- `hybrid`
- failure injection

这让系统可以在不依赖真实上游源或真实模型的情况下做流程联调和故障演练。

#### 4. source health 和 drift detection

`SourceHealthService` 会基于成功率、降级率、平均延迟、结果量来构建 source health dashboard，并识别 drift。  
这说明系统连“数据源本身是否开始失真”都在持续监控。

### 3.8 当前真实边界，答辩时要诚实讲

为了保证表达可信，下面这些点建议在答辩时按真实状态表述。

1. `weak_signal_mining_node` 当前还是占位实现，默认返回空列表。  
   所以可以说“已经预留弱信号挖掘阶段”，但不要说“弱信号聚类已全面落地”。

2. CrewAI 协同层是可选增强，不是主流程硬依赖。  
   即使没有 CrewAI，系统仍然能按 fallback 路径稳定运行。

3. BOM reviewer 的主实现当前在 AI BOM 子图里。  
   讲解时应按当前实际执行路径来描述，而不是把独立节点和子图路径混在一起。

4. STIX、BOM、反思、coverage gap 等关键环节是已实现的，但不同策略下存在 `llm_required`、`llm_optional`、`rules_only`、`rules_only_degraded` 这些降级路径。  
   所以系统的强项不只是“智能”，也是“在模型不稳定时还能继续工作”。

## 4. 面向评委的 3 分钟讲稿

下面这版可以直接照着讲，节奏按 3 分钟控制。

---

各位评委老师好，下面我介绍的是我们项目中的 WP1-1 情报采集智能体，也就是 `intel_agents` 模块。

如果用一句话概括，它不是一个简单的漏洞爬虫，而是一套面向 AI 安全场景的多智能体情报生产系统。它的目标不是抓几篇文章回来，而是持续地从多个外部来源发现新的 AI 安全风险，把这些风险变成结构化知识，再反过来指导下一轮更有针对性的采集。

这套系统最核心的设计，是把整个流程做成了一个基于 `LangGraph` 的有状态图。也就是说，它不是脚本顺序执行，而是把规划、采集、分析、补采、告警这些阶段都放进一个统一的状态机里。系统会记录本次运行的状态、游标、错误、审计信息和中间产物，所以它可以断点恢复，也可以从指定节点继续跑。

在采集阶段，我们不是只接一个数据源，而是同时面向结构化漏洞库、代码社区、论文、社区讨论和安全公告等多类来源。更重要的是，系统不会把所有来源都当成同一种搜索任务来处理。它会先由 Supervisor 规划这轮要搜什么，再把任务并行分发给不同的 collector。底层调度器已经实现了限流、重试、退避、断路器和游标续跑，所以它具备比较完整的工程稳态控制能力。

这套智能体真正有特点的地方，是它有两个闭环。第一个闭环是“采集完之后先反思”。系统会统计每次查询的结果量、新颖度、噪声比例和源是否匹配。如果发现这次采集结果太少、太杂，或者根本找错了地方，它不会直接结束，而是自动改写查询，再发起一轮新的采集。第二个闭环是“看覆盖率再决定下一轮补什么”。系统会根据已经沉淀下来的攻击知识，去分析哪些攻击类别、哪些模型家族、哪些组件类型还覆盖不够，再自动生成一轮定向补采计划。

采集回来的原始数据，也不会直接停留在文本层面。后面还有一整条情报生产线。首先，系统会把异构的原始记录标准化成统一的攻击情报对象。然后，它会做语义去重，把多篇不同来源但描述同一攻击的内容合并成稳定攻击记录。接着，它会识别这条攻击影响了哪些 AI 组件，也就是做 AI BOM 映射，并且用 reviewer 做二次复核，不够确定的结果会进入人工 review 队列。最后，它还会把攻击关系构造成 STIX 2.1 兼容的安全知识图谱，方便后续系统继续消费。

从工程角度看，我们也专门考虑了可靠性。比如模型调用不是绑死一个接口，而是做成了 profile pool 和路由预设；失败时可以切换、冷却和降级。运行时也支持 live、hybrid 和 stub 模式，便于联调、演练和恢复。所以这套系统的价值，不只是“能用大模型做一点抽取”，而是把 AI 安全情报这件事做成了一条可运行、可恢复、可演进的自动化流水线。

如果再往前看，它还可以继续给后续的渗透测试智能体、沙盒模拟智能体和防御智能体提供输入，所以我们把它看成整个系统里非常关键的上游知识引擎。谢谢各位老师。

---

## 5. 5 页以内展示提纲

### 第 1 页：我们要解决什么问题

标题建议：`为什么需要情报采集智能体`

这一页只讲 3 件事：

- AI 安全情报分散在漏洞库、代码社区、论文和公告里，人工跟踪成本很高
- 原始材料很多，但真正能直接用于后续防御和测试的结构化知识很少
- 我们希望把“发现风险”做成一个持续、自我调整的自动化系统

一句收束：

“我们的目标不是多抓几条数据，而是持续生产可消费的 AI 安全知识。”

### 第 2 页：系统架构长什么样

标题建议：`一个有状态的多智能体情报生产线`

建议画面：

- 中间画主图流程
- 左边画多源输入
- 右边画结构化输出

这一页重点讲：

- `LangGraph` 主图负责全局编排
- `WP11GraphState` 负责全局状态
- 主流程包括规划、采集、反思、标准化、去重、BOM、STIX、覆盖分析、告警
- 采集阶段支持并行 fan-out
- 运行时支持 checkpoint 和 recover

一句收束：

“它不是单点 Agent，而是一个带状态的协作式流水线。”

### 第 3 页：最重要的两个闭环

标题建议：`它会自己调整，而不是采一次就结束`

建议画面：

- 左边一个“查询反思闭环”
- 右边一个“覆盖补全闭环”

左边闭环讲：

- 采集后看 `result_count`、`novelty_yield`、`noise_ratio`
- 结果不好就自动改写查询
- 反馈会写回 memory，影响后续运行

右边闭环讲：

- 刷新 coverage view
- 找出 taxonomy / source / component / vendor-model 维度的缺口
- 自动生成 gap fill 计划并发起下一轮补采

一句收束：

“系统不是静态执行，而是在围绕质量和覆盖率不断自我修正。”

### 第 4 页：系统最终产出什么

标题建议：`从原始文本到可运营知识`

建议按流水线讲 5 步：

1. 原始记录入库和落盘
2. 标准化成统一攻击对象
3. 语义去重，沉淀稳定攻击记录
4. 解析受影响的 AI BOM 组件
5. 构建 STIX 2.1 兼容知识图谱并生成告警候选

这一页可以强调：

- 输出不是网页链接，而是结构化攻击知识
- 能服务后续测试、防御和运营
- 证据链、审计和 review queue 都被保留

一句收束：

“我们产出的不是情报碎片，而是可直接进入安全闭环的知识资产。”

### 第 5 页：这套系统的差异化价值

标题建议：`为什么这不是普通爬虫或普通 RAG`

这一页建议讲 4 个关键词：

- `Stateful`：有状态图编排，不是一次性脚本
- `Adaptive`：会根据产出质量和覆盖缺口自我调整
- `Structured`：输出 BOM、STIX、稳定攻击记录，而不只是文本摘要
- `Reliable`：支持降级、恢复、stub/hybrid/live、多模型路由

最后一句建议直接作为结束页结论：

“我们把 AI 安全情报从人工收集，推进到了可持续运行、可自我优化、可被下游系统直接消费的智能体流水线。”

## 6. 答辩时可直接引用的代码锚点

如果评委追问“这部分具体在哪里实现”，可以直接回答下面这些路径。

### 主编排

- `backend/agents/intel_agents/orchestrator/graph.py`
- `backend/agents/intel_agents/orchestrator/state.py`
- `backend/agents/intel_agents/orchestrator/router.py`
- `backend/agents/intel_agents/orchestrator/runtime.py`
- `backend/agents/intel_agents/orchestrator/nodes.py`

### 子图

- `backend/agents/intel_agents/orchestrator/subgraphs/ai_bom_graph.py`
- `backend/agents/intel_agents/orchestrator/subgraphs/stix_graph.py`

### 智能体能力

- `backend/agents/intel_agents/agents/supervisor_agent.py`
- `backend/agents/intel_agents/agents/search_reflection_agent.py`
- `backend/agents/intel_agents/agents/standardizer_agent.py`
- `backend/agents/intel_agents/agents/dedup_merge_agent.py`
- `backend/agents/intel_agents/agents/bom_mapper_agent.py`
- `backend/agents/intel_agents/agents/bom_resolution_reviewer_agent.py`
- `backend/agents/intel_agents/agents/coverage_analyst_agent.py`

### 支撑服务

- `backend/agents/intel_agents/services/source_registry.py`
- `backend/agents/intel_agents/services/source_scheduler.py`
- `backend/agents/intel_agents/services/raw_ingest_flow.py`
- `backend/agents/intel_agents/services/query_feedback_memory.py`
- `backend/agents/intel_agents/services/coverage_read_model_service.py`
- `backend/agents/intel_agents/services/gap_scoring_service.py`
- `backend/agents/intel_agents/services/component_resolution_service.py`
- `backend/agents/intel_agents/services/stix_graph_service.py`
- `backend/agents/intel_agents/services/attack_signature_memory.py`

### LLM 调用与可靠性

- `backend/agents/intel_agents/tools/llm_client_factory.py`
- `backend/agents/intel_agents/tools/source_fetch_tools.py`

## 7. 最后建议

如果现场时间真的只有 3 分钟，建议只抓住三句话：

1. 这不是爬虫，而是有状态的多智能体情报生产线。
2. 它最重要的能力不是采集，而是“反思查询”和“根据覆盖缺口自动补采”这两个闭环。
3. 它最终产出的是可被后续系统消费的结构化安全知识，而不是一堆原始文本。
