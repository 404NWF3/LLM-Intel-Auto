"""Source-search tools the agent calls directly inside a round.

Each registered source is a typed ``@tool`` exposing its advanced operators, so
the agent learns to combine them (this is the roadmap's "high-level search
strategy" capability). Handlers are thin wrappers over ``sources.search_source``;
they enforce the API-call budget and cross-round query dedup, apply the active
time scope (incremental mode), and record every call for playbook harvesting.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from ..analysis import operator_signature, source_query_key, SourceQuerySpec
from ..community_sources import COMMUNITY_SOURCE_NAMES, PAGE_PARAMS, TIME_PARAMS
from ..engine.gaps import SOURCE_CHANNEL
from ..sources import build_arxiv_search_query, search_source
from .context import ToolContext
from .constants import SOURCE_TOOL_NAMES

_NVD_SCHEMA = {
    "type": "object",
    "properties": {
        "query_text": {"type": "string", "description": "Free-text mission query / keywordSearch."},
        "nvd_cwe_id": {"type": "string", "description": "CWE filter, e.g. CWE-94, CWE-502."},
        "nvd_cvss_v3_severity": {"type": "string", "description": "HIGH or CRITICAL."},
        "nvd_pub_start_date": {"type": "string", "description": "ISO-8601 ext, e.g. 2026-07-01T00:00:00.000"},
        "nvd_pub_end_date": {"type": "string", "description": "ISO-8601 ext; pair with start."},
        "nvd_has_kev": {"type": "boolean", "description": "Only CVEs in the CISA KEV catalog."},
        "nvd_keyword_exact_match": {"type": "boolean", "description": "Phrase match for multi-word keywords."},
        "nvd_cve_id": {"type": "string", "description": "Direct CVE lookup."},
        "nvd_start_index": {"type": "integer", "minimum": 0, "description": "NVD page offset."},
        "candidate_id": {"type": "string", "description": "Approved adaptive candidate ID."},
    },
    "required": ["query_text"],
}

_ARXIV_SCHEMA = {
    "type": "object",
    "properties": {
        "query_text": {"type": "string", "description": "Mission query (used if no arxiv_search_query)."},
        "arxiv_search_query": {
            "type": "string",
            "description": 'arXiv query language: all:/ti:/abs:, AND/OR, quoted phrases, cat:cs.CR. '
            'E.g. (all:"prompt injection") AND (cat:cs.CR)',
        },
        "arxiv_start": {"type": "integer", "minimum": 0, "description": "arXiv page offset."},
        "candidate_id": {"type": "string", "description": "Approved adaptive candidate ID."},
    },
    "required": ["query_text"],
}

_CISA_SCHEMA = {
    "type": "object",
    "properties": {
        "query_text": {"type": "string", "description": "Keyword to match against KEV entries."},
        "cisa_keyword": {"type": "string", "description": "Explicit keyword override."},
        "cisa_cve_ids": {"type": "array", "items": {"type": "string"}, "description": "Specific CVE IDs."},
        "candidate_id": {"type": "string", "description": "Approved adaptive candidate ID."},
    },
    "required": ["query_text"],
}

_OSV_SCHEMA = {
    "type": "object",
    "properties": {
        "query_text": {"type": "string", "description": "Mission query / identifier."},
        "osv_ecosystem": {"type": "string", "description": "e.g. PyPI, npm, Go."},
        "osv_package_name": {"type": "string", "description": "Package to query (pair with ecosystem)."},
        "osv_purl": {"type": "string", "description": "Package URL."},
        "osv_vuln_id": {"type": "string", "description": "OSV/GHSA/PYSEC/CVE id for direct lookup."},
        "candidate_id": {"type": "string", "description": "Approved adaptive candidate ID."},
    },
    "required": ["query_text"],
}

_PARAM_KEYS: dict[str, tuple[str, ...]] = {
    "nvd_cve_api": (
        "nvd_cwe_id", "nvd_cvss_v3_severity", "nvd_pub_start_date", "nvd_pub_end_date",
        "nvd_has_kev", "nvd_keyword_exact_match", "nvd_cve_id",
        "nvd_start_index",
    ),
    "arxiv_api": ("arxiv_search_query", "arxiv_start"),
    "cisa_kev_json": ("cisa_keyword", "cisa_cve_ids"),
    "osv_dev_api": ("osv_ecosystem", "osv_package_name", "osv_purl", "osv_vuln_id"),
    "github_issues": (*TIME_PARAMS, "github_page"),
    "hackernews": (*TIME_PARAMS, "hn_page", "hn_tags"),
    "discourse": (*TIME_PARAMS, "discourse_page"),
    "reddit": (*TIME_PARAMS, "reddit_subreddit"),
}


def _community_schema(source: str) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "query_text": {"type": "string", "description": "Focused LLM-security keywords."},
        "candidate_id": {"type": "string", "description": "Approved adaptive candidate ID."},
        "community_since": {"type": "string", "description": "ISO-8601 lower time bound."},
        "community_until": {"type": "string", "description": "ISO-8601 upper time bound."},
    }
    if source in PAGE_PARAMS:
        first = 0 if source == "hackernews" else 1
        properties[PAGE_PARAMS[source]] = {"type": "integer", "minimum": first,
                                          "description": f"Server page; first page is {first}."}
    if source == "hackernews":
        properties["hn_tags"] = {"type": "string", "enum": ["story", "comment"]}
    if source == "reddit":
        properties["reddit_subreddit"] = {"type": "string", "description": "Configured subreddit; omitted means all configured subreddits."}
    return {"type": "object", "properties": properties, "required": ["query_text"]}


def validate_adaptive_candidate_call(
    ctx: ToolContext, source_name: str, candidate_id: str
) -> str | None:
    """Apply the hook/handler shared adaptive-query safety checks."""
    if source_name not in ctx.enabled_sources:
        return "Source is disabled or requires configuration."
    if not ctx.adaptive:
        return None
    candidate = ctx.approved_candidates.get(candidate_id)
    if candidate is None:
        return "Adaptive source calls require an approved candidate_id."
    if candidate.source_name != source_name:
        return f"Candidate {candidate.candidate_id} is for {candidate.source_name}."
    if candidate.evidence_channel != SOURCE_CHANNEL[source_name]:
        return "Candidate evidence_channel does not match the selected source."
    if candidate_exceeds_time_scope(ctx, source_name, candidate.params):
        return "Candidate time operators exceed the authoritative incremental window."
    params = {
        key: value
        for key, value in candidate.params.items()
        if key in _PARAM_KEYS[source_name] and value not in (None, "", [], {})
    }
    _apply_time_scope(source_name, params, ctx)
    spec = SourceQuerySpec(
        source_name=source_name,
        query_text=candidate.query_text,
        target_topics=list(candidate.target_topics),
        max_results=ctx.max_results_per_call,
        strategy_name="agent",
        params=params,
    )
    if source_query_key(spec) in ctx.executed_keys:
        return "This exact approved query already ran."
    if len(ctx.executed_calls) >= ctx.max_calls_this_round:
        return "Per-round source-call budget exhausted."
    if not ctx.budget_remaining():
        return "API-call budget exhausted for this run."
    return None


def candidate_exceeds_time_scope(
    ctx: ToolContext, source_name: str, params: dict[str, Any]
) -> bool:
    since, until = ctx.source_time_scope(source_name)
    if since is None:
        return False
    if source_name in COMMUNITY_SOURCE_NAMES:
        start = _parse_time_operator(params.get("community_since"))
        end = _parse_time_operator(params.get("community_until"))
        return bool((start and start < since) or (until and end and end > until))
    if source_name == "nvd_cve_api":
        start = _parse_time_operator(params.get("nvd_pub_start_date"))
        end = _parse_time_operator(params.get("nvd_pub_end_date"))
        return bool((start and start < since) or (until and end and end > until))
    if source_name == "arxiv_api":
        query = str(params.get("arxiv_search_query") or "")
        match = re.search(
            r"submittedDate:\[(\d{12})\s+TO\s+(\d{12})\]", query, re.IGNORECASE
        )
        if not match:
            return False
        start = datetime.strptime(match.group(1), "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
        end = datetime.strptime(match.group(2), "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
        return start < since or bool(until and end > until)
    return False


def _parse_time_operator(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)


def _apply_time_scope(source_name: str, params: dict[str, Any], ctx: ToolContext) -> None:
    """Inject native date operators for sources that support them (incremental mode)."""
    if source_name in PAGE_PARAMS:
        params.setdefault(PAGE_PARAMS[source_name], 0 if source_name == "hackernews" else 1)
    if source_name == "hackernews":
        params.setdefault("hn_tags", "story")
    since, until = ctx.source_time_scope(source_name)
    if since is None:
        return
    if source_name in COMMUNITY_SOURCE_NAMES:
        # The run window is authoritative in both adaptive and rules modes.
        params["community_since"] = since.isoformat()
        params["community_until"] = (until or datetime.now(timezone.utc)).isoformat()
    elif source_name == "nvd_cve_api" and (ctx.adaptive or "nvd_pub_start_date" not in params):
        params["nvd_pub_start_date"] = since.strftime("%Y-%m-%dT%H:%M:%S.000")
        end = until if until is not None else datetime.now(timezone.utc)
        params["nvd_pub_end_date"] = end.strftime("%Y-%m-%dT%H:%M:%S.000")
    elif source_name == "arxiv_api":
        existing = params.get("arxiv_search_query") or ""
        if ctx.adaptive and "submittedDate" in existing:
            existing = re.sub(
                r"\s+AND\s+submittedDate:\[[^\]]+\]",
                "",
                str(existing),
                flags=re.IGNORECASE,
            ).strip()
        if "submittedDate" not in existing:
            frm = since.strftime("%Y%m%d%H%M")
            to = until.strftime("%Y%m%d%H%M") if until is not None else since.strftime("%Y%m%d") + "2359"
            window = f"submittedDate:[{frm} TO {to}]"
            params["arxiv_search_query"] = f"({existing}) AND {window}" if existing else window


def _run_call(ctx: ToolContext, source_name: str, args: dict[str, Any]) -> dict[str, Any]:
    if source_name not in ctx.enabled_sources or source_name not in _PARAM_KEYS:
        return _text("Denied: source is disabled or requires configuration.")
    query_text = str(args.get("query_text") or "").strip()
    candidate_id = str(args.get("candidate_id") or "").strip() or None
    params = {
        key: args[key]
        for key in _PARAM_KEYS[source_name]
        if key in args and args[key] not in (None, "", [], {})
    }
    query_intent = "gap_fill"
    target_topics = list(ctx.target_topics)
    target_gap_ids: list[str] = []
    evidence_channel = SOURCE_CHANNEL[source_name]
    if ctx.adaptive:
        denial = validate_adaptive_candidate_call(ctx, source_name, candidate_id or "")
        if denial:
            return _text(f"Denied: {denial}")
        candidate = ctx.approved_candidates[candidate_id or ""]
        query_text = candidate.query_text
        params = {
            key: value
            for key, value in candidate.params.items()
            if key in _PARAM_KEYS[source_name] and value not in (None, "", [], {})
        }
        query_intent = candidate.query_intent
        target_topics = list(candidate.target_topics)
        target_gap_ids = list(candidate.target_gap_ids)
    if source_name == "arxiv_api" and not params.get("arxiv_search_query"):
        params["arxiv_search_query"] = build_arxiv_search_query(
            query_text, target_topics or ctx.target_topics
        )
    _apply_time_scope(source_name, params, ctx)

    spec = SourceQuerySpec(
        source_name=source_name, query_text=query_text, target_topics=target_topics,
        max_results=ctx.max_results_per_call, strategy_name="agent", params=params,
    )
    key = source_query_key(spec)
    if key in ctx.executed_keys:
        return _text(f"Skipped: this exact {source_name} query already ran. Vary the operators or query text.")
    if ctx.adaptive and len(ctx.executed_calls) >= ctx.max_calls_this_round:
        return _text("Skipped: per-round source-call budget exhausted. Call submit_round_summary.")
    if not ctx.budget_remaining():
        return _text("Skipped: API-call budget exhausted for this run. Call submit_round_summary.")

    items, stat = search_source(
        source_name, query_text or " ".join(ctx.target_topics[:3]),
        target_topics=target_topics or ctx.target_topics,
        max_results=ctx.max_results_per_call,
        **params,
    )
    ctx.executed_keys.add(key)
    ctx.api_calls_used += 1
    ctx.stats.append(stat)

    new_ids: list[str] = []
    kept = 0
    duplicates = 0
    for item in items:
        if not ctx.in_time_scope(item):
            continue
        kept += 1
        if item.item_id in ctx.existing_item_ids or item.item_id in ctx.collected_items:
            duplicates += 1
            continue
        item.metadata["collection_strategy"] = "agent"
        item.metadata["source_query"] = query_text
        item.metadata["source_query_params"] = params
        ctx.collected_items[item.item_id] = item
        new_ids.append(item.item_id)

    has_more = (
        bool(getattr(stat, "has_more", False)) if source_name in COMMUNITY_SOURCE_NAMES
        else source_name in {"nvd_cve_api", "arxiv_api"} and len(items) >= ctx.max_results_per_call
    )
    next_params = {}
    if has_more and source_name in PAGE_PARAMS:
        next_params = {**params, PAGE_PARAMS[source_name]: stat.next_page}
    call_id = f"{ctx.run_id}:call:{ctx.api_calls_used}"
    ctx.executed_calls.append(
        {
            "call_id": call_id,
            "candidate_id": candidate_id,
            "source_name": source_name,
            "query_text": query_text,
            "params": params,
            "query_intent": query_intent,
            "evidence_channel": evidence_channel,
            "target_topics": target_topics,
            "target_gap_ids": target_gap_ids,
            "new_item_ids": new_ids,
            "signature": operator_signature(source_name, params),
            "raw_count": len(items),
            "in_scope_count": kept,
            "duplicate_count": duplicates,
            "has_more": has_more,
            "next_params": next_params,
            "success": stat.success,
            "error_type": stat.error_type,
            "latency_ms": stat.latency_ms,
        }
    )
    if candidate_id:
        ctx.approved_candidates.pop(candidate_id, None)
    if not stat.success:
        return _text(f"{source_name} error: {stat.error_type}. Try a different source or operators.")
    titles = "; ".join(item.title[:70] for item in list(ctx.collected_items.values())[-3:])
    return _text(
        f"{source_name}: fetched {len(items)} raw / {kept} in-scope, "
        f"{duplicates} duplicate, {len(new_ids)} new, has_more={has_more}. "
        f"next_params={_fmt(next_params)}. "
        f"operators={_fmt(params)}. Newest: {titles or '(none)'}"
    )


def build_source_tools(ctx: ToolContext) -> list[Any]:
    from claude_agent_sdk import tool

    @tool("search_nvd", "Search the NVD CVE API 2.0 for LLM/AI-related CVEs. "
          "Combine keyword_text with nvd_cwe_id / nvd_cvss_v3_severity / date window / nvd_has_kev "
          "to cut noise (e.g. CWE-502 unsafe deserialization, CWE-94 code injection).", _NVD_SCHEMA)
    async def search_nvd(args: dict[str, Any]) -> dict[str, Any]:
        return _run_call(ctx, "nvd_cve_api", args)

    @tool("search_arxiv", "Search arXiv for LLM-security papers. Prefer arxiv_search_query with the "
          "arXiv query language (field prefixes, AND/OR, quoted phrases, cat:cs.CR) for precision.",
          _ARXIV_SCHEMA)
    async def search_arxiv(args: dict[str, Any]) -> dict[str, Any]:
        return _run_call(ctx, "arxiv_api", args)

    @tool("search_cisa_kev", "Search the CISA Known Exploited Vulnerabilities catalog by keyword or "
          "specific CVE IDs. Best for confirming real-world exploited AI-stack CVEs.", _CISA_SCHEMA)
    async def search_cisa_kev(args: dict[str, Any]) -> dict[str, Any]:
        return _run_call(ctx, "cisa_kev_json", args)

    @tool("search_osv", "Search OSV.dev for open-source ecosystem advisories. Use osv_ecosystem + "
          "osv_package_name (e.g. PyPI/mlflow) or osv_vuln_id for direct lookup.", _OSV_SCHEMA)
    async def search_osv(args: dict[str, Any]) -> dict[str, Any]:
        return _run_call(ctx, "osv_dev_api", args)

    @tool("search_hackernews", "Search HN stories or comments by date via Algolia. "
          "Does not fetch external articles; title-only results are labelled. Evidence channel: community.",
          _community_schema("hackernews"))
    async def search_hackernews(args: dict[str, Any]) -> dict[str, Any]:
        return _run_call(ctx, "hackernews", args)

    @tool("search_hf_forum", "Search Hugging Face Discourse forum. Returns search excerpts, "
          "not full posts; retains the complete server page. Evidence channel: community.",
          _community_schema("discourse"))
    async def search_hf_forum(args: dict[str, Any]) -> dict[str, Any]:
        return _run_call(ctx, "discourse", args)

    @tool("search_github_issues", "Search GitHub issue bodies within configured repositories/organizations. "
          "Uses update time, excludes pull requests and does not fetch comments. Evidence channel: community.",
          _community_schema("github_issues"))
    async def search_github_issues(args: dict[str, Any]) -> dict[str, Any]:
        return _run_call(ctx, "github_issues", args)

    @tool("search_reddit", "Search configured subreddits using public RSS. A bounded feed, "
          "not a full-history scan. Evidence channel: community.", _community_schema("reddit"))
    async def search_reddit(args: dict[str, Any]) -> dict[str, Any]:
        return _run_call(ctx, "reddit", args)

    tools = [search_nvd, search_arxiv, search_cisa_kev, search_osv,
             search_hackernews, search_hf_forum, search_github_issues, search_reddit]
    return [entry for entry in tools if SOURCE_TOOL_NAMES[entry.name] in ctx.enabled_sources]


def _fmt(params: dict[str, Any]) -> str:
    return json.dumps(params, ensure_ascii=False) if params else "base"


def _text(message: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": message}]}
