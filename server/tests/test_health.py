from app import __version__


def test_health_returns_ok_and_version(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__, "contract": 1}


def test_about_gives_version_and_github_links(client):
    body = client.get("/api/local/about").json()
    assert body["version"] == __version__
    labels = [link["label"] for link in body["links"]]
    assert "Privacy statement" in labels and "Security policy" in labels
    assert all(
        link["url"].startswith("https://github.com/Redsuperninja/budget-buddy/")
        for link in body["links"]
    )
