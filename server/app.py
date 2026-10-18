"""Fit Test Builder web server.

POST /api/build builds the coupons for a parameter set (cached by a hash of
the parameters plus fitgen's GENERATOR_VERSION, as Rocket Builder does) and
returns the plate report. The page then loads the GLB previews (the plate
layout, and every peg seated in a copy of its socket) and offers the 3MF and
the STL ZIP, which are written on first download.

    uvicorn server.app:app --reload        (from the repo root)
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from collections import OrderedDict, defaultdict, deque
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Literal

import numpy as np
import trimesh
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from fitgen import GENERATOR_VERSION, SHAPES, FitParams, GeometryError, build, layout, rocket, step_zip, stl_zip, write_3mf
from fitgen.coupons import CORNERED, DEFAULT_CLEARANCES, DEFAULT_LENGTHS, DEFAULT_SIZES, DEFAULT_WALL, SIDES, code
from fitgen.plate import MARGIN

STATIC = Path(__file__).parent / "static"
CACHE_SIZE = 16  # one-motor rocket sets are cached one by one and combined into plates; 1 GB machine
PRINTERS = {"Bambu Lab X1C / P1S / A1": 256, "Bambu Lab A1 mini": 180}
SOCKET_COLOR = (0.60, 0.63, 0.68)
# pegs graded by clearance, tight (blue) to loose (orange)
TIGHT, LOOSE = np.array((0.16, 0.42, 0.86)), np.array((0.96, 0.52, 0.12))

app = FastAPI(title="Fit Test Builder")
app.mount("/static", StaticFiles(directory=STATIC), name="static")

_builds: OrderedDict[str, dict] = OrderedDict()
_lock = threading.Lock()  # one OpenCascade build at a time
_plate_lock = threading.Lock()  # /api/plate: one combine at a time (no OpenCascade work)
# Hosted in Rocket Builder's Fly app, which swaps in its own lock so the two
# never build at once on the 1 GB machine. A visitor waits at most
# BUILD_WAIT_S for their turn, and each address gets a budget of new
# (uncached) builds, as on Rocket Builder.
BUILD_WAIT_S = float(os.environ.get("FITGEN_BUILD_WAIT_S", 60))
BUILDS_PER_10_MIN = int(os.environ.get("FITGEN_BUILDS_PER_10_MIN", 30))
_hits: defaultdict[str, deque] = defaultdict(deque)


def _client(request: Request) -> str:
    # Behind Cloudflare and Fly's proxy the socket address is the proxy's.
    h = request.headers
    return h.get("cf-connecting-ip") or h.get("fly-client-ip") or (request.client.host if request.client else "?")


def _rate_limit(request: Request) -> None:
    now, q = time.monotonic(), _hits[_client(request)]
    while q and now - q[0] > 600:
        q.popleft()
    if len(q) >= BUILDS_PER_10_MIN:
        raise HTTPException(429, "Too many builds from your address; wait a few minutes and try again.")
    q.append(now)


@contextmanager
def _turn():
    lock = _lock  # read at call time: the host app may have replaced it
    if not lock.acquire(timeout=BUILD_WAIT_S):
        raise HTTPException(503, "The builder is busy; try again in a minute.")
    try:
        yield
    finally:
        lock.release()


class BuildRequest(BaseModel):
    # "general": any shape; "rocket": Rocket Builder's joints and motor thread,
    # sized from the motor, wall and body OD offset (fitgen/rocket.py).
    mode: Literal["general", "rocket"] = "general"
    shape: Literal[SHAPES] = "round"
    sizes: list[float] = Field(default_factory=lambda: [10.0], max_length=6)
    clearances: list[float] = Field(default_factory=lambda: list(DEFAULT_CLEARANCES), max_length=20)
    lengths: list[float] = Field(default_factory=lambda: [10.0], max_length=5)
    wall: float | None = None
    chamfer: float = 0.5
    seat: Literal["countersink", "flat"] = "countersink"
    corner_radius: float = 1.0
    orientation: Literal["flat", "functional"] = "flat"
    vent: bool = True
    plate: float = 256.0
    # rocket mode
    motor: str = "M18"  # one motor (older requests); `motors` wins when given
    motors: list[str] = Field(default_factory=list, max_length=5)  # fitgen allows 2 per request (rocket.MAX_MOTORS)
    body_offset: float = 0.0
    joints: list[Literal["body", "nose"]] = Field(default_factory=lambda: ["body"], max_length=2)
    thread: bool = True
    thread_clearances: list[float] = Field(default_factory=lambda: list(rocket.DEFAULT_THREAD_CLEARANCES), max_length=12)

    def params(self) -> "FitParams | rocket.RocketParams":
        d = self.model_dump()
        for k in ("sizes", "clearances", "lengths", "thread_clearances"):
            d[k] = tuple(round(float(v), 4) for v in d[k])
        if self.mode == "rocket":
            return rocket.RocketParams(motors=tuple(self.motors or [self.motor]), wall=self.wall, offset=self.body_offset,
                                       joints=tuple(self.joints), clearances=d["clearances"], thread=self.thread,
                                       thread_clearances=d["thread_clearances"], chamfer=self.chamfer, seat=self.seat,
                                       orientation=self.orientation, plate=self.plate)
        for k in ("mode", "motor", "motors", "body_offset", "joints", "thread", "thread_clearances"):
            d.pop(k)
        return FitParams(**d)


def _build(p) -> tuple[list, list[str]]:
    return rocket.build(p) if isinstance(p, rocket.RocketParams) else build(p)


def _key(p: FitParams) -> str:
    return hashlib.sha256(json.dumps([GENERATOR_VERSION, p.to_dict()], sort_keys=True).encode()).hexdigest()[:16]


def _colors(items) -> dict[str, list[float]]:
    cs = sorted({c.clearance for c in items if c.role == "peg"})
    out = {}
    for c in items:
        if c.role == "socket":
            out[c.name] = list(SOCKET_COLOR)
        else:
            t = cs.index(c.clearance) / max(1, len(cs) - 1)
            out[c.name] = [round(float(v), 3) for v in TIGHT + (LOOSE - TIGHT) * t]
    return out


def _arrays(c, which: str) -> tuple[np.ndarray, np.ndarray]:
    """A coupon's preview mesh (vertices, triangles), tessellated once and
    kept on the coupon: "print" (as printed, at the origin) or "seated"."""
    cache = c.__dict__.setdefault("_meshes", {})
    if which not in cache:
        solid = c.print_solid if which == "print" else c.seated
        verts, tris = solid.tessellate(0.02, 0.2)
        cache[which] = (np.array([(v.X, v.Y, v.Z) for v in verts]), np.array(tris))
    return cache[which]


def _mesh(c, which: str, x: float, y: float) -> trimesh.Trimesh:
    v, t = _arrays(c, which)
    return trimesh.Trimesh(v + (x, y, 0.0), t, process=False)


def _glbs(plate) -> tuple[bytes, bytes]:
    """The plate layout, and each peg seated in a copy of its socket at the
    peg's place. Meshes come from the coupons' caches, so laying out a plate
    of sets already built (/api/plate) needs no OpenCascade work."""
    flat, assembled = trimesh.Scene(), trimesh.Scene()
    sockets = {p.coupon.name: p.coupon for p in plate.placed if p.coupon.role == "socket"}
    for p in plate.placed:
        c = p.coupon
        flat.add_geometry(_mesh(c, "print", p.x, p.y), node_name=c.name, geom_name=c.name)
        if c.role == "peg":
            assembled.add_geometry(_mesh(c, "seated", p.x, p.y), node_name=c.name, geom_name=c.name)
            assembled.add_geometry(_mesh(sockets[c.socket], "print", p.x, p.y),
                                   node_name=f"{c.name}::socket", geom_name=f"{c.name}::socket")
    return flat.export(file_type="glb"), assembled.export(file_type="glb")


def _report(p, plate, notes: list[str]) -> dict:
    colors = _colors([q.coupon for q in plate.placed])
    rows = []
    for q in plate.placed:
        c, bb = q.coupon, q.solid.bounding_box()
        rows.append({
            "name": c.name, "role": c.role, "size": c.size, "clearance": c.clearance, "length": c.length,
            "code": code(c.clearance) if c.clearance is not None else None, "socket": c.socket,
            "label": c.label, "x": round(q.x, 3), "y": round(q.y, 3), "color": colors[c.name],
            "volume_mm3": round(c.volume, 1), "grams": round(c.grams, 2),
            "width": round(bb.size.X, 1), "depth": round(bb.size.Y, 1), "height": round(bb.size.Z, 1),
        })
    warnings = list(notes)
    if not plate.fits:
        warnings.append(f"The layout is {plate.width:.0f} × {plate.depth:.0f} mm and doesn't fit inside a "
                        f"{p.plate:g} mm plate with a {MARGIN:g} mm margin. Use fewer clearances, lengths or sizes, "
                        "or a bigger plate.")
    extra = {"rockets": [rocket.dims(m, p.wall, p.offset) for m in p.motors]} if isinstance(p, rocket.RocketParams) else {}
    return {
        "generator_version": GENERATOR_VERSION,
        "mode": "rocket" if extra else "general",
        **extra,
        "params": p.to_dict(),
        "coupons": rows,
        "count": len(rows),
        "pegs": sum(r["role"] == "peg" for r in rows),
        "grams": round(sum(r["grams"] for r in rows), 1),
        "plate": {"side": p.plate, "width": round(plate.width, 1), "depth": round(plate.depth, 1),
                  "fits": plate.fits, "margin": MARGIN},
        "warnings": warnings,
    }


def _get(build_id: str) -> dict:
    b = _builds.get(build_id)
    if b is None:
        raise HTTPException(404, "That build has expired; press Build again.")
    return b


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/options")
def options():
    return {
        "generator_version": GENERATOR_VERSION,
        "shapes": {s: {"sizes": list(DEFAULT_SIZES[s]), "lengths": list(DEFAULT_LENGTHS[s]), "wall": DEFAULT_WALL[s],
                       "cornered": s in CORNERED, "sides": SIDES.get(s)}
                   for s in SHAPES},
        "rocket": {"motors": list(rocket.motors()), "default_motor": "M18", "joints": list(rocket.JOINTS),
                   "thread_clearances": list(rocket.DEFAULT_THREAD_CLEARANCES),
                   "dims": {m: rocket.dims(m) for m in rocket.motors()}},
        "clearances": list(DEFAULT_CLEARANCES),
        "printers": PRINTERS,
    }


@app.get("/api/rocket")
def rocket_dims(motor: str = "M18", wall: float | None = None, offset: float = 0.0):
    """The joint and thread numbers for a rocket, for the page's hints (no geometry)."""
    try:
        return rocket.dims(motor, wall, offset)
    except GeometryError as e:
        return JSONResponse({"error": str(e)}, status_code=422)


