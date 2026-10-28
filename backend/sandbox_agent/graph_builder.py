"""Native GraphRAG index pipeline, run inside the isolated red-team environment."""

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1] / "red_team/runtime"


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


async def build(folder: Path):
    import pandas as pd
    import yaml
    from graphrag import api
    from graphrag.callbacks.noop_workflow_callbacks import NoopWorkflowCallbacks
    from graphrag.config.load_config import load_config
    from llm_defense_graphrag.deepseek_completion import register_deepseek_completion
    from saads_attack_agent.security_graph import REQUIRED_TABLES, SecurityGraph

    root = folder / "results" / "graph"
    provenance = json.loads((root / "source_manifest.json").read_text())
    progress = {
        "phase": "preparing_graph",
        "completed": [],
        "total": 8,
        "indexed_items": provenance["indexed_items"],
    }

    class Callbacks(NoopWorkflowCallbacks):
        def workflow_start(self, name, instance):
            progress["phase"] = name
            save(folder / "graph_progress.json", progress)
            print(f"GraphRAG · {name}", flush=True)

        def workflow_end(self, name, instance):
            progress["completed"].append(name)
            save(folder / "graph_progress.json", progress)

    register_deepseek_completion()
    # Global GraphRAG uses entity/relationship communities, without a vector model.
    # Explicit workflows avoid configuring or calling an unavailable embedding API.
    workflows = [
        "load_input_documents",
        "create_base_text_units",
        "create_final_documents",
        "extract_graph",
        "finalize_graph",
        "create_communities",
        "create_final_text_units",
        "create_community_reports",
    ]
    prompts = RUNTIME / "prompts"
    config = {
        "completion_models": {
            "default_completion_model": {
                "type": "deepseek_json_object",
                "model_provider": "openai",
                "model": os.environ["DEEPSEEK_CHAT_MODEL"],
                "api_key": "${DEEPSEEK_API_KEY}",
                "api_base": "https://api.deepseek.com/v1",
                "auth_method": "api_key",
                "call_args": {
                    "temperature": 0,
                    "max_tokens": 4096,
                    "timeout": 120,
                    "extra_body": {"thinking": {"type": "disabled"}},
                },
                "retry": {
                    "type": "exponential_backoff",
                    "max_retries": 3,
                    "base_delay": 2,
                    "max_delay": 20,
                    "jitter": True,
                },
            }
        },
        "embedding_models": {},
        "concurrent_requests": 2,
        "workflows": workflows,
        "input": {
            "type": "json",
            "file_pattern": r"intel_corpus\.json$$",
            "id_column": "id",
            "title_column": "title",
            "text_column": "text",
        },
        "input_storage": {"type": "file", "base_dir": str(root / "input")},
        "output_storage": {"type": "file", "base_dir": str(root / "output")},
        "reporting": {"type": "file", "base_dir": str(root / "logs")},
        "cache": {
            "type": "json",
            "storage": {"type": "file", "base_dir": str(root / "cache")},
        },
        "vector_store": {"type": "lancedb", "db_uri": str(root / "unused-vectors")},
        "chunking": {
            "type": "tokens",
            "size": 1200,
            "overlap": 100,
            "encoding_model": "cl100k_base",
        },
        "extract_graph": {
            "prompt": str(prompts / "extract_graph.txt"),
            "entity_types": [
                "ATTACK_TECHNIQUE",
                "DEFENSE_CONTROL",
                "COMPONENT",
                "VULNERABILITY",
                "TOOL",
                "STANDARD",
                "EVALUATION",
            ],
            "max_gleanings": 0,
        },
        "summarize_descriptions": {
            "prompt": str(prompts / "summarize_descriptions.txt"),
            "max_length": 350,
        },
        "cluster_graph": {"max_cluster_size": 10},
        "community_reports": {
            "graph_prompt": str(prompts / "community_report_graph.txt"),
            "max_length": 1000,
            "max_input_length": 6000,
        },
        "global_search": {
            "map_prompt": str(prompts / "global_search_map_system_prompt.txt"),
            "reduce_prompt": str(prompts / "global_search_reduce_system_prompt.txt"),
            "knowledge_prompt": str(
                prompts / "global_search_knowledge_system_prompt.txt"
            ),
            "max_context_tokens": 6000,
            "data_max_tokens": 6000,
        },
    }
    (root / "settings.yaml").write_text(
        yaml.safe_dump(config, allow_unicode=True), encoding="utf-8"
    )
    loaded = load_config(root)
    results = await asyncio.wait_for(
        api.build_index(loaded, callbacks=[Callbacks()]), timeout=3600
    )
    if any(result.error is not None for result in results):
        raise RuntimeError("GraphRAG 构建失败，请查看任务日志；原有索引继续保留。")
    tables = {
        name: pd.read_parquet(root / "output" / f"{name}.parquet")
        for name in (*REQUIRED_TABLES, "documents")
    }
    counts = {name: len(table) for name, table in tables.items()}
    if any(value == 0 for value in counts.values()):
        raise RuntimeError("图谱存在空表，无法发布，请增加有关联的情报后重建。")
    expected = {row["document_id"] for row in provenance["sources"]}
    if set(tables["documents"]["id"].astype(str)) != expected:
        raise RuntimeError("GraphRAG 文档与情报来源清单不一致。")
    titles = set(tables["entities"]["title"].astype(str))
    links = set(tables["relationships"]["source"]).union(
        tables["relationships"]["target"]
    )
    if not links.issubset(titles):
        raise RuntimeError("图谱关系引用了缺失实体。")
    manifest = {k: v for k, v in provenance.items() if k != "sources"}
    manifest.update(
        run_id=folder.name,
        retrieval_mode="global",
        completion_provider="deepseek",
        model=os.environ["DEEPSEEK_CHAT_MODEL"],
        counts=counts,
        status="validating",
        built_at=datetime.now(timezone.utc).isoformat(),
    )
    save(root / "manifest.json", manifest)
    progress["phase"] = "validating_graph"
    save(folder / "graph_progress.json", progress)
    graph = SecurityGraph.load(root)
    evidence = await asyncio.wait_for(
        graph.query(
            "threat_modeling",
            "根据已有情报，概括主要的大模型安全攻击技术和相关防御控制，引用社区报告证据。",
        ),
        timeout=300,
    )
    save(root / "query_check.json", evidence.model_dump(mode="json"))
    manifest.update(status="ready", query_verified=True)
    save(root / "manifest.json", manifest)
    (root / "report.md").write_text(
        f"# 情报知识图谱构建报告\n\n采用 Microsoft GraphRAG 实体关系抽取、社区报告和全局检索。\n\n"
        f"- 情报库：{manifest['available_items']} 条\n- 匹配：{manifest['matching_items']} 条\n- 本次索引：{manifest['indexed_items']} 条\n"
        f"- 实体：{counts['entities']}\n- 关系：{counts['relationships']}\n- 社区报告：{counts['community_reports']}\n"
        f"- 语料指纹：`{manifest['corpus_sha256']}`\n\n## 检索验证\n\n{evidence.answer}\n\n"
        "来源对应关系见 source_manifest.json。社区报告属于模型生成的分析，应结合原始情报核对。\n",
        encoding="utf-8",
    )
    progress.update(phase="complete", counts=counts)
    save(folder / "graph_progress.json", progress)
    print(f"GraphRAG ready · {counts}", flush=True)
    return 0
