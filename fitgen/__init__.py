"""fitgen: printable slip-fit test coupons (build123d). See docs/spec.md."""

from . import rocket
from .coupons import SHAPES, Coupon, FitParams, build
from .geom import GeometryError
from .plate import Plate, layout, step_zip, stl_zip, write_3mf, write_stls

GENERATOR_VERSION = "0.2.0"  # 0.2: polygons, Rocket Builder presets and thread coupons

__all__ = ["SHAPES", "Coupon", "FitParams", "GeometryError", "Plate", "build", "layout", "step_zip", "stl_zip", "write_3mf",
           "write_stls", "GENERATOR_VERSION", "rocket"]