@app.post("/api/build")
def build_set(req: BuildRequest, request: Request):
    try:
        p = req.params()
    except TypeError as e:
        raise HTTPException(422, str(e))
    key = _key(p)
    if key in _builds:  # cached: answer straight away, even while another build holds the lock
        _builds.move_to_end(key)
        return {"id": key, "report": _builds[key]["report"]}
    _rate_limit(request)
    with _turn():
        if key not in _builds:
            try:
                items, notes = _build(p)
            except GeometryError as e:
                return JSONResponse({"error": str(e)}, status_code=422)
            plate = layout(items, p.plate)
            flat, assembled = _glbs(plate)
            _store(key, p, items, notes, plate)
        _builds.move_to_end(key)
    return {"id": key, "report": _builds[key]["report"]}


def _store(key: str, p, items, notes: list[str], plate) -> None:
    flat, assembled = _glbs(plate)
    _builds[key] = {"p": p, "notes": notes, "plate": plate, "items": items, "report": _report(p, plate, notes),
                    "plate_glb": flat, "assembled_glb": assembled, "3mf": None, "zip": None, "step": None}
    while len(_builds) > CACHE_SIZE:
        _builds.popitem(last=False)


class PlateRequest(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=6)
    plate: float = Field(256.0, ge=60, le=500)


