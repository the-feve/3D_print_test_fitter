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
    assert set(o["shapes"]) == {"round", "square", "pentagon", "hexagon", "octagon", "tube"}


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
    s = client.get(f"/api/builds/{bid}/step.zip")
    assert 'filename="fit_test_round_step.zip"' in s.headers["content-disposition"]
    zs = zipfile.ZipFile(io.BytesIO(s.content))
    assert sorted(zs.namelist()) == ["D8_L6_C10.step", "D8_L6_C20.step", "D8_socket.step", "fit_test.json"]
    assert zs.read("D8_socket.step").startswith(b"ISO-10303-21;")


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
    # Import map addresses must start with ./ ../ or / ; a bare "static/..." is
    # ignored, three.js never loads and Build falls back to a plain form submit.
    import json, re
    imports = json.loads(re.search(r'<script type="importmap">(.*?)</script>', page, re.S).group(1))["imports"]
    assert imports and all(v.startswith("./") for v in imports.values()), imports
    assert c.get("/fit/static/vendor/three/build/three.module.js").status_code == 200
    assert "shapes" in c.get("/fit/api/options").json()
    # Brand fonts and icons (relative URLs; CSS url() resolves against the page).
    assert "url(/static/" not in page and 'href="/static/' not in page
    for path in ["static/fonts/inter.woff2", "static/fonts/space-grotesk.woff2", "static/favicon.svg",
                 "static/apple-touch-icon.png"]:
        assert path in page and c.get(f"/fit/{path}").status_code == 200, path
    assert 'name="robots"' not in page  # public and linked since 2026-10-18


def test_new_builds_are_rate_limited(monkeypatch):
    import server.app as srv
    monkeypatch.setattr(srv, "BUILDS_PER_10_MIN", 0)
    monkeypatch.setattr(srv, "_hits", srv.defaultdict(srv.deque))
    r = client.post("/api/build", json={**REQ, "clearances": [0.3]})
    assert r.status_code == 429 and "Too many" in r.json()["detail"]


def test_options_list_polygons_and_rocket_motors():
    o = client.get("/api/options").json()
    assert {"pentagon", "hexagon", "octagon"} <= set(o["shapes"]) and o["shapes"]["hexagon"]["sides"] == 6
    assert o["rocket"]["motors"][:2] == ["M13", "M18"] and o["rocket"]["dims"]["M18"]["body_id"] == 18.4
    d = client.get("/api/rocket", params={"motor": "M24", "wall": 2, "offset": 5}).json()
    assert d["body_id"] == 34.4 and d["lengths"]["body"] == 24.8
    assert "Unknown motor" in client.get("/api/rocket", params={"motor": "X"}).json()["error"]


def test_rocket_mode_build():
    r = client.post("/api/build", json={"mode": "rocket", "motor": "M13", "joints": ["body", "nose"],
                                        "clearances": [0.15], "thread_clearances": [0.25]})
    assert r.status_code == 200, r.text
    rep = r.json()["report"]
    assert rep["mode"] == "rocket" and rep["rockets"][0]["body_id"] == 13.4
    assert [c["name"] for c in rep["coupons"]] == ["D13.4_socket", "D13.4_L10_C15", "D13.4_L7_C15", "M13_boss", "M13_T25"]
    z = client.get(f"/api/builds/{r.json()['id']}/stl.zip")
    assert 'filename="fit_test_rocket_M13_stl.zip"' in z.headers["content-disposition"]


def test_general_polygon_build_and_messages():
    r = client.post("/api/build", json={"shape": "hexagon", "sizes": [10], "clearances": [0.15], "lengths": [6]})
    assert r.status_code == 200 and [c["name"] for c in r.json()["report"]["coupons"]] == ["H10_socket", "H10_L6_C15"]
    r = client.post("/api/build", json={"shape": "hexagon", "sizes": [10], "corner_radius": 4})
    assert r.status_code == 422 and "quarter" in r.json()["error"]
    r = client.post("/api/build", json={"mode": "rocket", "joints": [], "thread": False})
    assert r.status_code == 422 and "Pick something" in r.json()["error"]


def test_plate_combines_one_motor_builds():
    base = {"mode": "rocket", "joints": ["body"], "clearances": [0.15], "thread_clearances": [0.25]}
    a = client.post("/api/build", json={**base, "motors": ["M13"]}).json()["id"]
    b = client.post("/api/build", json={**base, "motors": ["M18"]}).json()["id"]
    r = client.post("/api/plate", json={"ids": [a, b]})
    assert r.status_code == 200, r.text
    rep = r.json()["report"]
    assert rep["params"]["motors"] == ["M13", "M18"] and [d["motor"] for d in rep["rockets"]] == ["M13", "M18"]
    assert [c["name"] for c in rep["coupons"]][::4] == ["D13.4_socket", "D18.4_socket"] and rep["count"] == 8
    pid = r.json()["id"]
    assert client.get(f"/api/builds/{pid}/plate.glb").content[:4] == b"glTF"
    z = client.get(f"/api/builds/{pid}/stl.zip")
    assert 'fit_test_rocket_M13-M18_stl.zip' in z.headers["content-disposition"]
    assert client.post("/api/plate", json={"ids": [a, a]}).json()["error"].startswith("Those sets share")
    assert client.post("/api/plate", json={"ids": ["nope"]}).status_code == 404
    g = client.post("/api/build", json={"shape": "round", "sizes": [8], "clearances": [0.1], "lengths": [6]}).json()["id"]
    assert "Only Rocket Builder" in client.post("/api/plate", json={"ids": [a, g]}).json()["error"]


def test_cached_builds_and_plates_answer_while_the_lock_is_held():
    import server.app as srv
    base = {"mode": "rocket", "joints": ["body"], "clearances": [0.2], "thread_clearances": [0.25]}
    a = client.post("/api/build", json={**base, "motors": ["M13"]}).json()["id"]
    b = client.post("/api/build", json={**base, "motors": ["M18"]}).json()["id"]
    old = srv.BUILD_WAIT_S
    srv._lock.acquire()  # another build is running
    try:
        srv.BUILD_WAIT_S = 0.5
        assert client.post("/api/build", json={**base, "motors": ["M13"]}).json()["id"] == a
        assert client.post("/api/plate", json={"ids": [a, b]}).status_code == 200
        assert client.post("/api/build", json={**base, "motors": ["M24"]}).status_code == 503  # a new one waits
    finally:
        srv.BUILD_WAIT_S = old
        srv._lock.release()
