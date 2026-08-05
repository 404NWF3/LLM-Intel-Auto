# 情报采集智能体学术化：范围综述

## 1. 综述问题与方法

本综述回答四个问题：

1. LLM agent 如何形成“推理 - 行动 - 观测”的闭环？
2. 主动检索在有限预算下如何平衡覆盖、质量与成本？
3. LLM/agent 安全与 CTI 知识图谱有哪些可复用的标准、数据与评测？
4. 当前文献还缺少什么，使本项目有形成论文贡献的空间？

这是**范围综述（scoping review）**，不是 PRISMA 系统综述。检索时间为
2026-07-15，入口包括 arXiv/作者页、OpenReview、IEEE/DOI、NIST、OWASP、MITRE、
OASIS 与四个数据源的官方文档。检索词覆盖 `LLM agent benchmark`、`deep research
agent evaluation`、`active search multi-armed bandit`、`cyber threat intelligence
knowledge graph LLM`、`agent prompt injection benchmark`、`AI risk framework` 等。

纳入标准：原始研究、正式标准或官方数据源文档；方法/任务与主动采集、agent 工具
使用、LLM 安全、CTI/KG、评测或闭环控制直接相关；预印本必须显式标注。排除标准：
只做产品宣传、无方法与数据、二手博客、无法核对作者/链接的条目。最终保留 20 个
核心来源。时间分布明显偏向 2024-2026，这是 agentic search 的快速演进所致；同时
保留 2002 UCB、2003 autonomic computing、2012 active search 三项基础工作以缓解
“只追新论文”的偏差。

## 2. 文献矩阵

| 研究流 | 代表来源 | 核心对象 | 主要贡献 | 对本项目的启示 | 尚未解决 |
|---|---|---|---|---|---|
| 推理与工具使用 | ReAct (ICLR 2023) | 交错 reasoning/action | 用环境反馈更新计划 | trace 应成为可评测过程数据 | 不解决来源异质性与证据质量 |
| 学会搜索 | Search-R1 (COLM 2025) | 多轮搜索 + RL | outcome reward 学出 query/tool use | reward 可从 gap reduction 构造 | 主要是 QA 正确率，不是 CTI coverage |
| 通用 agent 评测 | AgentBench (ICLR 2024) | 8 个交互环境 | 多轮决策失败类型 | 需测长期规划与指令遵循 | 不含情报采集与来源审计 |
| 工具安全 | AgentDojo (NeurIPS 2024) | 97 任务、629 安全用例 | 同测 utility 与 prompt injection | 应加入恶意源内容与工具越权测试 | 不评价检索证据覆盖 |
| Web agent 安全 | ST-WebAgentBench (预印本 2024) | policy completion/risk | 完成度与策略风险并列 | 采集系统不能只看任务成功 | 不是 CTI 专项 |
| deep research 评测 | DeepResearch Bench (预印本 2025) | 100 任务、22 学科 | report quality、有效引用、引用准确率 | 建立 evidence effectiveness 指标 | 任务规模仍小，且 web 环境漂移 |
| 主动搜索 | Garnett et al. (ICML 2012) | 固定预算找尽可能多正例 | Bayesian decision utility | “找更多 relevant”比分类误差更贴近采集目标 | 精确后验在大空间昂贵 |
| bandit | Auer et al. (2002) | exploration/exploitation | UCB 有限时间分析 | 为 source/query arm 提供简单基线 | 当前代码 reward 非平稳且结构化 |
| 自主管理 | Kephart & Chess (2003) | MAPE-K 闭环 | monitor-analyze-plan-execute + knowledge | blackboard/playbook 是 Knowledge；DMAIC 可治理该环 | 不提供 CTI 指标 |
| 风险治理 | NIST AI RMF 1.0/GAI Profile | Map/Measure/Manage/Govern | 风险与 TEVV 框架 | Control 阶段需要风险登记与持续测量 | 不给本项目的具体阈值 |
| LLM 风险分类 | OWASP LLM Top 10 2025 | 应用级十大风险 | prompt injection、excessive agency 等 | 可校准 Core taxonomy | Top 10 不是覆盖完备的本体 |
| 攻击知识库 | MITRE ATLAS | AI 攻击 tactic/technique | 现实观察、案例、mitigation | 提供 technique 层标签与 provenance | 活知识库版本持续变化 |
| CTI 标准 | STIX 2.1 | CTI 对象/关系交换 | 统一表达与共享 | 可作为全局图的互操作层 | 不规定 LLM 安全主题或采集策略 |
| CTI-KG | CTINexus (EuroS&P 2025) | 150 报告/10 平台 | ICL 抽取、实体对齐、长关系补全 | 支撑 item-KG 下游 | 不解决上游主动来源选择 |
| attack graph | AttacKG+ (预印本 2024) | 时间展开攻击图 | rewriter/parser/identifier/summarizer | 应保留事件时序与 TTP | 需更多公开可复现实验 |
| 知识增强抽取 | KnowCTI (C&S 2024) | 实体与关系抽取 | 注入领域知识提升 CTI 理解 | taxonomy/KG 可反向增强 relevance | 依赖标注与领域适配 |
| 持续 OSCTI | ThreatKG (预印本 2022) | 多源报告持续入图 | 采集、抽取与更新一体化 | 证明持续图谱路线可行 | 不关注 LLM/agent 特有威胁 |
| 数据源 | NVD CVE API 2.0 | CVE/CVSS/CWE/CPE/KEV | 精确过滤、分页、时间窗 | advisory 的强结构化源 | LLM 原生风险并非都映射到 CVE |
| 数据源 | OSV API 1.0 | package/version/commit | 开源依赖漏洞查询 | 适合供应链与精确确认 | 不支持开放式语义主题搜索 |
| 数据源 | arXiv API | 论文元数据/字段查询 | boolean/field/time/paging | research 通道与新趋势 | 预印本不等于可利用漏洞证据 |

