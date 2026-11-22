from dataclasses import dataclass

from receive.holdings import Receipt, ReceiptStore


@dataclass(frozen=True)
class ComparisonRequest:
    left_receipt_id: int
    right_receipt_id: int
    minuend: str
    subtrahend: str


@dataclass(frozen=True)
class SelectedReceipts:
    request: ComparisonRequest
    left: Receipt
    right: Receipt


def select_receipts(db, request):
    if not isinstance(request, ComparisonRequest):
        raise ValueError('expected a comparison request')
    store = ReceiptStore(db)
    left = store.read_receipt(request.left_receipt_id)
    right = store.read_receipt(request.right_receipt_id)
    left_origin, right_origin = left.entry.origin, right.entry.origin
    if left_origin.station == right_origin.station:
        raise ValueError('comparison requires two different stations')
    if left_origin.batch != right_origin.batch or left_origin.channels != right_origin.channels:
        raise ValueError('comparison requires a common batch and channel directory')
    channels = left_origin.channels
    if request.minuend == request.subtrahend:
        raise ValueError('comparison requires two distinct channels')
    if request.minuend not in channels or request.subtrahend not in channels:
        raise ValueError('requested channel is outside the directory')
    return SelectedReceipts(request, left, right)
