"""Rocket Builder presets (fitgen/rocket.py) and the motor-thread coupons
(fitgen/thread.py)."""

from __future__ import annotations

import pytest
from fitgen import GeometryError, layout
from fitgen.geom import as_shape, box, meshes, overlap_volume, solids_of
from fitgen.rocket import RocketParams, build, dims, motors, params


def test_dims_follow_rocket_builder():
    # rocketgen compute_derived: bay = motor + 0.4, OD = bay + 2 wall (+ 2 offset),
    # body shoulder max(0.75 OD - 4, 10), nose 70% of it (min 7).
    assert list(motors()) == ["M13", "M18", "M24", "M24L", "M29"]
    d = dims("M18")
    assert (d["bay_id"], d["body_od"], d["body_id"], d["lengths"]) == (18.4, 21.4, 18.4, {"body": 12.0, "nose": 8.4})
    assert d["thread"]["pitch"] == 2.5 and dims("M24")["thread"]["pitch"] == 3.0
    assert dims("M13")["lengths"] == {"body": 10.0, "nose": 7.0}  # the minimums
    d = dims("M24", wall=2.0, offset=5)
    assert (d["body_od"], d["body_id"], d["lengths"]["body"]) == (38.4, 34.4, 24.8)
    p = params("M18", joints=("nose", "body"))
    assert (p.shape, p.sizes, p.lengths, p.wall, p.seat) == ("tube", (18.4,), (12.0, 8.4), 1.5, "countersink")


@pytest.mark.parametrize("kw, msg", [
    (dict(motor="M99"), "Unknown motor"),
    (dict(wall=4.0), "between 0.8 and 3"),
    (dict(joints=(), thread=False), "Pick something"),
    (dict(joints=(), thread_clearances=(0.2, 0.2001)), "must not repeat"),
    (dict(joints=(), thread_clearances=(1.5,)), "out of range"),
])
def test_bad_rocket_parameters_are_explained(kw, msg):
    with pytest.raises(GeometryError, match=msg):
        build(RocketParams(**kw))


_sets: dict = {}


def thread_set(motor):
    if motor not in _sets:
        _sets[motor] = build(RocketParams(motor=motor, joints=("body",), clearances=(0.15,),
                                          thread_clearances=(0.15, 0.3) if motor == "M13" else (0.25,)))[0]
    return _sets[motor]


def _slice(s):
    # A thin slab through the axis. OpenCascade's intersection of two whole
    # threaded solids can silently come back empty (seen with the M24 boss and
    # cap); on slices it is reliable.
    return as_shape(s.intersect(box(-0.5, 0.5, -60, 60, -1, 60)))


@pytest.mark.parametrize("motor", ["M13", "M24"])
def test_thread_coupons(motor):
    items = thread_set(motor)
    names = [c.name for c in items]
    tag = dims(motor)["body_id"]
    assert names[:2] == [f"D{tag:g}_socket", f"D{tag:g}_L{dims(motor)['lengths']['body']:g}_C15"]
    assert names[2] == f"{motor}_boss" and all(n.startswith(f"{motor}_T") for n in names[3:])
    boss = items[2].print_solid
    for c in items:
        for s in [c.print_solid] + ([c.seated] if c.seated else []):
            assert len(solids_of(s)) == 1 and s.is_valid and meshes(s), c.name
        assert c.print_solid.bounding_box().min.Z == pytest.approx(0, abs=1e-6), c.name
    a = _slice(boss)
    for c in items[3:]:
        assert c.socket == f"{motor}_boss" and c.label == [f"T{c.name.split('_T')[1]}"]
        b = _slice(c.seated)
        assert overlap_volume(a, b) < 1e-3, c.name  # seated: clear all round
        assert overlap_volume(a, b.translate((0, c.clearance - 0.03, 0))) < 1e-3, c.name
        assert overlap_volume(a, b.translate((0, c.clearance + 0.05, 0))) > 1e-2, c.name
        assert overlap_volume(a, b.translate((0, 0, -1.0))) > 1e-2, c.name  # thread flanks engage


def test_default_rocket_set_fits_the_plate():
    items = thread_set("M13")
    assert layout(items, 256.0).fits
