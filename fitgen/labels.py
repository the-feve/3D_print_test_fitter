"""Recessed labels, cut into the face that sits on the bed.

The font ships with the package (fonts/FreeSansBold.ttf) so the labels don't
depend on the system. Raised text on top of a part needed a bridged cap in
the rocket fit test; text recessed 0.6 mm into the bed face prints cleanly
and reads from below.
"""

from __future__ import annotations

from pathlib import Path

from build123d import Align, Plane, Solid, Text, extrude

from .geom import as_shape

FONT_PATH = Path(__file__).parent / "fonts" / "FreeSansBold.ttf"
TEXT_H = 0.6  # recess depth
SIZE = 4.0  # preferred cap height of the first line, mm
MIN_SIZE = 2.2  # smaller than this doesn't print legibly with a 0.4 nozzle
LINE = 1.25  # line pitch / font size
SECOND = 0.8  # later lines are smaller than the first


def _line(text: str, size: float):
    return Text(text, font_size=size, font_path=str(FONT_PATH), align=(Align.CENTER, Align.CENTER))


def _stack(lines: list[str], size: float):
    """Sketches for each line, stacked downward and centred on the origin."""
    sizes = [size] + [size * SECOND] * (len(lines) - 1)
    pitch = [s * LINE for s in sizes]
    total = sum(pitch)
    y, out = total / 2, []
    for text, s, p in zip(lines, sizes, pitch):
        out.append(_line(text, s).translate((0, y - p / 2, 0)))
        y -= p
    return out


def extent(lines: list[str], size: float = SIZE) -> tuple[float, float]:
    """(width, height) of the stacked label."""
    xs, ys = [], []
    for sk in _stack(lines, size):
        bb = sk.bounding_box()
        xs += [bb.min.X, bb.max.X]
        ys += [bb.min.Y, bb.max.Y]
    return max(xs) - min(xs), max(ys) - min(ys)


def fit_size(lines: list[str], max_w: float, max_h: float) -> tuple[list[str], float] | None:
    """The largest size (<= SIZE) at which the label fits max_w x max_h,
    dropping trailing lines if needed; None if not even the first line fits."""
    lines = list(lines)
    while lines:
        w, h = extent(lines, SIZE)
        s = min(SIZE, SIZE * max_w / w, SIZE * max_h / h)
        if s >= MIN_SIZE:
            return lines, s
        lines.pop()
    return None


def cutter(lines: list[str], size: float, z_face: float, up: bool, x: float = 0.0, y: float = 0.0) -> Solid:
    """Text solid for cutting a recess TEXT_H deep into a horizontal face at
    z_face. up=True: the face looks up (+Z), the text reads from above;
    up=False: the face looks down, the text is mirrored so it reads from
    below. It overshoots the face by 0.01 mm so the cut is clean."""
    solids = [extrude(sk, TEXT_H + 0.01) for sk in _stack(lines, size)]
    t = solids[0]
    for s in solids[1:]:
        t = t.fuse(s)
    t = as_shape(t)
    if up:
        t = t.translate((0, 0, z_face - TEXT_H))
    else:
        t = t.mirror(Plane.YZ).translate((0, 0, z_face - 0.01))
    return t.translate((x, y, 0))


def fit_circle(lines: list[str], radius: float) -> tuple[list[str], float] | None:
    """Like fit_size, for a label inside a circle of this radius."""
    lines = list(lines)
    while lines:
        w, h = extent(lines, SIZE)
        s = min(SIZE, SIZE * 2 * radius / (w * w + h * h) ** 0.5)
        if s >= MIN_SIZE:
            return lines, s
        lines.pop()
    return None
