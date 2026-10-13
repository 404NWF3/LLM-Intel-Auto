# SAADS Community Intelligence V1.0.0 release gate

Date: 2026-09-16. Requested annotated tag: `saads-community-v1.0.0`.

Decision: **PASS — Community V1 release authorized by the scoped gate.**

This Community-only gate supersedes the broad gate in
`community_v1_release_check.md`, as explicitly authorized by the user. No failed
repository-wide test is reclassified as passing.

## Included gate

| Capability | Result / evidence |
|---|---|
| Real GitHub Issues, HN, Hugging Face Forum collection | PASS: captured live rounds 10→2, 10→10, 50→11 items respectively; zero ID overlap; no stub/degraded results |
| Reddit public RSS | PASS: real run `community-v1-bb300626a79d`, 5 fetched / 4 LLM-retained and structured |
| Incremental, per-query cursors, checkpoint/recovery | PASS: query hashes independently checkpointed; actual timeout retried twice, cursor unchanged, real resume successful |
| Dynamic keywords → keyword/LLM filter | PASS: HN-learned `echoleak` and `365 copilot` drove subsequent scoped GitHub queries; 6 traced matches. Earlier real 47 keyword rejections and 11 LLM rejections revalidated |
| Structured/STIX, semantic dedup/cross-platform | PASS: actual DeepSeek structured results; HN + three GitHub EchoLeak reports merged; Cursor and CKEditor negative controls remain separate |
| Provenance/first-seen | PASS: original payload hashes, source artifacts, STIX external references and observations verified; publication chronology is not a claim of causal propagation |
| API | PASS: original FastAPI lifespan, auth 401/authorized 200, request IDs, missing run 404, nodes endpoint, and real captured run replay through original RunStore/state routes |
| Community regression | PASS: 47 passed, 5 deliberately deselected (graph runtime/BOM and CrewAI coordination outside gate) |
| Community frontend | PASS: dashboard/navigation 3 files / 4 tests; production build; actual Next production server `/dashboard` and `/dashboard/wp11` HTTP 200 |
| Secret / diff | PASS: 407 staged files scanned, zero findings; `git diff --cached --check` clean. Credential-bearing template comment removed; no secret values printed |

Live evidence reuse is deliberate: **199 production/source files** in the previous
live-acceptance freeze matched SHA-256 at this gate. The remaining `.env.example`
has only its credential-bearing DSN comment sanitized since that freeze; it is
checked by the staged secret gate. No live result was replaced
with a fixture. `scripts/community_release_gate.py` fails if these hashes or
required captures are missing/mismatched. API testing explicitly replays genuine
results; it does not assert a new API-triggered collection or browser-rendered
data capture. Unit regression doubles are not counted as live evidence.

Evidence paths (local, deliberately excluded from Git):

- `.runtime/release/community/evidence-gate.json`
- `.runtime/release/community-regression.xml` and `community-regression.log`
- `.runtime/release/community-frontend-tests.log`, `community-frontend-build.log`
- `.runtime/release/community/frontend-start.json`
- `.runtime/release/community/secret-gate.json`
- `.runtime/community-discovery/remaining-v1-final/acceptance.json`
- `.runtime/community-discovery/probe-32cd140b09/` (real timeout/recovery)

## Explicit exclusions and boundaries

- BOM / component resolution, WP1-2, PostgreSQL integration: downstream systems,
  not Community V1's responsibility. No user's database was truncated or seeded
  for this gate. API startup's absent-database warning is expected in this gate.
- Phase 6 planning / reflection: separate orchestration scope; existing removed
  fields/signature mismatches remain documented, not hidden or fixed by adding
  features.
- Nine legacy crawler scripts: import an absent historical `saads` package;
  not the current adapters and not runnable automated Community tests.
- External LLM reviewer tests unrelated to community filtering/standardization/
  semantic dedup: excluded; real DeepSeek community evidence remains required.
- Discord and Twitter/X: **BLOCKED** for absent authorized credentials, disabled
  by default, explicitly nonblocking for this release.
- Reddit acceptance covers public RSS, not OAuth/private content or exhaustive
  historical pagination. HF Forum is Discourse search evidence, not the entire
  Hugging Face ecosystem.
- Pre-existing latent-intelligence demo/sample files are preserved in the
  requested current-worktree snapshot, but are not activated, used in the gate,
  or represented as live production data. No feature was added for this release.

## Commands

```powershell
$env:USE_TORCH='0'; $env:USE_TF='0'
python scripts/community_release_gate.py
python -m pytest tests/wp11/test_phase2_sources.py tests/wp11/test_llm_provider_compat.py tests/wp11/test_phase3_standardization.py tests/wp11/test_phase4_dedup_merge.py tests/wp11/test_phase1_parallel_and_crews.py -q -k 'not runtime and not crewai'
# From frontend/: npm test -- --maxWorkers=1 --minWorkers=1 --no-file-parallelism src/app/dashboard/page.test.tsx "src/app/dashboard/[wp]/page.test.tsx" src/components/dashboard/DashboardSidebar/DashboardSidebar.test.tsx
# From frontend/: npm run build; npm start -- --hostname 127.0.0.1 --port 3311
# After staging, before commit:
python scripts/community_secret_gate.py
git diff --cached --check
```

## Release hygiene

`.env`, frontend local credentials, runtime artifacts, caches, dependencies and
conversation exports are excluded. Previously tracked local config/cache/export
files are removed from the index only; local copies remain. History is not
rewritten. No push is authorized or performed. The old local freeze manifest is
a historical pre-release snapshot, not the identity of this Git release; the
annotated tag identifies the actual committed snapshot.
