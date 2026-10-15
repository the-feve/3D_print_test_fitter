"""Coupon tests. OpenCascade's is_valid alone isn't enough: every coupon must
also tessellate, seat without overlap, and sit on the plate."""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile

import pytest
from fitgen import FitParams, GeometryError, build, layout, write_3mf
from fitgen import labels
from fitgen.coupons import code
from fitgen.geom import as_shape, box, meshes, overlap_volume, revolve, solids_of

CASES = {
    "round": FitParams.for_shape("round", sizes=(8.0, 13.0), clearances=(0.05,), lengths=(7.0, 10.0)),
    "square": FitParams.for_shape("square", sizes=(10.0,), clearances=(0.1, 1.2), lengths=(8.0,)),
    "tube": FitParams.for_shape("tube", sizes=(13.4,), clearances=(0.05, 0.3), lengths=(7.0,)),
    "tube_flat": FitParams.for_shape("tube", sizes=(18.4,), clearances=(0.15,), lengths=(12.0,), seat="flat",
                                     orientation="functional", chamfer=0.0),
}
_built: dict = {}


def coupons(case):
    if case not in _built:
        _built[case] = build(CASES[case])[0]
    return _built[case]


@pytest.mark.parametrize("case", CASES)
def test_every_coupon_is_one_sound_solid(case):
    items = coupons(case)
    p = CASES[case]
    assert len(items) == len(p.sizes) * (1 + len(p.lengths) * len(p.clearances))
    for c in items:
        for s in [c.print_solid] + ([c.seated] if c.seated else []):
            assert len(solids_of(s)) == 1 and s.is_valid and meshes(s), c.name
    assert len({c.name for c in items}) == len(items)


@pytest.mark.parametrize("case", CASES)
def test_pegs_seat_without_overlap(case):
    """Seated, a peg doesn't touch its socket; 0.05 mm further in it does (it
    seats on the stop / countersink). Lifted 1 mm off the seat, it can move
    sideways by just under its clearance, and not by just over it."""
    items = coupons(case)
    sockets = {c.name: c.print_solid for c in items if c.role == "socket"}
    for c in items:
        if c.role != "peg":
            continue
        sock, peg = sockets[c.socket], c.seated
        assert overlap_volume(sock, peg) < 1e-3, c.name
        assert overlap_volume(sock, peg.translate((0, 0, -0.05))) > 0.3, c.name
        lifted = peg.translate((0, 0, 1.0))
        assert overlap_volume(sock, lifted.translate((c.clearance - 0.02, 0, 0))) < 1e-3, c.name
        assert overlap_volume(sock, lifted.translate((c.clearance + 0.03, 0, 0))) > 1e-3, c.name


@pytest.mark.parametrize("case", CASES)
def test_layout_on_plate(case):
    items = coupons(case)
    plate = layout(items, CASES[case].plate)
    assert plate.fits
    boxes = []
    for pl in plate.placed:
        bb = pl.solid.bounding_box()
        assert bb.min.Z == pytest.approx(0, abs=1e-6), pl.coupon.name
        assert 0 <= bb.min.X and bb.max.X <= plate.side and 0 <= bb.min.Y and bb.max.Y <= plate.side, pl.coupon.name
        boxes.append(bb)
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            apart = a.max.X <= b.min.X or b.max.X <= a.min.X or a.max.Y <= b.min.Y or b.max.Y <= a.min.Y
            assert apart


