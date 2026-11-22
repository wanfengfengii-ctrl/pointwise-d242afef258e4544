from dataclasses import dataclass
from uuid import uuid4

from profiles.channels import ChannelDirectory, validate_name
from profiles.scales import StationScale


@dataclass(frozen=True)
class ProfileReference:
    version: str
    batch: str
    station: str


@dataclass(frozen=True)
class ProfileRevision:
    reference: ProfileReference
    directory: ChannelDirectory
    scale: StationScale


def make_profile_revision(directory, station, scale):
    validate_name(station, 'station name')
    reference = ProfileReference(f'profile-{uuid4().hex}', directory.batch, station)
    return ProfileRevision(reference, directory, scale)
