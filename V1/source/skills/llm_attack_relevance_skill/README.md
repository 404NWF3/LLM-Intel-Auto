# llm_attack_relevance_skill

一个挂在智能体一下面的轻量 skill bundle，用于对关键词召回后的原始候选内容做“大模型攻击主题”甄别。

核心链路：

1. 清洗正文
2. 句子切分
3. 关键词定位
4. 抽取命中窗口
5. 由规则或 LLM 判断整篇是否实质性讨论 LLM 攻击
6. 返回可供上游路由的结构化结果

推荐放在 `collect_from_sources` / `store_raw_records` 之后、`parse_and_standardize` 之前。

