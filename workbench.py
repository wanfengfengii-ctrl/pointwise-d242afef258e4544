import argparse
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from capture.freezing import freeze
from capture.imports import ingest
from capture.storage import CaptureStore
from issue.register import initialize_issue_store, issue_piece, read_issue_entry
from profiles.catalog import configure
from profiles.storage import ProfileStore
from receive.holdings import ReceiptStore
from receive.intake import receive_piece
from reports.history import read_report
from reports.publish import compare
from reports.requests import ComparisonRequest
from reports.results import encode_result
from reports.storage import ReportStore


def initialize_station(db):
    db.execute('PRAGMA foreign_keys = ON')
    ProfileStore(db).initialize()
    CaptureStore(db).initialize()
    initialize_issue_store(db)


def initialize_review(db):
    db.execute('PRAGMA foreign_keys = ON')
    ReceiptStore(db).initialize()
    ReportStore(db).initialize()


def _transfer(station, review, freeze_id):
    piece, entry = issue_piece(station, freeze_id)
    registered = read_issue_entry(station, entry.origin.issue_id)
    return receive_piece(review, piece, registered)


def _sample(name):
    path = Path(__file__).resolve().parent / 'samples' / name
    return json.loads(path.read_text(encoding='utf-8'))


def demo():
    day, night, morning = (_sample(name) for name in ('day.json', 'night.json', 'morning.json'))
    with TemporaryDirectory(prefix='hengjia-') as temporary:
        root = Path(temporary)
        review_path = root / 'review.sqlite'
        paths, references, frozen, received = {}, {}, {}, {}
        with closing(sqlite3.connect(review_path)) as review:
            initialize_review(review)
            for index, incoming in enumerate(day['stations']):
                station = incoming['station']
                path = root / f'station-{index}.sqlite'
                paths[station] = path
                with closing(sqlite3.connect(path)) as source:
                    initialize_station(source)
                    reference = configure(source, day['batch'], station, day['channels'],
                                          incoming['coefficients'], incoming['offset_bounds'])
                    references[station] = reference
                    revision = ingest(source, reference, incoming['rows'])
                    frozen[station] = freeze(source, revision.revision_id).freeze_id
                    received[station] = _transfer(source, review, frozen[station])
            left, right = night['stations']
            old = compare(review, ComparisonRequest(received[left], received[right], *night['difference']))
            amended_station = morning['station']
            with closing(sqlite3.connect(paths[amended_station])) as source:
                initialize_station(source)
                amended = ingest(source, references[amended_station], morning['rows'], frozen[amended_station])
                amended_freeze = freeze(source, amended.revision_id)
                received[amended_station] = _transfer(source, review, amended_freeze.freeze_id)
            new = compare(review, ComparisonRequest(received[left], received[right], *night['difference']))
        with closing(sqlite3.connect(review_path)) as reopened:
            initialize_review(reopened)
            historical = (read_report(reopened, old.report_id), read_report(reopened, new.report_id))
            downstream = {
                'snapshots_unchanged': historical == (old, new),
                'old_receipts': [source.receipt_id for source in historical[0].sources],
                'new_receipts': [source.receipt_id for source in historical[1].sources],
                'acknowledged_reports': [report.acknowledgment.report_id for report in historical],
            }
            actual = [json.loads(encode_result(report.result)) for report in historical]
            expected = [night['expected'], morning['expected']]
            downstream_expected = morning['expected_history']
            if actual != expected or downstream != downstream_expected:
                raise RuntimeError('sample conclusions or historical provenance differ from the hand calculation')
            scenario = {
                'case_id': 'v10',
                'input': {'stations': day['stations'], 'difference': night['difference'], 'amendment': morning['rows']},
                'expected': expected, 'actual': actual,
                'downstream_expected': downstream_expected, 'downstream_actual': downstream,
                'code_paths': ['capture/imports.py', 'issue/register.py', 'receive/intake.py',
                               'reports/reconcile.py', 'reports/storage.py', 'reports/history.py'],
                'oracle': 'The original X cells share only an excluded half tick. After correction both cells are closed around zero and X minus Y spans minus one through one.',
            }
            print('POINTWISE_SCENARIO ' + json.dumps(scenario, sort_keys=True, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description='Hengjia bench comparison workbench')
    parser.add_argument('command', choices=('demo',))
    parser.parse_args()
    demo()


if __name__ == '__main__':
    main()
