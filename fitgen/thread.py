"""Motor-retention thread coupons: a short threaded boss and a cap per thread
clearance, ported from rocket-builder-web geometry/rocketgen/thread.py
(sweepThreadRidge, buildThreadedBoss, buildThreadedCap) and
params.py `thread_geometry`.

A truncated-V thread with 45-degree flanks (pitch 2.5 mm for motors under
21 mm, else 3 mm; 3 turns), so the boss and the cap print without supports.
The ridges are swept along a helix a pitch past each end, then trimmed by a
revolved band with a 45-degree lead-in cone; the cap's ridge sits half a
pitch off the boss's, in its groove. The thread clearance is radial: the
gap between the boss's crests and the cap's bore (Rocket Builder: 0.25 mm,
since a printed thread needs far more than a slip joint).

Built in Rocket Builder's coordinates (the tail at z = 0, the boss hanging
below it, the cap's top 2 mm under the tail), then:

- boss coupon: turned over about Y onto a 3 mm flange (the tail) that rests
  on the bed, boss pointing up, with a label tab on the bed;
- cap coupon: face down as Rocket Builder prints it, with a solid floor
  (no nozzle bore) so the label fits, recessed into the floor's bottom face.

Each cap is also kept seated on the boss, in the boss coupon's coordinates,
for the seating test and the Assembled view.
"""

from __future__ import annotations

import math

from build123d import Axis, Helix, Solid, Wire

from . import labels
from .geom import GeometryError, as_shape, one_solid, revolve, sound, xz_face

TURNS = 3
CAP_WALL = 1.6
GAP = 0.5  # boss end to the cap's floor
TAIL_T = 3.0  # the boss coupon's flange (the aft's tail)
CAP_TOP = -2.0  # the cap's top, below the tail


def geometry(mtr_d: float, bay_id: float, wall: float, thread_clear: float) -> dict:
    """The subset of Rocket Builder's thread_geometry a coupon needs. The
    boss's root is the motor mount's OD (bay bore + 2 x wall)."""
    p = 2.5 if mtr_d < 21 else 3.0
    h = 0.35 * p
    r_root = bay_id / 2 + wall
    r_crest = r_root + h
    r_cap_in = r_crest + thread_clear
    r_cap_out = r_cap_in + CAP_WALL
    cap_face_t = max(1.5, 0.08 * mtr_d)
    z_face = CAP_TOP - TURNS * p - GAP
    rib_out, base_chamfer = 0.6, min(1.0, cap_face_t * 0.5)
    return {
        "p": p, "h": h, "b": 0.85 * p, "c": 0.15 * p, "thread_clear": thread_clear,
        "boss_id_r": bay_id / 2, "r_root": r_root, "r_crest": r_crest,
        "r_cap_in": r_cap_in, "r_cap_out": r_cap_out, "r_cap_max": r_cap_out + rib_out,
        "rib_r": 0.8, "rib_out": rib_out, "n_ribs": max(4, math.floor(2 * math.pi * r_cap_out / 10.0)),
        "overlap": TAIL_T, "cap_top": CAP_TOP, "z_face": z_face, "z_boss_end": z_face + GAP,
        "cap_face_t": cap_face_t, "base_chamfer": base_chamfer,
        "base_chamfer_h": base_chamfer * math.tan(math.radians(60)),
        "top_chamfer": 1.0, "top_chamfer_h": 1.0 * math.tan(math.radians(60)),
    }


def _intersect(a, b):
    return as_shape(a.intersect(b))


