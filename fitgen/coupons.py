"""Fit-test coupons: a socket per size and a peg per clearance (x length).

The shapes:

- round: a solid round peg in a blind round socket. The peg has a head (a
  flat shoulder stop) that rests on the socket's top face when seated.
- square: the same with a square peg and socket. The socket's inside
  corners are rounded (sharp inside corners print tight); the peg is the
  socket hole offset inward by the clearance, so the gap is the same all
  round, corners included.
- pentagon, hexagon, octagon: regular polygons, built like the square (size
  = across flats, inside corners rounded, peg = socket hole offset inward by
  the clearance). A flat faces +Y, where the socket's label tab is.
- tube: the rocket joint, ported from rocket-builder-web
  geometry/rocketgen/fit_test.py: a hollow shoulder (a cup with a closed
  end) into a tube bore, seated on a 45-degree countersink or a flat stop.

Every peg is built in its seated position, in the socket's coordinates
(socket as it prints, standing on z = 0), so seating can be tested by
intersecting the two solids. The print orientation is derived from that:
"flat" (default) turns the peg over so its flat closed end / head is on the
bed and the recessed label reads from below; "functional" prints it as the
real part would, insertion end down, where the bed-edge chamfer also takes
off the elephant foot.

Clearances are radial (per side): the diameter gap is twice the number.
Labels are the clearance in hundredths of a mm: C15 = 0.15 mm radial.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

from build123d import Axis, Circle, Kind, Polygon, Rectangle, RectangleRounded, Solid, extrude, offset

from . import labels
from .geom import GeometryError, box, revolve, sound

SIDES = {"pentagon": 5, "hexagon": 6, "octagon": 8}  # regular polygons: size = across flats
SHAPES = ("round", "square", *SIDES, "tube")
CORNERED = ("square", *SIDES)  # shapes with a socket corner radius
DEFAULT_WALL = {"round": 2.5, "square": 2.5, **{k: 2.5 for k in SIDES}, "tube": 1.5}
DEFAULT_SIZES = {"round": (10.0,), "square": (10.0,), **{k: (10.0,) for k in SIDES}, "tube": (18.4,)}  # tube: the M18 rocket's body ID
DEFAULT_LENGTHS = {"round": (10.0,), "square": (10.0,), **{k: (10.0,) for k in SIDES}, "tube": (12.0,)}
TAGS = {"round": "D", "square": "S", "pentagon": "P", "hexagon": "H", "octagon": "O", "tube": "D"}
DEFAULT_CLEARANCES = (0.05, 0.10, 0.15, 0.20, 0.25, 0.30)

FLOOR = 2.0  # blind socket floor
BOTTOM_GAP = 1.0  # between the longest peg's tip and the socket floor
HEAD_T = 2.0  # peg head (flat stop) thickness; the label is recessed into it
CAP = 1.6  # tube plug's closed end
BAND = 5.0  # tube plug: body tube above the joint
FLAG_T = 2.0  # socket label tab thickness
VENT_D = 2.0  # vent hole through a blind socket's floor (a sealed peg acts as a piston)
PLA_DENSITY = 1.24  # g/cm3


@dataclass
class FitParams:
    shape: str = "round"
    sizes: tuple[float, ...] = (10.0,)  # nominal: hole diameter / square side / polygon across flats / tube bore (ID), mm
    clearances: tuple[float, ...] = DEFAULT_CLEARANCES  # radial, per side, mm
    lengths: tuple[float, ...] = (10.0,)  # engagement length, mm
    wall: float | None = None  # socket wall (round, square) or tube wall; None = the shape's default
    chamfer: float = 0.5  # 45-degree chamfer on the peg's insertion end; 0 = none
    seat: str = "countersink"  # tube only: "countersink" or "flat"
    corner_radius: float = 1.0  # square and polygons: the socket hole's inside corner radius
    orientation: str = "flat"  # "flat" (closed end / head on the bed) or "functional" (insertion end down)
    vent: bool = True  # vent hole in a blind socket's floor
    plate: float = 256.0  # build plate side, mm
    label_size: bool = False  # always add the size line to peg labels (several rocket motors on one plate)

    @classmethod
    def for_shape(cls, shape: str, **kw) -> "FitParams":
        kw.setdefault("sizes", DEFAULT_SIZES.get(shape, (10.0,)))
        kw.setdefault("lengths", DEFAULT_LENGTHS.get(shape, (10.0,)))
        return cls(shape=shape, **kw)

    def wall_mm(self) -> float:
        return self.wall if self.wall is not None else DEFAULT_WALL[self.shape]

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("sizes", "clearances", "lengths"):
            d[k] = list(d[k])
        return d


@dataclass
class Coupon:
    name: str  # object / file name, e.g. D10_L10_C15 or D10_socket
    role: str  # "socket" or "peg"
    size: float
    print_solid: Solid  # as printed: axis at x = y = 0, resting on z = 0
    clearance: float | None = None
    length: float | None = None
    seated: Solid | None = None  # peg only: seated in its socket, in the socket's (print) coordinates
    socket: str | None = None  # peg only: its socket's name
    label: list[str] = field(default_factory=list)

    @property
    def volume(self) -> float:
        return self.print_solid.volume

    @property
    def grams(self) -> float:
        return self.volume / 1000 * PLA_DENSITY


def code(c: float) -> str:
    """Clearance in hundredths of a mm: 0.15 -> '15', 0.05 -> '05', 0.175 -> '17.5'."""
    v = round(c * 100, 1)
    return f"{int(v):02d}" if v == int(v) else f"{v:g}"


def num(x: float) -> str:
    return f"{x:g}"


# ---------- validation ----------

def check(p: FitParams) -> list[str]:
    """Raise GeometryError for a set that can't be built; return notes."""
    if p.shape not in SHAPES:
        raise GeometryError(f"Unknown shape {p.shape!r}; choose one of {', '.join(SHAPES)}.")
    if p.orientation not in ("flat", "functional"):
        raise GeometryError("Orientation must be 'flat' or 'functional'.")
    if p.seat not in ("countersink", "flat"):
        raise GeometryError("Seat must be 'countersink' or 'flat'.")
    if not p.sizes or not p.clearances or not p.lengths:
        raise GeometryError("Give at least one size, one clearance and one engagement length.")
    if len(p.sizes) > 6 or len(p.lengths) > 5 or len(p.clearances) > 20:
        raise GeometryError("At most 6 sizes, 5 lengths and 20 clearances.")
    n = len(p.sizes) * len(p.lengths) * len(p.clearances)
    if n > 60:
        raise GeometryError(f"That's {n} pegs; keep it to 60 or fewer (fewer clearances, lengths or sizes).")
    if len(set(p.sizes)) != len(p.sizes) or len(set(p.lengths)) != len(p.lengths):
        raise GeometryError("Sizes and lengths must not repeat.")
    if len({code(c) for c in p.clearances}) != len(p.clearances):
        raise GeometryError("Clearances must differ by at least 0.001 mm (labels are in hundredths of a mm, to one decimal).")
    w = p.wall_mm()
    if not 0.8 <= w <= 10:
        raise GeometryError("Wall must be between 0.8 and 10 mm.")
    if not 0 <= p.chamfer <= 2:
        raise GeometryError("Chamfer must be between 0 and 2 mm.")
    if not 60 <= p.plate <= 500:
        raise GeometryError("Plate size must be between 60 and 500 mm.")
    for c in p.clearances:
        if not 0 <= c <= 1.5:
            raise GeometryError(f"Clearance {c} mm is out of range (0 to 1.5 mm radial).")
    for L in p.lengths:
        if not 2 <= L <= 80:
            raise GeometryError(f"Engagement length {num(L)} mm is out of range (2 to 80 mm).")
        if p.chamfer > L / 3:
            raise GeometryError(f"The {num(p.chamfer)} mm chamfer is too big for a {num(L)} mm engagement length.")
    cmax = max(p.clearances)
    for s in p.sizes:
        if not 3 <= s <= 150:
            raise GeometryError(f"Size {num(s)} mm is out of range (3 to 150 mm).")
        inner = s / 2 - cmax  # peg radius / half side at the loosest clearance
        if p.shape == "tube":
            inner -= w  # the shoulder's bore radius
            if inner < 1.5:
                raise GeometryError(f"A {num(s)} mm bore is too small for a {num(w)} mm wall: the shoulder would be nearly solid. "
                                    "Use a thinner wall or the round peg.")
        if p.chamfer > 0.4 * inner:
            raise GeometryError(f"The {num(p.chamfer)} mm chamfer is too big for size {num(s)} mm.")
    notes = []
    if p.shape in CORNERED and p.corner_radius < 0:
        raise GeometryError("Corner radius can't be negative.")
    if p.shape in CORNERED and p.corner_radius > min(p.sizes) / 4:
        raise GeometryError("Corner radius must be at most a quarter of the smallest size.")
    if p.shape in CORNERED and 0 < p.corner_radius < cmax:
        notes.append("Corner radius is smaller than the largest clearance: those pegs get sharp corners.")
    return notes