def test_3mf_reads_back(tmp_path):
    """One named object per coupon, every mesh on the bed and inside the plate.
    (Parses the 3MF's XML: Mesher().read takes most of a minute.)"""
    items = coupons("round")
    plate = layout(items)
    path = write_3mf(plate, tmp_path / "plate.3mf")
    ns = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("3D/3dmodel.model"))
    objs = root.findall(".//m:resources/m:object", ns)
    named = {o.get("id"): o.get("name") for o in objs if o.get("name")}
    assert sorted(named.values()) == sorted(c.name for c in items)
    items_built = root.findall(".//m:build/m:item", ns)
    assert len(items_built) == len(items)
    for o in objs:
        vs = o.findall(".//m:vertices/m:vertex", ns)
        if not vs:
            continue
        xs, ys, zs = ([float(v.get(k)) for v in vs] for k in "xyz")
        assert min(zs) == pytest.approx(0, abs=1e-4)
        assert 0 <= min(xs) and max(xs) <= plate.side and 0 <= min(ys) and max(ys) <= plate.side


def test_flat_orientation_puts_label_face_on_bed():
    """Printed flat, the peg's head / closed end is on the bed and the label
    is cut into it: the bottom 0.6 mm slab has less area than a solid one."""
    for case in ("round", "square", "tube"):
        peg = next(c for c in coupons(case) if c.role == "peg")
        s = peg.print_solid
        bb = s.bounding_box()
        assert bb.min.Z == pytest.approx(0, abs=1e-6)
        slab = as_shape(s.intersect(box(bb.min.X - 1, bb.max.X + 1, bb.min.Y - 1, bb.max.Y + 1, 0, 0.3)))
        above = as_shape(s.intersect(box(bb.min.X - 1, bb.max.X + 1, bb.min.Y - 1, bb.max.Y + 1, 0.9, 1.2)))
        assert slab.volume < above.volume - 0.5, case  # text removed from the bed face


def _glyph_order(label_solid):
    """Glyph solids of a recessed label, ordered by x."""
    return sorted(solids_of(label_solid), key=lambda s: s.center().X)


def test_labels_read_from_below():
    """A label cut into a bed face is mirrored so it reads from below: seen
    from underneath, the first glyph (C) is on the viewer's left, which is +X."""
    t = labels.cutter(["C1"], labels.SIZE, 0.0, up=False)
    glyphs = _glyph_order(t)
    c_vol = labels.cutter(["C"], labels.SIZE, 0.0, up=False).volume
    assert glyphs[-1].volume == pytest.approx(c_vol, rel=1e-3)
    # and a peg printed flat carries its label that way round
    peg = next(c for c in build(FitParams(sizes=(10.0,), clearances=(0.15,), lengths=(5.0,)))[0] if c.role == "peg")
    rh = peg.print_solid.bounding_box().size.X / 2
    removed = revolve([(0, 0), (rh - 0.2, 0), (rh - 0.2, 0.5), (0, 0.5)]).cut(peg.print_solid)
    glyphs = [g for g in _glyph_order(removed) if g.volume > 0.01]
    assert len(glyphs) == 3  # C, 1, 5
    c_glyph = c_vol * 0.5 / (labels.TEXT_H + 0.01)
    assert glyphs[-1].volume == pytest.approx(c_glyph, rel=0.02)


def test_clearance_codes():
    assert code(0.05) == "05" and code(0.15) == "15" and code(0.175) == "17.5" and code(1.0) == "100"


@pytest.mark.parametrize("kw, msg", [
    (dict(shape="tube", sizes=(5.0,)), "too small"),
    (dict(clearances=(0.15, 0.1504)), "differ"),
    (dict(shape="hex"), "Unknown shape"),
    (dict(sizes=(10.0,), clearances=tuple(0.01 * i for i in range(20)), lengths=(5.0, 7.0, 10.0, 12.0)), "60 or fewer"),
    (dict(lengths=(1.0,)), "out of range"),
])
def test_bad_parameters_are_explained(kw, msg):
    with pytest.raises(GeometryError, match=msg):
        build(FitParams(**kw))


def test_big_set_reports_it_does_not_fit():
    items, _ = build(FitParams(sizes=(40.0, 45.0), clearances=(0.1, 0.2, 0.3), lengths=(5.0, 8.0)))
    assert not layout(items, 180.0).fits
