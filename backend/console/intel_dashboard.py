"""Intelligence corpus statistics and Matplotlib views for the Gradio console."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Any

from matplotlib.figure import Figure

from intel_agent.engine.gaps import (
    SOURCE_CHANNEL,
    canonical_event_key,
    compute_corpus_gaps,
    extended_topic_trends,
    relevance_probability,
)
from intel_agent.schemas import IntelRunBlackboard, RawIntelItem
from intel_agent.store import default_store
from intel_agent.topics import (
    ALL_SECURITY_TOPICS,
    CORE_SECURITY_TOPICS,
    EXTENDED_SECURITY_TOPICS,
    detect_topics,
)

HEALTH_HEADERS = ["指标", "当前值", "说明"]
GAP_HEADERS = [
    "主题",
    "证据通道",
    "有效证据",
    "目标证据",
    "覆盖率 (%)",
    "时效",
    "优先级",
    "最新证据",
    "推荐来源",
]
SOURCE_HEADERS = [
    "来源",
    "去重情报",
    "有效情报",
    "调用数",
    "成功率 (%)",
    "有效新增/调用",
    "新颖率 (%)",
    "重复率 (%)",
    "噪声率 (%)",
    "平均延迟 (ms)",
    "平均 Reward",
]
CANDIDATE_HEADERS = [
    "候选主题",
    "状态",
    "涌现分数",
    "独立证据",
    "来源数",
    "近30天",
    "Burst Ratio",
    "平均相关性",
]


def _known_topics(item: RawIntelItem) -> set[str]:
    topics = set(item.metadata.get("topics") or [])
    relevance = item.metadata.get("relevance")
    if isinstance(relevance, dict) and relevance.get("topic"):
        topics.add(str(relevance["topic"]))
    topics.update(detect_topics(f"{item.title} {item.summary} {item.raw_text or ''}"))
    return topics & set(ALL_SECURITY_TOPICS)


def _percentage(numerator: float, denominator: float) -> float:
    return round(100.0 * numerator / denominator, 1) if denominator else 0.0


def _observed_at(item: RawIntelItem) -> datetime:
    observed = item.published_at or item.fetched_at
    return observed.replace(tzinfo=timezone.utc) if observed.tzinfo is None else observed


def build_dashboard_data(
    items: list[RawIntelItem],
    blackboards: list[IntelRunBlackboard],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build one dashboard snapshot without performing storage IO."""
    now = now or datetime.now(timezone.utc)
    gaps = compute_corpus_gaps(items, now=now)
    relevant_items = [item for item in items if relevance_probability(item) >= 0.5]
    required_cells = len(gaps)
    sufficient_cells = sum(gap.effective_evidence >= gap.target_evidence for gap in gaps)
    fresh_cells = sum(gap.freshness_gap == 0 for gap in gaps)
    empty_cells = sum(gap.effective_evidence == 0 for gap in gaps)
    high_priority_gaps = sum(
        gap.status == "open" and gap.priority_score >= 0.65 for gap in gaps
    )
    coverage_index = (
        sum(min(1.0, gap.effective_evidence / gap.target_evidence) for gap in gaps)
        / required_cells
        if required_cells
        else 0.0
    )

    event_sources: dict[str, set[str]] = defaultdict(set)
    topic_counts = {topic: 0 for topic in CORE_SECURITY_TOPICS}
    source_item_counts: dict[str, int] = defaultdict(int)
    source_relevant_counts: dict[str, int] = defaultdict(int)
    unclassified_relevant = 0
    missing_published = 0
    for item in items:
        source_item_counts[item.source_name] += 1
        if item.published_at is None:
            missing_published += 1
        if relevance_probability(item) < 0.5:
            continue
        source_relevant_counts[item.source_name] += 1
        event_sources[canonical_event_key(item)].add(item.source_name)
        topics = _known_topics(item)
        if not topics:
            unclassified_relevant += 1
        for topic in topics & set(CORE_SECURITY_TOPICS):
            topic_counts[topic] += 1

    corroborated_events = sum(len(sources) >= 2 for sources in event_sources.values())
    source_concentration = (
        max(source_relevant_counts.values(), default=0) / len(relevant_items)
        if relevant_items
        else 0.0
    )
    topics_with_no_evidence = sum(
        all(gap.effective_evidence == 0 for gap in gaps if gap.topic == topic)
        for topic in CORE_SECURITY_TOPICS
    )

    outcomes: dict[tuple[str, str], Any] = {}
    candidates: dict[str, Any] = {}
    for board in blackboards:
        for outcome in board.query_outcomes:
            outcomes.setdefault((board.run_id, outcome.call_id), outcome)
        for candidate in board.candidate_topics:
            candidates.setdefault(candidate.candidate_id, candidate)

    source_outcomes: dict[str, list[Any]] = defaultdict(list)
    for outcome in outcomes.values():
        source_outcomes[outcome.source_name].append(outcome)

    all_sources = sorted(set(source_item_counts) | set(source_outcomes))
    source_rows: list[list[Any]] = []
    for source in all_sources:
        calls = source_outcomes[source]
        call_count = len(calls)
        in_scope = sum(call.in_scope_count for call in calls)
        new_count = sum(call.new_count for call in calls)
        relevant_new = sum(call.relevant_new for call in calls)
        duplicates = sum(call.duplicate_count for call in calls)
        noise = sum(call.noise_count for call in calls)
        latencies = [call.latency_ms for call in calls if call.latency_ms is not None]
        source_rows.append(
            [
                source,
                source_item_counts[source],
                source_relevant_counts[source],
                call_count,
                _percentage(sum(call.success for call in calls), call_count),
                round(relevant_new / call_count, 2) if call_count else 0.0,
                _percentage(new_count, in_scope),
                _percentage(duplicates, in_scope),
                _percentage(noise, new_count),
                round(sum(latencies) / len(latencies), 1) if latencies else None,
                round(sum(call.reward for call in calls) / call_count, 3)
                if call_count
                else None,
            ]
        )

    gap_rows = [
        [
            gap.topic,
            gap.evidence_channel,
            round(gap.effective_evidence, 2),
            round(gap.target_evidence, 2),
            round(100.0 * (1.0 - gap.coverage_gap), 1),
            "新鲜" if gap.freshness_gap == 0 else "过期/缺失",
            round(gap.priority_score, 3),
            gap.metadata.get("last_evidence_at") or "",
            ", ".join(gap.recommended_sources),
        ]
        for gap in gaps
        if gap.status == "open"
    ]

    health_rows = [
        ["必需覆盖单元", required_cells, "Core 主题 × 必需证据通道"],
        ["证据量达标单元", sufficient_cells, "有效证据达到目标值"],
        ["完全空白单元", empty_cells, "尚无有效证据"],
        ["完全空白 Core 主题", topics_with_no_evidence, "所有必需通道均为空"],
        ["过期/缺失单元", required_cells - fresh_cells, "超出通道 freshness SLA"],
        ["未分类有效情报", unclassified_relevant, "相关但未命中正式 taxonomy"],
        ["缺少发布时间", missing_published, "只能使用抓取时间进行趋势统计"],
        ["最大来源占比", f"{source_concentration:.1%}", "越高表示来源越集中"],
    ]

    candidate_rows = []
    for candidate in sorted(
        candidates.values(), key=lambda row: (-row.emergence_score, row.proposed_name)
    ):
        metadata = candidate.metadata or {}
        candidate_rows.append(
            [
                candidate.proposed_name,
                candidate.status,
                round(candidate.emergence_score, 3),
                metadata.get("independent_evidence_count", len(candidate.supporting_item_ids)),
                len(candidate.source_names),
                metadata.get("recent_30d", 0),
                metadata.get("burst_ratio", 0),
                round(candidate.mean_relevance, 3),
            ]
        )

    return {
        "now": now,
        "items": items,
        "relevant_items": relevant_items,
        "gaps": gaps,
        "trends": extended_topic_trends(items, now=now),
        "topic_counts": topic_counts,
        "source_rows": source_rows,
        "gap_rows": gap_rows,
        "health_rows": health_rows,
        "candidate_rows": candidate_rows,
        "kpis": {
            "effective_items": len(relevant_items),
            "coverage_index": coverage_index,
            "sufficient_rate": sufficient_cells / required_cells if required_cells else 0.0,
            "fresh_rate": fresh_cells / required_cells if required_cells else 0.0,
            "corroboration_rate": (
                corroborated_events / len(event_sources) if event_sources else 0.0
            ),
            "high_priority_gaps": high_priority_gaps,
        },
    }


