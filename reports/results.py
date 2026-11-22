import json
from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class DifferenceInterval:
    lower: Fraction
    upper: Fraction
    lower_closed: bool
    upper_closed: bool

    def __post_init__(self):
        if type(self.lower) is not Fraction or type(self.upper) is not Fraction:
            raise ValueError('difference endpoints must be exact fractions')
        if type(self.lower_closed) is not bool or type(self.upper_closed) is not bool:
            raise ValueError('invalid difference endpoint qualifiers')
        if self.lower > self.upper:
            raise ValueError('reversed difference interval')
        if self.lower == self.upper and not (self.lower_closed and self.upper_closed):
            raise ValueError('a singleton requires two attained endpoints')


@dataclass(frozen=True)
class ComparisonResult:
    status: str
    difference: DifferenceInterval | None

    def __post_init__(self):
        if self.status == 'compatible' and isinstance(self.difference, DifferenceInterval):
            return
        if self.status == 'incompatible' and self.difference is None:
            return
        raise ValueError('status and difference do not agree')


def encode_result(result):
    interval = result.difference
    difference = None
    if interval is not None:
        difference = {
            'lower': str(interval.lower), 'upper': str(interval.upper),
            'lower_closed': interval.lower_closed, 'upper_closed': interval.upper_closed,
        }
    return json.dumps({'status': result.status, 'difference': difference}, sort_keys=True, separators=(',', ':'))


def decode_result(encoded):
    data = json.loads(encoded)
    if not isinstance(data, dict) or set(data) != {'status', 'difference'}:
        raise ValueError('invalid persisted report result')
    fields = data['difference']
    interval = None
    if fields is not None:
        if not isinstance(fields, dict) or set(fields) != {'lower', 'upper', 'lower_closed', 'upper_closed'}:
            raise ValueError('invalid persisted difference interval')
        lower, upper = fields['lower'], fields['upper']
        if type(lower) is not str or type(upper) is not str:
            raise ValueError('persisted difference endpoints must be rational strings')
        try:
            first, last = Fraction(lower), Fraction(upper)
        except (ValueError, ZeroDivisionError) as exc:
            raise ValueError('invalid persisted difference endpoint') from exc
        if str(first) != lower or str(last) != upper:
            raise ValueError('noncanonical persisted difference endpoint')
        interval = DifferenceInterval(first, last, fields['lower_closed'], fields['upper_closed'])
    return ComparisonResult(data['status'], interval)
