from collections.abc import Mapping
from dataclasses import dataclass

from profiles.channels import check_channel_coverage
from profiles.revisions import ProfileReference


@dataclass(frozen=True)
class DisplayRow:
    channel: str
    ticks: int


@dataclass(frozen=True)
class DisplayRevision:
    revision_id: str
    configuration: ProfileReference
    rows: tuple[DisplayRow, ...]
    parent_freeze_id: str | None


def normalize_display_rows(directory, rows):
    if isinstance(rows, (str, bytes, Mapping)):
        raise ValueError('display rows must be a sequence of named pairs')
    normalized = []
    try:
        for raw in rows:
            if isinstance(raw, DisplayRow):
                channel, ticks = raw.channel, raw.ticks
            elif isinstance(raw, (tuple, list)) and len(raw) == 2:
                channel, ticks = raw
            else:
                raise ValueError('invalid display row')
            if type(ticks) is not int:
                raise ValueError('display must be an integer')
            normalized.append(DisplayRow(channel, ticks))
    except TypeError as exc:
        raise ValueError('display rows must be iterable') from exc
    check_channel_coverage(directory, (row.channel for row in normalized))
    return tuple(sorted(normalized, key=lambda row: row.channel))