def sweep_thread_ridge(t: dict, z0: float, z1: float, r_base: float, male: bool) -> Solid:
    """One ridge from z0 (ridge centre at angle 0) up past z1. Wide side on
    r_base plus a 0.3 mm embed into that surface so the union fuses. Male
    ridges grow outward, female inward; both right-handed."""
    sgn = 1 if male else -1
    e = 0.3
    # The 45-degree flanks run on 0.1 mm past r_base: with the flank's
    # corner exactly on r_base its swept edge lies ON the base cylinder and
    # OpenCascade's union fails (Onshape coped). Same ridge outside r_base.
    e0 = 0.1
    hw = t["b"] / 2 + e0
    prof = xz_face([
        (r_base - sgn * e, z0 - hw),
        (r_base - sgn * e0, z0 - hw),
        (r_base + sgn * t["h"], z0 - t["c"] / 2),
        (r_base + sgn * t["h"], z0 + t["c"] / 2),
        (r_base - sgn * e0, z0 + hw),
        (r_base - sgn * e, z0 + hw),
    ])
    turns = math.ceil((z1 - z0) / t["p"])
    helix = Helix(pitch=t["p"], height=turns * t["p"], radius=r_base + sgn * t["h"] / 2, center=(0, 0, z0))
    # Frenet framing keeps the profile in the axial plane along a helix.
    return Solid.sweep(prof, Wire(helix.edges()), is_frenet=True)


def _boss(t: dict) -> Solid:
    """Boss + external thread on the tail flange, in Rocket Builder's coordinates."""
    r_flange = t["r_cap_max"] + 2.0
    boss = revolve([
        (t["boss_id_r"], t["overlap"]),
        (r_flange, t["overlap"]),
        (r_flange, 0.0),
        (t["r_root"], 0.0),
        (t["r_root"], t["z_boss_end"]),
        (t["boss_id_r"], t["z_boss_end"]),
    ])
    ridge = sweep_thread_ridge(t, t["z_boss_end"] - t["p"], t["cap_top"] + t["p"], t["r_root"], True)
    r_out = t["r_crest"] + 0.5
    band = revolve([
        (t["r_root"] - 1, t["z_boss_end"]),
        (t["r_root"], t["z_boss_end"]),
        (r_out, t["z_boss_end"] + (r_out - t["r_root"])),
        (r_out, t["cap_top"]),
        (t["r_root"] - 1, t["cap_top"]),
    ])
    return one_solid(boss.fuse(_intersect(ridge, band)), "thread boss")


def _cap(t: dict, lines: list[str], ribs: bool = False) -> Solid:
    """Rocket Builder's cap with a solid floor and the label recessed into its
    bottom face, in assembled position. The grip ribs are off by default: they
    don't change the fit, and a test cap is small enough to turn without them
    (they cost about a fifth of the cap's build time on the server)."""
    z_bottom = t["z_face"] - t["cap_face_t"]
    cup = revolve([
        (0.0, z_bottom),
        (t["r_cap_out"] - t["base_chamfer"], z_bottom),
        (t["r_cap_out"], z_bottom + t["base_chamfer_h"]),
        (t["r_cap_out"], t["cap_top"] - t["top_chamfer_h"]),
        (t["r_cap_out"] - t["top_chamfer"], t["cap_top"]),
        (t["r_cap_in"], t["cap_top"]),
        (t["r_cap_in"], t["z_face"]),
        (0.0, t["z_face"]),
    ])
    z0 = t["z_boss_end"] - 1.5 * t["p"]
    ridge = sweep_thread_ridge(t, z0, t["cap_top"] + t["p"], t["r_cap_in"], False)
    r_in = t["r_root"] + t["thread_clear"] - 0.5
    band = revolve([
        (r_in, t["z_face"] - t["cap_face_t"] / 2),
        (t["r_cap_in"] + 1, t["z_face"] - t["cap_face_t"] / 2),
        (t["r_cap_in"] + 1, t["cap_top"]),
        (t["r_cap_in"], t["cap_top"]),
        (r_in, t["cap_top"] - (t["r_cap_in"] - r_in)),
    ])
    cap = one_solid(cup.fuse(_intersect(ridge, band)), "motor cap")
    if ribs:
        cap = _add_ribs(cap, t, z_bottom)
    # The label goes in last. Cut into the plain cup first, it made the
    # thread union four times slower (each boolean pays for the text's faces).
    fit = labels.fit_circle(lines, t["r_cap_in"] - 0.5)
    if fit is None:
        raise GeometryError("The motor cap is too small for a label.")
    return cap.cut(labels.cutter(fit[0], fit[1], z_bottom, up=False)).clean()