def _kpi_html(kpis: dict[str, Any]) -> str:
    cards = [
        ("有效情报", f"{kpis['effective_items']:,}", "去重且相关性不低于 0.5"),
        ("Core 覆盖指数", f"{kpis['coverage_index']:.1%}", "必需覆盖单元的平均有效覆盖"),
        ("证据量达标率", f"{kpis['sufficient_rate']:.1%}", "有效证据达到目标的单元比例"),
        ("新鲜覆盖率", f"{kpis['fresh_rate']:.1%}", "最新证据仍处于 freshness SLA 内"),
        ("跨源佐证率", f"{kpis['corroboration_rate']:.1%}", "由两个及以上独立来源支持的事件"),
        ("高优先级缺口", str(kpis["high_priority_gaps"]), "priority score 不低于 0.65"),
    ]
    body = "".join(
        (
            '<div style="padding:14px;border:1px solid var(--border-color-primary);'
            'border-radius:10px;background:var(--background-fill-secondary);min-width:150px">'
            f'<div style="font-size:13px;opacity:.75">{escape(label)}</div>'
            f'<div style="font-size:26px;font-weight:700;margin:4px 0">{escape(value)}</div>'
            f'<div style="font-size:11px;opacity:.65">{escape(note)}</div></div>'
        )
        for label, value, note in cards
    )
    return f'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px">{body}</div>'