## 3. 综合结论

### 3.1 已有共识

- Agent 的价值来自观测反馈驱动的多轮策略调整，而不是把固定检索模板换成 LLM 文案。
- 完成任务与安全守规必须同时评测；工具返回内容是不可信输入。
- “找到更多正例”是主动搜索问题；在固定预算下，策略比较必须报告 coverage、precision、
  independence、freshness 与 cost，而不能只报告 item 数。
- CTI 结构化研究已能把文本映射为实体、关系和事件图，但上游“检索什么、何时停止、
  如何证明覆盖”仍缺少统一方法。

### 3.2 与本项目最相关的研究空白

1. **结构化 coverage 缺口**：deep-research benchmark 重引用准确率，CTI-KG 重抽取质量，
   但很少把 `topic × evidence channel × provenance independence × freshness` 定义成可计算目标。
2. **跨源 reward 归因缺口**：UCB 假定可比较 reward；真实源的结构、时延、分页和适用主题
   不同，简单 new-items/call 会偏向 arXiv 等高吞吐源。
3. **停止决策缺口**：多数 agent benchmark 评价最终成功，不证明停止时“已足够覆盖”或
   “预算继续投入的期望收益已低于成本”。
4. **测量系统缺口**：相关性、主题标签、事件去重和来源独立性都带误差；若先调控制策略
   而不做 MSA，会把分类器偏差优化成系统行为。
5. **采集 - 图谱闭环缺口**：现有 CTI-KG 多是单向 `documents -> graph`；尚少利用 KG 的
   结构空洞、实体冲突与不确定边反向生成采集计划。

## 4. 可形成论文贡献的组合

推荐主线是 **EvidenceGap-Agent**：以有效证据张量而非 item count 定义状态，以 source-aware
active search 选择 query portfolio，以 risk-bounded stopping 结束，并用 provenance-aware KG
把采集结果反馈到下一轮。贡献可拆成：

1. 形式化的 `topic × channel` 覆盖状态与有效证据公式；
2. 非平稳、带约束的 contextual bandit / active search 策略；
3. 含测量不确定性的停止规则与风险上界；
4. LLM-security CTI 主动采集 benchmark、标注协议和可复现 trace；
5. 采集与全局 KG 之间的闭环 query generation。

## 5. 注释书目（核心 20 项）

