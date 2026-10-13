# WP1-1 运行参数与 LLM 配置索引

这份文档现在只作为索引页使用。

具体内容请看两份拆分手册：

- 运维参数手册：[wp11_operations_runtime_manual.md](/e:/@4C-2026/SUFE-SAADS-Qwen/docs/wp11_operations_runtime_manual.md)
- LLM 配置池手册：[wp11_llm_pool_manual.md](/e:/@4C-2026/SUFE-SAADS-Qwen/docs/wp11_llm_pool_manual.md)

当前 LLM 配置文件位于仓库根目录：

- [wp11_llm_profiles.json](/e:/@4C-2026/SUFE-SAADS-Qwen/wp11_llm_profiles.json)
- [wp11_llm_route_presets.json](/e:/@4C-2026/SUFE-SAADS-Qwen/wp11_llm_route_presets.json)

常用验证入口：

```powershell
python main.py --validate-suite wp11_bugfixes
python main.py --validate-suite wp11_persist_robustness
python main.py --validate-suite wp11_llm_pool
```
