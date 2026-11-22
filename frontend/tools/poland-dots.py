"""Dot grid of Poland for the "Ile mapy już naładowaliśmy?" map.

Input: voivodeship boundaries from GUGiK PRG (WFS AdministrativeBoundaries, layer ms:A01_Granice_wojewodztw,
SRSNAME=EPSG:4326, GML 2). Output: src/assets/aed/poland-dots.json with the grid and the voivodeship of every dot.

    python3 tools/poland-dots.py woj.gml src/assets/aed/poland-dots.json
"""

import json
import math
import sys
import xml.etree.ElementTree as ET

STEP = 0.11  # degrees of latitude between rows
LAT0 = 52.0  # longitude is scaled by cos(LAT0) so the dots form a square grid on the map
NS = {"gml": "http://www.opengis.net/gml", "ms": "http://mapserver.gis.umn.edu/mapserver"}


def rings(member):
    out = []
    for polygon in member.iter("{%s}Polygon" % NS["gml"]):
        for outer in polygon.iter("{%s}outerBoundaryIs" % NS["gml"]):
            text = outer.find(".//gml:coordinates", NS).text.split()
            out.append([(float(p.split(",")[1]), float(p.split(",")[0])) for p in text])
    return out


def inside(x, y, ring):
    hit = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            hit = not hit
        j = i
    return hit


def main(source, target):
    regions = []
    for member in ET.parse(source).getroot().iter("{%s}A01_Granice_wojewodztw" % NS["ms"]):
        code = member.find("ms:JPT_KOD_JE", NS).text.strip()
        name = member.find("ms:JPT_NAZWA_", NS).text.strip()
        parts = rings(member)
        box = [min(x for r in parts for x, _ in r), min(y for r in parts for _, y in r)]
        box += [max(x for r in parts for x, _ in r), max(y for r in parts for _, y in r)]
        regions.append({"code": code, "name": name, "rings": parts, "box": box})
    lon0, lat0 = min(r["box"][0] for r in regions), min(r["box"][1] for r in regions)
    lon1, lat1 = max(r["box"][2] for r in regions), max(r["box"][3] for r in regions)
    kx = math.cos(math.radians(LAT0))
    cols, rows = int((lon1 - lon0) * kx / STEP) + 1, int((lat1 - lat0) / STEP) + 1
    dots = []
    for row in range(rows):
        lat = lat1 - row * STEP
        for col in range(cols):
            lon = lon0 + col * STEP / kx
            for region in regions:
                b = region["box"]
                if b[0] <= lon <= b[2] and b[1] <= lat <= b[3] and any(inside(lon, lat, r) for r in region["rings"]):
                    dots.append([col, row, region["code"]])
                    break
    names = {r["code"]: r["name"] for r in regions}
    grid = {"lon0": lon0, "lat1": lat1, "step": STEP, "kx": kx, "cols": cols, "rows": rows}
    with open(target, "w", encoding="utf-8") as fp:
        json.dump({"grid": grid, "names": names, "dots": dots}, fp, ensure_ascii=False, separators=(",", ":"))
    print(len(dots), "dots,", cols, "x", rows)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