1. [Yao et al., ReAct](https://arxiv.org/abs/2210.03629), ICLR 2023。奠定交错推理与行动范式；
   本项目的 SDK tool loop 与其精神一致，但实际安全边界由 Python controller 保持。
2. [Jin et al., Search-R1](https://arxiv.org/abs/2503.09516), COLM 2025。用 RL 学习多轮搜索；
   支持把 gap reduction 设计成可验证 reward，而不是依赖主观 LLM critic。
3. [Liu et al., AgentBench](https://arxiv.org/abs/2308.03688), ICLR 2024。覆盖 8 个环境；说明
   长期推理、决策和指令遵循是 agent 可靠性的核心薄弱点。
4. [Debenedetti et al., AgentDojo](https://arxiv.org/abs/2406.13352), NeurIPS 2024。97 个任务、
   629 个安全测试；为本项目的 source-content prompt-injection 测试提供模板。
5. [ST-WebAgentBench](https://arxiv.org/abs/2410.06703), 2024 预印本。用 policy-aware 指标
   同时刻画任务完成与风险，提示安全采集不能只以 yield 最大化。
6. [Du et al., DeepResearch Bench](https://arxiv.org/abs/2506.11763), 2025 预印本。100 个
   博士级任务、22 学科，提出有效引用数和引用准确率；可扩展为有效情报证据。
7. [Auer, Cesa-Bianchi & Fischer, UCB](https://doi.org/10.1023/A:1013689704352), 2002。
   为 exploration bonus 提供理论基础；当前代码是 gap-aware 工程变体，不应宣称保留原 regret 保证。
8. [Garnett et al., Bayesian Optimal Active Search](https://arxiv.org/abs/1206.6406), ICML 2012。
   把固定预算内发现更多目标类作为 utility，贴近情报采集目标。
9. [Kephart & Chess, The Vision of Autonomic Computing](https://doi.org/10.1109/MC.2003.1160055),
   2003。MAPE-K 为 controller/blackboard/playbook 的闭环解释提供经典参照。
10. [NIST AI RMF 1.0](https://doi.org/10.6028/NIST.AI.100-1), 2023。提供 Govern/Map/Measure/Manage
    的风险治理框架；本报告将其与 DMAIC 的 Control 对齐。
11. [NIST GAI Profile](https://doi.org/10.6028/NIST.AI.600-1), 2024。补充生成式 AI 的风险与
    TEVV 关注点，可用于 agent 运行控制和人机责任边界。
12. [OWASP Top 10 for LLM Applications 2025](https://genai.owasp.org/resource/owasp-top-10-for-llm-applications-2025/)。
    作为风险 taxonomy 参照，但不能替代本项目更细的 33 主题体系。
13. [MITRE ATLAS](https://atlas.mitre.org/)。持续更新的 AI 对抗 tactic/technique/case-study
    知识库；适合映射 technique 与 evidence provenance，引用需记录访问日期。
14. [OASIS STIX 2.1](https://docs.oasis-open.org/cti/stix/v2.1/os/stix-v2.1-os.html), 2021。
    为未来全局 KG 的互操作、关系和来源表达提供正式标准。
15. [Cheng et al., CTINexus](https://doi.org/10.1109/EUROSP63326.2025.00057), EuroS&P 2025。
    以 150 份真实 CTI 报告评价 ICL 抽取、层次实体对齐与长距离关系补全；当前仓库使用 0.2.1。
16. [Zhang et al., AttacKG+](https://arxiv.org/abs/2405.04753), 2024 预印本。把攻击建模为
    时间展开事件并结合 TTP 标签，对 item-KG 到全局图融合有启发。
17. [KnowCTI](https://doi.org/10.1016/j.cose.2024.103824), Computers & Security 141 (2024)。
    说明领域知识增强可改善 CTI 实体/关系抽取，也支持 KG -> relevance 的反向增强设想。
18. [ThreatKG](https://arxiv.org/abs/2212.10388), 2022 预印本。展示多源 OSCTI 自动采集、
    知识抽取和持续更新的一体化系统，是长期路线的重要对照。
19. [NVD CVE API 2.0](https://nvd.nist.gov/developers/vulnerabilities)。官方说明 CVE、CPE、
    CWE、CVSS、KEV、时间窗与分页；报告中的 source capability 以它和当前代码共同核对。
20. [OSV API 1.0](https://google.github.io/osv.dev/api/) 与
    [arXiv API Manual](https://info.arxiv.org/help/api/user-manual.html)。前者是 package/commit/
    version 查询，后者提供 fielded boolean、排序和分页；两者的适用证据通道不可互换。

