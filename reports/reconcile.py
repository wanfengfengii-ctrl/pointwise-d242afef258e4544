from fractions import Fraction
from itertools import combinations

from issue.body import decode_evidence_body
from reports.requests import SelectedReceipts
from reports.results import ComparisonResult, DifferenceInterval


def _check_bounded(bounds, count):
    """Every channel must be pinned from both sides for the difference to be finite."""
    lower = [False] * count
    upper = [False] * count
    for bound in bounds:
        terms = [(index, weight) for index, weight in enumerate(bound.weights) if weight]
        if len(terms) != 1:
            continue
        index, weight = terms[0]
        if weight < 0:
            lower[index] = True
        else:
            upper[index] = True
    if not all(lower) or not all(upper):
        raise ValueError("station evidence does not bound the channel directory")


def _solve(matrix, limits):
    size = len(matrix)
    rows = [[Fraction(value) for value in row] + [Fraction(limit)]
            for row, limit in zip(matrix, limits)]
    for column in range(size):
        pivot = next((row for row in range(column, size) if rows[row][column] != 0), None)
        if pivot is None:
            return None
        rows[column], rows[pivot] = rows[pivot], rows[column]
        divisor = rows[column][column]
        rows[column] = [value / divisor for value in rows[column]]
        for row in range(size):
            if row != column and rows[row][column] != 0:
                factor = rows[row][column]
                rows[row] = [value - factor * pivot_value
                             for value, pivot_value in zip(rows[row], rows[column])]
    return tuple(rows[row][size] for row in range(size))


def _vertices(bounds, count):
    limits = [bound.limit for bound in bounds]
    weights = [bound.weights for bound in bounds]
    found = []
    seen = set()
    for selection in combinations(range(len(bounds)), count):
        point = _solve([weights[index] for index in selection], [limits[index] for index in selection])
        if point is None or point in seen:
            continue
        if all(sum(weight * value for weight, value in zip(bound.weights, point)) <= bound.limit
               for bound in bounds):
            seen.add(point)
            found.append(point)
    return tuple(found)


def _tight_at_all(bounds, vertices, bound):
    return all(sum(weight * value for weight, value in zip(bound.weights, vertex)) == bound.limit
               for vertex in vertices)


def _some_open_point(bounds, vertices):
    """Is there a point strictly inside every open bound?

    A compact polytope misses the strict interior exactly when one of the open
    bounds is tight along the whole polytope, i.e. tight at every vertex.
    """
    return not any(bound.strict and _tight_at_all(bounds, vertices, bound) for bound in bounds)


def reconcile_difference(selected: SelectedReceipts):
    left = decode_evidence_body(selected.left.body)
    right = decode_evidence_body(selected.right.body)
    names = selected.left.entry.origin.channels
    if left.channels != names or right.channels != names:
        raise ValueError("body channels conflict with the selected directory")
    count = len(names)
    bounds = tuple(left.bounds) + tuple(right.bounds)
    _check_bounded(bounds, count)

    vertices = _vertices(bounds, count)
    if not vertices or not _some_open_point(bounds, vertices):
        return ComparisonResult("incompatible", None)

    request = selected.request
    first, second = names.index(request.minuend), names.index(request.subtrahend)

    def difference(vertex):
        return vertex[first] - vertex[second]

    values = [difference(vertex) for vertex in vertices]
    lowest, highest = min(values), max(values)
    low_vertices = [vertex for vertex, value in zip(vertices, values) if value == lowest]
    high_vertices = [vertex for vertex, value in zip(vertices, values) if value == highest]
    lower_closed = _some_open_point(bounds, low_vertices)
    upper_closed = _some_open_point(bounds, high_vertices)
    return ComparisonResult(
        "compatible",
        DifferenceInterval(lowest, highest, lower_closed, upper_closed),
    )
