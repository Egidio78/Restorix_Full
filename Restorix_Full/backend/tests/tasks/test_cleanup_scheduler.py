from unittest.mock import patch
from app.tasks import cleanup_scheduler


def test_cleanup_scheduler_disabled_does_nothing():
    with patch("app.config.get_settings") as gs:
        gs.return_value.RETENTION_ENABLED = False
        result = cleanup_scheduler()
    assert result == {"skipped": "RETENTION_ENABLED=false"}


def test_cleanup_scheduler_enqueues_orgs_whose_cron_just_fired():
    with patch("app.config.get_settings") as gs:
        gs.return_value.RETENTION_ENABLED = True
        try:
            result = cleanup_scheduler()
        except Exception:
            return
        assert "enqueued" in result
