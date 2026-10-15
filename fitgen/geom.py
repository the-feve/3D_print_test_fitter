"""Small build123d helpers (ported from rocket-builder-web geometry/rocketgen/geom.py).

Profiles are lists of (r, z) points in the XZ half-plane (x = radius, y = 0),
revolved about world Z.
"""

from __future__ import annotations

from build123d import Axis, Face, Solid, Vector, Wire


class GeometryError(Exception):
    """A coupon set that can't be built; the message is meant for the user."""


def xz_face(pts, y: float = 0.0) -> Face:
    """Closed polygon in the plane y = const, from (x, z) points."""
    return Face(Wire.make_polygon([Vector(x, y, z) for x, z in pts], close=True))


def revolve(pts) -> Solid:
    """Closed (r, z) profile revolved 360 degrees about Z."""
    return Solid.revolve(xz_face(pts), 360, Axis.Z)


def box(x0: float, x1: float, y0: float, y1: float, z0: float, z1: float) -> Solid:
    return Solid.make_box(x1 - x0, y1 - y0, z1 - z0).translate((x0, y0, z0))


def solids_of(shape) -> list[Solid]:
    return list(shape.solids()) if hasattr(shape, "solids") else [shape]


def one_solid(shape, what: str) -> Solid:
    """Every coupon must be one body; check it."""
    s = solids_of(shape)
    if len(s) != 1:
        raise GeometryError(f"{what}: expected 1 solid, got {len(s)}")
    return s[0]


def as_shape(result):
    """build123d booleans can return a ShapeList; collapse it to one shape."""
    from build123d import Compound, ShapeList
    if isinstance(result, ShapeList):
        if not result:
            return None
        return result[0] if len(result) == 1 else Compound(list(result))
    return result


def overlap_volume(a, b) -> float:
    sec = as_shape(a.intersect(b))
    return 0.0 if sec is None else sec.volume


def meshes(solid) -> bool:
    """Every face tessellates. OpenCascade's is_valid alone isn't enough:
    some faces only fail once tessellated, which would break STL export."""
    try:
        for f in solid.faces():
            f.tessellate(0.1, 0.3)
    except Exception:
        return False
    return True


def sound(solid, what: str) -> Solid:
    """One valid solid that tessellates, or GeometryError."""
    s = one_solid(solid, what)
    if not s.is_valid or not meshes(s) or s.volume <= 0:
        raise GeometryError(f"{what}: the result is not a sound solid")
    return s
