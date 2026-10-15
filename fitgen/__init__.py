"""fitgen: printable slip-fit test coupons (build123d). See docs/spec.md."""

from .coupons import SHAPES, Coupon, FitParams, build
from .geom import GeometryError
from .plate import Plate, layout, stl_zip, write_3mf, write_stls

GENERATOR_VERSION = "0.1.0"

__all__ = ["SHAPES", "Coupon", "FitParams", "GeometryError", "Plate", "build", "layout", "stl_zip", "write_3mf",
           "write_stls", "GENERATOR_VERSION"]