# ---------- shared pieces ----------

def _flag(y_attach: float, lines: list[str]) -> tuple[Solid, Solid]:
    """A label tab on the bed at the socket's +Y side (overlapping its wall
    by 1 mm so it fuses), and the label cutter recessed into its bottom face."""
    w, h = labels.extent(lines)
    fw, fl = max(12.0, w + 4.0), h + 4.0
    tab = box(-fw / 2, fw / 2, y_attach - 1.0, y_attach + fl, 0, FLAG_T)
    cut = labels.cutter(lines, labels.SIZE, 0.0, up=False, y=y_attach + fl / 2)
    return tab, cut


def _to_print(seated: Solid, flat: bool) -> Solid:
    # About Y, so a label that reads from above in the seated position reads
    # from below, the right way up, with its top towards +Y like the socket tabs.
    s = seated.rotate(Axis.Y, 180) if flat else seated
    return s.translate((0, 0, -s.bounding_box().min.Z))


def _vent(z1: float) -> Solid:
    return revolve([(0, -1), (VENT_D / 2, -1), (VENT_D / 2, z1), (0, z1)])


def _peg_lines(p: FitParams, size: float, L: float, c: float) -> list[str]:
    lines = [f"C{code(c)}"]
    if len(p.lengths) > 1:
        lines.append(f"L{num(L)}")
    if len(p.sizes) > 1 or p.label_size:
        lines.append(f"{_tag(p, size)}")
    return lines


