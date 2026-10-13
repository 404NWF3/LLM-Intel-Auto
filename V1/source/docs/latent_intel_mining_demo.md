# 潜在情报挖掘 Demo

## 模块目标

本 Demo 新增一个独立的公开来源 OSINT 弱信号挖掘模块，用于从 GitHub Issue、HuggingFace Discussion、arXiv 摘要、技术博客和社区讨论等文本中发现大模型安全相关的潜在情报候选项。当前版本内置样例数据，也支持从 JSON 文件读取输入，输出 JSON、CSV 和控制台 Top 候选摘要。

## 为什么叫“潜在情报挖掘”

公开社区里的早期安全线索常常不是标准漏洞公告，也没有 CVE、完整复现步骤或统一字段。它们可能只是“某个 RAG 应用被检索文档影响”“agent 调用了奇怪工具”“模型卡泄露了 prompt template”这类弱信号。潜在情报挖掘的目标，是把人工刷社区、读讨论、判断风险价值的过程自动化，先形成候选项，再交给 WP1-1 的标准化和去重流程继续处理。

## 分类依据

标签体系参考了四类知识来源：

- LLM 安全攻击综述：用于覆盖 prompt injection、jailbreak、prompt leakage、data exfiltration 等攻击类型。
- Agent 安全和工具调用攻击：用于突出 indirect prompt injection、tool calling attack、agent hijacking 和多智能体传播风险。
- RAG 与知识库污染研究：用于识别 rag_poisoning、retrieval_poisoning、context_pollution 等早期风险。
- OWASP LLM Top 10：用于把研究分类转化为工程可落地的输入验证、供应链、敏感信息泄露、插件与工具调用等风险视角。

当前支持的 attack_family 标签包括：

`prompt_injection`, `indirect_prompt_injection`, `jailbreak`, `rag_poisoning`, `retrieval_poisoning`, `tool_calling_attack`, `agent_hijacking`, `context_pollution`, `prompt_leakage`, `data_exfiltration`, `model_supply_chain`, `unknown_or_other`。

## 处理流程

1. `load_samples`：加载内置样例，或从 `--input` 指定的 JSON 文件读取 `title`, `text`, `source_type`, `source_url`, `created_at`。
2. `clean_text`：合并标题和正文，去除多余空白。
3. `relevance_scoring`：用关键词规则判断是否与 AI 安全相关，输出 0 到 1 的分数。
4. `attack_family_classification`：基于标签词典做多标签打分，选择最高分攻击类型，并记录匹配关键词。
5. `target_surface_detection`：识别攻击面，例如 RAG pipeline、retriever、tool executor、autonomous agent、model repository 等。
6. `evidence_extraction`：抽取 1 到 3 个风险证据句，优先包含 attack、injection、poison、leak、tool、agent、retrieve、jailbreak 等关键词的句子。
7. `novelty_scoring`：与内置已知攻击条目做纯 Python TF-IDF cosine similarity，输出 `1 - max_similarity`。
8. `confidence_scoring`：综合 relevance、source_weight、evidence_density、attack_keyword_strength 和 novelty。
9. `deduplication`：用 TF-IDF cosine similarity 做相似去重，默认阈值 0.86，保留高置信候选。
10. `export_results`：导出 `latent_intel_candidates.json` 和 `latent_intel_candidates.csv`。

## 输出字段

每条候选项包含：

- `candidate_id`
- `title`
- `source_type`
- `source_url`
- `attack_family`
- `target_surface`
- `risk_level`
- `summary`
- `evidence_sentences`
- `matched_keywords`
- `relevance_score`
- `novelty_score`
- `confidence_score`
- `recommended_action`

其中 `recommended_action` 当前固定为 `send_to_wp11_standardization`，表示该候选项适合进入 WP1-1 后续处理。

## 如何接入 WP1-1

该 Demo 当前不直接修改 LangGraph 主流程，而是作为 WP1-1 的前置增强模块。后续可以把输出的 `latent_intel_candidates` 作为 `raw_items` 或 `standardized_items` 的候选输入，送入现有标准化、去重、BOM 映射和测试方案生成流程。

建议接入位置：

- 前置采集增强：在 `backend/agents/intel_agents/services/raw_ingest_flow.py` 中，把潜在情报候选转换为 `RawCollectedItemDTO`。
- 编排接入：在 `backend/agents/intel_agents/orchestrator/nodes.py` 或 `backend/agents/intel_agents/orchestrator/graph.py` 中增加一个可选 latent-intel mining 节点。
- 标准化衔接：把候选摘要、证据句和标签作为 `backend/agents/intel_agents/agents/standardizer_agent.py` 的输入上下文。

## 运行命令

使用内置样例：

```bash
python scripts/run_latent_intel_demo.py
```

使用 JSON 样例文件：

```bash
python scripts/run_latent_intel_demo.py --input data/latent_intel/sample_community_posts.json --output-dir outputs/latent_intel --top-k 10
```

输出路径：

- `outputs/latent_intel/latent_intel_candidates.json`
- `outputs/latent_intel/latent_intel_candidates.csv`

## 下一步工作

- 增加面向 GitHub、HuggingFace、arXiv、技术博客 RSS 的公开 API/离线缓存适配器。
- 用 WP1-1 已有标准化 DTO 包装候选项，接入 raw ingest 和 standardizer。
- 将规则词典替换为“规则召回 + LLM 复核”的两阶段流程。
- 为 novelty scoring 接入历史稳定攻击库、组件库和去重记忆。
- 在前端 WP1-1 调试面板增加潜在情报候选列表和证据句展示。
