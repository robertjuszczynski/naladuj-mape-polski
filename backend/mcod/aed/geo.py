import json
import math
import os
from functools import lru_cache

from mcod.aed.constants import DATA_DIR, POLAND_BBOX

METERS_PER_DEGREE_LAT = 110540
METERS_PER_DEGREE_LON_AT_EQUATOR = 111320


def point_in_ring(lon, lat, ring):
    inside, j = False, len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def in_boundary(lat, lon, boundary):
    return any(
        point_in_ring(lon, lat, polygon[0]) and not any(point_in_ring(lon, lat, hole) for hole in polygon[1:])
        for polygon in boundary["polygons"]
    )


def distance_to_boundary_m(lat, lon, boundary):
    kx, ky = METERS_PER_DEGREE_LON_AT_EQUATOR * math.cos(math.radians(lat)), METERS_PER_DEGREE_LAT
    best = float("inf")
    for polygon in boundary["polygons"]:
        for ring in polygon:
            for a, b in zip(ring, ring[1:]):
                ax, ay = (a[0] - lon) * kx, (a[1] - lat) * ky
                bx, by = (b[0] - lon) * kx, (b[1] - lat) * ky
                dx, dy = bx - ax, by - ay
                t = max(0, min(1, -(ax * dx + ay * dy) / ((dx * dx + dy * dy) or 1)))
                best = min(best, math.hypot(ax + t * dx, ay + t * dy))
    return best


def in_poland(lat, lon):
    return POLAND_BBOX["min_lat"] <= lat <= POLAND_BBOX["max_lat"] and POLAND_BBOX["min_lon"] <= lon <= POLAND_BBOX["max_lon"]


class Boundaries:
    """Municipality boundaries from data/gminy.geojson, keyed by TERYT code."""

    @staticmethod
    @lru_cache(maxsize=1)
    def all():
        with open(os.path.join(DATA_DIR, "gminy.geojson"), encoding="utf-8") as fp:
            collection = json.load(fp)
        out = {}
        for feature in collection["features"]:
            geometry = feature["geometry"]
            polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
            out[feature["properties"]["kod_teryt_gminy"]] = {"name": feature["properties"]["nazwa"], "polygons": polygons}
        return out

    @classmethod
    def get(cls, teryt):
        return cls.all().get(teryt or "")

    @staticmethod
    @lru_cache(maxsize=1)
    def boxes():
        """(min_lon, min_lat, max_lon, max_lat) per municipality, to skip polygons that cannot contain a point."""
        out = {}
        for teryt, boundary in Boundaries.all().items():
            points = [p for polygon in boundary["polygons"] for p in polygon[0]]
            out[teryt] = (
                min(p[0] for p in points),
                min(p[1] for p in points),
                max(p[0] for p in points),
                max(p[1] for p in points),
            )
        return out

    @classmethod
    def teryt_at(cls, lat, lon):
        """TERYT code of the municipality containing the point, or ""."""
        boundaries = cls.all()
        for teryt, (x1, y1, x2, y2) in cls.boxes().items():
            if x1 <= lon <= x2 and y1 <= lat <= y2 and in_boundary(lat, lon, boundaries[teryt]):
                return teryt
        return ""

    @classmethod
    def containing(cls, lat, lon, exclude=None):
        return next((b for b in cls.all().values() if b is not exclude and in_boundary(lat, lon, b)), None)
