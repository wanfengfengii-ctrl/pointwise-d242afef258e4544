from dataclasses import dataclass

from issue.envelope import IssueEntry, StationPiece, body_fingerprint


@dataclass(frozen=True)
class VerifiedDelivery:
    entry: IssueEntry
    body: bytes


def verify_delivery(piece, entry):
    if not isinstance(piece, StationPiece) or not isinstance(entry, IssueEntry):
        raise ValueError('a station piece and its trusted issue entry are required')
    if piece.entry != entry:
        raise ValueError('station piece identity or origin conflicts with the issue entry')
    if body_fingerprint(piece.body) != entry.body_sha256:
        raise ValueError('station body digest conflicts with the issue entry')
    return VerifiedDelivery(entry, piece.body)
