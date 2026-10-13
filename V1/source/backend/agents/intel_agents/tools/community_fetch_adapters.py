"""Community adapters using the existing fetch, retry and artifact contracts.

Design reference: PrompTrend (9596165), platform collectors. No upstream runtime
or research data is imported. Incoming content is evidence, never instructions.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from bs4 import BeautifulSoup


def scan_window(cursor_state, query_run):
    """Freeze the upper bound while draining pages; advance only at end-of-scan."""
    raw = cursor_state.get("cursor")
    state = json.loads(raw) if raw and str(raw).startswith("{") else {}
    now = datetime.now(timezone.utc)
    if not state:
        state = {"since": (now - timedelta(days=query_run.time_window_days or 7)).isoformat(),
                 "until": now.isoformat(), "page": 1}
    elif state.get("complete"):
        state = {"since": state["until"], "until": now.isoformat(), "page": 1}
    return state


def scan_cursor(state, more):
    return json.dumps({**state, "page": state["page"] + 1 if more else 1,
                       "complete": not more}, separators=(",", ":"))


def text_content(value):
    return BeautifulSoup(value or "", "html.parser").get_text(" ", strip=True)


class CommunityFetchAdapters:
    def _fetch_github_issues(self, client, source, query_run, *, cursor_state, request_plan):
        state = scan_window(cursor_state, query_run)
        query = f'{query_run.query_text} is:issue updated:{state["since"]}..{state["until"]}'
        size = min(100, query_run.max_results)
        response = client.get(source.base_uri, params={"q": query, "sort": "updated",
                              "order": "asc", "per_page": size, "page": state["page"]})
        self._check_response(response)
        data = response.json()
        if data.get("incomplete_results"):
            raise RuntimeError("GitHub search returned incomplete_results; checkpoint unchanged")
        if int(data.get("total_count", 0)) > 1000:
            raise RuntimeError("GitHub search exceeds 1000-result cap; narrow query/window")
        items = []
        for issue in data.get("items", []):
            items.append(self._item(
                source_name=source.source_name, source_uri=issue["html_url"],
                external_id=str(issue["id"]), title=issue["title"],
                summary=(issue.get("body") or "")[:1000],
                author=(issue.get("user") or {}).get("login"),
                published_at=issue.get("created_at"), raw_format="json",
                payload=json.dumps(issue, ensure_ascii=False),
                metadata={"platform": "github", "updated_at": issue.get("updated_at"),
                          "thread_uri": issue["html_url"], "repository_uri": issue["repository_url"],
                          "comments": issue.get("comments"), "query_intent": query_run.query_intent} ))
        more = state["page"] * size < int(data.get("total_count", 0))
        return items, scan_cursor(state, more)

    def _fetch_discourse(self, client, source, query_run, *, cursor_state, request_plan):
        state = scan_window(cursor_state, query_run)
        base = source.base_uri.rstrip("/")
        # Search posts, retaining topic and reply IDs; use a frozen time window.
        query = f'{query_run.query_text} after:{state["since"][:10]} before:{(datetime.fromisoformat(state["until"]) + timedelta(days=1)).date()} order:latest'
        response = client.get(base + "/search.json", params={"q": query, "page": state["page"]})
        self._check_response(response)
        data = response.json()
        posts = data.get("posts", [])
        # Preserve the whole server page; a local slice would permanently lose posts.
        topics = {topic["id"]: topic for topic in data.get("topics", [])}
        items = []
        since = datetime.fromisoformat(state["since"])
        until = datetime.fromisoformat(state["until"])
        for post in posts:
            created = post.get("created_at")
            if not created or not since <= datetime.fromisoformat(created.replace("Z", "+00:00")) <= until:
                continue
            topic = topics.get(post["topic_id"], {})
            uri = f'{base}/t/{post["topic_id"]}/{post.get("post_number", 1)}'
            items.append(self._item(
                source_name=source.source_name, source_uri=uri, external_id=str(post["id"]),
                title=topic.get("title") or "", summary=text_content(post.get("blurb")),
                author=post.get("username"), published_at=created, raw_format="json",
                payload=json.dumps({"post": post, "topic": topic}, ensure_ascii=False),
                metadata={"platform": "forum", "thread_uri": f'{base}/t/{post["topic_id"]}',
                          "post_number": post.get("post_number"), "topic_id": post["topic_id"],
                          "content_scope": "search_excerpt", "query_intent": query_run.query_intent} ))
        more = bool(data.get("grouped_search_result", {}).get("more_full_page_results"))
        return items, scan_cursor(state, more)

    def _fetch_discord(self, client, source, query_run, *, cursor_state, request_plan):
        token = os.getenv("DISCORD_BOT_TOKEN")
        channel = str(source.default_params.get("channel_id") or "")
        guild = str(source.default_params.get("guild_id") or "")
        if not token or not channel.isdecimal() or not guild.isdecimal():
            raise ValueError("Discord requires DISCORD_BOT_TOKEN and configured numeric channel_id/guild_id")
        client.headers["Authorization"] = "Bot " + token
        state = scan_window(cursor_state, query_run)
        since_id = int((datetime.fromisoformat(state["since"]).timestamp()*1000 - 1420070400000)) << 22
        after = state.get("after") or str(since_id)
        response = client.get(f'{source.base_uri.rstrip("/")}/channels/{channel}/messages',
                              params={"after": after, "limit": min(100, query_run.max_results)})
        self._check_response(response)
        data = response.json()
        data.sort(key=lambda message: int(message["id"]))
        items = []
        for message in data:
            uri = f'https://discord.com/channels/{guild}/{channel}/{message["id"]}'
            items.append(self._item(
                source_name=source.source_name, source_uri=uri, external_id=message["id"],
                title=(message.get("content") or "")[:120], summary=message.get("content") or "",
                author=(message.get("author") or {}).get("username"), published_at=message.get("timestamp"),
                raw_format="json", payload=json.dumps(message, ensure_ascii=False),
                metadata={"platform": "discord", "channel_id": channel, "guild_id": guild,
                          "reply_reference": message.get("message_reference"),
                          "thread_uri": f'https://discord.com/channels/{guild}/{channel}',
                          "query_intent": query_run.query_intent} ))
        if data:
            state["after"] = data[-1]["id"]
        # Keep the snowflake watermark even on empty rounds.
        return items, json.dumps(state, separators=(",", ":"))

    def _fetch_twitter(self, client, source, query_run, *, cursor_state, request_plan):
        state = scan_window(cursor_state, query_run)
        params = {"query": query_run.query_text, "max_results": max(10, min(100, query_run.max_results)),
                  "tweet.fields": "created_at,conversation_id,referenced_tweets,public_metrics,entities,author_id",
                  "start_time": state["since"], "end_time": state["until"]}
        if state.get("next_token"):
            params["next_token"] = state["next_token"]
        response = client.get(source.base_uri, params=params)
        self._check_response(response)
        data = response.json()
        if data.get("errors"):
            raise RuntimeError("X returned partial errors; checkpoint unchanged")
        items = [self._item(
            source_name=source.source_name, source_uri=f'https://x.com/i/status/{tweet["id"]}',
            external_id=tweet["id"], title=tweet["text"][:120], summary=tweet["text"],
            author=tweet.get("author_id"), published_at=tweet.get("created_at"),
            raw_format="json", payload=json.dumps(tweet, ensure_ascii=False),
            metadata={"platform": "twitter", "conversation_id": tweet.get("conversation_id"),
                      "referenced_tweets": tweet.get("referenced_tweets", []),
                      "public_metrics": tweet.get("public_metrics", {}),
                      "query_intent": query_run.query_intent}) for tweet in data.get("data", [])]
        token = data.get("meta", {}).get("next_token")
        state["next_token"] = token
        return items, scan_cursor(state, bool(token))
