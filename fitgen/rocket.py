"""Rocket Builder presets: the body-tube joint coupons for a rocket as Rocket
Builder (the-feve/rocket-builder-web) would build it.

The motor and settings tables in data/ are copied from rocket-builder-web
geometry/rocketgen/data/ (which copies them from OS_Rocket_Builder); keep
them in sync. The arithmetic mirrors rocketgen/params.py `compute_derived`
and the website's body OD offset (server/app.py `resolved_od`):

- motor bay bore = motor diameter + 2 x mtr_clear
- stock body OD = bay bore + 2 x wall; the offset adds 2 x offset to it
- body bore (ID) = body OD - 2 x wall: the joint's socket size
- body joint shoulder = max(0.75 x body OD - 4, 10) mm
- nose shoulder = max(0.7 x body shoulder, 7) mm (30% shorter, owner's
  request on Rocket Builder, 2026-10-09)

Lengths are rounded to 0.1 mm: that much makes no difference to a fit and
keeps the peg labels short.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

from . import thread
from .coupons import DEFAULT_CLEARANCES, Coupon, FitParams, _flag, build as build_set, code
from .geom import GeometryError

DATA = Path(__file__).resolve().parent / "data"
JOINTS = ("body", "nose")
DEFAULT_THREAD_CLEARANCES = (0.15, 0.20, 0.25, 0.30, 0.35)  # Rocket Builder builds with 0.25


def _mm(text: str) -> float:
    value, unit = text.split()
    assert unit == "mm", text
    return float(value)


@lru_cache(maxsize=1)
def motors() -> dict[str, float]:
    """{motor: diameter, mm}, in the table's order (M13, M18, M24, M24L, M29)."""
    with open(DATA / "rocket_library_motors.csv", newline="") as f:
        return {row["Motor"]: _mm(row["mtr_d"]) for row in csv.DictReader(f)}


@lru_cache(maxsize=1)
def settings() -> dict[str, float]:
    with open(DATA / "rocket_global_settings.csv", newline="") as f:
        return {row["Name"]: _mm(row["Value"]) for row in csv.DictReader(f)}


def dims(motor: str = "M18", wall: float | None = None, offset: float = 0.0) -> dict:
    """The joint's numbers for this motor, wall and body OD offset."""
    if motor not in motors():
        raise GeometryError(f"Unknown motor {motor!r}; choose one of {', '.join(motors())}.")
    st = settings()
    wall = st["wall"] if wall is None else wall
    if not 0.8 <= wall <= 3.0:
        raise GeometryError("Rocket Builder's wall is between 0.8 and 3 mm.")
    if not 0 <= offset <= 80:
        raise GeometryError("Body OD offset must be between 0 and 80 mm.")
    bay = motors()[motor] + 2 * st["mtr_clear"]
    od = bay + 2 * wall + 2 * offset
    body = max(0.75 * od - 4.0, 10.0)
    return {
        "motor": motor, "wall": wall, "offset": offset,
        "bay_id": round(bay, 3), "body_od": round(od, 3), "body_id": round(od - 2 * wall, 3),
        "lengths": {"body": round(body, 1), "nose": round(max(0.7 * body, 7.0), 1)},
        "fit_slip": st["fit_slip"],  # the clearance Rocket Builder builds its joints with now
        "thread": {"pitch": 2.5 if motors()[motor] < 21 else 3.0, "turns": thread.TURNS, "clearance": 0.25,
                   "length": thread.length(motors()[motor])},
    }


def params(motor: str = "M18", wall: float | None = None, offset: float = 0.0, joints=("body",), **kw) -> FitParams:
    """FitParams for the tube coupons of this rocket's joints: one socket (the
    body bore) and a peg per joint length and clearance, on the rocket's 45°
    countersink seat unless `seat` says otherwise."""
    d = dims(motor, wall, offset)
    joints = [j for j in JOINTS if j in set(joints)]
    if not joints:
        raise GeometryError("Pick at least one joint to test: the body joint, the nose joint or both.")
    kw.setdefault("seat", "countersink")
    return FitParams(shape="tube", sizes=(d["body_id"],), lengths=tuple(d["lengths"][j] for j in joints),
                     wall=d["wall"], **kw)


