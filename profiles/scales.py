from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

from profiles.channels import check_channel_coverage


def as_fraction(value):
    if type(value) not in (int, str, Fraction):
        raise ValueError('expected an exact rational number')
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError('invalid rational number') from exc


@dataclass(frozen=True)
class StationScale:
    coefficients: tuple[tuple[str, Fraction], ...]
    offset_lower: Fraction
    offset_upper: Fraction


def make_station_scale(directory, coefficients, offset_bounds):
    if not isinstance(coefficients, Mapping):
        raise ValueError('coefficients must be keyed by channel name')
    check_channel_coverage(directory, coefficients)
    ordered = tuple((name, as_fraction(coefficients[name])) for name in directory.names)
    if any(value <= 0 for _, value in ordered):
        raise ValueError('every scale coefficient must be positive')
    if isinstance(offset_bounds, (str, bytes, Mapping)):
        raise ValueError('offset bounds must contain two rational numbers')
    try:
        lower_value, upper_value = offset_bounds
    except (TypeError, ValueError) as exc:
        raise ValueError('offset bounds must contain two rational numbers') from exc
    lower, upper = as_fraction(lower_value), as_fraction(upper_value)
    if lower > upper:
        raise ValueError('reversed offset bounds')
    return StationScale(ordered, lower, upper)
