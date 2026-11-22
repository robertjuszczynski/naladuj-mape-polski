import json
from pathlib import Path

B = Path(__file__).resolve().parent
W = B.parent
durs = W / "lektor" / "durations.json"
html = (B / "wideo.template.html").read_text()
html = html.replace("/*SCRIPT*/", (B / "scenariusz.json").read_text())
html = html.replace("/*DURATIONS*/", durs.read_text() if durs.exists() else "{}")
html = html.replace("/*BOXES*/", (B / "boxes.json").read_text())
html = html.replace("/*WORLD*/", (B / "worldmap.json").read_text())
(W / "wideo.html").write_text(html)
print("wideo.html", "z lektorem" if durs.exists() else "bez lektora (szacowane czasy)")
