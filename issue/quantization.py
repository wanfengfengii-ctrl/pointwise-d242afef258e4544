from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class TickCell:
    lower: Fraction
    upper: Fraction
    strict: bool


def tick_cell(display):
    if type(display) is not int:
        raise ValueError('display must be an integer')
    half = Fraction(1, 2)
    return TickCell(display - half, display + half, bool(display % 2))
