"""Bake Potrace's closed contours into an outward, filled vector outline.

Cubic curves are adaptively flattened in Potrace coordinates. A planar sweep
unions miter-joined stroke polygons and subtracts the original nonzero fill.
The result is closed filled trapezoids: no SVG strokes, masks or dependencies.
Intersections split sweep bands, so concave corners, holes and overlapping
offsets are handled by geometry rather than by importer-specific SVG effects.
"""

import math
import re


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _sub(a, b):
    return a[0] - b[0], a[1] - b[1]


def _area(points):
    return sum(_cross(a, b) for a, b in zip(points, points[1:] + points[:1])) / 2


def _flatten(p0, p1, p2, p3, tolerance, output, depth=0):
    # Distance to the chord segment also catches collinear cubic overshoot.
    chord = _sub(p3, p0)
    length2 = chord[0] ** 2 + chord[1] ** 2
    def distance(p):
        t = max(0, min(1, sum(x*y for x, y in zip(_sub(p, p0), chord)) / length2)) if length2 else 0
        return math.hypot(p[0] - p0[0] - t*chord[0], p[1] - p0[1] - t*chord[1])
    if max(distance(p1), distance(p2)) <= tolerance:
        output.append(p3)
        return
    if depth >= 24:
        raise ValueError('Shell curve could not be flattened accurately')
    def mid(a, b):
        return (a[0] + b[0])/2, (a[1] + b[1])/2
    a, b, c = mid(p0, p1), mid(p1, p2), mid(p2, p3)
    d, e = mid(a, b), mid(b, c)
    f = mid(d, e)
    _flatten(p0, a, d, f, tolerance, output, depth + 1)
    _flatten(f, e, c, p3, tolerance, output, depth + 1)


def potrace_contours(path_data, tolerance):
    """Parse Potrace M/L/C/Z (including relative and repeated coordinates)."""
    tokens = re.findall(r'[A-Za-z]|[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?', path_data)
    contours, points = [], []
    current = (0.0, 0.0)
    command, i = None, 0
    while i < len(tokens):
        if tokens[i].isalpha():
            command = tokens[i]
            i += 1
        if command in ('z', 'Z'):
            if points:
                current = points[0]
                if points[-1] == points[0]:
                    points.pop()
                if len(points) >= 3:
                    contours.append(points)
            points, command = [], None
            continue
        if command not in ('m', 'M', 'l', 'L', 'c', 'C'):
            raise ValueError(f'Unsupported shell path command: {command}')
        count = 6 if command.lower() == 'c' else 2
        values = list(map(float, tokens[i:i + count]))
        if len(values) != count:
            raise ValueError('Incomplete shell path')
        i += count
        coords = [(values[j], values[j+1]) for j in range(0, count, 2)]
        if command.islower():
            coords = [(x + current[0], y + current[1]) for x, y in coords]
        if command.lower() == 'm':
            if points:
                raise ValueError('Shell contour is not closed')
            points = [coords[0]]
            command = 'l' if command.islower() else 'L'
        elif command.lower() == 'l':
            if coords[0] != current:
                points.append(coords[0])
        else:
            _flatten(current, *coords, tolerance, points)
        current = coords[-1]
    if points:
        raise ValueError('Shell contour is not closed')
    return contours


def _stroke_polygons(contours, radius):
    polygons = []
    def add(points):
        area = _area(points)
        if abs(area) > 1e-14:
            polygons.append(points if area > 0 else points[::-1])
    for points in contours:
        directions = []
        for a, b in zip(points, points[1:] + points[:1]):
            dx, dy = _sub(b, a)
            length = math.hypot(dx, dy)
            if not length:
                raise ValueError('Degenerate shell edge')
            d = (dx / length, dy / length)
            directions.append(d)
            nx, ny = -d[1]*radius, d[0]*radius
            add([(a[0]+nx, a[1]+ny), (a[0]-nx, a[1]-ny),
                 (b[0]-nx, b[1]-ny), (b[0]+nx, b[1]+ny)])
        for i, p in enumerate(points):
            d0, d1 = directions[i-1], directions[i]
            turn = _cross(d0, d1)
            if abs(turn) < 1e-12:
                continue
            side = -1 if turn > 0 else 1
            a = (p[0]-d0[1]*radius*side, p[1]+d0[0]*radius*side)
            b = (p[0]-d1[1]*radius*side, p[1]+d1[0]*radius*side)
            t = _cross(_sub(b, a), d1) / turn
            miter = (a[0]+t*d0[0], a[1]+t*d0[1])
            # SVG's default miter limit is 4, with a bevel beyond the limit.
            if math.dist(p, miter) <= 4*radius:
                add([p, a, miter, b])
            else:
                add([p, a, b])
    return polygons


