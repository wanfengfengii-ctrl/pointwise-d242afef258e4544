from uuid import uuid4

from capture.amendments import resolve_amendment_parent
from capture.observations import DisplayRevision, normalize_display_rows
from capture.storage import CaptureStore
from profiles.catalog import read_configuration


def ingest(db, reference, rows, parent_freeze_id=None):
    profile = read_configuration(db, reference)
    observations = normalize_display_rows(profile.directory, rows)
    parent = resolve_amendment_parent(db, parent_freeze_id, profile)
    revision = DisplayRevision(f'display-{uuid4().hex}', profile.reference, observations, parent)
    CaptureStore(db).save_revision(revision)
    return revision
