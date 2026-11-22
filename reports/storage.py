import sqlite3
from dataclasses import dataclass

from issue.envelope import decode_issue_entry, encode_issue_entry
from receive.holdings import ReceiptSource
from reports.requests import ComparisonRequest, SelectedReceipts
from reports.results import ComparisonResult, decode_result, encode_result


@dataclass(frozen=True)
class ReportAcknowledgment:
    acknowledgment_id: int
    report_id: int


@dataclass(frozen=True)
class PublishedComparison:
    report_id: int
    request: ComparisonRequest
    sources: tuple[ReceiptSource, ReceiptSource]
    result: ComparisonResult
    acknowledgment: ReportAcknowledgment


class ReportStore:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def initialize(self):
        self.connection.executescript('''
            CREATE TABLE IF NOT EXISTS reports (
                report_id INTEGER PRIMARY KEY,
                left_receipt INTEGER NOT NULL REFERENCES receipts(receipt_id),
                right_receipt INTEGER NOT NULL REFERENCES receipts(receipt_id),
                minuend TEXT NOT NULL,
                subtrahend TEXT NOT NULL,
                left_entry TEXT NOT NULL,
                right_entry TEXT NOT NULL,
                result TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS report_acknowledgments (
                acknowledgment_id INTEGER PRIMARY KEY,
                report_id INTEGER NOT NULL UNIQUE REFERENCES reports(report_id)
            );
        ''')

    def save_pair(self, selected: SelectedReceipts, result: ComparisonResult):
        request = selected.request
        left, right = selected.left.source, selected.right.source
        payload = (
            left.receipt_id, right.receipt_id, request.minuend, request.subtrahend,
            encode_issue_entry(left.entry), encode_issue_entry(right.entry), encode_result(result),
        )
        self.connection.execute('BEGIN IMMEDIATE')
        with self.connection:
            report_id = self.connection.execute('''
                INSERT INTO reports(left_receipt, right_receipt, minuend, subtrahend, left_entry, right_entry, result)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', payload).lastrowid
            acknowledgment_id = self.connection.execute(
                'INSERT INTO report_acknowledgments(report_id) VALUES (?)', (report_id,),
            ).lastrowid
        acknowledgment = ReportAcknowledgment(acknowledgment_id, report_id)
        return PublishedComparison(report_id, request, (left, right), result, acknowledgment)

    def read_snapshot(self, report_id):
        if type(report_id) is not int or report_id <= 0:
            raise ValueError('invalid report number')
        if report_id > (1 << 63) - 1:
            raise KeyError(report_id)
        row = self.connection.execute('''
            SELECT r.left_receipt, r.right_receipt, r.minuend, r.subtrahend,
                   r.left_entry, r.right_entry, r.result, a.acknowledgment_id
            FROM reports AS r JOIN report_acknowledgments AS a ON a.report_id = r.report_id
            WHERE r.report_id = ?
        ''', (report_id,)).fetchone()
        if row is None:
            raise KeyError(report_id)
        left_id, right_id, first, second, left_data, right_data, result, ack_id = row
        request = ComparisonRequest(left_id, right_id, first, second)
        sources = (
            ReceiptSource(left_id, decode_issue_entry(left_data)),
            ReceiptSource(right_id, decode_issue_entry(right_data)),
        )
        return PublishedComparison(report_id, request, sources, decode_result(result),
                                   ReportAcknowledgment(ack_id, report_id))
