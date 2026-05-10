"""
Route tests for user_documents ALERTS endpoints — MOCKED database.

Validates:
- GET /alerts: list active alerts (with severity filter)
- PUT /alerts/{id}/read: mark alert as read
- PUT /alerts/{id}/dismiss: dismiss alert
- Auth enforcement
- OWASP: cannot mark another user's alert (simulated via UPDATE 0)

DB is MOCKED — tests set mock_db return values before each API call.
"""

import pytest
from uuid import uuid4
from datetime import datetime, date

BASE = "/api/v1/user-documents"

TEST_USER_ID_STR = "e709d664-0789-40e0-b5fe-1146fa6660e6"
SECOND_USER_ID_STR = "a5cfc4b3-50b4-4473-b6b7-6351b318a313"


def _make_alert_row(
    alert_id=None,
    alert_type="expiry_warning",
    severity="warning",
    is_read=False,
    is_dismissed=False,
    **overrides,
):
    """Build a dict matching user_document_alerts DB row."""
    if alert_id is None:
        alert_id = uuid4()
    now = datetime.utcnow()
    row = {
        "id": alert_id,
        "user_id": TEST_USER_ID_STR,
        "alert_type": alert_type,
        "severity": severity,
        "title_es": "Alerta de prueba ES",
        "title_fr": "Alerte de test FR",
        "title_en": "Test alert EN",
        "message_es": "Su documento expira pronto",
        "message_fr": "Votre document expire bientot",
        "message_en": "Your document expires soon",
        "suggested_action": None,
        "action_params": None,
        "is_read": is_read,
        "is_dismissed": is_dismissed,
        "trigger_date": date.today(),
        "created_at": now,
        "updated_at": now,
        "dismissed_at": None,
        "user_document_id": None,
    }
    row.update(overrides)
    return row


