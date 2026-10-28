"""V1 community HTTP sources, adapted to the existing RawIntelItem contract.

Only fetching/parsing is migrated. Calls fetch one server page (or one RSS feed)
and use the collector's existing budgets, deduplication and persistence.
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from typing import Any

from .runtime.client import _dotenv_values, _setting
from .schemas import ApprovedSource, RawIntelItem
from .topics import detect_topics

GITHUB_ISSUES_URL = "https://api.github.com/search/issues"
HACKERNEWS_URL = "https://hn.algolia.com/api/v1/search_by_date"
HF_FORUM_URL = "https://discuss.huggingface.co"
REDDIT_URL = "https://www.reddit.com"
COMMUNITY_SOURCE_NAMES = ("hackernews", "discourse", "github_issues", "reddit")
PAGE_PARAMS = {"hackernews": "hn_page", "discourse": "discourse_page", "github_issues": "github_page"}
TIME_PARAMS = ("community_since", "community_until")
ATOM = {"a": "http://www.w3.org/2005/Atom"}


def _csv_setting(name: str, default: str = "") -> list[str]:
    # An explicitly empty setting disables sources/scopes, including in .env.
    raw = os.environ.get(name)
    if raw is None:
        raw = _dotenv_values().get(name, default)
    return list(dict.fromkeys(value.strip() for value in raw.split(",") if value.strip()))


def github_scope() -> tuple[list[str], list[str]]:
    repos = _csv_setting("INTEL_GITHUB_REPOSITORIES")
    orgs = _csv_setting("INTEL_GITHUB_ORGANIZATIONS")
    if any(not re.fullmatch(r"[\w.-]+/[\w.-]+", repo, re.ASCII) for repo in repos):
        raise ValueError("INTEL_GITHUB_REPOSITORIES must contain comma-separated owner/repo names")
    if any(not re.fullmatch(r"[\w-]+", org, re.ASCII) for org in orgs):
        raise ValueError("INTEL_GITHUB_ORGANIZATIONS must contain comma-separated organization names")
    return repos, orgs


def reddit_subreddits() -> list[str]:
    values = _csv_setting("INTEL_REDDIT_SUBREDDITS")
    if any(not re.fullmatch(r"[A-Za-z0-9_]+", value) for value in values):
        raise ValueError("INTEL_REDDIT_SUBREDDITS must contain comma-separated subreddit names")
    return values


def registered_community_sources() -> list[ApprovedSource]:
    requested = set(_csv_setting("INTEL_COMMUNITY_SOURCES", ",".join(COMMUNITY_SOURCE_NAMES)))
    repos, orgs = github_scope()
    subreddits = reddit_subreddits()
    return [
        ApprovedSource(source_name="hackernews", base_uri=HACKERNEWS_URL, source_type="community",
                       trust_level=0.5, enabled="hackernews" in requested,
                       notes="HN stories/comments via Algolia; linked articles are not fetched."),
        ApprovedSource(source_name="discourse", base_uri=HF_FORUM_URL, source_type="community",
                       trust_level=0.55, enabled="discourse" in requested,
                       notes="Hugging Face forum search excerpts, not full posts."),
        ApprovedSource(source_name="github_issues", base_uri=GITHUB_ISSUES_URL, source_type="community",
                       trust_level=0.6, enabled="github_issues" in requested and bool(repos or orgs),
                       notes="GitHub issue bodies; configure INTEL_GITHUB_REPOSITORIES or INTEL_GITHUB_ORGANIZATIONS.",
                       metadata={"repositories": repos, "organizations": orgs}),
        ApprovedSource(source_name="reddit", base_uri=REDDIT_URL, source_type="community",
                       trust_level=0.45, enabled="reddit" in requested and bool(subreddits),
                       notes="Bounded public RSS; configure INTEL_REDDIT_SUBREDDITS. No history completeness guarantee.",
                       metadata={"subreddits": subreddits}),
    ]


class _HTMLText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"p", "br", "div", "li", "pre", "blockquote"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "div", "li", "pre", "blockquote"}:
            self.parts.append("\n")


def text_content(value: str | None) -> str:
    parser = _HTMLText()
    parser.feed(value or "")
    return "".join(parser.parts).strip()


def _date(value: Any) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)


def _window(params: dict[str, Any]) -> tuple[datetime | None, datetime | None]:
    since, until = (_date(params.get(name)) for name in TIME_PARAMS)
    if since and until and since > until:
        raise ValueError("community_since must not be after community_until")
    return since, until


def _within(value: Any, since: datetime | None, until: datetime | None) -> bool:
    observed = _date(value)
    return bool(observed and (since is None or since <= observed) and (until is None or observed <= until))


def _rows(data: dict[str, Any], key: str) -> list[dict[str, Any]]:
    if not isinstance(data, dict) or not isinstance(data.get(key), list):
        raise ValueError(f"Invalid community response: missing {key} list")
    if any(not isinstance(row, dict) for row in data[key]):
        raise ValueError(f"Invalid community response: {key} entries must be objects")
    return data[key]


def _item(source: str, item_id: str, uri: str, title: str, body: str, published: Any,
          payload: Any, **metadata: Any) -> RawIntelItem:
    from .sources import estimate_relevance

    topics = detect_topics(f"{title} {body}")
    return RawIntelItem(
        item_id=item_id, source_name=source, source_uri=uri, title=title,
        summary=body, raw_text=body, published_at=_date(published),
        relevance_score=estimate_relevance(f"{title} {body}", topics),
        extraction_notes=f"Parsed from {source}; content_scope={metadata['content_scope']}.",
        metadata={"source_type": "community", "topics": topics, "source_payload": payload, **metadata},
    )


def search_community_source(source: str, query: str, max_results: int, timeout: int,
                            **params: Any) -> tuple[list[RawIntelItem], dict[str, Any]]:
    """Return one page plus pagination metadata; never fetch linked articles."""
    from .sources import _fetch_json, _fetch_text, _url_with_params

    since, until = _window(params)
    size = max(1, min(100, max_results))
    if source == "github_issues":
        repos, orgs = github_scope()
        if not repos and not orgs:
            raise ValueError("GitHub Issues requires an explicitly configured repository or organization")
        page = max(1, int(params.get("github_page") or 1))
        if page * size > 1000:
            raise ValueError("GitHub search only exposes 1000 results; narrow the query or time window")
        scopes = [f"repo:{repo}" for repo in repos] + [f"org:{org}" for org in orgs]
        qualifiers = ["is:issue", *scopes]
        if since:
            qualifiers.append(f"updated:>={since.isoformat()}")
        if until:
            qualifiers.append(f"updated:<={until.isoformat()}")
        headers = {"Accept": "application/vnd.github+json"}
        token = _setting("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data = _fetch_json(_url_with_params(GITHUB_ISSUES_URL, {
            "q": " ".join([query, *qualifiers]), "sort": "updated", "order": "desc",
            "per_page": str(size), "page": str(page),
        }), timeout, headers=headers)
        rows = _rows(data, "items")
        if data.get("incomplete_results"):
            raise ValueError("GitHub search returned incomplete_results; narrow the query")
        items = []
        for issue in rows:
            repository = str(issue.get("repository_url") or "").removeprefix("https://api.github.com/repos/")
            allowed = repository.lower() in {repo.lower() for repo in repos} or repository.split("/")[0].lower() in {org.lower() for org in orgs}
            if not allowed or issue.get("pull_request") or not issue.get("id") or not issue.get("html_url"):
                continue
            observed = issue.get("updated_at") or issue.get("created_at")
            if (since or until) and not _within(observed, since, until):
                continue
            items.append(_item(
                source, f"github-issue:{issue['id']}", issue["html_url"], issue.get("title") or "",
                issue.get("body") or "", issue.get("created_at"), issue,
                content_scope="issue_body", author=(issue.get("user") or {}).get("login"),
                updated_at=observed, repository=repository, thread_uri=issue["html_url"],
                comments=issue.get("comments"),
            ))
        total = int(data.get("total_count") or 0)
        more = bool(rows) and page * size < min(total, 1000)
        return items, {"has_more": more, "next_page": page + 1 if more else None,
                       "search_capped": total > 1000, "total_count": total}

    if source == "hackernews":
        page = max(0, int(params.get("hn_page") or 0))
        tags = params.get("hn_tags") or "story"
        if tags not in {"story", "comment"}:
            raise ValueError("hn_tags must be story or comment")
        query_params = {"query": query, "tags": tags, "hitsPerPage": str(min(size, 20)), "page": str(page)}
        filters = []
        if since:
            filters.append(f"created_at_i>={int(since.timestamp())}")
        if until:
            filters.append(f"created_at_i<={int(until.timestamp())}")
        if filters:
            query_params["numericFilters"] = ",".join(filters)
        data = _fetch_json(_url_with_params(HACKERNEWS_URL, query_params), timeout)
        items = []
        for hit in _rows(data, "hits"):
            if not hit.get("objectID"):
                continue
            if (since or until) and not _within(hit.get("created_at"), since, until):
                continue
            title = hit.get("title") or hit.get("story_title") or ""
            content = hit.get("story_text") or hit.get("comment_text")
            uri = f"https://news.ycombinator.com/item?id={hit['objectID']}"
            items.append(_item(
                source, f"hn:{hit['objectID']}", uri, title, text_content(content) if content else title,
                hit.get("created_at"), hit, content_scope="post_text" if content else "title_only",
                author=hit.get("author"), linked_url=hit.get("url") or hit.get("story_url"),
                thread_uri=f"https://news.ycombinator.com/item?id={hit.get('story_id') or hit['objectID']}",
                points=hit.get("points"), comments=hit.get("num_comments"),
            ))
        more = page + 1 < int(data.get("nbPages") or 0)
        return items, {"has_more": more, "next_page": page + 1 if more else None}

    if source == "discourse":
        page = max(1, int(params.get("discourse_page") or 1))
        qualifiers = ["order:latest"]
        if since:
            qualifiers.append(f"after:{since.date()}")
        if until:
            qualifiers.append(f"before:{(until + timedelta(days=1)).date()}")
        data = _fetch_json(_url_with_params(f"{HF_FORUM_URL}/search.json", {
            "q": " ".join([query, *qualifiers]), "page": str(page),
        }), timeout)
        topics = {topic["id"]: topic for topic in _rows(data, "topics") if topic.get("id")}
        items = []
        # Preserve the whole server page: slicing before advancing page loses posts.
        for post in _rows(data, "posts"):
            if not post.get("id") or not post.get("topic_id"):
                continue
            if (since or until) and not _within(post.get("created_at"), since, until):
                continue
            topic = topics.get(post["topic_id"], {})
            thread = f"{HF_FORUM_URL}/t/{post['topic_id']}"
            items.append(_item(
                source, f"hf-post:{post['id']}", f"{thread}/{post.get('post_number', 1)}",
                topic.get("title") or "", text_content(post.get("blurb")), post.get("created_at"),
                {"post": post, "topic": topic}, content_scope="search_excerpt",
                author=post.get("username"), thread_uri=thread, topic_id=post["topic_id"],
                post_number=post.get("post_number"),
            ))
        more = bool((data.get("grouped_search_result") or {}).get("more_full_page_results"))
        return items, {"has_more": more, "next_page": page + 1 if more else None}

    if source == "reddit":
        subreddits = reddit_subreddits()
        if not subreddits:
            raise ValueError("Reddit RSS requires INTEL_REDDIT_SUBREDDITS")
        selected = str(params.get("reddit_subreddit") or "+".join(subreddits))
        if not selected or any(sub.lower() not in {s.lower() for s in subreddits} for sub in selected.split("+")):
            raise ValueError("reddit_subreddit must be within INTEL_REDDIT_SUBREDDITS")
        days = (datetime.now(timezone.utc) - since).total_seconds() / 86400 if since else float("inf")
        time_filter = next((label for days_max, label in [(1, "day"), (7, "week"), (31, "month"), (365, "year")] if days <= days_max), "all")
        raw = _fetch_text(_url_with_params(f"{REDDIT_URL}/r/{selected}/search.rss", {
            "q": query, "restrict_sr": "on", "sort": "new", "t": time_filter, "limit": str(size),
        }), timeout)
        root = ET.fromstring(raw)
        if root.tag != f"{{{ATOM['a']}}}feed":
            raise ValueError("Reddit response is not an Atom feed")
        items = []
        for entry in root.findall("a:entry", ATOM)[:size]:
            external_id = entry.findtext("a:id", "", ATOM)
            link = next((node.get("href", "") for node in entry.findall("a:link", ATOM)
                         if node.get("rel", "alternate") == "alternate"), "")
            if not external_id or not link:
                continue
            published = entry.findtext("a:published", None, ATOM) or entry.findtext("a:updated", None, ATOM)
            if (since or until) and not _within(published, since, until):
                continue
            items.append(_item(
                source, f"reddit:{external_id}", link, entry.findtext("a:title", "", ATOM),
                text_content(entry.findtext("a:content", "", ATOM)), published,
                ET.tostring(entry, encoding="unicode"), content_scope="rss_entry",
                author=entry.findtext("a:author/a:name", "", ATOM), thread_uri=link,
                subreddit=selected, time_filter=time_filter,
            ))
        return items, {"has_more": False, "bounded_feed": True}

    raise ValueError(f"Unregistered community source: {source}")
