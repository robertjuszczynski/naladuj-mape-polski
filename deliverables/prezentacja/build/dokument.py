"""Składa dokument PDF (opis rozwiązania) ze stylów prezentacji i build/dokument.body.html."""
import re
from pathlib import Path

P = Path(__file__).resolve().parent.parent
deck = (P / "prezentacja.html").read_text()
style = re.search(r"<style>(.*?)</style>", deck, re.S).group(1)
fields = re.search(r"const FIELDS = \[.*?\];", deck, re.S).group(0)
extra = """
@font-face { font-family: "ManropeS"; font-weight: 500; src: url("assets/fonts/manrope-latin-500-normal.woff2") format("woff2"); unicode-range: U+0000-00FF, U+2000-206F, U+2190-2193; }
@font-face { font-family: "ManropeS"; font-weight: 500; src: url("assets/fonts/manrope-latin-ext-500-normal.woff2") format("woff2"); unicode-range: U+0100-02BA, U+1E00-1EFF; }
@font-face { font-family: "ManropeS"; font-weight: 600; src: url("assets/fonts/manrope-latin-600-normal.woff2") format("woff2"); unicode-range: U+0000-00FF, U+2000-206F, U+2190-2193; }
@font-face { font-family: "ManropeS"; font-weight: 600; src: url("assets/fonts/manrope-latin-ext-600-normal.woff2") format("woff2"); unicode-range: U+0100-02BA, U+1E00-1EFF; }
@font-face { font-family: "ManropeS"; font-weight: 700; src: url("assets/fonts/manrope-latin-700-normal.woff2") format("woff2"); unicode-range: U+0000-00FF, U+2000-206F, U+2190-2193; }
@font-face { font-family: "ManropeS"; font-weight: 700; src: url("assets/fonts/manrope-latin-ext-700-normal.woff2") format("woff2"); unicode-range: U+0100-02BA, U+1E00-1EFF; }
@font-face { font-family: "ManropeS"; font-weight: 800; src: url("assets/fonts/manrope-latin-800-normal.woff2") format("woff2"); unicode-range: U+0000-00FF, U+2000-206F, U+2190-2193; }
@font-face { font-family: "ManropeS"; font-weight: 800; src: url("assets/fonts/manrope-latin-ext-800-normal.woff2") format("woff2"); unicode-range: U+0100-02BA, U+1E00-1EFF; }
:root { --sans: "ManropeS", system-ui, sans-serif; }

.d-cover { display: grid; place-items: center; align-content: center; gap: 44px; text-align: center; padding: 0; }
.d-cover img { height: 520px; }
.d-sub { font: 700 40px/1.3 var(--sans); color: var(--cream); }
.d-meta { font: 500 22px/1 var(--mono); letter-spacing: .12em; text-transform: uppercase; color: rgba(247,244,238,.6); }
.d-lead { margin-bottom: 64px; }
.toc { display: grid; grid-template-columns: 1fr 1fr; gap: 30px 72px; }
.toc > div { position: relative; border-top: 2px solid var(--navy); padding: 22px 110px 0 0; }
.toc h3 { font-size: 31px; margin-bottom: 8px; }
.toc p { font: 500 23px/1.42 var(--sans); color: var(--muted); }
.pgref { position: absolute; right: 0; top: 24px; font: 500 22px/1 var(--mono); color: var(--red); }

.slide.f { display: grid; grid-template-columns: 640px 1fr; gap: 80px; align-items: center; padding: 0 120px 70px; }
.ftext h2 { font-size: 54px; margin: 0 0 20px; }
.flead { font: 600 27px/1.4 var(--sans); color: var(--ink); margin: 0 0 34px; }
.olist.sm li { font-size: 23px; line-height: 1.42; margin-bottom: 15px; padding-left: 56px; }
.olist.sm li::before { width: 36px; height: 36px; font-size: 17px; top: -1px; }
.fnote { margin-top: 22px; padding-top: 18px; border-top: 1px solid var(--line); font: 500 20px/1.5 var(--sans); color: var(--muted); }
.code.sm { font-size: 18px; line-height: 1.7; padding: 22px 26px; margin-top: 8px; }

.stage { position: relative; display: flex; align-items: center; justify-content: center; height: 800px; }
.laptop { position: relative; width: 960px; }
.lid { position: relative; background: #12161d; border-radius: 24px 24px 4px 4px; padding: 26px 18px 18px; box-shadow: inset 0 0 0 2px #262c36; }
.cam { position: absolute; top: 10px; left: 50%; width: 7px; height: 7px; margin-left: -3.5px; border-radius: 50%; background: #2f3744; }
.scr { overflow: hidden; background: #fff; }
.lid .scr { aspect-ratio: 16 / 10; border-radius: 3px; }
.scr img { display: block; width: 100%; height: 100%; object-fit: cover; object-position: top center; }
.base { position: relative; height: 22px; margin: 0 -70px; background: linear-gradient(#eceef1, #c3c8cf 70%, #a9afb8); border-radius: 2px 2px 26px 26px; box-shadow: 0 34px 46px -22px rgba(11,37,69,.42); }
.base::before { content: ""; position: absolute; left: 50%; top: 0; width: 160px; height: 9px; margin-left: -80px; background: #b3b9c1; border-radius: 0 0 12px 12px; }

.phone { position: relative; width: 270px; background: #12161d; border-radius: 46px; padding: 11px; box-shadow: inset 0 0 0 2px #2a313c, 0 34px 50px -24px rgba(11,37,69,.45); }
.phone .scr { aspect-ratio: 390 / 844; border-radius: 36px; }
.phone::after { content: ""; position: absolute; top: 22px; left: 50%; width: 76px; height: 22px; margin-left: -38px; background: #12161d; border-radius: 12px; }

.stage.duo .laptop { width: 800px; margin-right: 150px; }
.stage.duo .phone { position: absolute; right: 10px; bottom: 70px; width: 250px; }
.stage.pair { gap: 70px; }
.stage.pair .phone { width: 310px; }
.stage.pair .phone:nth-child(2) { margin-top: 0; }
.stage.pair.small { height: 720px; gap: 48px; }
.stage.pair.small .phone { width: 280px; }

.reqh { font-size: 30px; margin: 0 0 20px; }
.list.sm li { font-size: 23px; margin-bottom: 14px; }
.prose.sm { font-size: 22px; }
.phone, .print .phone { transform: none !important; animation: none !important; }
*, *::before, *::after { box-shadow: none !important; text-shadow: none !important; filter: none !important; }
.phone { border: 2px solid #2a313c; }
.lid { border: 2px solid #262c36; }
.base { background: #c9ced5; }
.req2 { display: grid; grid-template-columns: 1fr 760px; gap: 80px; align-items: center; }
.phone .scr { display: flex; flex-direction: column; }
.phone .scr img { height: auto; flex: none; }
.sb { flex: none; height: 38px; display: flex; align-items: center; justify-content: space-between; padding: 4px 24px 0 30px; background: #fff; color: #111; font: 700 13px/1 var(--sans); }
.sb i { width: 24px; height: 11px; border: 1.5px solid currentColor; border-radius: 3px; opacity: .8; }
.sb.dark { background: var(--navy); color: #fff; }
"""
body = (Path(__file__).parent / "dokument.body.html").read_text()
body = re.sub(r'<div class="phone"><div class="scr"><img src="([^"]+)"', lambda m: '<div class="phone"><div class="scr"><div class="sb%s"><b>9:41</b><i></i></div><img src="%s"' % (" dark" if "P-akcja" in m.group(1) else "", m.group(1)), body)
html = f"""<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<title>Naładuj mapę Polski – opis rozwiązania</title>
<style>{style}{extra}</style>
</head>
<body>
{body}
<script>
document.documentElement.classList.add('print');
const slides = [...document.querySelectorAll('.slide')];
slides.forEach((s, i) => {{ const pg = s.querySelector('.pg'); if (pg) pg.textContent = String(i + 1).padStart(2, '0') + ' / ' + String(slides.length).padStart(2, '0'); s.classList.add('active'); }});
{fields}
const f = document.getElementById('fields');
if (f) f.innerHTML = FIELDS.map(([n, c]) => `<span class="${{c || ''}}">${{n}}</span>`).join('');
</script>
</body>
</html>
"""
(P / "dokument.html").write_text(html)
print("dokument.html")
