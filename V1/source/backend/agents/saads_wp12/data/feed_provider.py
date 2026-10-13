from __future__ import annotations

from typing import Protocol

from backend.agents.saads_wp12.config import get_config
from backend.agents.saads_wp12.data.db_feed_provider import DbAttackFeedProvider
from backend.agents.saads_wp12.data.local_feed_provider import LocalAttackFeedProvider
from backend.agents.saads_wp12.data.mock_feed_provider import MockAttackFeedProvider
from backend.agents.saads_wp12.data.models import Wp12AttackFeedItem


class AttackFeedProvider(Protocol):
    def get_attack_feed_item(self, attack_id: str | None = None) -> Wp12AttackFeedItem:
        """Return a single feed item for WP1-2 consumption."""

    def list_attack_feed_refs(self) -> list[tuple[str, str]]:
        """Return lightweight attack references for batch workflows."""

    def list_attack_feed_snapshots(self) -> list[Wp12AttackFeedItem]:
        """Return lightweight feed items for scheduling or inspection."""

    def collect_attack_feed_items(
        self,
        attack_refs: list[tuple[str, str]],
        *,
        continue_on_error: bool = True,
    ) -> tuple[list[Wp12AttackFeedItem], list[dict[str, str]]]:
        """Return full feed items for the provided refs plus any per-item errors."""


def get_attack_feed_provider() -> AttackFeedProvider:
    config = get_config()
    if config.feed_source == "db":
        return DbAttackFeedProvider(
            main_backend_path=config.saads_main_backend_path,
            min_cvss=config.db_feed_min_cvss,
            limit=config.db_feed_limit,
            taxonomy_codes=config.db_feed_taxonomy_codes,
            backend_db_env={
                "POSTGRES_MIN_SIZE": str(config.db_pool_min_size),
                "POSTGRES_MAX_SIZE": str(config.db_pool_max_size),
                "POSTGRES_CONNECT_TIMEOUT": str(config.db_pool_connect_timeout),
                "POSTGRES_STATEMENT_TIMEOUT_MS": str(
                    config.db_pool_statement_timeout_ms
                ),
                "POSTGRES_APPLICATION_NAME": config.db_pool_application_name,
            },
        )
    if config.feed_source == "local_json":
        return LocalAttackFeedProvider(
            root_path=config.local_feed_root,
            min_cvss=config.db_feed_min_cvss,
            limit=config.db_feed_limit,
            taxonomy_codes=config.db_feed_taxonomy_codes,
        )
    return MockAttackFeedProvider()
