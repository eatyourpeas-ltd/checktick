import pytest


@pytest.mark.django_db
def test_redoc_page_renders(client):
    resp = client.get("/api/redoc")
    assert resp.status_code == 200
    assert b"API Reference (ReDoc)" in resp.content
