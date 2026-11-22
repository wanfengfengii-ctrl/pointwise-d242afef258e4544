from reports.storage import ReportStore


def read_report(db, report_id):
    return ReportStore(db).read_snapshot(report_id)
