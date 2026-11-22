from issue.body import decode_evidence_body
from reports.requests import SelectedReceipts
from reports.results import ComparisonResult, DifferenceInterval


def _closed_channel_ranges(bounds, count):
    lower = [None] * count
    upper = [None] * count
    for bound in bounds:
        terms = [(index, weight) for index, weight in enumerate(bound.weights) if weight]
        if len(terms) != 1:
            continue
        index, weight = terms[0]
        limit = bound.limit / weight
        if weight < 0:
            lower[index] = limit if lower[index] is None else max(lower[index], limit)
        else:
            upper[index] = limit if upper[index] is None else min(upper[index], limit)
    if None in lower or None in upper:
        raise ValueError("station evidence does not bound the channel directory")
    return lower, upper


def reconcile_difference(selected: SelectedReceipts):
    left = decode_evidence_body(selected.left.body)
    right = decode_evidence_body(selected.right.body)
    names = selected.left.entry.origin.channels
    if left.channels != names or right.channels != names:
        raise ValueError("body channels conflict with the selected directory")
    left_lower, left_upper = _closed_channel_ranges(left.bounds, len(names))
    right_lower, right_upper = _closed_channel_ranges(right.bounds, len(names))
    lower = tuple(map(max, left_lower, right_lower))
    upper = tuple(map(min, left_upper, right_upper))
    if any(start > end for start, end in zip(lower, upper)):
        return ComparisonResult("incompatible", None)
    request = selected.request
    first, second = names.index(request.minuend), names.index(request.subtrahend)
    interval = DifferenceInterval(lower[first] - upper[second], upper[first] - lower[second], True, True)
    return ComparisonResult("compatible", interval)
