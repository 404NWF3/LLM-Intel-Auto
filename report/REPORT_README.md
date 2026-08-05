# 情报采集智能体 Beamer 报告

本目录新增的最终交付物以 `intelligence_collection_agent_report` 为前缀。原有的
`main.tex` / `main.pdf` 和 `intel-agent/` 是 2026-07-08 前后的旧 IEEE 论文草稿，
引用了已经迁移的 `src/...` 代码路径；本次没有删除或覆盖这些历史文件。

## 最终交付物

- `intelligence_collection_agent_report.tex`：16:9 中文 LaTeX Beamer 主文件。
- `slides/*.tex`：按主题拆分的报告页，涵盖架构、原理、算法、数理解释、代码映射、运行结果、DMAIC、综述和实验计划。
- `intelligence_agent_references.bib`：经过链接/DOI 核验的参考文献。
- `literature_review.md`：范围综述、纳排标准、文献矩阵和研究空白。
- `code_evidence_matrix.md`：每个关键结论到当前源码位置的证据索引。
- `runtime_snapshot.json`：2026-07-15 统一口径的 Mongo、trace、测试与记忆状态快照。
- `build_report.ps1`：XeLaTeX + Biber 的可复现构建脚本。
- `intelligence_collection_agent_report.pdf`：最终演示文稿（101 页，16:9）。

## 构建

在仓库根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File report/build_report.ps1
```

脚本会在 `report/build_final/` 中生成中间文件，并将 PDF 复制到 `report/`。主文件必须
使用 XeLaTeX，因为中文字体由 `xeCJK` 配置。构建脚本会检查每一步外部命令的退出码，
并拒绝复制页数不足 90、存在版式溢出、空参考文献或未解析引用的产物。

## 证据口径

报告只把当前 `backend/` 代码和 2026-07-15 的运行快照写成“已实现/已观测”。
DMAIC 改进项与学术创新均以“建议/待验证”标注。运行总量来自本机 MongoDB
`intel_agent` 库；最新一次 full/bootstrap 运行与 trace 统计来自同一 `run_id`。

验证基线：

```text
86 passed in 10.09s
SMOKE PASSED
```