def _add_ribs(cap: Solid, t: dict, z_bottom: float) -> Solid:
    # Grip ribs: half-cylinders standing rib_out proud, both ends cut back
    # along the base and top chamfer cones so the chamfers stay visible.
    rib_c = t["r_cap_out"] + t["rib_out"] - t["rib_r"]
    ribs = None
    for i in range(t["n_ribs"]):
        a = 2 * math.pi * i / t["n_ribs"]
        rib = Solid.make_cylinder(t["rib_r"], t["cap_top"] - z_bottom).translate(
            (rib_c * math.cos(a), rib_c * math.sin(a), z_bottom))
        ribs = rib if ribs is None else ribs.fuse(rib)
    # The cut cones sit 0.01 mm inside the cap's chamfer cones: exactly
    # coincident cones make OpenCascade's union return an invalid solid.
    eps = 0.01
    base_slope = t["base_chamfer_h"] / t["base_chamfer"]
    cone_r0 = t["r_cap_out"] - t["base_chamfer"] - 1
    cone_r1 = t["r_cap_max"] + 1
    base_z0 = z_bottom - base_slope * 1 + eps
    base_cut = revolve([(cone_r0, base_z0), (cone_r1, base_z0), (cone_r1, base_z0 + base_slope * (cone_r1 - cone_r0))])
    top_slope = t["top_chamfer_h"] / t["top_chamfer"]
    top_r0 = t["r_cap_out"] - t["top_chamfer"] - 1
    top_z0 = t["cap_top"] + top_slope * 1 - eps
    top_cut = revolve([(top_r0, top_z0), (cone_r1, top_z0), (cone_r1, top_z0 - top_slope * (cone_r1 - top_r0))])
    ribs = ribs.cut(base_cut).cut(top_cut)
    return one_solid(cap.fuse(ribs), "motor cap")


def _to_boss_print(s: Solid) -> Solid:
    """Rocket coordinates -> the boss coupon's: turned over about Y (the
    thread stays right-handed), flange on the bed."""
    return s.rotate(Axis.Y, 180).translate((0, 0, TAIL_T))


def boss_coupon(mtr_d: float, bay_id: float, wall: float, tag: str, flag) -> Solid:
    """The boss coupon as printed. `flag(y, lines)` is coupons._flag (the label
    tab), passed in to keep the import one-way."""
    t = geometry(mtr_d, bay_id, wall, 0.25)
    boss = _to_boss_print(_boss(t))
    tab, cut = flag(t["r_cap_max"] + 2.0, [tag])
    tab = tab.cut(revolve([(0, -1), (t["boss_id_r"], -1), (t["boss_id_r"], TAIL_T + 1), (0, TAIL_T + 1)]))  # keep the bore open
    return sound(boss.fuse(tab).cut(cut).clean(), f"{tag} boss")


def cap_coupon(mtr_d: float, bay_id: float, wall: float, clear: float, lines: list[str], name: str) -> tuple[Solid, Solid]:
    """(cap as printed, face down on the bed; cap seated on the boss coupon)."""
    t = geometry(mtr_d, bay_id, wall, clear)
    cap = _cap(t, lines)
    printed = cap.translate((0, 0, -(t["z_face"] - t["cap_face_t"])))
    return sound(printed, name), sound(_to_boss_print(cap), name)


def length(mtr_d: float) -> float:
    """Thread engagement, mm (turns x pitch), for the report."""
    return TURNS * (2.5 if mtr_d < 21 else 3.0)
