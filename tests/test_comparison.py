import json
from fractions import Fraction

from capture.imports import ingest
from issue.register import issue_piece, read_issue_entry
from receive.holdings import ReceiptStore
from reports.history import read_report
from reports.publish import compare
from reports.requests import ComparisonRequest
from reports.results import ComparisonResult, encode_result
from tests.fixtures import ODD_ROWS, ProjectCase, interval, scenario


class TestComparison(ProjectCase):
    def assert_signed(self, review, left, right, expected, first='X', second='Y', message=None):
        request = ComparisonRequest(left[0], right[0], first, second)
        report = compare(review, request)
        self.assertEqual(report.result, expected, message)
        self.assertEqual(report.request, request)
        self.assertEqual([item.receipt_id for item in report.sources], [left[0], right[0]])
        self.assertEqual([item.entry for item in report.sources], [left[2], right[2]])
        self.assertEqual(report.acknowledgment.report_id, report.report_id)
        self.assertEqual(read_report(review, report.report_id), report)
        return report

    def test_shared_offset(self):
        review = self.open_review()
        left, right = self.offline_pair(review, offsets_a=(-1, 1), offsets_b=(-1, 1))
        report = self.assert_signed(review, left, right, interval(-1, 1))
        saved = read_report(review, report.report_id)
        actual = json.loads(encode_result(report.result))
        expected = {'status': 'compatible', 'difference': {'lower': '-1', 'upper': '1',
                                                           'lower_closed': True, 'upper_closed': True}}
        scenario('v3', {'ticks': [[0, 0], [0, 0]], 'offsets': [[-1, 1], [-1, 1]]}, expected, actual,
                 [left[0], right[0]], [source.receipt_id for source in saved.sources],
                 ['issue/evidence.py', 'reports/reconcile.py', 'reports/storage.py'],
                 'The shared offset cancels on subtraction. At zero offset the endpoint tick pairs are both allowed.')

    def test_named_order(self):
        review = self.open_review()
        left, right = self.offline_pair(
            review, rows_a=(('Z', 4), ('X', 0), ('Y', 2)), rows_b=(('Y', 2), ('Z', 4), ('X', 0)),
            offsets_a=(-1, 1), offsets_b=(-1, 1),
        )
        self.assertEqual(left[1].body, right[1].body)
        self.assert_signed(review, left, right, interval(-3, -1))
        self.assert_signed(review, right, left, interval(1, 3), 'Y', 'X')

    def test_unrequested_channel(self):
        review = self.open_review()
        left, right = self.offline_pair(
            review, rows_a=(('X', 0), ('Y', 0), ('Z', 0)), rows_b=(('X', 0), ('Y', 0), ('Z', 4)),
            offsets_a=(-1, 1), offsets_b=(-1, 1),
        )
        self.assert_signed(review, left, right, ComparisonResult('incompatible', None))

    def test_half_tick_contact(self):
        review = self.open_review()
        left, right = self.offline_pair(review, rows_b=ODD_ROWS)
        store = ReceiptStore(review)
        self.assertEqual(store.read_receipt(left[0]).body, left[1].body)
        self.assertEqual(store.read_receipt(right[0]).body, right[1].body)
        report = self.assert_signed(review, left, right, ComparisonResult('incompatible', None),
                                    message='HALF_TICK_CONTACT_WRONG_RESULT')
        saved = read_report(review, report.report_id)
        scenario('v4', {'ticks': [[0, 0], [1, 0]], 'offsets': [0, 0], 'difference': ['X', 'Y']},
                 {'status': 'incompatible', 'difference': None}, json.loads(encode_result(report.result)),
                 [left[0], right[0]], [item.receipt_id for item in saved.sources],
                 ['issue/register.py', 'receive/intake.py', 'reports/reconcile.py', 'reports/history.py'],
                 'The only point of contact for the X cells is one half, which rounds to zero.')

    def test_equal_closed_marginals_do_not_determine_compatibility(self):
        review = self.open_review()
        left, right = self.offline_pair(review, rows_b=(('X', 0), ('Y', -1)), offsets_b=(-1, -1))
        self.assert_signed(review, left, right, interval(0, 1, False, False))

    def test_repeatable_body(self):
        db = self.open_station('a')
        source = self.prepare(db, 'A', offsets=(-1, 1))
        first, entry = issue_piece(db, source.freeze_id)
        db.close()
        reopened = self.open_station('a')
        second, new_entry = issue_piece(reopened, source.freeze_id)
        self.assertEqual(first.body, second.body)
        self.assertEqual(entry.body_sha256, new_entry.body_sha256)
        self.assertEqual(read_issue_entry(reopened, entry.origin.issue_id), entry)
        self.assertEqual(new_entry.origin.freeze_id, entry.origin.freeze_id)
        self.assertNotEqual(new_entry.origin.issue_id, entry.origin.issue_id)

    def test_unfrozen_source(self):
        db = self.open_station('a')
        source = self.prepare(db, 'A')
        issue_piece(db, source.freeze_id)
        unfrozen = ingest(db, source.profile.reference, ODD_ROWS)
        with self.assertRaises(KeyError):
            issue_piece(db, unfrozen.revision_id)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM issue_entries').fetchone()[0], 1)

    def test_open_ends(self):
        review = self.open_review()
        left, right = self.offline_pair(review, rows_a=ODD_ROWS, rows_b=ODD_ROWS)
        self.assert_signed(review, left, right, interval(0, 2, False, False))

    def test_reversed_request(self):
        review = self.open_review()
        left, right = self.offline_pair(review, rows_a=ODD_ROWS, rows_b=ODD_ROWS)
        self.assert_signed(review, left, right, interval(-2, 0, False, False), 'Y', 'X')

    def test_asymmetric_ends(self):
        review = self.open_review()
        left, right = self.offline_pair(review, rows_b=ODD_ROWS, offsets_b=('1/4', '1/4'))
        self.assert_signed(review, left, right, interval(0, 1, False, True))
        self.assert_signed(review, left, right, interval(-1, 0, True, False), 'Y', 'X')

    def test_closed_singleton(self):
        review = self.open_review()
        scale = {'X': 1, 'Y': 3}
        rows = (('X', 0), ('Y', 2))
        left, right = self.offline_pair(review, rows_a=rows, rows_b=rows, offsets_b=(1, 1),
                                        scale_a=scale, scale_b=scale)
        x, y = Fraction(-1, 2), Fraction(1, 2)
        for offset in (0, 1):
            self.assertEqual((round(x + offset), round(3 * y + offset)), (0, 2))
        self.assert_signed(review, left, right, interval(-1, -1))

    # --- regressions for the night-shift misticket -------------------------

    def test_half_tick_contact_keeps_provenance(self):
        """The incident case must still record both receipts and acknowledgment."""
        review = self.open_review()
        left, right = self.offline_pair(review, rows_b=ODD_ROWS)
        report = self.assert_signed(review, left, right, ComparisonResult('incompatible', None))
        self.assertIsNone(report.result.difference)
        saved = read_report(review, report.report_id)
        self.assertEqual([item.receipt_id for item in saved.sources], [left[0], right[0]])
        self.assertEqual([item.entry for item in saved.sources], [left[2], right[2]])
        self.assertEqual(saved.acknowledgment.report_id, report.report_id)
        reopened = self.open_review()
        self.assertEqual(read_report(reopened, report.report_id), report)

    def test_shared_offset_is_joint_not_per_axis(self):
        """A station cannot mix offsets across channels; the offset is one value per freeze."""
        review = self.open_review()
        left, right = self.offline_pair(review, offsets_a=(-1, 1), offsets_b=(-1, 1))
        self.assert_signed(review, left, right, interval(-1, 1))

    def test_unrequested_third_channel_blocks_incompatible(self):
        review = self.open_review()
        left, right = self.offline_pair(
            review, rows_a=(('X', 0), ('Y', 0), ('Z', 0)), rows_b=(('X', 0), ('Y', 0), ('Z', 4)),
            offsets_a=(-1, 1), offsets_b=(-1, 1),
        )
        self.assert_signed(review, left, right, ComparisonResult('incompatible', None))

    def test_interval_merely_touching_at_excluded_endpoint(self):
        """Equal, closed per-axis ranges are not enough; the joint point is excluded."""
        review = self.open_review()
        left, right = self.offline_pair(review, rows_b=(('X', 0), ('Y', -1)), offsets_b=(-1, -1))
        self.assert_signed(review, left, right, interval(0, 1, False, False))
