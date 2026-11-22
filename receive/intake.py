from receive.deduplication import record_or_reuse_receipt
from receive.holdings import ReceiptStore
from receive.provenance import verify_delivery


def receive_piece(db, piece, entry):
    delivery = verify_delivery(piece, entry)
    store = ReceiptStore(db)
    with store.write_transaction():
        receipt_id = record_or_reuse_receipt(store, delivery)
    return receipt_id
