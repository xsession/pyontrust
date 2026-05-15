# SPDX-License-Identifier: Apache-2.0
"""Focused tests for the Phase 1 frontend serving boundary."""


class TestFrontendShellRoute:
    def test_root_redirects_to_app(self, client):
        resp = client.get("/", follow_redirects=False)

        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/app")

    def test_frontend_app_serves_index_and_spa_fallback(self, client, tmp_path, monkeypatch):
        import server

        dist_dir = tmp_path / "dist"
        dist_dir.mkdir()
        (dist_dir / "index.html").write_text("<html><body><div id='root'>frontend</div></body></html>", encoding="utf-8")
        monkeypatch.setattr(server, "_FRONTEND_DIST_DIR", dist_dir)

        direct = client.get("/app")
        fallback = client.get("/app/workspace/shell")

        assert direct.status_code == 200
        assert "frontend" in direct.get_data(as_text=True)
        assert fallback.status_code == 200
        assert "frontend" in fallback.get_data(as_text=True)

    def test_frontend_app_serves_static_assets(self, client, tmp_path, monkeypatch):
        import server

        dist_dir = tmp_path / "dist"
        assets_dir = dist_dir / "assets"
        assets_dir.mkdir(parents=True)
        (dist_dir / "index.html").write_text("<html><body>ok</body></html>", encoding="utf-8")
        (assets_dir / "app.js").write_text("console.log('frontend');", encoding="utf-8")
        monkeypatch.setattr(server, "_FRONTEND_DIST_DIR", dist_dir)

        resp = client.get("/app/assets/app.js")

        assert resp.status_code == 200
        assert "frontend" in resp.get_data(as_text=True)

    def test_frontend_app_returns_helpful_404_without_build(self, client, tmp_path, monkeypatch):
        import server

        monkeypatch.setattr(server, "_FRONTEND_DIST_DIR", tmp_path / "missing-dist")

        resp = client.get("/app")

        assert resp.status_code == 404
        assert "Frontend bundle not found" in resp.get_data(as_text=True)