def _tag(p: FitParams, size: float) -> str:
    return f"{TAGS[p.shape]}{num(size)}"


# ---------- round ----------

def _round_socket(p: FitParams, size: float) -> tuple[Solid, float]:
    """Blind bore with a floor, a vent, and a label tab. Returns (solid, top z)."""
    r, R = size / 2, size / 2 + p.wall_mm()
    hs = FLOOR + max(p.lengths) + BOTTOM_GAP
    rv = VENT_D / 2 if p.vent else 0.0
    pts = [(R, 0), (R, hs), (r, hs), (r, FLOOR)] + ([(rv, FLOOR), (rv, 0)] if rv else [(0, FLOOR), (0, 0)])
    body = revolve(pts)
    tab, cut = _flag(R, [_tag(p, size)])
    if rv:
        tab = tab.cut(_vent(FLAG_T + 1))
    return body.fuse(tab).cut(cut).clean(), hs


def _round_peg(p: FitParams, size: float, c: float, L: float, hs: float, lines: list[str]) -> Solid:
    """Seated: the shaft hangs into the bore, the head rests on the socket top."""
    rp, ch = size / 2 - c, p.chamfer
    w, h = labels.extent(lines)
    rh = max(size / 2 + p.wall_mm(), math.hypot(w, h) / 2 + 1.0)
    z0, top = hs - L, hs + HEAD_T
    tip = [(0, z0), (rp - ch, z0), (rp, z0 + ch)] if ch > 0 else [(0, z0), (rp, z0)]
    peg = revolve(tip + [(rp, hs), (rh, hs), (rh, top), (0, top)])
    return peg.cut(labels.cutter(lines, labels.SIZE, top, up=True)).clean()


# ---------- square ----------

def _rect(side: float, r: float):
    return RectangleRounded(side, side, r) if r > 0.01 else Rectangle(side, side)


def _square_socket(p: FitParams, size: float) -> tuple[Solid, float]:
    w, cr = p.wall_mm(), p.corner_radius
    so = size + 2 * w
    hs = FLOOR + max(p.lengths) + BOTTOM_GAP
    body = extrude(_rect(so, cr + w if cr > 0.01 else 1.0), hs)
    body = body.cut(extrude(_rect(size, cr), hs).translate((0, 0, FLOOR)))
    tab, cut = _flag(so / 2, [_tag(p, size)])
    body = body.fuse(tab)
    if p.vent:
        body = body.cut(_vent(FLOOR + 1))
    return body.cut(cut).clean(), hs


