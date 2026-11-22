from profiles.channels import build_directory
from profiles.revisions import ProfileReference, make_profile_revision
from profiles.scales import make_station_scale
from profiles.storage import ProfileStore


def configure(db, batch, station, channels, coefficients, offset_bounds):
    directory = build_directory(batch, channels)
    scale = make_station_scale(directory, coefficients, offset_bounds)
    revision = make_profile_revision(directory, station, scale)
    ProfileStore(db).add_revision(revision)
    return revision.reference


def read_configuration(db, reference):
    if not isinstance(reference, ProfileReference):
        raise ValueError('expected a configuration reference')
    revision = ProfileStore(db).read_revision(reference.version)
    if revision.reference != reference:
        raise ValueError('configuration reference does not match the registered version')
    return revision
