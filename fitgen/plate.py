"""Lay coupons out on the build plate and write the 3MF and STLs."""

from __future__ import annotations

import io
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from build123d import Mesher, export_stl

from .coupons import Coupon

GAP = 5.0  # between coupons
MARGIN = 8.0  # kept clear at the plate edge


@dataclass
class Placed:
    coupon: Coupon
    x: float  # the coupon's axis on the plate (its print solid is translated by (x, y, 0))
    y: float

    @property
    def solid(self):
        return self.coupon.print_solid.translate((self.x, self.y, 0))


@dataclass
class Plate:
    side: float
    placed: list[Placed]
    width: float  # extent of the layout, mm
    depth: float

    @property
    def fits(self) -> bool:
        return self.width <= self.side - 2 * MARGIN + 1e-6 and self.depth <= self.side - 2 * MARGIN + 1e-6


def layout(items: list[Coupon], side: float = 256.0, gap: float = GAP) -> Plate:
    """Rows from the front of the plate (low Y), in order, each as wide as
    fits inside the margin; the whole block centred on the plate. A set that
    is too deep runs off the back edge and Plate.fits is False."""
    usable = side - 2 * MARGIN
    rows: list[list[tuple[Coupon, float, float]]] = [[]]  # (coupon, x of bbox min, row-relative)
    x = 0.0
    for c in items:
        bb = c.print_solid.bounding_box()
        if rows[-1] and x + bb.size.X > usable:
            rows.append([])
            x = 0.0
        rows[-1].append((c, x, bb))
        x += bb.size.X + gap
    placed, y, width = [], 0.0, 0.0
    for row in rows:
        depth = max(bb.size.Y for _, _, bb in row)
        for c, x0, bb in row:
            # centre each coupon in the row's depth
            placed.append(Placed(c, x0 - bb.min.X, y + (depth - bb.size.Y) / 2 - bb.min.Y))
        width = max(width, row[-1][1] + row[-1][2].size.X)
        y += depth + gap
    depth_all = y - gap
    ox = (side - width) / 2
    oy = (side - depth_all) / 2 if depth_all <= usable else MARGIN
    for p in placed:
        p.x += ox
        p.y += oy
    return Plate(side, placed, width, depth_all)


def write_3mf(plate: Plate, path: Path) -> Path:
    """One named object per coupon, in its plate position (Bambu Studio keeps them as separate objects)."""
    mesher = Mesher()
    for p in plate.placed:
        s = p.solid
        s.label = p.coupon.name
        mesher.add_shape(s, linear_deflection=0.01, angular_deflection=0.1)
    path.parent.mkdir(parents=True, exist_ok=True)
    mesher.write(str(path))
    return path


def stl_bytes(coupon: Coupon) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "c.stl"
        export_stl(coupon.print_solid, p, tolerance=0.01, angular_tolerance=0.1)
        return p.read_bytes()


def write_stls(items: list[Coupon], folder: Path) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    out = []
    for c in items:
        p = folder / f"{c.name}.stl"
        p.write_bytes(stl_bytes(c))
        out.append(p)
    return out


def stl_zip(items: list[Coupon], extra: dict[str, bytes] | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for c in items:
            z.writestr(f"{c.name}.stl", stl_bytes(c))
        for name, data in (extra or {}).items():
            z.writestr(name, data)
    return buf.getvalue()
