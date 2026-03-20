import pytest


@pytest.mark.django_db
def test_healthcheck_public(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json().get("status") == "ok"