def _filled_difference(strokes, shell):
    edges, levels = [], set()
    # Edges: low x/y, high x/y, category (stroke/shell), winding direction.
    for kind, polygons in enumerate((strokes, shell)):
        for polygon in polygons:
            for a, b in zip(polygon, polygon[1:] + polygon[:1]):
                levels.update((a[1], b[1]))
                if abs(a[1] - b[1]) < 1e-12:
                    continue
                direction = 1 if a[1] < b[1] else -1
                low, high = (a, b) if direction == 1 else (b, a)
                edges.append((*low, *high, kind, direction))
    edges.sort(key=lambda e: e[1])
    active = []
    for edge in edges:
        active = [other for other in active if other[3] > edge[1]]
        x0, y0, x1, y1 = edge[:4]
        d = (x1-x0, y1-y0)
        for other in active:
            if max(x0, x1) < min(other[0], other[2]) or min(x0, x1) > max(other[0], other[2]):
                continue
            v = (other[2]-other[0], other[3]-other[1])
            denominator = _cross(d, v)
            if abs(denominator) < 1e-12:
                continue
            delta = (other[0]-x0, other[1]-y0)
            t, u = _cross(delta, v)/denominator, _cross(delta, d)/denominator
            if 0 < t < 1 and 0 < u < 1:
                levels.add(y0 + t*d[1])
        active.append(edge)

    def x_at(edge, y):
        return edge[0] + (y-edge[1])*(edge[2]-edge[0])/(edge[3]-edge[1])

    levels = sorted(levels)
    active, cursor, output = [], 0, []
    runs = {}
    for lower, upper in zip(levels, levels[1:]):
        if upper-lower < 1e-10:
            continue
        middle = (lower+upper)/2
        while cursor < len(edges) and edges[cursor][1] < middle:
            active.append(edges[cursor])
            cursor += 1
        active = [edge for edge in active if edge[3] > middle]
        crossings = sorted((x_at(edge, middle), index, edge) for index, edge in enumerate(active))
        winding = [0, 0]
        start = None
        next_runs = {}
        i = 0
        while i < len(crossings):
            x, _, edge = crossings[i]
            was_filled = winding[0] != 0 and winding[1] == 0
            while i < len(crossings) and abs(crossings[i][0]-x) < 1e-9:
                boundary = crossings[i][2]
                winding[boundary[4]] += boundary[5]
                i += 1
            filled = winding[0] != 0 and winding[1] == 0
            if filled and not was_filled:
                start = edge
            elif was_filled and not filled:
                polygon = [(x_at(start, lower), lower), (x_at(edge, lower), lower),
                           (x_at(edge, upper), upper), (x_at(start, upper), upper)]
                if _area(polygon) > 1e-12:
                    # Unrelated edges also split the sweep into bands. Join
                    # adjacent bands bounded by the same two straight edges.
                    key = (start, edge)
                    previous = runs.get(key)
                    if previous is not None and abs(previous[2][1]-lower) < 1e-8:
                        previous[2:] = polygon[2:]
                        next_runs[key] = previous
                    else:
                        output.append(polygon)
                        next_runs[key] = polygon
        runs = next_runs
    return output


def outline_path(path_data, radius):
    if radius <= 0:
        return ''
    # Potrace group scale is 0.1: this is at most 0.002 output units, and
    # at most 1% of the wall radius, independent of render resolution.
    tolerance = min(0.02, radius*0.01)
    contours = [contour for data in path_data for contour in potrace_contours(data, tolerance)]
    polygons = _filled_difference(_stroke_polygons(contours, radius), contours)
    return ''.join('M' + 'L'.join(f'{x:.8f},{y:.8f}' for x, y in polygon) + 'Z' for polygon in polygons)
