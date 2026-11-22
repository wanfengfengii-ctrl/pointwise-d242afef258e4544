from receive.holdings import ReceiptStore
from receive.provenance import VerifiedDelivery


def record_or_reuse_receipt(store: ReceiptStore, delivery: VerifiedDelivery):
    existing = store.find_by_issue(delivery.entry.origin.issue_id)
    if existing is None:
        return store.insert_receipt(delivery)
    if existing.entry != delivery.entry or existing.body != delivery.body:
        raise ValueError('delivery conflicts with the recorded receipt for this issue')
    return existing.receipt_id
