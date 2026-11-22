import json
import sqlite3
import unittest
from contextlib import closing
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory

from capture.freezing import freeze
from capture.imports import ingest
from issue.register import issue_piece, read_issue_entry
from profiles.catalog import configure
from receive.intake import receive_piece
from reports.results import ComparisonResult, DifferenceInterval
from workbench import initialize_review, initialize_station


ZERO_ROWS = (('X', 0), ('Y', 0))
ODD_ROWS = (('X', 1), ('Y', 0))


def interval(lower, upper, lower_closed=True, upper_closed=True):
    return ComparisonResult('compatible', DifferenceInterval(Fraction(lower), Fraction(upper),
                                                            lower_closed, upper_closed))


def report_counts(db):
    return (
        db.execute('SELECT COUNT(*) FROM reports').fetchone()[0],
        db.execute('SELECT COUNT(*) FROM report_acknowledgments').fetchone()[0],
    )


def display_counts(db):
    return (
        db.execute('SELECT COUNT(*) FROM display_revisions').fetchone()[0],
        db.execute('SELECT COUNT(*) FROM display_rows').fetchone()[0],
    )


def scenario(case_id, inputs, expected, actual, downstream_expected, downstream_actual, paths, oracle):
    print('POINTWISE_SCENARIO ' + json.dumps({
        'case_id': case_id, 'input': inputs, 'expected': expected, 'actual': actual,
        'downstream_expected': downstream_expected, 'downstream_actual': downstream_actual,
        'code_paths': paths, 'oracle': oracle,
    }, sort_keys=True))


class ProjectCase(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory(prefix='hengjia-tests-')))

    def open_station(self, name):
        db = self.enterContext(closing(sqlite3.connect(self.root / f'{name}.sqlite')))
        initialize_station(db)
        return db

    def open_review(self):
        db = self.enterContext(closing(sqlite3.connect(self.root / 'review.sqlite')))
        initialize_review(db)
        return db

    def prepare(self, db, station, rows=ZERO_ROWS, *, batch='batch-17', offsets=(0, 0), coefficients=None):
        if coefficients is None:
            coefficients = {name: 1 for name, _ in rows}
        reference = configure(db, batch, station, tuple(coefficients), coefficients, offsets)
        revision = ingest(db, reference, rows)
        return freeze(db, revision.revision_id)

    def transfer(self, db, review, source):
        piece, entry = issue_piece(db, source.freeze_id)
        trusted = read_issue_entry(db, entry.origin.issue_id)
        self.assertEqual(trusted, entry)
        return receive_piece(review, piece, trusted), piece, trusted

    def offline_pair(self, review, *, rows_a=ZERO_ROWS, rows_b=ZERO_ROWS, offsets_a=(0, 0), offsets_b=(0, 0),
                     scale_a=None, scale_b=None, batch_a='batch-17', batch_b='batch-17'):
        a, b = self.open_station('a'), self.open_station('b')
        source_a = self.prepare(a, 'A', rows_a, batch=batch_a, offsets=offsets_a, coefficients=scale_a)
        source_b = self.prepare(b, 'B', rows_b, batch=batch_b, offsets=offsets_b, coefficients=scale_b)
        left = self.transfer(a, review, source_a)
        right = self.transfer(b, review, source_b)
        a.close()
        b.close()
        return left, right
