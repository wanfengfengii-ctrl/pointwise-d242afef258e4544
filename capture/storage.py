import sqlite3
from dataclasses import dataclass
from uuid import uuid4

from capture.observations import DisplayRevision, DisplayRow
from profiles.channels import validate_name
from profiles.revisions import ProfileReference


@dataclass(frozen=True)
class FreezeRecord:
    freeze_id: str
    revision_id: str
    configuration: ProfileReference


class CaptureStore:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def initialize(self):
        self.connection.executescript('''
            CREATE TABLE IF NOT EXISTS display_revisions (
                revision_id TEXT PRIMARY KEY,
                profile_id TEXT NOT NULL REFERENCES profile_revisions(version),
                parent_freeze_id TEXT REFERENCES frozen_sources(freeze_id)
            );
            CREATE TABLE IF NOT EXISTS display_rows (
                revision_id TEXT NOT NULL REFERENCES display_revisions(revision_id),
                channel TEXT NOT NULL,
                ticks TEXT NOT NULL,
                PRIMARY KEY (revision_id, channel)
            );
            CREATE TABLE IF NOT EXISTS frozen_sources (
                freeze_id TEXT PRIMARY KEY,
                revision_id TEXT NOT NULL UNIQUE REFERENCES display_revisions(revision_id),
                profile_id TEXT NOT NULL REFERENCES profile_revisions(version)
            );
        ''')

    def save_revision(self, revision):
        self.connection.execute('BEGIN IMMEDIATE')
        with self.connection:
            self.connection.execute('''
                INSERT INTO display_revisions(revision_id, profile_id, parent_freeze_id) VALUES (?, ?, ?)
            ''', (revision.revision_id, revision.configuration.version, revision.parent_freeze_id))
            self.connection.executemany('''
                INSERT INTO display_rows(revision_id, channel, ticks) VALUES (?, ?, ?)
            ''', ((revision.revision_id, row.channel, str(row.ticks)) for row in revision.rows))

    def read_revision(self, revision_id):
        validate_name(revision_id, 'display revision number')
        header = self.connection.execute('''
            SELECT p.version, p.batch, p.station, d.parent_freeze_id
            FROM display_revisions AS d JOIN profile_revisions AS p ON p.version = d.profile_id
            WHERE d.revision_id = ?
        ''', (revision_id,)).fetchone()
        if header is None:
            raise KeyError(revision_id)
        version, batch, station, parent_id = header
        rows = self.connection.execute('''
            SELECT channel, ticks FROM display_rows WHERE revision_id = ? ORDER BY channel
        ''', (revision_id,))
        observations = tuple(DisplayRow(channel, int(ticks)) for channel, ticks in rows)
        return DisplayRevision(revision_id, ProfileReference(version, batch, station), observations, parent_id)

    def save_freeze(self, revision):
        candidate = f'freeze-{uuid4().hex}'
        self.connection.execute('BEGIN IMMEDIATE')
        with self.connection:
            self.connection.execute('''
                INSERT INTO frozen_sources(freeze_id, revision_id, profile_id) VALUES (?, ?, ?)
                ON CONFLICT(revision_id) DO NOTHING
            ''', (candidate, revision.revision_id, revision.configuration.version))
            saved = self.connection.execute(
                'SELECT freeze_id FROM frozen_sources WHERE revision_id = ?', (revision.revision_id,),
            ).fetchone()[0]
            record = self.read_freeze(saved)
        return record

    def read_freeze(self, freeze_id):
        validate_name(freeze_id, 'freeze number')
        row = self.connection.execute('''
            SELECT f.revision_id, p.version, p.batch, p.station
            FROM frozen_sources AS f JOIN profile_revisions AS p ON p.version = f.profile_id
            WHERE f.freeze_id = ?
        ''', (freeze_id,)).fetchone()
        if row is None:
            raise KeyError(freeze_id)
        revision_id, version, batch, station = row
        return FreezeRecord(freeze_id, revision_id, ProfileReference(version, batch, station))
