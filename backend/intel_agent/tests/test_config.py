"""Configuration must work from .env without exporting shell variables."""
from intel_agent.runtime.client import _dotenv_values, _setting
from intel_agent.analysis import coverage_quota
from intel_agent.agent.loop import resolve_max_turns
from intel_agent.relevance import default_pipeline


def test_dotenv_controls_collection_and_environment_takes_precedence(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for key in ('INTEL_COVERAGE_QUOTA', 'INTEL_AGENT_MAX_TURNS', 'INTEL_RELEVANCE_ENABLED'):
        monkeypatch.delenv(key, raising=False)
    (tmp_path / '.env').write_text(
        'INTEL_COVERAGE_QUOTA=7\nINTEL_AGENT_MAX_TURNS=9\nINTEL_RELEVANCE_ENABLED=0\n',
        encoding='utf-8',
    )
    _dotenv_values.cache_clear()
    try:
        assert coverage_quota() == 7
        assert resolve_max_turns(None) == 9
        assert default_pipeline() is None
        monkeypatch.setenv('INTEL_COVERAGE_QUOTA', '5')
        assert coverage_quota() == 5
        assert _setting('UNSET_CONFIG', 'fallback') == 'fallback'
    finally:
        _dotenv_values.cache_clear()
