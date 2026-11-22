import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SVG = HERE.parents[2] / "znak/logo/svg/naladuj-mape-polski_pionowy_kolor.svg"

svg = SVG.read_text()
vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', svg).group(1).split()]
syg = re.search(r'<g transform="translate\(([-\d.]+) ([-\d.]+)\) scale\(1\)">', svg)
contour = re.search(r'<path class="r"[^>]* d="([^"]+)"', svg).group(1)
pulse = re.search(r'<path class="p"[^>]* d="([^"]+)"', svg).group(1)
glyphs = [
    {"transform": m.group(1), "d": m.group(2), "fill": m.group(3)}
    for m in re.finditer(r'<path transform="([^"]+)" d="([^"]+)" fill="([^"]+)"', svg)
]

data = {
    "sygOffset": [float(syg.group(1)), float(syg.group(2))],
    "center": [vb[0] + vb[2] / 2, vb[1] + vb[3] / 2],
    "contour": contour,
    "pulse": pulse,
    "glyphs": glyphs,
}

html = (HERE / "intro.template.html").read_text().replace("/*LOGO_DATA*/", json.dumps(data))
(HERE.parent / "intro.html").write_text(html)
print(f"intro.html: {len(glyphs)} glyphs")
