import sqlite3

from capture.freezing import load_frozen_source
from issue.body import encode_evidence_body
from issue.envelope import decode_issue_entry, encode_issue_entry, make_envelope
from issue.evidence import build_station_evidence
from profiles.channels import validate_name


def initialize_issue_store(db: sqlite3.Connection):
    db.execute('''
        CREATE TABLE IF NOT EXISTS issue_entries (
            issue_id TEXT PRIMARY KEY,
            freeze_id TEXT NOT NULL REFERENCES frozen_sources(freeze_id),
            entry TEXT NOT NULL
        )
    ''')


def issue_piece(db, freeze_id):
    source = load_frozen_source(db, freeze_id)
    evidence = build_station_evidence(source)
    piece = make_envelope(source, encode_evidence_body(evidence))
    entry = piece.entry
    db.execute('BEGIN IMMEDIATE')
    with db:
        db.execute('INSERT INTO issue_entries(issue_id, freeze_id, entry) VALUES (?, ?, ?)',
                   (entry.origin.issue_id, freeze_id, encode_issue_entry(entry)))
    return piece, entry


def read_issue_entry(db, issue_id):
    validate_name(issue_id, 'issue number')
    row = db.execute('SELECT entry FROM issue_entries WHERE issue_id = ?', (issue_id,)).fetchone()
    if row is None:
        raise KeyError(issue_id)
    return decode_issue_entry(row[0])
