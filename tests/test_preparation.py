from fractions import Fraction

from capture.freezing import freeze, load_frozen_source
from capture.imports import ingest
from capture.storage import CaptureStore
from profiles.catalog import configure, read_configuration
from tests.fixtures import ProjectCase, ZERO_ROWS, display_counts


class TestPreparation(ProjectCase):
    def test_freeze_keeps_configuration(self):
        db = self.open_station('a')
        old = self.prepare(db, 'A')
        new = configure(db, 'batch-17', 'A', ('Y', 'X'), {'X': 2, 'Y': 3}, (-1, 1))
        self.assertNotEqual(new, old.profile.reference)
        old_again = load_frozen_source(db, old.freeze_id)
        self.assertEqual(old_again, old)
        self.assertEqual(dict(old_again.profile.scale.coefficients), {'X': Fraction(1), 'Y': Fraction(1)})
        recent = ingest(db, new, ZERO_ROWS)
        self.assertEqual(freeze(db, recent.revision_id).profile.reference, new)
        self.assertEqual(freeze(db, old.revision.revision_id).freeze_id, old.freeze_id)
        with self.assertRaises(KeyError):
            freeze(db, 'unknown-display')
        self.assertEqual(db.execute('SELECT COUNT(*) FROM frozen_sources').fetchone()[0], 2)

    def test_invalid_configuration(self):
        db = self.open_station('a')
        old = self.prepare(db, 'A').profile
        cases = [
            (('X', 'Y'), {'X': 0, 'Y': 1}, (0, 0)),
            (('X', 'Y'), {'X': 1, 'Y': 1}, (1, 0)),
            (('X', 'Y', 'Z'), {'X': 1, 'Y': 1, 'Z': 1}, (0, 0)),
            (('X', 'Y'), {'X': True, 'Y': 1}, (0, 0)),
        ]
        for names, coefficients, bounds in cases:
            with self.subTest(coefficients=coefficients, bounds=bounds):
                with self.assertRaises(ValueError):
                    configure(db, 'batch-17', 'A', names, coefficients, bounds)
        self.assertEqual(read_configuration(db, old.reference), old)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM profile_revisions').fetchone()[0], 1)

    def test_incomplete_display_batch(self):
        db = self.open_station('a')
        original = self.prepare(db, 'A')
        before = display_counts(db)
        for rows in ((('X', 0),), (('X', 0), ('U', 0)), (('X', 1.0), ('Y', 0)), (('X', True), ('Y', 0))):
            with self.subTest(rows=rows):
                with self.assertRaises(ValueError):
                    ingest(db, original.profile.reference, rows)
                self.assertEqual(display_counts(db), before)
        self.assertEqual(load_frozen_source(db, original.freeze_id), original)

    def test_three_channel_coverage(self):
        db = self.open_station('a')
        source = self.prepare(db, 'A', (('Z', 5), ('X', 3), ('Y', 4)))
        before = display_counts(db)
        for rows in ((('X', 3), ('Y', 4)), (('X', 3), ('X', 7), ('Y', 4), ('Z', 5))):
            with self.subTest(rows=rows):
                with self.assertRaises(ValueError):
                    ingest(db, source.profile.reference, rows)
                self.assertEqual(display_counts(db), before)
        self.assertEqual(CaptureStore(db).read_revision(source.revision.revision_id), source.revision)
        self.assertEqual(load_frozen_source(db, source.freeze_id), source)