@dataclass
class RocketParams:
    """A Rocket Builder preset: the joint coupons (tube shape, from the
    motor, wall and body OD offset) and the motor-retention thread coupons,
    for one or more motor sizes."""

    motors: tuple[str, ...] = ("M18",)
    wall: float | None = None  # None = Rocket Builder's (1.5 mm)
    offset: float = 0.0  # body OD offset, radial mm, as on Rocket Builder
    joints: tuple[str, ...] = ("body",)
    clearances: tuple[float, ...] = DEFAULT_CLEARANCES  # joint clearances, radial
    thread: bool = True
    thread_clearances: tuple[float, ...] = DEFAULT_THREAD_CLEARANCES  # radial, crest to cap bore
    chamfer: float = 0.5
    seat: str = "countersink"
    orientation: str = "flat"
    plate: float = 256.0

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("motors", "joints", "clearances", "thread_clearances"):
            d[k] = list(d[k])
        d["mode"] = "rocket"
        return d

    def joint_params(self, motor: str) -> FitParams | None:
        if not self.joints:
            return None
        return params(motor, self.wall, self.offset, self.joints, clearances=self.clearances, chamfer=self.chamfer,
                      seat=self.seat, orientation=self.orientation, plate=self.plate, label_size=len(self.motors) > 1)


MAX_PEGS = 60  # joint pegs + caps on one plate, all motors
MAX_CAPS = 15  # thread caps, all motors: about 3.5 s each to build


def build(p: RocketParams) -> tuple[list[Coupon], list[str]]:
    """For each motor size: its joint coupons (socket, then pegs), then its
    boss and caps. Motors with the same joints and thread as one already
    on the plate (M24 and M24L: only the motor length differs) are skipped
    with a note."""
    if not p.motors:
        raise GeometryError("Add at least one motor size.")
    if len(set(p.motors)) != len(p.motors):
        raise GeometryError("Each motor size only once, please.")
    if not p.joints and not p.thread:
        raise GeometryError("Pick something to test: a joint, the motor thread or both.")
    sets, notes, seen = [], [], {}
    for m in p.motors:
        d = dims(m, p.wall, p.offset)  # validates motor, wall and offset
        same = (d["body_id"], tuple(d["lengths"].values()), d["bay_id"], d["thread"]["pitch"])
        if same in seen:
            notes.append(f"{m} has the same joints and thread as {seen[same]}, so it isn't repeated: use the {seen[same]} coupons.")
            continue
        seen[same] = m
        sets.append((m, d))
    n_caps = len(sets) * len(p.thread_clearances) if p.thread else 0
    n_pegs = len(sets) * len(p.joints) * len(p.clearances) + n_caps
    if n_caps > MAX_CAPS:
        raise GeometryError(f"That's {n_caps} motor caps; keep it to {MAX_CAPS} or fewer (fewer motor sizes or thread clearances).")
    if n_pegs > MAX_PEGS:
        raise GeometryError(f"That's {n_pegs} pegs and caps; keep it to {MAX_PEGS} or fewer (fewer motor sizes or clearances).")
    if p.thread:
        tc = p.thread_clearances
        if not tc or len(tc) > 12:
            raise GeometryError("Give between 1 and 12 thread clearances.")
        if len({code(c) for c in tc}) != len(tc):
            raise GeometryError("Thread clearances must not repeat (labels are in hundredths of a mm).")
        for c in tc:
            if not 0.05 <= c <= 1.0:
                raise GeometryError(f"Thread clearance {c} mm is out of range (0.05 to 1 mm radial).")
    out = []
    for m, d in sets:
        jp = p.joint_params(m)
        if jp:
            items, n = build_set(jp)
            out += items
            notes += n
        if p.thread:
            mtr_d = motors()[m]
            boss_name = f"{m}_boss"
            out.append(Coupon(boss_name, "socket", d["bay_id"],
                              thread.boss_coupon(mtr_d, d["bay_id"], d["wall"], m, _flag), label=[m]))
            for c in p.thread_clearances:
                name = f"{m}_T{code(c)}"
                lines = [f"T{code(c)}"] + ([m] if len(p.motors) > 1 else [])
                # The cap always prints face down (as on Rocket Builder): its
                # thread's 45-degree flanks need that way up.
                printed, seated = thread.cap_coupon(mtr_d, d["bay_id"], d["wall"], c, lines, name)
                out.append(Coupon(name, "peg", d["bay_id"], printed, clearance=c, length=thread.length(mtr_d),
                                  seated=seated, socket=boss_name, label=lines))
    return out, notes
