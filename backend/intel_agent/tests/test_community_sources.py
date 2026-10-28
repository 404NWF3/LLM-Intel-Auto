"""Source migration contracts, with HTTP fixtures and the real collector/store/API."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from xml.sax.saxutils import escape

import mongomock
import pytest
from fastapi.testclient import TestClient

from intel_agent import community_sources as community, sources
from intel_agent.agent.loop import IntelAgentLoop
from intel_agent.api import CollectionService, create_app
from intel_agent.engine.controller import IntelAgentController
from intel_agent.engine.gaps import compute_corpus_gaps
from intel_agent.engine.modes import FullCollectionMode, IncrementalCollectionMode
from intel_agent.memory.playbook import PlaybookStore
from intel_agent.mongo_store import MongoIntelRunStore
from intel_agent.persistence import JsonIntelRunStore
from intel_agent.schemas import IntelRunBlackboard, QueryCandidate, RunBudget, SourceCheckpoint
from intel_agent.tools.adaptive_tools import build_adaptive_tools, candidate_validation_error
from intel_agent.tools.context import ToolContext
from intel_agent.tools.server import build_round_server
from intel_agent.tools.source_tools import _run_call
from .conftest import make_item
from .test_controller import _stop_engine

NOW = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
BODY = "Prompt injection against a large language model.\n\n```python\nprint('中文')\n```\n" * 100 + "END OF SOURCE"


@pytest.fixture(autouse=True)
def scopes(monkeypatch):
    monkeypatch.setenv("INTEL_COMMUNITY_SOURCES", ",".join(community.COMMUNITY_SOURCE_NAMES))
    monkeypatch.setenv("INTEL_GITHUB_REPOSITORIES", "example/agent")
    monkeypatch.setenv("INTEL_GITHUB_ORGANIZATIONS", "")
    monkeypatch.setenv("INTEL_REDDIT_SUBREDDITS", "netsec,LocalLLaMA")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token-not-a-secret")
    monkeypatch.setenv("INTEL_INCREMENTAL_STRATEGY", "adaptive")


@pytest.fixture
def http(monkeypatch):
    issue = {
        "id": 42, "html_url": "https://github.com/example/agent/issues/2",
        "title": "Prompt injection", "body": BODY, "created_at": "2026-06-01T00:00:00Z",
        "updated_at": NOW.isoformat(), "repository_url": "https://api.github.com/repos/example/agent",
        "user": {"login": "researcher"}, "comments": 3,
    }
    responses = {
        "github_issues": {"items": [issue], "total_count": 4, "incomplete_results": False},
        "hackernews": {"hits": [{
            "objectID": "123", "title": "Prompt injection", "story_text": f"<p>{escape(BODY)}</p>",
            "created_at": NOW.isoformat(), "url": "https://example.org/article", "author": "researcher",
        }], "nbPages": 3},
        "discourse": {"posts": [{
            "id": 9, "topic_id": 7, "post_number": 2, "blurb": "<p>prompt <b>injection</b> &amp; LLM</p>",
            "created_at": NOW.isoformat(), "username": "researcher",
        }], "topics": [{"id": 7, "title": "LLM security"}],
            "grouped_search_result": {"more_full_page_results": True}},
    }
    feed = f'''<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>t3_xyz</id>
    <title>Prompt injection</title><link href="https://www.reddit.com/r/netsec/comments/xyz/post/"/>
    <content>{escape('<p>' + escape(BODY) + '</p>')}</content><updated>{NOW.isoformat()}</updated>
    <author><name>researcher</name></author></entry></feed>'''
    calls = []

    def fetch_json(url, timeout, **kwargs):
        calls.append((url, kwargs))
        for name, base in [("github_issues", community.GITHUB_ISSUES_URL),
                           ("hackernews", community.HACKERNEWS_URL), ("discourse", community.HF_FORUM_URL)]:
            if url.startswith(base):
                return responses[name]
        raise AssertionError(f"Unexpected HTTP call: {url}")

    def fetch_text(url, timeout, **kwargs):
        assert url.startswith(community.REDDIT_URL)
        calls.append((url, kwargs))
        return feed

    monkeypatch.setattr(sources, "_fetch_json", fetch_json)
    monkeypatch.setattr(sources, "_fetch_text", fetch_text)
    return responses, calls


def ctx(**kwargs):
    return ToolContext(run_id="test", target_topics=["prompt injection"], topic_bucket="prompt injection", **kwargs)


def test_explicit_empty_source_configuration_and_scope_gates(monkeypatch):
    monkeypatch.setenv("INTEL_GITHUB_REPOSITORIES", "")
    monkeypatch.setenv("INTEL_REDDIT_SUBREDDITS", "")
    assert sources.enabled_source_names() & set(community.COMMUNITY_SOURCE_NAMES) == {"hackernews", "discourse"}
    context = ctx()
    _, allowed = build_round_server(context)
    assert not any(name.endswith("__search_github_issues") or name.endswith("__search_reddit") for name in allowed)
    assert "Denied" in _run_call(context, "github_issues", {"query_text": "x"})["content"][0]["text"]
    assert context.api_calls_used == 0
    monkeypatch.setenv("INTEL_COMMUNITY_SOURCES", "")
    assert not sources.enabled_source_names() & set(community.COMMUNITY_SOURCE_NAMES)
    monkeypatch.delenv("INTEL_COMMUNITY_SOURCES")
    monkeypatch.setattr(community, "_dotenv_values", lambda: {"INTEL_COMMUNITY_SOURCES": ""})
    assert not sources.enabled_source_names() & set(community.COMMUNITY_SOURCE_NAMES)


@pytest.mark.parametrize("source,expected_id,scope", [
    ("github_issues", "github-issue:42", "issue_body"),
    ("hackernews", "hn:123", "post_text"),
    ("discourse", "hf-post:9", "search_excerpt"),
    ("reddit", "reddit:t3_xyz", "rss_entry"),
])
def test_source_text_identity_and_payload_preserved(http, source, expected_id, scope):
    items, stat = sources.search_source(source, "prompt injection", max_results=1)
    assert stat.success and len(items) == 1
    item = items[0]
    assert item.item_id == expected_id
    assert item.metadata["content_scope"] == scope
    assert item.metadata["source_payload"]
    assert item.raw_text == item.summary
    assert item.raw_text == ("prompt injection & LLM" if source == "discourse" else BODY)
    assert "test-token" not in item.model_dump_json()
    assert len(http[1]) == 1  # no hidden detail/comment/article fetches


def test_hackernews_title_only_and_native_page_window(http):
    payload, calls = http
    payload["hackernews"]["hits"][0].pop("story_text")
    items, stat = sources.search_source(
        "hackernews", "prompt injection", hn_page=1,
        community_since=(NOW - timedelta(days=1)).isoformat(), community_until=NOW.isoformat(),
    )
    assert items[0].raw_text == "Prompt injection"
    assert items[0].metadata["content_scope"] == "title_only"
    query = parse_qs(urlsplit(calls[0][0]).query)
    assert query["page"] == ["1"]
    assert query["numericFilters"] == [f"created_at_i>={int((NOW-timedelta(days=1)).timestamp())},created_at_i<={int(NOW.timestamp())}"]
    assert stat.has_more and stat.next_page == 2


def test_hf_preserves_entire_server_page_and_labels_excerpt(http):
    payload, _ = http
    original = payload["discourse"]["posts"][0]
    payload["discourse"]["posts"] = [{**original, "id": n} for n in range(1, 5)]
    items, stat = sources.search_source("discourse", "prompt injection", max_results=1)
    assert len(items) == 4
    assert all(item.metadata["content_scope"] == "search_excerpt" for item in items)
    assert stat.next_page == 2


def test_github_filters_scope_prs_and_preserves_old_created_date(http):
    payload, calls = http
    issue = payload["github_issues"]["items"][0]
    payload["github_issues"]["items"] += [
        {**issue, "id": 43, "repository_url": "https://api.github.com/repos/unapproved/agent"},
        {**issue, "id": 44, "pull_request": {"url": "https://api.github.com/repos/example/agent/pulls/1"}},
    ]
    context = ctx(since=NOW-timedelta(days=1), until=NOW)
    _run_call(context, "github_issues", {"query_text": "prompt injection"})
    assert list(context.collected_items) == ["github-issue:42"]
    assert context.collected_items["github-issue:42"].published_at.month == 6
    query = parse_qs(urlsplit(calls[0][0]).query)["q"][0]
    assert "repo:example/agent" in query and "is:issue" in query and "updated:>=" in query
    assert calls[0][1]["headers"]["Authorization"] == "Bearer test-token-not-a-secret"
    assert "test-token" not in json.dumps(context.executed_calls)


@pytest.mark.parametrize("payload", [{"message": "rate limit"}, {"items": [], "incomplete_results": True}])
def test_invalid_or_incomplete_responses_are_failures(http, payload):
    http[0]["github_issues"] = payload
    items, stat = sources.search_source("github_issues", "prompt injection")
    assert not items and not stat.success and stat.error_type == "ValueError"


def test_budget_failure_dedup_and_native_pagination(http, monkeypatch):
    context = ctx(max_api_calls=3, max_results_per_call=1)
    original = sources._fetch_json

    def fail_github(url, *args, **kwargs):
        if url.startswith(community.GITHUB_ISSUES_URL):
            raise HTTPError(url, 403, "Forbidden", {}, None)
        return original(url, *args, **kwargs)

    monkeypatch.setattr(sources, "_fetch_json", fail_github)
    _run_call(context, "github_issues", {"query_text": "prompt injection"})
    assert not context.stats[0].success
    _run_call(context, "hackernews", {"query_text": "prompt injection"})
    _run_call(context, "hackernews", {"query_text": "prompt injection", "hn_page": 0, "hn_tags": "story"})
    assert context.api_calls_used == 2  # equivalent query is deduplicated
    next_params = context.executed_calls[-1]["next_params"]
    assert next_params["hn_page"] == 1
    _run_call(context, "hackernews", {"query_text": "prompt injection", **next_params})
    assert context.executed_calls[-1]["duplicate_count"] == 1
    _run_call(context, "discourse", {"query_text": "prompt injection"})
    assert context.api_calls_used == 3 and len(context.stats) == 3
    assert len(context.collected_items) == 1


def test_reddit_rejects_unconfigured_subreddit_without_http(http):
    items, stat = sources.search_source("reddit", "prompt injection", reddit_subreddit="unapproved")
    assert not items and not stat.success and not http[1]


def test_community_candidate_cannot_escape_incremental_window():
    context = ctx(adaptive=True, since=NOW-timedelta(days=1), until=NOW)
    candidate = QueryCandidate(candidate_id="hn", source_name="hackernews", query_text="prompt injection",
                               evidence_channel="community", query_intent="discovery", target_topics=[],
                               target_gap_ids=[], params={"community_since": "2020-01-01"})
    assert "time operators" in candidate_validation_error(candidate, context)
    candidate.params = {}
    assert candidate_validation_error(candidate, context) is None
    candidate.evidence_channel = "research"
    assert "do not match" in candidate_validation_error(candidate, context)


def test_community_posts_do_not_fill_or_reduce_research_advisory_credit():
    original = make_item("nvd:cve-2026-1234", published=NOW)
    community_item = make_item("github-issue:42", source_name="github_issues", published=NOW-timedelta(days=1))
    community_item.title = "CVE-2026-1234 prompt injection"
    before = compute_corpus_gaps([original], now=NOW)
    after = compute_corpus_gaps([community_item, original], now=NOW)
    assert after == before


class _RulesRelevance:
    def annotate(self, items):
        for item in items:
            item.metadata["relevance"] = {"label": "relevant", "score": 0.9, "topic": "prompt injection"}


@pytest.mark.parametrize("backend", ["json", "mongo"])
@pytest.mark.parametrize("adaptive", [False, True])
def test_existing_controller_persistence_api_and_export(http, tmp_path, backend, adaptive):
    store = (JsonIntelRunStore(tmp_path / "runs") if backend == "json" else
             MongoIntelRunStore(database=mongomock.MongoClient().db))

    async def runner(context, prompt, model, max_turns):
        if adaptive:
            candidates = [QueryCandidate(
                candidate_id=name, source_name=name, query_text="prompt injection",
                evidence_channel="community", query_intent="entity_expand", target_topics=["prompt injection"],
                target_gap_ids=[],
            ).model_dump(mode="json") for name in community.COMMUNITY_SOURCE_NAMES]
            score = next(tool for tool in build_adaptive_tools(context) if tool.name == "score_query_candidates")
            result = await score.handler({"candidates": candidates})
            assert len(json.loads(result["content"][0]["text"])["approved"]) == 4
        for name in community.COMMUNITY_SOURCE_NAMES:
            _run_call(context, name, {"query_text": "prompt injection", "candidate_id": name})
        context.notes.append({"summary": "four sources collected", "covered_topics": [], "remaining_gaps": []})
        return "done"

    controller = IntelAgentController(store=store, loop=IntelAgentLoop(runner=runner),
                                      relevance=_RulesRelevance(), playbook=PlaybookStore(path=None),
                                      decision_engine=_stop_engine(), max_results_per_call=1)
    mode = (IncrementalCollectionMode(focus="prompt injection", since=NOW-timedelta(days=1), until=NOW)
            if adaptive else FullCollectionMode(focus="prompt injection"))
    board = controller.run(mode=mode, budget=RunBudget(max_rounds=1, max_api_calls=4), run_id="community")
    assert not board.errors
    assert len(board.raw_items) == 4 and board.metrics.api_calls_used == 4
    if adaptive:
        assert board.collection_strategy == "adaptive" and len(board.query_outcomes) == 4
        assert all(outcome.evidence_channel == "community" for outcome in board.query_outcomes)
        assert not board.source_checkpoints
        pages = [gap for gap in board.run_gaps if gap.gap_type == "pagination"]
        assert len(pages) == 3
        assert next(gap for gap in pages if gap.source_name == "hackernews").metadata["params"]["hn_page"] == 1
    with TestClient(create_app(CollectionService(store, data_dir=tmp_path))) as client:
        overview = client.get("/api/intel/overview").json()
        assert set(overview["sources"]) == set(community.COMMUNITY_SOURCE_NAMES)
        assert len(client.get("/api/intel/items?source=github_issues").json()) == 1
        detail = client.get("/api/intel/items/github-issue:42").json()
        assert detail["raw_text"] == BODY
        exported = client.get("/api/intel/export").json()
        assert exported["item_count"] == 4
        assert next(item for item in exported["items"] if item["item_id"] == "github-issue:42")["metadata"] == detail["metadata"]
        assert "test-token" not in json.dumps(exported)


def test_rules_fallback_includes_enabled_sources_within_budget(http, tmp_path, monkeypatch):
    from intel_agent.engine.fallback import run_fallback_round
    from intel_agent.schemas import SearchQueryPlan, SourceExecutionStat
    calls = []

    def fetch(source, *args, **kwargs):
        calls.append(source)
        return [], SourceExecutionStat(source_name=source, success=True)

    monkeypatch.setattr("intel_agent.tools.source_tools.search_source", fetch)
    context = ctx(max_api_calls=7)
    run_fallback_round(context, IntelRunBlackboard(run_id="r", run_goal="test"),
                       SearchQueryPlan(query_text="prompt injection"), ["prompt injection"])
    assert len(calls) == 7 and {"hackernews", "discourse", "github_issues"} <= set(calls)


def test_incremental_community_window_is_independent_of_other_source_watermarks(http, tmp_path):
    store = JsonIntelRunStore(tmp_path / "runs")
    store.save_run(IntelRunBlackboard(run_id="old", run_goal="test", source_checkpoints=[
        SourceCheckpoint(source_name="nvd_cve_api", watermark=NOW-timedelta(days=200), complete=True),
    ]))

    async def runner(context, *args):
        assert context.source_since["hackernews"] == NOW-timedelta(days=1)
        assert context.source_since["nvd_cve_api"] < NOW-timedelta(days=100)
        context.notes.append({"summary": "window checked", "covered_topics": [], "remaining_gaps": []})
        return "done"

    controller = IntelAgentController(store=store, loop=IntelAgentLoop(runner=runner),
                                      relevance=_RulesRelevance(), playbook=PlaybookStore(path=None),
                                      decision_engine=_stop_engine())
    board = controller.run(mode=IncrementalCollectionMode(window_days=1, until=NOW),
                           budget=RunBudget(max_rounds=1), run_id="new")
    assert not board.errors and board.collection_strategy == "adaptive"
