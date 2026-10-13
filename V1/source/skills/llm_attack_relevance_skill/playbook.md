# Playbook

方法论顺序固定为：

1. 校验输入
2. 清洗正文与摘要
3. 句子切分并保留索引
4. 定位 `llm_terms`、`attack_terms`、`exclusion_terms`
5. 围绕命中句构建前后窗口
6. 控制窗口数量、长度与总字符预算
7. 用 LLM 或规则判断“整篇文章是否关于 LLM 攻击”
8. 将判断结果映射为 `keep_and_parse / drop / review`

