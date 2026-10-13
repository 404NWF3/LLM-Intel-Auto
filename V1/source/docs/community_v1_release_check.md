# Community V1 release gate — 2026-09-16

Historical broad-gate result. Superseded for the authorized Community-only
release by `community_v1_release.md`; failures below remain accurately recorded.

Requested tag: `saads-community-v1.0.0`.

**NOT RELEASED**: the final automated regression gate has failures. No commit
or tag has been created. HEAD remains `f226d9e`.

| Check | Result |
|---|---|
| `git diff --check` | PASS (only Git line-ending conversion warnings) |
| Working snapshot secret scan | No active configured secret or provider-token/private-key pattern found; one commented database URL placeholder in `.env.example` reviewed |
| Frontend Vitest | 7 files, 13 tests PASS using one worker |
| Frontend production build | PASS; required network access to fetch the existing Inter Google Font |
| Current backend automated suite | 119 PASS, 27 FAIL, 6 SKIP; 152 collected |
| Discord / Twitter(X) | External credentials BLOCKED; not a release blocker |

Backend command selected `tests --ignore=tests/scrawler-script`. Nine legacy
manual crawler scripts fail collection because they import the absent `saads`
package; these were explicitly excluded, not counted as passing or skipped.
The six PostgreSQL integration tests skip because `SAADS_TEST_DSN` is not set.
No integration test was pointed at a user database: its fixtures truncate tables.

The test process cleared POSTGRES_DSN/HOST/DB/USER in its own environment to
avoid implicit reads/writes against the user's local database. `.env` and
production configuration were not changed. The existing offline BOM fallback
was exercised, not a replacement production database.

## Failure groups

- Source scheduler test expects one shared cursor to advance across different
  queries. Current verified collection deliberately maintains per-query cursors.
- Several runtime tests report `partial_success`; BOM enrichment tests still
  reach database/LLM paths despite expecting self-contained regression behavior.
- Phase 6 planning tests pass `weak_signal_summary`, which `plan_run` does not
  accept; reflection fixtures include the removed `weak_signal_focus_terms`
  field. The planning signature mismatch also exists in the pre-change HEAD.
- LLM reviewer tests fail when attempting real external connections/cooldowns.

Detailed failure names/messages and counts:
`.runtime/release/pytest.xml`; console log: `.runtime/release/pytest.log`.
Frontend logs: `.runtime/release/frontend-tests.log` and
`.runtime/release/frontend-build.log`.
Secret scan locations only: `.runtime/release/secret-scan.json` (no values).

## Release hygiene changes prepared

Added `.gitignore`. Removed the previously tracked frontend local environment,
conversation exports, Python bytecode and TypeScript build cache from the Git
index **only**; all local files remain available. Existing Git history was not
rewritten. No credential value is printed or committed. No product feature was
added. The index removals are staged; application changes remain uncommitted.

The earlier live Community acceptance and local hash freeze remain evidence of
those specific successful checks, not proof that this final regression gate
passed. Do not create the release tag until the failed checks are resolved or
the user explicitly approves a documented narrower release gate.
