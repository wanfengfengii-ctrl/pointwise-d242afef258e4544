from fractions import Fraction

from capture.freezing import FrozenSource
from issue.body import EvidenceBody, LinearBound
from issue.quantization import tick_cell


def build_station_evidence(source: FrozenSource):
    channels = source.profile.directory.names
    scale = source.profile.scale
    displays = {row.channel: row.ticks for row in source.revision.rows}
    coefficients = dict(scale.coefficients)
    bounds = []
    for index, channel in enumerate(channels):
        cell = tick_cell(displays[channel])
        lower = (cell.lower - scale.offset_upper) / coefficients[channel]
        upper = (cell.upper - scale.offset_lower) / coefficients[channel]
        axis = tuple(Fraction(position == index) for position in range(len(channels)))
        bounds.append(LinearBound(tuple(-weight for weight in axis), -lower, False))
        bounds.append(LinearBound(axis, upper, False))
    return EvidenceBody(channels, tuple(bounds))
