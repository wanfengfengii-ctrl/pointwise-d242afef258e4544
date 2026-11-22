from dataclasses import dataclass


def validate_name(value, label):
    if not isinstance(value, str) or not value or value != value.strip() or not value.isprintable():
        raise ValueError(f'invalid {label}')
    return value


@dataclass(frozen=True)
class ChannelDirectory:
    batch: str
    names: tuple[str, ...]


def build_directory(batch, channels):
    validate_name(batch, 'batch name')
    if isinstance(channels, (str, bytes)):
        raise ValueError('the directory requires a sequence of channel names')
    try:
        names = tuple(validate_name(name, 'channel name') for name in channels)
    except TypeError as exc:
        raise ValueError('invalid channel directory') from exc
    if len(names) not in (2, 3) or len(set(names)) != len(names):
        raise ValueError('the directory requires two or three distinct channels')
    return ChannelDirectory(batch, tuple(sorted(names)))


def check_channel_coverage(directory, channel_names):
    seen = set()
    for name in channel_names:
        validate_name(name, 'channel name')
        if name in seen:
            raise ValueError(f'duplicate channel: {name}')
        seen.add(name)
    expected = set(directory.names)
    if seen != expected:
        raise ValueError(f'missing channels {sorted(expected - seen)}, unknown channels {sorted(seen - expected)}')
