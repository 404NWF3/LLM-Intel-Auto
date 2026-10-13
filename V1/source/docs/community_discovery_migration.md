# Community discovery integration review

Upstream: https://github.com/theconsciouslab-ai/Promptrend
Pinned commit: `9596165303495a2fff67a3664b35eb83f64c1aff`.
Paper: https://arxiv.org/html/2507.19185v1 (sections 3.2 and 3.4).
The independent reference directory contains 151 hash-verified source/configuration
files; research datasets are excluded from acceptance evidence.

## Findings and integration boundary

| Mechanism | Upstream code | SAADS integration |
|---|---|---|
| Reddit | `reddit_client.py`, `keyword_filter.py`, `reddit_agent.py`: OAuth, comment trees, keyword then LLM | Preserve RSS adapter; add authorized OAuth adapter, actual permalink and checkpoint |
| GitHub | issue collector uses `get_issues(since=...)`; discussion collector actually filters issue titles | Add explicit Issues source; retain SAADS native GraphQL Discussions |
| Forum | Discourse `latest.json` and topic JSON retain posts | Add Discourse adapter with source/parent links and bounded pagination |
| Discord | historical/realtime collectors group replies and threads | Authorized bot REST adapter; channel IDs explicitly configured |
| X | recent search, conversation IDs and referenced tweets | Authorized v2 recent-search adapter with cursor and conversation metadata |
| Dynamic terms | `KeywordMonitor` layers core/context/emergent; Reddit filter persists lexicon | Evidence-grounded terms in existing checkpoint, used in subsequent filtering/query plans |
| Two-stage filter | keyword prefilter then LLM relevance | Dedicated pre-standardization service using existing LLM pool, fail closed with audit |
| Semantic correlation | MiniLM embeddings, provenance and temporal metadata | Keep SAADS merge judge and STIX; retain observation context; do not port coordinator wholesale |

Upstream limitations: `SemanticFingerprinter._get_embedding_for_fingerprint`
returns `None`; coordinator `_compute_similarity` returns fixed 0.9/0.5 based
on hash equality, and `process_new_content` matches exact embedding hashes.
These are not production semantic deduplication. Its propagation timestamps and
platform order do not establish causal transmission. SAADS must distinguish
explicit links, semantic similarity and observed chronology.

SAADS findings: HN score 0.6 is a fixed source score, not content filtering;
the monitor counts all standardized items as retained. Failed batches currently
overwrite cursors; multiple queries share one source cursor. Standardization
currently catches even llm_required errors and degrades. These need explicit
corrections before claiming the stronger acceptance criteria.

## Minimal migration sequence

1. Preserve existing architecture and dirty worktree; extend fetch toolbox and
   registry, with new credential-dependent sources disabled by default.
2. Protect failed checkpoints and isolate each query's cursor. Store bounded
   scan windows for incremental collection; no page-offset-only freshness claim.
3. Add audited keyword/LLM filtering at the existing standardization boundary;
   preserve raw evidence and attach approved terms/context to metadata/STIX.
4. Extend existing monitoring runner configuration and persisted state.
5. Verify real source requests, successive rounds and failure recovery; then
   verify actual LLM filtering and cross-platform merge evidence.

## Environment at review

2026-09-15 update: GitHub token preserved. DeepSeek official credentials were
configured locally by the user. Profiles 301/302/303 resolve OPENAI_API_KEY,
OPENAI_BASE_URL and OPENAI_FAST_MODEL/OPENAI_MODEL. Official endpoint returned
HTTP 200 for models and a forced structured tool call using deepseek-flash.
Thinking uses DeepSeek's thinking.type request field, not enable_thinking.
No credential values are recorded here.

Live run community-v1-499495e35793 collected 70 real items from GitHub Issues,
Hacker News and Hugging Face Discourse: 47 keyword rejections, 11 LLM
rejections, 12 retained and LLM-standardized new records, zero merges,
159.208 seconds. Artifacts and checkpoint are under the local runtime
directory `.runtime/community-discovery/deepseek-live` (do not commit
runtime data or credentials). Cross-platform semantic merge is NOT yet proven.
The following round failed exact evidence validation and did not advance the
checkpoint. Source-only timeout/recovery evidence is separately stored in
`.runtime/community-discovery/probe-32cd140b09`; it is not LLM acceptance.

After bounded evidence retries, deterministic JSON/HTML body rendering, and
preservation of GitHub repository scope in learned queries, live run
`community-v1-ce9b0dcaca5e` completed in 150.25 seconds with 70 raw items,
5 retained LLM-primary structured items, 0 new, 1 merge, 4 review decisions,
and no source failures. The merge is HN item 49604092 observed in successive
rounds with different queries; it is NOT cross-platform correlation evidence.
All three failed monitor rounds preserved the preceding source cursors exactly.
Regression subset: 45 passed, 3 runtime integration tests deselected (not PASS).
Full-suite and cross-platform acceptance remain incomplete.

Reddit OAuth, Discord bot and X bearer token remain absent. Missing credentials
are external blockers, not successful zero-result runs.
No PVAF, attack execution, WP1-2 or database migration is included.

## Final remaining acceptance update

See `community_v1_remaining_acceptance.md` and the machine-checked
`.runtime/community-discovery/remaining-v1-final/acceptance.json`.
These supersede the earlier environment/unfinished-acceptance observations:
Reddit public RSS, cross-platform positive/negative correlation, and live dynamic
keyword queries/two-stage filtering now pass. Discord and X remain BLOCKED for
missing authorized credentials. Freeze is a local file-hash snapshot, not a tag
of the pre-change Git HEAD.
