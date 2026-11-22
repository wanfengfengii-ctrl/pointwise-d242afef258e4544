from capture.storage import CaptureStore
from profiles.catalog import read_configuration
from profiles.revisions import ProfileRevision


def resolve_amendment_parent(db, parent_freeze_id, new_profile: ProfileRevision):
    if parent_freeze_id is None:
        return None
    record = CaptureStore(db).read_freeze(parent_freeze_id)
    parent_profile = read_configuration(db, record.configuration)
    if (parent_profile.reference.station != new_profile.reference.station
            or parent_profile.directory != new_profile.directory):
        raise ValueError('amendment parent must belong to the same station, batch and directory')
    return record.freeze_id