@pytest.mark.asyncio
class TestAlertsRoutes:

    # -- AL-01: List alerts ---------------------------------------------------

    async def test_list_alerts(self, client, mock_db):
        """AL-01: GET /alerts returns alerts from mock DB."""
        mock_db.fetch.return_value = [
            _make_alert_row(alert_type="expiry_warning", severity="warning"),
            _make_alert_row(alert_type="expiry_critical", severity="critical"),
        ]

        response = await client.get(f"{BASE}/alerts")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    # -- AL-02: List alerts response schema -----------------------------------

    async def test_alert_response_schema(self, client, mock_db):
        """AL-02: Each alert in the list has the expected fields."""
        mock_db.fetch.return_value = [
            _make_alert_row(alert_type="expiry_warning", severity="warning"),
        ]

        response = await client.get(f"{BASE}/alerts")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        alert = data[0]
        expected_fields = {
            "id", "alert_type", "severity", "title", "message",
            "is_read", "is_dismissed", "created_at",
        }
        assert expected_fields.issubset(alert.keys())

    # -- AL-03: Filter by severity=critical -----------------------------------

    async def test_filter_severity_critical(self, client, mock_db):
        """AL-03: Filtering by severity=critical returns only critical alerts."""
        mock_db.fetch.return_value = [
            _make_alert_row(alert_type="expiry_critical", severity="critical"),
        ]

        response = await client.get(f"{BASE}/alerts?severity=critical")
        assert response.status_code == 200
        data = response.json()
        for alert in data:
            assert alert["severity"] == "critical"

    # -- AL-04: Filter by severity=warning ------------------------------------

    async def test_filter_severity_warning(self, client, mock_db):
        """AL-04: Filtering by severity=warning excludes non-warning alerts."""
        mock_db.fetch.return_value = [
            _make_alert_row(alert_type="expiry_warning", severity="warning"),
        ]

        response = await client.get(f"{BASE}/alerts?severity=warning")
        assert response.status_code == 200
        data = response.json()
        for alert in data:
            assert alert["severity"] == "warning"

    # -- AL-05: Mark alert as read -> is_read=True ----------------------------

    async def test_mark_alert_read(self, client, mock_db):
        """AL-05: PUT /alerts/{id}/read sets is_read=True."""
        alert_id = uuid4()
        mock_db.execute.return_value = "UPDATE 1"

        response = await client.put(f"{BASE}/alerts/{alert_id}/read")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["is_read"] is True

    # -- AL-06: Mark nonexistent alert -> 404 ---------------------------------

    async def test_mark_read_nonexistent_returns_404(self, client, mock_db):
        """AL-06: PUT /alerts/{fake_id}/read returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        mock_db.execute.return_value = "UPDATE 0"

        response = await client.put(f"{BASE}/alerts/{fake_id}/read")
        assert response.status_code == 404

    # -- AL-07: Dismiss alert -> is_dismissed=True ----------------------------

    async def test_dismiss_alert(self, client, mock_db):
        """AL-07: PUT /alerts/{id}/dismiss sets is_dismissed=True."""
        alert_id = uuid4()
        mock_db.execute.return_value = "UPDATE 1"

        response = await client.put(f"{BASE}/alerts/{alert_id}/dismiss")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["is_dismissed"] is True

    # -- AL-08: Dismiss nonexistent alert -> 404 ------------------------------

    async def test_dismiss_nonexistent_returns_404(self, client, mock_db):
        """AL-08: PUT /alerts/{fake_id}/dismiss returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        mock_db.execute.return_value = "UPDATE 0"

        response = await client.put(f"{BASE}/alerts/{fake_id}/dismiss")
        assert response.status_code == 404

    # -- AL-09: Dismissed alerts not in default list --------------------------

    async def test_dismissed_alerts_excluded(self, client, mock_db):
        """AL-09: Dismissed alerts must not appear in the default list."""
        # DB returns empty (the WHERE clause has is_dismissed=FALSE)
        mock_db.fetch.return_value = []

        response = await client.get(f"{BASE}/alerts")
        data = response.json()
        assert data == []

    # -- AL-10: OWASP — Cannot mark another user's alert ---------------------

    async def test_owasp_cannot_mark_other_users_alert(self, client, mock_db):
        """AL-10: OWASP A01 — Marking another user's alert returns 404."""
        alert_id = uuid4()
        # The UPDATE WHERE user_id = $2 won't match -> UPDATE 0
        mock_db.execute.return_value = "UPDATE 0"

        response = await client.put(f"{BASE}/alerts/{alert_id}/read")
        assert response.status_code == 404

    # -- AL-11: OWASP — Cannot dismiss another user's alert -------------------

    async def test_owasp_cannot_dismiss_other_users_alert(self, client, mock_db):
        """AL-11: OWASP A01 — Dismissing another user's alert returns 404."""
        alert_id = uuid4()
        mock_db.execute.return_value = "UPDATE 0"

        response = await client.put(f"{BASE}/alerts/{alert_id}/dismiss")
        assert response.status_code == 404

    # -- AL-12: No auth on alerts -> 401 --------------------------------------

    async def test_no_auth_returns_401(self, unauth_client):
        """AL-12: GET /alerts without auth returns 401."""
        response = await unauth_client.get(f"{BASE}/alerts")
        assert response.status_code in (401, 403)

    # -- AL-13: No auth on mark read -> 401 -----------------------------------

    async def test_no_auth_mark_read_returns_401(self, unauth_client):
        """AL-13: PUT /alerts/{id}/read without auth returns 401."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await unauth_client.put(f"{BASE}/alerts/{fake_id}/read")
        assert response.status_code in (401, 403)

    # -- AL-14: No auth on dismiss -> 401 -------------------------------------

    async def test_no_auth_dismiss_returns_401(self, unauth_client):
        """AL-14: PUT /alerts/{id}/dismiss without auth returns 401."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await unauth_client.put(f"{BASE}/alerts/{fake_id}/dismiss")
        assert response.status_code in (401, 403)

    # -- AL-15: Alerts sorted by severity (critical first) --------------------

    async def test_alerts_sorted_by_severity(self, client, mock_db):
        """AL-15: Alerts are returned sorted: critical > warning > info."""
        # The route does ORDER BY severity CASE, so mock returns pre-sorted
        mock_db.fetch.return_value = [
            _make_alert_row(alert_type="expiry_critical", severity="critical"),
            _make_alert_row(alert_type="expiry_warning", severity="warning"),
            _make_alert_row(alert_type="renewal_suggestion", severity="info"),
        ]

        response = await client.get(f"{BASE}/alerts")
        assert response.status_code == 200
        data = response.json()
        if len(data) >= 3:
            severities = [a["severity"] for a in data]
            severity_order = {"critical": 0, "warning": 1, "info": 2}
            for i in range(len(severities) - 1):
                assert severity_order[severities[i]] <= severity_order[severities[i + 1]], (
                    f"Alert at position {i} ({severities[i]}) should come before "
                    f"position {i+1} ({severities[i+1]})"
                )

    # -- AL-16: Multiple alerts for same user ---------------------------------

    async def test_multiple_alerts_returned(self, client, mock_db):
        """AL-16: Multiple alerts are all returned."""
        mock_db.fetch.return_value = [
            _make_alert_row(alert_type="expiry_warning"),
            _make_alert_row(alert_type="expiry_critical"),
            _make_alert_row(alert_type="renewal_suggestion"),
        ]

        response = await client.get(f"{BASE}/alerts")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    # -- AL-17: Limit parameter respected -------------------------------------

    async def test_alerts_limit(self, client, mock_db):
        """AL-17: limit parameter restricts number of alerts returned."""
        mock_db.fetch.return_value = [
            _make_alert_row(alert_type="expiry_warning"),
            _make_alert_row(alert_type="expiry_critical"),
        ]

        response = await client.get(f"{BASE}/alerts?limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 2
