import json
import sqlite3

from profiles.channels import build_directory, validate_name
from profiles.revisions import ProfileReference, ProfileRevision
from profiles.scales import make_station_scale


class ProfileStore:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def initialize(self):
        self.connection.executescript('''
            CREATE TABLE IF NOT EXISTS channel_directories (
                batch TEXT PRIMARY KEY,
                names TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS profile_revisions (
                version TEXT PRIMARY KEY,
                batch TEXT NOT NULL REFERENCES channel_directories(batch),
                station TEXT NOT NULL,
                coefficients TEXT NOT NULL,
                offset_lower TEXT NOT NULL,
                offset_upper TEXT NOT NULL
            );
        ''')

    def add_revision(self, revision):
        reference = revision.reference
        names = json.dumps(revision.directory.names, ensure_ascii=False, separators=(',', ':'))
        scale = revision.scale
        coefficients = json.dumps(
            {name: str(value) for name, value in scale.coefficients},
            ensure_ascii=False, separators=(',', ':'),
        )
        self.connection.execute('BEGIN IMMEDIATE')
        with self.connection:
            self.connection.execute(
                'INSERT INTO channel_directories(batch, names) VALUES (?, ?) ON CONFLICT(batch) DO NOTHING',
                (reference.batch, names),
            )
            current = self.connection.execute(
                'SELECT names FROM channel_directories WHERE batch = ?', (reference.batch,),
            ).fetchone()[0]
            if tuple(json.loads(current)) != revision.directory.names:
                raise ValueError('batch directory is already fixed')
            self.connection.execute('''
                INSERT INTO profile_revisions(version, batch, station, coefficients, offset_lower, offset_upper)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (reference.version, reference.batch, reference.station, coefficients,
                  str(scale.offset_lower), str(scale.offset_upper)))

    def read_revision(self, version):
        validate_name(version, 'configuration version')
        row = self.connection.execute('''
            SELECT p.batch, p.station, d.names, p.coefficients, p.offset_lower, p.offset_upper
            FROM profile_revisions AS p
            JOIN channel_directories AS d ON d.batch = p.batch
            WHERE p.version = ?
        ''', (version,)).fetchone()
        if row is None:
            raise KeyError(version)
        batch, station, names, coefficients, lower, upper = row
        directory = build_directory(batch, json.loads(names))
        scale = make_station_scale(directory, json.loads(coefficients), (lower, upper))
        return ProfileRevision(ProfileReference(version, batch, station), directory, scale)
