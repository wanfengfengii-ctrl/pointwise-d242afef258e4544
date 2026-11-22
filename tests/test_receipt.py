from dataclasses import replace

from issue.envelope import body_fingerprint
from issue.register import issue_piece
from receive.holdings import ReceiptStore
from receive.intake import receive_piece
from tests.fixtures import ProjectCase


class TestReceipt(ProjectCase):
    def test_redelivery_and_conflict(self):
        db, review = self.open_station('a'), self.open_review()
        source = self.prepare(db, 'A')
        receipt_id, piece, entry = self.transfer(db, review, source)
        store = ReceiptStore(review)
        saved = store.read_receipt(receipt_id)
        self.assertEqual(saved.body, piece.body)
        self.assertEqual(saved.entry, entry)
        self.assertEqual(receive_piece(review, piece, entry), receipt_id)

        changed_body = piece.body + b' '
        with self.assertRaises(ValueError):
            receive_piece(review, replace(piece, body=changed_body), entry)
        with self.assertRaises(ValueError):
            receive_piece(review, piece, replace(entry, origin=replace(entry.origin, station='B')))

        # Even a separately consistent pair cannot redefine a recorded issue identity.
        changed_entry = replace(entry, body_sha256=body_fingerprint(changed_body))
        with self.assertRaises(ValueError):
            receive_piece(review, replace(piece, entry=changed_entry, body=changed_body), changed_entry)
        self.assertEqual(store.read_receipt(receipt_id), saved)
        self.assertEqual(review.execute('SELECT COUNT(*) FROM receipts').fetchone()[0], 1)
        fresh_piece, fresh_entry = issue_piece(db, source.freeze_id)
        with self.assertRaises(ValueError):
            receive_piece(review, fresh_piece, entry)
        self.assertEqual(review.execute('SELECT COUNT(*) FROM receipts').fetchone()[0], 1)
        self.assertNotEqual(fresh_entry.origin.issue_id, entry.origin.issue_id)

    def test_redelivery_after_reopen(self):
        db, review = self.open_station('a'), self.open_review()
        receipt_id, piece, entry = self.transfer(db, review, self.prepare(db, 'A'))
        saved = ReceiptStore(review).read_receipt(receipt_id)
        db.close()
        review.close()
        reopened = self.open_review()
        self.assertEqual(receive_piece(reopened, piece, entry), receipt_id)
        self.assertEqual(ReceiptStore(reopened).read_receipt(receipt_id), saved)
        self.assertEqual(reopened.execute('SELECT COUNT(*) FROM receipts').fetchone()[0], 1)
