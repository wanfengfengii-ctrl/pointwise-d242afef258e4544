import hashlib
import json
from dataclasses import asdict, dataclass
from string import hexdigits
from uuid import uuid4

from profiles.channels import build_directory, validate_name


@dataclass(frozen=True)
class PieceOrigin:
    issue_id: str
    freeze_id: str
    revision_id: str
    profile_id: str
    station: str
    batch: str
    channels: tuple[str, ...]

    def __post_init__(self):
        for name in ('issue_id', 'freeze_id', 'revision_id', 'profile_id', 'station', 'batch'):
            validate_name(getattr(self, name), name)
        directory = build_directory(self.batch, self.channels)
        if directory.names != self.channels:
            raise ValueError('source channels must use directory order')


@dataclass(frozen=True)
class IssueEntry:
    version: int
    origin: PieceOrigin
    body_sha256: str

    def __post_init__(self):
        if type(self.version) is not int or self.version != 1 or not isinstance(self.origin, PieceOrigin):
            raise ValueError('invalid V1 issue entry')
        digest = self.body_sha256
        if (not isinstance(digest, str) or len(digest) != 64 or digest != digest.lower()
                or any(letter not in hexdigits for letter in digest)):
            raise ValueError('invalid issue body digest')


@dataclass(frozen=True)
class StationPiece:
    entry: IssueEntry
    body: bytes


def body_fingerprint(body):
    if type(body) is not bytes:
        raise ValueError('station body must be bytes')
    return hashlib.sha256(body).hexdigest()


def make_envelope(source, body):
    reference = source.profile.reference
    origin = PieceOrigin(
        f'issue-{uuid4().hex}', source.freeze_id, source.revision.revision_id,
        reference.version, reference.station, reference.batch, source.profile.directory.names,
    )
    entry = IssueEntry(1, origin, body_fingerprint(body))
    return StationPiece(entry, body)


def encode_issue_entry(entry):
    return json.dumps(asdict(entry), ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def decode_issue_entry(encoded):
    data = json.loads(encoded)
    if not isinstance(data, dict) or set(data) != {'version', 'origin', 'body_sha256'}:
        raise ValueError('invalid persisted issue entry')
    origin = data['origin']
    if not isinstance(origin, dict) or set(origin) != set(PieceOrigin.__dataclass_fields__):
        raise ValueError('invalid persisted origin')
    if not isinstance(origin['channels'], list):
        raise ValueError('invalid persisted directory')
    origin['channels'] = tuple(origin['channels'])
    return IssueEntry(data['version'], PieceOrigin(**origin), data['body_sha256'])