def _empty_figure(title: str, message: str = "No data") -> Figure:
    figure = Figure(figsize=(8, 3), layout="constrained")
    axis = figure.subplots()
    axis.set_title(title)
    axis.text(0.5, 0.5, message, ha="center", va="center", transform=axis.transAxes)
    axis.set_axis_off()
    return figure


def _coverage_figure(data: dict[str, Any]) -> Figure:
    import numpy as np
    from matplotlib import colormaps

    gaps = {(gap.topic, gap.evidence_channel): gap for gap in data["gaps"]}
    channels = ["research", "vulnerability_advisory"]
    matrix = np.full((len(CORE_SECURITY_TOPICS), len(channels)), np.nan)
    figure = Figure(figsize=(9, 10), layout="constrained")
    axis = figure.subplots()
    for row, topic in enumerate(CORE_SECURITY_TOPICS):
        for column, channel in enumerate(channels):
            gap = gaps.get((topic, channel))
            if gap is None:
                continue
            matrix[row, column] = min(1.0, gap.effective_evidence / gap.target_evidence)

    color_map = colormaps["RdYlGn"].copy()
    color_map.set_bad("#e5e7eb")
    image = axis.imshow(matrix, vmin=0, vmax=1, cmap=color_map, aspect="auto")
    axis.set_xticks(range(len(channels)), ["Research", "Vulnerability / Advisory"])
    axis.set_yticks(range(len(CORE_SECURITY_TOPICS)), CORE_SECURITY_TOPICS)
    axis.set_title("Core topic × evidence-channel coverage")
    axis.tick_params(axis="x", labelrotation=0)
    for row, topic in enumerate(CORE_SECURITY_TOPICS):
        for column, channel in enumerate(channels):
            gap = gaps.get((topic, channel))
            if gap is None:
                label = "N/A"
                color = "#6b7280"
            else:
                label = f"{gap.effective_evidence:.1f}/{gap.target_evidence:.0f}"
                if gap.freshness_gap:
                    label += "\nstale"
                color = "white" if matrix[row, column] < 0.45 else "black"
            axis.text(column, row, label, ha="center", va="center", fontsize=8, color=color)
    figure.colorbar(image, ax=axis, label="Effective coverage")
    return figure


def _topic_figure(data: dict[str, Any]) -> Figure:
    counts = data["topic_counts"]
    if not any(counts.values()):
        return _empty_figure("Relevant intelligence by Core topic")
    ordered = sorted(counts.items(), key=lambda row: (row[1], row[0]))
    figure = Figure(figsize=(9, 8), layout="constrained")
    axis = figure.subplots()
    labels = [row[0] for row in ordered]
    values = [row[1] for row in ordered]
    axis.barh(labels, values, color="#4f46e5")
    axis.set_title("Relevant intelligence by Core topic")
    axis.set_xlabel("Distinct relevant items")
    axis.grid(axis="x", alpha=0.2)
    return figure


