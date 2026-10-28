"""Read-only access to the project's existing Microsoft GraphRAG index."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

import pandas as pd
from claude_agent_sdk import create_sdk_mcp_server, tool
from graphrag import api
from graphrag.config.load_config import load_config
from mcp.types import ToolAnnotations

from llm_defense_graphrag.glm_completion import register_glm_completion
from llm_defense_graphrag.deepseek_completion import register_deepseek_completion
from saads_attack_agent.contracts import (
    GraphEvidence,
    QueryPurpose,
)

REQUIRED_TABLES = (
    "entities",
    "communities",
    "community_reports",
    "text_units",
    "relationships",
)
QUERY_PURPOSES = (
    "intent_classification",
    "case_grounding",
    "script_grounding",
    "threat_modeling",
    "hypothesis_grounding",
    "adjudication_grounding",
    "test_grounding",
)
SearchFunction = Callable[..., Awaitable[tuple[Any, Any]]]


class GraphConfigurationError(RuntimeError):
    """The existing GraphRAG project cannot be loaded safely."""


class GraphQueryError(RuntimeError):
    """A local GraphRAG query failed or returned no usable answer."""


@dataclass(frozen=True)
class LoadedGraph:
    config: Any
    entities: Any
    communities: Any
    community_reports: Any
    text_units: Any
    relationships: Any


class SecurityGraph:
    """Load the security graph once and issue purpose-labelled local searches."""

    def __init__(
        self,
        *,
        root: Path,
        loaded: LoadedGraph,
        search: SearchFunction = api.local_search,
        retrieval_mode: str = "local",
    ) -> None:
        self.root = root.resolve()
        self._loaded = loaded
        self._search = search
        self.retrieval_mode = retrieval_mode

    @classmethod
    def load(cls, root: Path) -> SecurityGraph:
        project_root = root.resolve()
        output_dir = project_root / "output"
        for table in REQUIRED_TABLES:
            table_path = output_dir / f"{table}.parquet"
            if not table_path.is_file():
                raise GraphConfigurationError(
                    f"Required GraphRAG table is missing: {table_path.name}"
                )

        settings_path = project_root / "settings.yaml"
        if not settings_path.is_file():
            raise GraphConfigurationError("GraphRAG settings.yaml is missing")

        try:
            register_glm_completion()
            register_deepseek_completion()
            config = load_config(project_root)
            tables = {
                table: pd.read_parquet(output_dir / f"{table}.parquet")
                for table in REQUIRED_TABLES
            }
            manifest_path = project_root / "manifest.json"
            manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}
        except Exception as exc:
            raise GraphConfigurationError(
                "Failed to load the existing GraphRAG project"
            ) from exc

        return cls(
            root=project_root,
            loaded=LoadedGraph(config=config, **tables),
            retrieval_mode=manifest.get("retrieval_mode", "local"),
            search=api.global_search if manifest.get("retrieval_mode") == "global" else api.local_search,
        )

    async def query(
        self,
        purpose: QueryPurpose,
        question: str,
    ) -> GraphEvidence:
        if purpose not in QUERY_PURPOSES:
            raise GraphQueryError(f"Unsupported GraphRAG query purpose: {purpose}")
        normalized_question = question.strip()
        if not normalized_question:
            raise GraphQueryError("GraphRAG question cannot be empty")

        try:
            arguments = dict(
                config=self._loaded.config,
                entities=self._loaded.entities,
                communities=self._loaded.communities,
                community_reports=self._loaded.community_reports,
                community_level=0 if self.retrieval_mode == "global" else 2,
                response_type="Multiple Paragraphs with source citations",
                query=normalized_question,
            )
            if self.retrieval_mode == "global":
                arguments["dynamic_community_selection"] = False
            else:
                arguments.update(text_units=self._loaded.text_units, relationships=self._loaded.relationships, covariates=None)
            answer, _context = await self._search(**arguments)
        except Exception as exc:
            raise GraphQueryError("GraphRAG search failed") from exc

        normalized_answer = (
            answer.strip()
            if isinstance(answer, str)
            else json.dumps(answer, ensure_ascii=False, sort_keys=True)
        )
        if not normalized_answer:
            raise GraphQueryError("GraphRAG local search returned an empty answer")

        digest = sha256(
            f"{purpose}\0{normalized_question}".encode("utf-8")
        ).hexdigest()[:12]
        return GraphEvidence(
            evidence_id=f"{purpose}-{digest}",
            purpose=purpose,
            question=normalized_question,
            answer=normalized_answer,
        )


def create_security_graph_server(
    graph: SecurityGraph,
    audit: list[GraphEvidence],
) -> dict[str, Any]:
    """Create a read-only in-process MCP server bound to one query audit."""

    input_schema = {
        "type": "object",
        "properties": {
            "purpose": {
                "type": "string",
                "enum": list(QUERY_PURPOSES),
            },
            "question": {
                "type": "string",
                "minLength": 1,
            },
        },
        "required": ["purpose", "question"],
        "additionalProperties": False,
    }

    @tool(
        "query_security_graph",
        "Query the existing security GraphRAG index for grounded evidence.",
        input_schema,
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def query_security_graph(args: dict[str, Any]) -> dict[str, Any]:
        try:
            evidence = await graph.query(
                args["purpose"],
                args["question"],
            )
        except (KeyError, TypeError, GraphConfigurationError, GraphQueryError):
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "The security graph query could not be completed.",
                    }
                ],
                "is_error": True,
            }

        audit.append(evidence)
        return {
            "content": [{"type": "text", "text": evidence.answer}],
            "structuredContent": evidence.model_dump(mode="json"),
        }

    return create_sdk_mcp_server(
        name="security_graph",
        version="1.0.0",
        tools=[query_security_graph],
    )
