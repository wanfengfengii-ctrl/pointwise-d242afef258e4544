import sqlite3

from capture.freezing import freeze, load_frozen_source
from capture.imports import ingest
from capture.storage import CaptureStore
from issue.register import read_issue_entry
from profiles.catalog import configure, read_configuration
from receive.holdings import ReceiptStore
from receive.intake import receive_piece
from reports.history import read_report
from reports.publish import compare
from reports.requests import ComparisonRequest
from reports.results import ComparisonResult
from tests.fixtures import ODD_ROWS, ZERO_ROWS, ProjectCase, display_counts, interval, report_counts
from workbench import initialize_review, initialize_station


class TestPublishing(ProjectCase):
    def test_mixed_batch(self):
        review = self.open_review()
        left, right = self.offline_pair(review, batch_b='another-batch')
        with self.assertRaises(ValueError):
            compare(review, ComparisonRequest(left[0], right[0], 'X', 'Y'))
        self.assertEqual(report_counts(review), (0, 0))

    def test_invalid_selection(self):
        review = self.open_review()
        a, b = self.open_station('a'), self.open_station('b')
        old_a = self.prepare(a, 'A')
        left = self.transfer(a, review, old_a)[0]
        other_a = self.transfer(a, review, self.prepare(a, 'A', ODD_ROWS))[0]
        right = self.transfer(b, review, self.prepare(b, 'B'))[0]
        a.close()
        b.close()
        cases = (
            (ComparisonRequest(left, 9999, 'X', 'Y'), KeyError),
            (ComparisonRequest(left, other_a, 'X', 'Y'), ValueError),
            (ComparisonRequest(left, right, 'X', 'X'), ValueError),
            (ComparisonRequest(left, right, 'X', 'Z'), ValueError),
            (ComparisonRequest(True, right, 'X', 'Y'), ValueError),
        )
        for request, error in cases:
            with self.subTest(request=request):
                with self.assertRaises(error):
                    compare(review, request)
                self.assertEqual(report_counts(review), (0, 0))
        self.assertEqual(compare(review, ComparisonRequest(left, right, 'X', 'Y')).result, interval(-1, 1))

    def test_report_receipt_rollback(self):
        review = self.open_review()
        left, right = self.offline_pair(review)
        request = ComparisonRequest(left[0], right[0], 'X', 'Y')
        old = compare(review, request)
        review.execute('''
            CREATE TRIGGER refuse_report_ack BEFORE INSERT ON report_acknowledgments
            BEGIN SELECT RAISE(ABORT, 'fixture refused report acknowledgment'); END
        ''')
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'fixture refused report acknowledgment'):
            compare(review, request)
        self.assertEqual(report_counts(review), (1, 1))
        review.close()
        reopened = self.open_review()
        self.assertEqual(report_counts(reopened), (1, 1))
        self.assertEqual(read_report(reopened, old.report_id), old)
        with self.assertRaises(KeyError):
            read_report(reopened, old.report_id + 1)
        reopened.execute('DROP TRIGGER refuse_report_ack')
        next_report = compare(reopened, request)
        self.assertEqual(next_report.result, old.result)
        self.assertEqual(read_report(reopened, next_report.report_id), next_report)
        self.assertEqual(report_counts(reopened), (2, 2))

    def test_invalid_parent(self):
        db = self.open_station('a')
        first = self.prepare(db, 'A')
        other = self.prepare(db, 'B', ODD_ROWS)
        before = display_counts(db)
        with self.assertRaises(ValueError):
            ingest(db, first.profile.reference, ZERO_ROWS, other.freeze_id)
        with self.assertRaises(KeyError):
            ingest(db, first.profile.reference, ZERO_ROWS, 'no-parent')
        another_batch = self.prepare(db, 'A', batch='another-batch')
        with self.assertRaises(ValueError):
            ingest(db, first.profile.reference, ZERO_ROWS, another_batch.freeze_id)
        self.assertEqual(display_counts(db), (before[0] + 1, before[1] + 2))
        self.assertEqual(load_frozen_source(db, first.freeze_id), first)
        self.assertEqual(load_frozen_source(db, other.freeze_id), other)

    def _publish_amendment(self):
        review = self.open_review()
        a, b = self.open_station('a'), self.open_station('b')
        original_a = self.prepare(a, 'A')
        original_b = self.prepare(b, 'B', ODD_ROWS)
        left = self.transfer(a, review, original_a)
        right = self.transfer(b, review, original_b)
        a.close()
        b.close()
        old = compare(review, ComparisonRequest(left[0], right[0], 'X', 'Y'))
        self.assertEqual(old.result, ComparisonResult('incompatible', None))

        b = self.open_station('b')
        new_ref = configure(b, 'batch-17', 'B', ('X', 'Y'), {'X': 1, 'Y': 1}, (0, 0))
        amended = ingest(b, new_ref, ZERO_ROWS, original_b.freeze_id)
        corrected = freeze(b, amended.revision_id)
        new_right = self.transfer(b, review, corrected)
        b.close()
        new = compare(review, ComparisonRequest(left[0], new_right[0], 'X', 'Y'))
        self.assertEqual(new.result, interval(-1, 1))
        self.assertNotEqual(old.report_id, new.report_id)
        self.assertEqual([source.entry for source in old.sources], [left[2], right[2]])
        self.assertEqual([source.entry for source in new.sources], [left[2], new_right[2]])
        review.close()
        return old, new, original_b, corrected, right, new_right

    def test_amend_and_reopen(self):
        old, new, original, corrected, right, new_right = self._publish_amendment()
        reopened = self.open_review()
        self.assertEqual(read_report(reopened, old.report_id), old)
        self.assertEqual(read_report(reopened, new.report_id), new)
        self.assertEqual(old.sources[1].entry.origin.freeze_id, original.freeze_id)
        self.assertEqual(new.sources[1].entry.origin.freeze_id, corrected.freeze_id)
        self.assertEqual((old.sources[1].receipt_id, new.sources[1].receipt_id), (right[0], new_right[0]))
        self.assertEqual((old.acknowledgment.report_id, new.acknowledgment.report_id), (old.report_id, new.report_id))
        self.assertEqual(report_counts(reopened), (2, 2))

    def test_unknown_report(self):
        old, new, *_ = self._publish_amendment()
        reopened = self.open_review()
        with self.assertRaises(KeyError):
            read_report(reopened, new.report_id + 100)
        self.assertEqual(read_report(reopened, old.report_id), old)
        self.assertEqual(read_report(reopened, new.report_id), new)
        self.assertEqual(report_counts(reopened), (2, 2))

    def test_reinitialize(self):
        old, new, original, corrected, right, new_right = self._publish_amendment()
        review, station = self.open_review(), self.open_station('b')
        initialize_review(review)
        initialize_station(station)
        review.close()
        station.close()
        review, station = self.open_review(), self.open_station('b')
        self.assertEqual(read_configuration(station, original.profile.reference), original.profile)
        self.assertEqual(read_configuration(station, corrected.profile.reference), corrected.profile)
        revision = CaptureStore(station).read_revision(corrected.revision.revision_id)
        self.assertEqual(revision.parent_freeze_id, original.freeze_id)
        self.assertEqual(load_frozen_source(station, revision.parent_freeze_id), original)
        self.assertEqual(load_frozen_source(station, corrected.freeze_id), corrected)
        for receipt_id, piece, entry in (right, new_right):
            self.assertEqual(read_issue_entry(station, entry.origin.issue_id), entry)
            saved = ReceiptStore(review).read_receipt(receipt_id)
            self.assertEqual((saved.body, saved.entry), (piece.body, entry))
        self.assertEqual(receive_piece(review, right[1], right[2]), right[0])
        self.assertEqual(review.execute('SELECT COUNT(*) FROM receipts').fetchone()[0], 3)
        self.assertEqual(read_report(review, old.report_id), old)
        self.assertEqual(read_report(review, new.report_id), new)
        self.assertEqual(report_counts(review), (2, 2))
