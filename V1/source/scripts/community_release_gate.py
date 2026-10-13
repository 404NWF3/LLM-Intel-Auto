"""Community-only release gate; verifies captured live evidence, never mocks it.

Run after the live acceptance scripts. Missing evidence fails, not skips.
Separate regression tests/build and staged secret scan are required in the report.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / '.runtime/release/community'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    frozen = read(ROOT / 'docs/community_v1_freeze.json')
    changed = [name for name, digest in frozen['source_sha256'].items() if name != '.env.example'
               if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest]
    assert not changed, f'Live-validated source changed: {changed}'
    subprocess.run([sys.executable, str(ROOT / 'scripts/summarize_community_remaining.py')], cwd=ROOT, check=True)
    acceptance = read(ROOT / '.runtime/community-discovery/remaining-v1-final/acceptance.json')
    probe = ROOT / '.runtime/community-discovery/probe-32cd140b09'
    rounds = [read(probe / f'round-{i}.json') for i in (0, 1)]
    sources = {}
    for name in ('github_issues', 'hackernews', 'discourse'):
        ids = []
        for result in rounds:
            collection = result['collection']
            rows = [r for r in collection['raw_items'] if r['source_name'] == name]
            assert rows and all(not r['metadata'].get('used_stub') for r in rows)
            assert all(r['success'] for r in collection['source_execution_stats'] if r['source_name'] == name)
            ids.append({r['external_id'] for r in rows})
        assert not ids[0] & ids[1]
        sources[name] = {'round_1': len(ids[0]), 'round_2': len(ids[1]), 'overlap': 0}
    failed = read(probe / 'failure-recovery.json')
    resumed = read(probe / 'resumed.json')
    assert failed['source_cursors'] == rounds[1]['collection']['source_cursors']
    assert all(not s['success'] and not s['used_stub'] and s['attempt_count'] == 2
               for s in failed['source_execution_stats'])
    assert all(s['success'] and not s['used_stub'] for s in resumed['source_execution_stats'])
    final = ROOT / '.runtime/community-discovery/remaining-v1-final'
    row = read(final / 'github-round.json')
    data = read(final / f"{row['run_id']}.json")
    for stat in row['source_stats']:
        key = hashlib.sha256(stat['query_text'].encode()).hexdigest()
        assert key in row['source_cursors'][stat['source_name']]['queries']
    assert len(row['source_cursors']['github_issues']['queries']) > 1
    from backend.agents.intel_agents.schemas.intel import StandardizedIntelDTO
    for item in data['standardized_items']:
        StandardizedIntelDTO.model_validate(item)
        assert item['stix_payload']['type'] == 'attack-pattern'

    # Replay genuine run results through the unmodified API store/routes. This
    # checks API presentation, NOT an assertion of new API-triggered collection.
    os.environ.update({'POSTGRES_DSN':'', 'POSTGRES_HOST':'', 'POSTGRES_DB':'', 'POSTGRES_USER':''})
    os.environ['SAADS_API_KEY'] = secrets.token_urlsafe(32)
    from fastapi.testclient import TestClient
    from backend.api.server import app
    with TestClient(app) as client:
        assert client.get('/health').status_code == 200
        assert client.get('/api/wp11/state/latest').status_code == 401
        headers = {'X-API-Key': os.environ['SAADS_API_KEY']}
        store = app.state.run_store
        store.create(row['run_id'], 'incremental')
        store.update_from_state(row['run_id'], {
            'run_id': row['run_id'], 'run_mode': 'incremental', 'run_status': 'succeeded',
            'raw_items': data['raw_items'], 'standardized_items': data['standardized_items'],
            'processed_count': len(data['standardized_items']),
            'new_attack_count': row['new_count'], 'dedup_merged_count': row['merged_count'],
        })
        paths = ['/api/wp11/state/latest', f"/api/wp11/runs/{row['run_id']}/state"]
        for path in paths:
            response = client.get(path, headers=headers)
            assert response.status_code == 200 and response.headers.get('X-Request-ID')
            body = response.json()
            assert body['raw_items_count'] == row['raw_count']
            assert body['processed_count'] == row['filtered_retained_count']
            assert body['dedup_merged_count'] == row['merged_count']
        assert client.get('/api/wp11/runs/release-missing/state', headers=headers).status_code == 404
        assert client.get('/api/wp11/nodes', headers=headers).status_code == 200
    report = {'status':'PASS', 'unchanged_live_source_files':len(frozen['source_sha256']) - 1,
              'template_only_change':'.env.example credential-bearing comment removed; staged secret gate required',
              'live_capture_revalidation':sources, 'per_query_cursor':'PASS',
              'real_timeout_retry_checkpoint_recovery':'PASS', 'structured_stix':'PASS',
              'api_real_run_replay':'PASS', 'api_auth_request_id':'PASS',
              'acceptance':{k:v['status'] for k,v in acceptance.items() if isinstance(v,dict)},
              'api_run_id':row['run_id'],
              'exclusions':['BOM','WP1-2','PostgreSQL','Phase 6 planning','legacy crawler','unrelated external LLM reviewers']}
    (OUT / 'evidence-gate.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
