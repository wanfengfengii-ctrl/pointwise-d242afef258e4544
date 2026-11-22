from dataclasses import dataclass

from capture.observations import DisplayRevision, normalize_display_rows
from capture.storage import CaptureStore, FreezeRecord
from profiles.catalog import read_configuration
from profiles.revisions import ProfileRevision


@dataclass(frozen=True)
class FrozenSource:
    record: FreezeRecord
    revision: DisplayRevision
    profile: ProfileRevision

    @property
    def freeze_id(self):
        return self.record.freeze_id


def freeze(db, revision_id):
    store = CaptureStore(db)
    revision = store.read_revision(revision_id)
    profile = read_configuration(db, revision.configuration)
    normalize_display_rows(profile.directory, revision.rows)
    record = store.save_freeze(revision)
    return FrozenSource(record, revision, profile)


def load_frozen_source(db, freeze_id):
    store = CaptureStore(db)
    record = store.read_freeze(freeze_id)
    revision = store.read_revision(record.revision_id)
    if revision.configuration != record.configuration:
        raise ValueError('frozen source configuration does not match its display revision')
    profile = read_configuration(db, record.configuration)
    normalize_display_rows(profile.directory, revision.rows)
    return FrozenSource(record, revision, profile)
