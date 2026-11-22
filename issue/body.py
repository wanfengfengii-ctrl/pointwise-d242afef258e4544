import json
from dataclasses import dataclass
from fractions import Fraction

from profiles.channels import build_directory


@dataclass(frozen=True)
class LinearBound:
    weights: tuple[Fraction, ...]
    limit: Fraction
    strict: bool


@dataclass(frozen=True)
class EvidenceBody:
    channels: tuple[str, ...]
    bounds: tuple[LinearBound, ...]


def _read_rational(text):
    if not isinstance(text, str):
        raise ValueError('evidence rationals must be encoded as strings')
    try:
        value = Fraction(text)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError('invalid evidence rational') from exc
    if str(value) != text:
        raise ValueError('noncanonical evidence rational')
    return value


def encode_evidence_body(evidence):
    bounds = [
        [[str(weight) for weight in bound.weights], str(bound.limit), bound.strict]
        for bound in evidence.bounds
    ]
    return json.dumps(
        {'channels': evidence.channels, 'bounds': bounds},
        ensure_ascii=False, sort_keys=True, separators=(',', ':'),
    ).encode('utf-8')


def decode_evidence_body(body):
    if type(body) is not bytes:
        raise ValueError('evidence body must be bytes')
    data = json.loads(body.decode('utf-8'))
    if not isinstance(data, dict) or set(data) != {'bounds', 'channels'}:
        raise ValueError('invalid evidence fields')
    raw_channels, raw_bounds = data['channels'], data['bounds']
    if not isinstance(raw_channels, list) or not isinstance(raw_bounds, list) or not raw_bounds:
        raise ValueError('invalid evidence channels or bounds')
    names = build_directory('evidence', raw_channels).names
    if names != tuple(raw_channels):
        raise ValueError('evidence channels are out of order')
    bounds = []
    for raw in raw_bounds:
        if not isinstance(raw, list) or len(raw) != 3:
            raise ValueError('invalid linear bound')
        weights, limit, strict = raw
        if not isinstance(weights, list) or len(weights) != len(names) or type(strict) is not bool:
            raise ValueError('invalid bound dimensions or strictness')
        bounds.append(LinearBound(tuple(map(_read_rational, weights)), _read_rational(limit), strict))
    return EvidenceBody(names, tuple(bounds))
