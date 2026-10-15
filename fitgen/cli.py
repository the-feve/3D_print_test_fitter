"""Command line: write a fit-test plate (3MF) and one STL per coupon.

    python -m fitgen --shape round --sizes 10 13 --lengths 7 10 --out out
    python -m fitgen --shape tube --sizes 18.4 --range 0.10 0.05 5
    python -m fitgen --shape square --clearances 0.1 0.15 0.2 --corner-radius 1.5
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .coupons import DEFAULT_CLEARANCES, SHAPES, FitParams, build
from .geom import GeometryError
from .plate import layout, write_3mf, write_stls


def clearance_range(start: float, step: float, count: int) -> tuple[float, ...]:
    return tuple(round(start + i * step, 4) for i in range(int(count)))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="fitgen", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--shape", choices=SHAPES, default="round")
    ap.add_argument("--sizes", nargs="+", type=float, help="nominal hole diameter / square side / tube bore, mm")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--clearances", nargs="+", type=float, help="radial (per side) clearances, mm")
    g.add_argument("--range", nargs=3, type=float, metavar=("START", "STEP", "COUNT"), help="radial clearances as a range")
    ap.add_argument("--lengths", nargs="+", type=float, help="engagement lengths, mm")
    ap.add_argument("--wall", type=float)
    ap.add_argument("--chamfer", type=float, default=0.5, help="45-degree chamfer on the peg's insertion end; 0 = none")
    ap.add_argument("--seat", choices=("countersink", "flat"), default="countersink", help="tube only")
    ap.add_argument("--corner-radius", type=float, default=1.0, help="square only: socket inside corner radius")
    ap.add_argument("--orientation", choices=("flat", "functional"), default="flat")
    ap.add_argument("--no-vent", action="store_true")
    ap.add_argument("--plate", type=float, default=256.0)
    ap.add_argument("--out", type=Path, default=Path("out"))
    a = ap.parse_args(argv)
    kw = dict(wall=a.wall, chamfer=a.chamfer, seat=a.seat, corner_radius=a.corner_radius,
              orientation=a.orientation, vent=not a.no_vent, plate=a.plate)
    if a.sizes:
        kw["sizes"] = tuple(a.sizes)
    if a.lengths:
        kw["lengths"] = tuple(a.lengths)
    kw["clearances"] = (tuple(a.clearances) if a.clearances else clearance_range(*a.range) if a.range
                        else DEFAULT_CLEARANCES)
    try:
        items, notes = build(FitParams.for_shape(a.shape, **kw))
    except GeometryError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    plate = layout(items, a.plate)
    for n in notes:
        print(f"note: {n}")
    if not plate.fits:
        print(f"warning: the layout is {plate.width:.0f} x {plate.depth:.0f} mm and doesn't fit a {a.plate:g} mm plate",
              file=sys.stderr)
    for p in write_stls(items, a.out / "stl"):
        print(p)
    print(write_3mf(plate, a.out / f"fit_test_{a.shape}.3mf"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
