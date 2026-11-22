from fractions import Fraction

from capture.freezing import FrozenSource
from issue.body import EvidenceBody, LinearBound
from issue.quantization import tick_cell


def build_station_evidence(source: FrozenSource):
    """Encode exactly the joint read values a frozen station can present.

    A station shares one offset ``b`` in ``[offset_lower, offset_upper]`` across
    every channel of the same freeze, and each channel must land in its tick
    cell ``a * x + b`` under round-half-to-even.  Eliminating ``b`` yields
    per-channel intervals plus pairwise separations that preserve precisely the
    feasible joint tuples, including the open ends of odd displays.
    """
    channels = source.profile.directory.names
    scale = source.profile.scale
    displays = {row.channel: row.ticks for row in source.revision.rows}
    coefficients = dict(scale.coefficients)
    cells = {channel: tick_cell(displays[channel]) for channel in channels}
    bounds = []
    for index, channel in enumerate(channels):
        cell = cells[channel]
        coefficient = coefficients[channel]
        lower = (cell.lower - scale.offset_upper) / coefficient
        upper = (cell.upper - scale.offset_lower) / coefficient
        axis = tuple(Fraction(position == index) for position in range(len(channels)))
        bounds.append(LinearBound(tuple(-weight for weight in axis), -lower, cell.strict))
        bounds.append(LinearBound(axis, upper, cell.strict))
    for first, name in enumerate(channels):
        for second, other in enumerate(channels):
            if first == second:
                continue
            left, right = cells[name], cells[other]
            left_coefficient, right_coefficient = coefficients[name], coefficients[other]
            weights = tuple(
                (left_coefficient if position == first else Fraction(0))
                - (right_coefficient if position == second else Fraction(0))
                for position in range(len(channels))
            )
            strict = left.strict or right.strict
            bounds.append(LinearBound(weights, left.upper - right.lower, strict))
            bounds.append(LinearBound(tuple(-weight for weight in weights),
                                      right.upper - left.lower, strict))
    return EvidenceBody(channels, tuple(bounds))