def _square_peg(p: FitParams, size: float, c: float, L: float, hs: float, lines: list[str], notes: list[str]) -> Solid:
    sp, rp, ch = size - 2 * c, p.corner_radius - c, p.chamfer
    shaft = extrude(_rect(sp, rp), L).translate((0, 0, hs - L))
    if ch > 0:
        tip = [e for e in shaft.edges() if abs(e.center().Z - (hs - L)) < 1e-6]
        try:
            shaft = sound(shaft.chamfer(ch, None, tip), "chamfer")
        except Exception:
            notes.append(f"{num(size)} mm C{code(c)}: the tip chamfer wouldn't build and was left off.")
    w, h = labels.extent(lines)
    sh = max(size + 2 * p.wall_mm(), w + 3.0, h + 3.0)
    head = extrude(RectangleRounded(sh, sh, min(2.0, sh / 4)), HEAD_T).translate((0, 0, hs))
    peg = shaft.fuse(head)
    return peg.cut(labels.cutter(lines, labels.SIZE, hs + HEAD_T, up=True)).clean()


# ---------- regular polygons ----------

def _polygon(n: int, flats: float, r: float):
    """A regular n-gon `flats` across flats with corners rounded to r, a flat
    facing +Y. Built as the sharp polygon r smaller, offset out by r with arcs,
    so the flats stay exactly where they should be."""
    a = flats / 2 - (r if r > 0.01 else 0.0)  # apothem of the sharp core
    R = a / math.cos(math.pi / n)
    pts = [(R * math.cos(math.radians(90 + 180 / n + i * 360 / n)), R * math.sin(math.radians(90 + 180 / n + i * 360 / n)))
           for i in range(n)]
    core = Polygon(*pts, align=None)
    return offset(core, r, kind=Kind.ARC) if r > 0.01 else core


def _polygon_socket(p: FitParams, size: float) -> tuple[Solid, float]:
    n, w, cr = SIDES[p.shape], p.wall_mm(), p.corner_radius
    so = size + 2 * w
    hs = FLOOR + max(p.lengths) + BOTTOM_GAP
    body = extrude(_polygon(n, so, cr + w if cr > 0.01 else 1.0), hs)
    body = body.cut(extrude(_polygon(n, size, cr), hs).translate((0, 0, FLOOR)))
    tab, cut = _flag(so / 2, [_tag(p, size)])
    body = body.fuse(tab)
    if p.vent:
        body = body.cut(_vent(FLOOR + 1))
    return body.cut(cut).clean(), hs


def _polygon_peg(p: FitParams, size: float, c: float, L: float, hs: float, lines: list[str], notes: list[str]) -> Solid:
    """As the square peg: the hole offset inward by the clearance (corner
    radius r - c, sharp if c >= r), with a round head as the stop."""
    n, ch = SIDES[p.shape], p.chamfer
    shaft = extrude(_polygon(n, size - 2 * c, p.corner_radius - c), L).translate((0, 0, hs - L))
    if ch > 0:
        tip = [e for e in shaft.edges() if abs(e.center().Z - (hs - L)) < 1e-6]
        try:
            shaft = sound(shaft.chamfer(ch, None, tip), "chamfer")
        except Exception:
            notes.append(f"{num(size)} mm C{code(c)}: the tip chamfer wouldn't build and was left off.")
    w, h = labels.extent(lines)
    rh = max((size / 2 + p.wall_mm()) / math.cos(math.pi / n), math.hypot(w, h) / 2 + 1.0)
    head = extrude(Circle(rh), HEAD_T).translate((0, 0, hs))
    peg = shaft.fuse(head)
    return peg.cut(labels.cutter(lines, labels.SIZE, hs + HEAD_T, up=True)).clean()


# ---------- tube (rocket joint) ----------

def _shoulder_foot(r: float, chamfer: float) -> list[tuple[float, float]]:
    """The shoulder's insertion-end outer corner: square, or a 45-degree
    chamfer that takes off the elephant foot and leads it into the socket
    (rocketgen/body.py shoulder_foot)."""
    if chamfer <= 0:
        return [(r, 0)]
    return [(r - chamfer, 0), (r, chamfer)]


