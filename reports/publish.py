from reports.reconcile import reconcile_difference
from reports.requests import select_receipts
from reports.storage import ReportStore


def compare(db, request):
    selected = select_receipts(db, request)
    result = reconcile_difference(selected)
    return ReportStore(db).save_pair(selected, result)