@app.post("/api/plate")
def combine(req: PlateRequest):
    """Several rocket sets built one motor at a time (each a cached build), laid
    out together on one plate, so no single request has to build them all.
    Answers like /api/build; the downloads work on the returned id."""
    key = "plate-" + hashlib.sha256(json.dumps([GENERATOR_VERSION, req.ids, req.plate]).encode()).hexdigest()[:16]
    # No build lock: the sets are built, and their preview meshes are cached
    # on the coupons (_arrays), so this is layout and GLB export only.
    with _plate_lock:
        if key not in _builds:
            parts = [_get(i) for i in req.ids]
            ps = [b["p"] for b in parts]
            if not all(isinstance(q, rocket.RocketParams) for q in ps):
                return JSONResponse({"error": "Only Rocket Builder sets can be combined on a plate."}, status_code=422)
            items = [c for b in parts for c in b["items"]]
            names = [c.name for c in items]
            dup = sorted({n for n in names if names.count(n) > 1})
            if dup:
                return JSONResponse({"error": f"Those sets share coupons ({', '.join(dup[:3])}); add each motor size once."},
                                    status_code=422)
            caps = sum(c.role == "peg" and c.socket and c.socket.endswith("_boss") for c in items)
            pegs = sum(c.role == "peg" for c in items)
            if caps > rocket.MAX_CAPS or pegs > rocket.MAX_PEGS:
                return JSONResponse({"error": f"That plate would have {pegs} pegs and caps ({caps} caps); keep it to "
                                              f"{rocket.MAX_PEGS} and {rocket.MAX_CAPS} (fewer sizes or clearances)."},
                                    status_code=422)
            motors = tuple(m for q in ps for m in q.motors)
            p = replace(ps[0], motors=motors, plate=req.plate)
            notes = list(dict.fromkeys(n for b in parts for n in b["notes"]))
            _store(key, p, items, notes, layout(items, req.plate))
        _builds.move_to_end(key)
    return {"id": key, "report": _builds[key]["report"]}