def _tube_socket(p: FitParams, size: float) -> tuple[Solid, float]:
    """The top of a body segment: plain bore, 45-degree countersink on top
    (or flat), deep enough that the longest shoulder never bottoms out. Open
    at both ends like the real tube; a tab on the bed carries the size."""
    w = p.wall_mm()
    ri, ro = size / 2, size / 2 + w
    cs = p.seat == "countersink"
    h = max(p.lengths) + (w if cs else 0.0) + 4.0
    ring = revolve([(ri, 0), (ro, 0), (ro, h), (ri, h - w if cs else h)])
    tab, cut = _flag(ro, [_tag(p, size)])
    tab = tab.cut(revolve([(0, -1), (ri, -1), (ri, FLAG_T + 1), (0, FLAG_T + 1)]))  # keep the bore open
    return ring.fuse(tab).cut(cut).clean(), h


def _tube_peg(p: FitParams, size: float, c: float, sh: float, h: float, lines: list[str], notes: list[str]) -> Solid:
    """Shoulder (at this clearance) + 45-degree rise (countersink seat) or a
    flat step + a band of body tube + a closed end with the label recessed
    into it. Built shoulder down, then moved to its seat."""
    w, ch = p.wall_mm(), p.chamfer
    ri, ro = size / 2, size / 2 + w
    r_sh = ri - c
    ri_sh = r_sh - w
    cs = p.seat == "countersink"
    rise = ro - r_sh if cs else 0.0
    step = ri - ri_sh  # inside: a 45-degree step out to the body bore (prints without support either way up)
    band = max(BAND, step + CAP + 1.5)
    top = sh + rise + band
    pts = [(ri_sh, 0), *_shoulder_foot(r_sh, ch), (r_sh, sh), (ro, sh + rise), (ro, top), (0, top),
           (0, top - CAP), (ri, top - CAP), (ri, sh + rise + step), (ri_sh, sh + rise)]
    plug = revolve(pts)
    fit = labels.fit_circle(lines, ro - 1.0)
    if fit is None:
        notes.append(f"{num(size)} mm C{code(c)}: too small for a label.")
    else:
        if len(fit[0]) < len(lines):
            notes.append(f"{num(size)} mm C{code(c)}: label shortened to {' '.join(fit[0])} to fit.")
        plug = plug.cut(labels.cutter(fit[0], fit[1], top, up=True))
    seat = h - w - c - sh if cs else h - sh
    return plug.clean().translate((0, 0, seat))


# ---------- the set ----------

def build(p: FitParams) -> tuple[list[Coupon], list[str]]:
    """All coupons for these parameters, socket first for each size, then its
    pegs by length and clearance. Returns (coupons, notes for the user)."""
    notes = check(p)
    flat = p.orientation == "flat"
    out: list[Coupon] = []
    for size in p.sizes:
        tag = _tag(p, size)
        if p.shape == "round":
            sock, hs = _round_socket(p, size)
        elif p.shape == "square":
            sock, hs = _square_socket(p, size)
        elif p.shape in SIDES:
            sock, hs = _polygon_socket(p, size)
        else:
            sock, hs = _tube_socket(p, size)
        sock_name = f"{tag}_socket"
        out.append(Coupon(sock_name, "socket", size, sound(sock, sock_name), label=[tag]))
        for L in p.lengths:
            for c in p.clearances:
                name = f"{tag}_L{num(L)}_C{code(c)}"
                lines = _peg_lines(p, size, L, c)
                if p.shape == "round":
                    seated = _round_peg(p, size, c, L, hs, lines)
                elif p.shape == "square":
                    seated = _square_peg(p, size, c, L, hs, lines, notes)
                elif p.shape in SIDES:
                    seated = _polygon_peg(p, size, c, L, hs, lines, notes)
                else:
                    seated = _tube_peg(p, size, c, L, hs, lines, notes)
                seated = sound(seated, name)
                out.append(Coupon(name, "peg", size, sound(_to_print(seated, flat), name), clearance=c, length=L,
                                  seated=seated, socket=sock_name, label=lines))
    return out, notes