def _timeline_figure(data: dict[str, Any]) -> Figure:
    now = data["now"]
    cutoff = (now - timedelta(weeks=12)).date()
    weekly: dict[tuple[Any, str], int] = defaultdict(int)
    for item in data["relevant_items"]:
        observed = _observed_at(item).date()
        week = observed - timedelta(days=observed.weekday())
        if week >= cutoff:
            weekly[(week, item.source_name)] += 1
    if not weekly:
        return _empty_figure("Relevant intelligence over the last 12 weeks")

    weeks = sorted({key[0] for key in weekly})
    sources = sorted({key[1] for key in weekly})
    figure = Figure(figsize=(10, 4), layout="constrained")
    axis = figure.subplots()
    bottoms = [0] * len(weeks)
    for source in sources:
        values = [weekly[(week, source)] for week in weeks]
        axis.bar(weeks, values, bottom=bottoms, width=5, label=source)
        bottoms = [left + right for left, right in zip(bottoms, values, strict=True)]
    axis.set_title("Relevant intelligence over the last 12 weeks")
    axis.set_ylabel("Distinct relevant items")
    axis.legend(fontsize=8, ncol=2)
    axis.grid(axis="y", alpha=0.2)
    return figure


def _extended_figure(data: dict[str, Any]) -> Figure:
    trends = data["trends"]
    if not trends:
        return _empty_figure("Extended-topic burst trends")
    ordered = sorted(
        trends.items(), key=lambda row: (row[1]["burst_ratio"], row[0])
    )[-10:]
    figure = Figure(figsize=(9, 5), layout="constrained")
    axis = figure.subplots()
    labels = [row[0] for row in ordered]
    values = [row[1]["burst_ratio"] for row in ordered]
    bars = axis.barh(labels, values, color="#f59e0b")
    axis.bar_label(
        bars,
        labels=[f"{row[1]['recent_30d']:.0f} recent" for row in ordered],
        padding=3,
        fontsize=8,
    )
    axis.axvline(1.0, color="#6b7280", linestyle="--", linewidth=1)
    axis.set_title("Extended-topic burst trends")
    axis.set_xlabel("Burst ratio (recent 30d / prior monthly baseline)")
    axis.grid(axis="x", alpha=0.2)
    return figure


def _empty_dashboard(message: str) -> tuple[Any, ...]:
    empty_kpis = {
        "effective_items": 0,
        "coverage_index": 0.0,
        "sufficient_rate": 0.0,
        "fresh_rate": 0.0,
        "corroboration_rate": 0.0,
        "high_priority_gaps": 0,
    }
    return (
        message,
        _kpi_html(empty_kpis),
        _empty_figure("Core topic × evidence-channel coverage", message),
        [],
        [],
        _empty_figure("Relevant intelligence by Core topic", message),
        [],
        _empty_figure("Relevant intelligence over the last 12 weeks", message),
        _empty_figure("Extended-topic burst trends", message),
        [],
    )


def refresh_intel_dashboard() -> tuple[Any, ...]:
    """Load the corpus and return every Gradio dashboard output in one refresh."""
    store = default_store()
    backend = getattr(store, "store_backend", lambda: type(store).__name__)()
    try:
        items = list(store.load_corpus_items())
        blackboards = list(store.load_all_blackboards(limit=1_000))
    except Exception as exc:  # noqa: BLE001 - UI should report store failures
        return _empty_dashboard(
            f"统计加载失败：{exc.__class__.__name__}: {exc}（后端：{backend}）"
        )

    data = build_dashboard_data(items, blackboards)
    refreshed = data["now"].astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    status = (
        f"后端：{backend} · 去重情报：{len(items):,} · "
        f"运行记录：{len(blackboards):,} · 刷新时间：{refreshed}"
    )
    return (
        status,
        _kpi_html(data["kpis"]),
        _coverage_figure(data),
        data["health_rows"],
        data["gap_rows"],
        _topic_figure(data),
        data["source_rows"],
        _timeline_figure(data),
        _extended_figure(data),
        data["candidate_rows"],
    )
