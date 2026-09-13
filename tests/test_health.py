def test_health_check(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "version": "0.1.0"}


def test_root_describes_service(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["documentation"] == "/docs"
    assert response.json()["demo"] == "/demo"
    assert "X-Request-ID" in response.headers


def test_interactive_demo_is_available(client):
    response = client.get("/demo")

    assert response.status_code == 200
    assert "FinFlow" in response.text
