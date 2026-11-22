import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass

from issue.envelope import IssueEntry, decode_issue_entry, encode_issue_entry


@dataclass(frozen=True)
class ReceiptSource:
    receipt_id: int
    entry: IssueEntry


@dataclass(frozen=True)
class Receipt:
    receipt_id: int
    entry: IssueEntry
    body: bytes

    @property
    def source(self):
        return ReceiptSource(self.receipt_id, self.entry)


class ReceiptStore:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def initialize(self):
        self.connection.execute('''
            CREATE TABLE IF NOT EXISTS receipts (
                receipt_id INTEGER PRIMARY KEY,
                issue_id TEXT NOT NULL UNIQUE,
                entry TEXT NOT NULL,
                body BLOB NOT NULL
            )
        ''')

    @staticmethod
    def _receipt(row):
        receipt_id, entry, body = row
        return Receipt(receipt_id, decode_issue_entry(entry), body)

    def read_receipt(self, receipt_id):
        if type(receipt_id) is not int or receipt_id <= 0:
            raise ValueError('invalid receipt number')
        # A valid but unknown Python integer may exceed SQLite's signed key range.
        if receipt_id > (1 << 63) - 1:
            raise KeyError(receipt_id)
        row = self.connection.execute(
            'SELECT receipt_id, entry, body FROM receipts WHERE receipt_id = ?', (receipt_id,),
        ).fetchone()
        if row is None:
            raise KeyError(receipt_id)
        return self._receipt(row)

    def find_by_issue(self, issue_id):
        row = self.connection.execute(
            'SELECT receipt_id, entry, body FROM receipts WHERE issue_id = ?', (issue_id,),
        ).fetchone()
        return self._receipt(row) if row is not None else None

    def insert_receipt(self, delivery):
        if not self.connection.in_transaction:
            raise RuntimeError('receipt insertion requires a write transaction')
        cursor = self.connection.execute(
            'INSERT INTO receipts(issue_id, entry, body) VALUES (?, ?, ?)',
            (delivery.entry.origin.issue_id, encode_issue_entry(delivery.entry), delivery.body),
        )
        return cursor.lastrowid

    @contextmanager
    def write_transaction(self):
        self.connection.execute('BEGIN IMMEDIATE')
        with self.connection:
            yield
