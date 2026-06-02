import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock


def make_payload(tier="business", valid_until=None, license_id="LIC-TEST-0001"):
    if valid_until is None:
        valid_until = datetime.now(timezone.utc) + timedelta(days=365)
    return {
        "license_version": 1,
        "license_id": license_id,
        "customer_name": "Test Srl",
        "customer_email": "test@test.it",
        "tier": tier,
        "max_servers": 4,
        "max_databases": 30,
        "max_folders": 12,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "valid_from": datetime.now(timezone.utc).isoformat(),
        "valid_until": valid_until.isoformat(),
        "period": "annual",
        "notes": "",
    }


def test_compute_status_demo_when_no_license():
    from app.core.license import compute_status
    now = datetime.now(timezone.utc)
    status = compute_status(None, now)
    assert status.state == "DEMO"
    assert status.tier == "demo"
    assert status.max_databases == 3


def test_compute_status_active_when_far_from_expiry():
    from app.core.license import compute_status, LicenseRecordLike
    now = datetime.now(timezone.utc)
    lic = LicenseRecordLike(
        tier="business",
        valid_from=now - timedelta(days=30),
        valid_until=now + timedelta(days=300),
        payload_json='{"some":"data"}',
        license_id="LIC-2026-0001",
        customer_name="Test",
    )
    status = compute_status(lic, now)
    assert status.state == "ACTIVE"
    assert status.tier == "business"
    assert status.max_databases == 30


def test_compute_status_grace_when_expired_under_14d():
    from app.core.license import compute_status, LicenseRecordLike
    now = datetime.now(timezone.utc)
    lic = LicenseRecordLike(
        tier="business", valid_from=now - timedelta(days=400),
        valid_until=now - timedelta(days=5),
        payload_json='{"x":1}', license_id="LIC", customer_name="X",
    )
    assert compute_status(lic, now).state == "GRACE"


def test_compute_status_readonly_when_expired_between_15_and_74d():
    from app.core.license import compute_status, LicenseRecordLike
    now = datetime.now(timezone.utc)
    lic = LicenseRecordLike(
        tier="business", valid_from=now - timedelta(days=400),
        valid_until=now - timedelta(days=20),
        payload_json='{"x":1}', license_id="LIC", customer_name="X",
    )
    assert compute_status(lic, now).state == "READ_ONLY"


def test_compute_status_locked_after_75d():
    from app.core.license import compute_status, LicenseRecordLike
    now = datetime.now(timezone.utc)
    lic = LicenseRecordLike(
        tier="business", valid_from=now - timedelta(days=400),
        valid_until=now - timedelta(days=80),
        payload_json='{"x":1}', license_id="LIC", customer_name="X",
    )
    assert compute_status(lic, now).state == "LOCKED"


def test_tier_limits_hard_coded():
    from app.core.license import TIER_LIMITS
    assert TIER_LIMITS["demo"]["max_databases"] == 3
    assert TIER_LIMITS["starter"]["max_databases"] == 6
    assert TIER_LIMITS["pro"]["max_databases"] == 10
    assert TIER_LIMITS["business"]["max_databases"] == 30
    assert TIER_LIMITS["enterprise"]["max_databases"] >= 9999


def test_canonical_json_deterministic():
    from app.core.license import canonical_json
    p1 = {"b": 2, "a": 1}
    p2 = {"a": 1, "b": 2}
    assert canonical_json(p1) == canonical_json(p2)


def test_verify_signature_rejects_corrupted(tmp_path):
    from app.core.license import verify_license_file
    bad = {"payload": {"tier": "business"}, "signature": "AAAA"}
    with pytest.raises(ValueError):
        verify_license_file(json.dumps(bad))
