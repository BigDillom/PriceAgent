"""Derivative product definitions."""

from derivkit.pricing.products.asian import AsianOption
from derivkit.pricing.products.barrier import BarrierOption
from derivkit.pricing.products.digital import DigitalOption
from derivkit.pricing.products.fcn import FCN
from derivkit.pricing.products.phoenix import Phoenix
from derivkit.pricing.products.snowball import StandardSnowball
from derivkit.pricing.products.vanilla import EuropeanVanilla

__all__ = [
    "AsianOption",
    "BarrierOption",
    "DigitalOption",
    "EuropeanVanilla",
    "FCN",
    "Phoenix",
    "StandardSnowball",
]
