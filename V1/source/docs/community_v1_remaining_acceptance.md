# Community V1 remaining acceptance — 2026-09-15

Scope: community intelligence acquisition and structured output only. Previously
accepted GitHub Issues, HN, Hugging Face Forum, incremental/checkpoint, API and
frontend checks were not repeated as broad acceptance suites. Targeted new live
queries below exercise the remaining correlation and keyword requirements.

## Results

| Item | Result | Actual evidence |
|---|---|---|
| Reddit public RSS | PASS | `community-v1-bb300626a79d`: 5 fetched, 4 LLM-retained and structured, 4 new, no source failures, 42.857 s |
| Discord | BLOCKED | `DISCORD_BOT_TOKEN` absent; authorized `default_params.guild_id/channel_id` also required; remains disabled |
| Twitter/X | BLOCKED | `TWITTER_BEARER_TOKEN` absent; authorized recent-search API access required; remains disabled |
| Cross-platform association | PASS | EchoLeak HN 44250774 and GitHub SecOpsNews/news issues 49420, 49449, 49453 share one stable record |
| Negative controls | PASS | Cursor CurXecute (SecOpsNews/news 51621) and CKEditor EchoLeak-style (dxpr/ckeditor5-ai-agent 159) remain separate from Copilot EchoLeak |
| Dynamic keywords | PASS | Real HN-derived `echoleak` and `365 copilot` entered later generated GitHub queries; 6 matching live query/filter observations, with learning evidence persisted |
| keyword → LLM filtering | PASS | New targeted runs use both stages. Prior real run `499495e35793` additionally proves 47 keyword rejections, 11 LLM rejections, 12 retained; reused without repeating collection |
| Provenance and chronology | PASS | All four positive source URIs, source artifacts, original adapter payload hashes and STIX provenance verified; first-seen `2025-06-11T17:50:30+00:00` |

Final targeted runs:

- HN seed: `community-v1-956560ae1c41`, 5 raw / 1 retained, 16.542 s.
- Dynamic GitHub: `community-v1-b99400605cca`, 18 raw / 9 retained / 7 merges / 2 new, 148.76 s.
- Additional negative control: `community-v1-805b03cd5283`, 3 raw / 2 retained / 2 new / 0 merges, 30.769 s; both LLM decisions `different_attack` (0.82, 0.90).

Machine-checked evidence is in
`.runtime/community-discovery/remaining-v1-final/acceptance.json`.
Reddit artifacts are in `.runtime/community-discovery/reddit-remaining-v1/`.
Credential presence/public Reddit probe evidence is in
`.runtime/community-discovery/remaining-v1/platforms.json`.

## Repairs verified against actual failures

- Reddit's requested time window was silently fixed to `week`; it now maps the
  requested window to Reddit's supported time filters. Public RSS returned real
  items without credentials. This does not certify private/OAuth access or
  exhaustive Reddit history/pagination.
- Standardization incorrectly treated the reporting research lab as an affected
  component, then duplicated a product's shorthand and full name. Tightened the
  existing extraction prompt/schema; did not lower BOM merge safety thresholds.
- Structured-output validation failures were incorrectly fatal; now retried
  within the existing bounded model-pool policy. The final live run recovered
  from actual invalid responses; it did not use rule-only or empty substitutes.
- Stable records/STIX now retain publication chronology and all independently
  collected artifacts. Chronology explicitly does **not** establish causal
  propagation. The first observed collection time is recorded separately.
- Added per-keyword original-source/hash/model evidence and deterministic XML
  text extraction for the existing Reddit RSS relevance gate.

Related regression command:
`python -m pytest tests/wp11/test_llm_provider_compat.py tests/wp11/test_phase3_standardization.py tests/wp11/test_phase4_dedup_merge.py -q -k 'not runtime'`
returned **40 passed, 3 deselected**. These tests are regression checks, not live
acceptance evidence. No full-suite PASS is asserted here.

## Freeze boundary

`docs/community_v1_freeze.json` freezes the actual local source snapshot by
SHA-256 and links the acceptance evidence hash. It is not a Git commit or tag:
the working tree contains pre-existing uncommitted changes, so tagging HEAD
would misrepresent the tested files. Suggested tag after a reviewed, secret-free
commit: `saads-community-v1-20260915`.

Discord/X remain excluded from enabled release capabilities until authorized
credentials permit separate real acceptance. No `.env`, token, database or
runtime content is committed. No migration, WP1-2, KG or attack execution is added.
