from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

psycopg = pytest.importorskip("psycopg")

from backend.db.unit_of_work import UnitOfWork
from backend.db.services.component_seed_service import AiComponentSeedService


@pytest.fixture(scope="session")
def integration_dsn() -> str:
    dsn = os.getenv("SAADS_TEST_DSN")
    if not dsn:
        pytest.skip("Set SAADS_TEST_DSN to run db integration tests")
    return dsn


@pytest.fixture(scope="session", autouse=True)
def ensure_schema(integration_dsn: str) -> None:
    schema_path = (
        Path(__file__).resolve().parents[3]
        / "backend"
        / "db"
        / "wp11_postgresql_schema.sql"
    )
    schema_sql = schema_path.read_text(encoding="utf-8")
    with psycopg.connect(integration_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(schema_sql)


@pytest.fixture()
def clean_db(integration_dsn: str) -> None:
    truncate_sql = """
    TRUNCATE TABLE
        wp11.bom_resolution_queue,
        wp11.dedup_audit,
        wp11.attack_component_impact,
        wp11.ai_component_alias,
        wp11.ai_component,
        wp11.remediation_advice,
        wp11.attack_seed_asset,
        wp11.attack_taxonomy_map,
        wp11.attack_evidence,
        wp11.attack_cvss_assessment,
        wp11.attack_entry,
        wp11.raw_intel_record,
        wp11.collection_task,
        wp11.intel_source
    RESTART IDENTITY CASCADE
    """
    with psycopg.connect(integration_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(truncate_sql)


@pytest.fixture()
def db_conn(integration_dsn: str, clean_db: None):
    conn = psycopg.connect(integration_dsn, autocommit=False)
    try:
        yield conn
    finally:
        conn.close()


def _insert_source(conn, name: str):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO wp11.intel_source (source_name, source_type, base_uri, trust_level)
            VALUES (%s, 'api', 'https://example.com', 3)
            RETURNING source_id
            """,
            (name,),
        )
        return cur.fetchone()[0]


def _insert_attack(uow: UnitOfWork, suffix: str):
    return uow.attacks.create_attack_entry(
        attack_code=f"TST-{suffix}",
        canonical_name=f"Attack {suffix}",
        attack_family="prompt_injection",
        severity_level="high",
        entry_status="active",
        summary=f"summary {suffix}",
        description=f"description {suffix}",
        confidence_score=0.9,
    )


def test_raw_record_idempotent_insert(db_conn) -> None:
    source_id = _insert_source(db_conn, f"src-{uuid4().hex[:8]}")

    with UnitOfWork(conn=db_conn) as uow:
        task = uow.sources.create_collection_task(
            source_id=source_id,
            task_mode="fast",
            trigger_type="manual",
            task_status="queued",
            created_by="pytest",
        )
        content_hash = hashlib.sha256(b"same-content").hexdigest()
        fetched_at = datetime.now(timezone.utc)

        first = uow.sources.insert_or_get_raw_record(
            source_id=source_id,
            task_id=task.task_id,
            source_uri="https://example.com/intel-1",
            title="intel",
            content_hash=content_hash,
            raw_format="json",
            payload_uri="file:///tmp/payload1.json",
            fetched_at=fetched_at,
        )
        second = uow.sources.insert_or_get_raw_record(
            source_id=source_id,
            task_id=task.task_id,
            source_uri="https://example.com/intel-1",
            title="intel",
            content_hash=content_hash,
            raw_format="json",
            payload_uri="file:///tmp/payload1.json",
            fetched_at=fetched_at,
        )

    assert first.raw_id == second.raw_id


def test_set_primary_cvss_in_single_attack_version(db_conn) -> None:
    with UnitOfWork(conn=db_conn) as uow:
        attack = _insert_attack(uow, uuid4().hex[:8])
        cvss1 = uow.attacks.insert_cvss_assessment(
            attack_id=attack.attack_id,
            source_raw_id=None,
            cvss_version="3.1",
            vector_string="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
            base_score=8.5,
            temporal_score=None,
            environmental_score=None,
            severity_label="High",
            exploitability_subscore=None,
            impact_subscore=None,
            score_origin="manual",
            score_provider="pytest",
            confidence_score=0.8,
            is_primary=False,
        )
        cvss2 = uow.attacks.insert_cvss_assessment(
            attack_id=attack.attack_id,
            source_raw_id=None,
            cvss_version="3.1",
            vector_string="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
            base_score=9.1,
            temporal_score=None,
            environmental_score=None,
            severity_label="Critical",
            exploitability_subscore=None,
            impact_subscore=None,
            score_origin="manual",
            score_provider="pytest",
            confidence_score=0.9,
            is_primary=False,
        )
        uow.attacks.set_primary_cvss(cvss2.score_id)
        all_scores = uow.attacks.list_cvss_assessments(attack.attack_id)

    primary = [score for score in all_scores if score.is_primary]
    assert len(primary) == 1
    assert primary[0].score_id == cvss2.score_id
    assert cvss1.score_id != cvss2.score_id


def test_replace_primary_taxonomy(db_conn) -> None:
    with UnitOfWork(conn=db_conn) as uow:
        attack = _insert_attack(uow, uuid4().hex[:8])
        uow.attacks.upsert_taxonomy_map(
            attack_id=attack.attack_id,
            taxonomy_type="OWASP_LLM",
            taxonomy_code="LLM02",
            taxonomy_name="Insecure Output Handling",
            is_primary=True,
            confidence_score=0.7,
        )
        uow.attacks.replace_primary_taxonomy(
            attack_id=attack.attack_id,
            taxonomy_type="OWASP_LLM",
            taxonomy_code="LLM01",
            taxonomy_name="Prompt Injection",
            confidence_score=0.95,
        )
        maps = uow.attacks.list_taxonomy_maps(attack.attack_id)

    primary = [m for m in maps if m.taxonomy_type == "OWASP_LLM" and m.is_primary]
    assert len(primary) == 1
    assert primary[0].taxonomy_code == "LLM01"


def test_bom_queue_resolve_status_consistency(db_conn) -> None:
    with UnitOfWork(conn=db_conn) as uow:
        attack = _insert_attack(uow, uuid4().hex[:8])
        component = uow.components.create_component(
            component_code=f"CMP-{uuid4().hex[:8]}",
            component_name="LangChain",
            vendor_name=None,
            component_type="framework",
        )
        queued = uow.governance.enqueue_bom_resolution(
            attack_id=attack.attack_id,
            raw_id=None,
            mentioned_name="Lang Chain",
            mentioned_vendor=None,
            mentioned_version=None,
            reason_code="alias_not_found",
        )
        resolved = uow.governance.resolve_bom_queue_item(
            queue_id=queued.queue_id,
            resolved_component_id=component.component_id,
        )

    assert resolved is not None
    assert resolved.queue_status == "resolved"
    assert str(resolved.resolved_component_id) == str(component.component_id)
    assert resolved.resolved_at is not None


def test_read_model_feed_and_mv_refresh(db_conn) -> None:
    unique = uuid4().hex[:8]
    with UnitOfWork(conn=db_conn) as uow:
        attack = _insert_attack(uow, unique)
        uow.attacks.insert_cvss_assessment(
            attack_id=attack.attack_id,
            source_raw_id=None,
            cvss_version="3.1",
            vector_string="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
            base_score=8.8,
            temporal_score=None,
            environmental_score=None,
            severity_label="High",
            exploitability_subscore=None,
            impact_subscore=None,
            score_origin="manual",
            score_provider="pytest",
            confidence_score=0.9,
            is_primary=True,
        )
        uow.attacks.replace_primary_taxonomy(
            attack_id=attack.attack_id,
            taxonomy_type="OWASP_LLM",
            taxonomy_code="LLM01",
            taxonomy_name="Prompt Injection",
            confidence_score=0.95,
        )
        component = uow.components.create_component(
            component_code=f"CMP-{unique}",
            component_name=f"Component-{unique}",
            vendor_name="ACME",
            component_type="framework",
        )
        uow.components.upsert_attack_component_impact(
            attack_id=attack.attack_id,
            component_id=component.component_id,
            version_constraint_raw=">=1.0,<2.0",
            normalized_constraint=">=1.0,<2.0",
            match_mode="range",
            impact_scope="direct",
            confidence_score=0.88,
        )
        checksum = hashlib.sha256(f"seed-{unique}".encode("utf-8")).hexdigest()
        uow.attacks.insert_seed_asset(
            attack_id=attack.attack_id,
            asset_type="payload_template",
            asset_name=f"seed-{unique}",
            artifact_uri=f"s3://bucket/{unique}.txt",
            checksum=checksum,
            qa_status="reviewed",
            is_template=True,
            metadata_json={"k": "v"},
        )

        feed = uow.read_models.list_wp12_attack_feed(min_cvss=7.0)
        uow.read_models.refresh_mv_owasp_coverage()
        owasp_rows = uow.read_models.list_owasp_coverage(limit=50)

    assert any(str(row.attack_id) == str(attack.attack_id) for row in feed)
    assert any(row.taxonomy_code == "LLM01" for row in owasp_rows)


def test_component_seed_bootstrap_populates_aliases(db_conn) -> None:
    with UnitOfWork(conn=db_conn) as uow:
        report = AiComponentSeedService(uow).bootstrap()
        alias_match = uow.components.find_component_by_alias("chatgptapi")
        transformers_match = uow.components.find_component_by_alias(
            "transformerslibrary"
        )

    assert report["seeded_components"] >= 10
    assert report["seeded_aliases"] >= report["seeded_components"]
    assert alias_match is not None
    assert alias_match.component_name == "OpenAI API"
    assert transformers_match is not None
    assert transformers_match.component_name == "HuggingFace Transformers"
