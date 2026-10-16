"""API: build, previews and downloads."""

import io
import zipfile

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from server.app import app  # noqa: E402

client = TestClient(app)
REQ = {"shape": "round", "sizes": [8], "clearances": [0.1, 0.2], "lengths": [6]}


def test_page_and_options():
    assert "Fit Test Builder" in client.get("/").text
    o = client.get("/api/options").json()
    assert set(o["shapes"]) == {"round", "square", "tube"}


def test_build_previews_and_downloads():
    r = client.post("/api/build", json=REQ)
    assert r.status_code == 200, r.text
    body = r.json()
    rep = body["report"]
    assert rep["count"] == 3 and rep["pegs"] == 2 and rep["plate"]["fits"]
    assert [c["name"] for c in rep["coupons"]] == ["D8_socket", "D8_L6_C10", "D8_L6_C20"]
    bid = body["id"]
    assert client.post("/api/build", json=REQ).json()["id"] == bid  # cached
    for f in ("plate.glb", "assembled.glb"):
        g = client.get(f"/api/builds/{bid}/{f}")
        assert g.status_code == 200 and g.content[:4] == b"glTF"
    m = client.get(f"/api/builds/{bid}/fit_test.3mf")
    assert m.status_code == 200 and zipfile.ZipFile(io.BytesIO(m.content)).read("3D/3dmodel.model").count(b'name="D8_') == 3
    z = zipfile.ZipFile(io.BytesIO(client.get(f"/api/builds/{bid}/stl.zip").content))
    assert sorted(z.namelist()) == ["D8_L6_C10.stl", "D8_L6_C20.stl", "D8_socket.stl", "fit_test.json"]


def test_bad_request_is_explained():
    r = client.post("/api/build", json={**REQ, "shape": "tube", "sizes": [5]})
    assert r.status_code == 422 and "too small" in r.json()["error"]
    assert client.get("/api/builds/nope/plate.glb").status_code == 404


def test_page_works_under_a_prefix():
    # Rocket Builder's Fly app mounts this at /fit/, so the page's URLs are relative.
    from fastapi import FastAPI
    host = FastAPI()
    host.mount("/fit", app)
    c = TestClient(host)
    page = c.get("/fit/").text
    assert "'/api/" not in page and '"/static/' not in page and "`/api/" not in page
    assert c.get("/fit/static/vendor/three/build/three.module.js").status_code == 200
    assert "shapes" in c.get("/fit/api/options").json()


def test_new_builds_are_rate_limited(monkeypatch):
    import server.app as srv
    monkeypatch.setattr(srv, "BUILDS_PER_10_MIN", 0)
    monkeypatch.setattr(srv, "_hits", srv.defaultdict(srv.deque))
    r = client.post("/api/build", json={**REQ, "clearances": [0.3]})
    assert r.status_code == 429 and "Too many" in r.json()["detail"]