@app.get("/api/builds/{build_id}/plate.glb")
def plate_glb(build_id: str):
    return Response(_get(build_id)["plate_glb"], media_type="model/gltf-binary")


@app.get("/api/builds/{build_id}/assembled.glb")
def assembled_glb(build_id: str):
    return Response(_get(build_id)["assembled_glb"], media_type="model/gltf-binary")


def _name(b: dict) -> str:
    pr = b["report"]["params"]
    return f"fit_test_rocket_{'-'.join(pr['motors'])}" if b["report"]["mode"] == "rocket" else f"fit_test_{pr['shape']}"


@app.get("/api/builds/{build_id}/fit_test.3mf")
def download_3mf(build_id: str):
    b = _get(build_id)
    with _turn():
        if b["3mf"] is None:
            import tempfile
            with tempfile.TemporaryDirectory() as tmp:
                b["3mf"] = write_3mf(b["plate"], Path(tmp) / "plate.3mf").read_bytes()
    return Response(b["3mf"], media_type="model/3mf",
                    headers={"Content-Disposition": f'attachment; filename="{_name(b)}.3mf"'})


@app.get("/api/builds/{build_id}/stl.zip")
def download_zip(build_id: str):
    b = _get(build_id)
    with _turn():
        if b["zip"] is None:
            extra = {"fit_test.json": json.dumps(b["report"], indent=2).encode()}
            b["zip"] = stl_zip(b["items"], extra)
    return Response(b["zip"], media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{_name(b)}_stl.zip"'})



@app.get("/api/builds/{build_id}/step.zip")
def download_step(build_id: str):
    """One STEP per coupon, as printed: for editing or slicing from CAD."""
    b = _get(build_id)
    with _turn():
        if b.get("step") is None:
            b["step"] = step_zip(b["items"], {"fit_test.json": json.dumps(b["report"], indent=2).encode()})
    return Response(b["step"], media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{_name(b)}_step.zip"'})