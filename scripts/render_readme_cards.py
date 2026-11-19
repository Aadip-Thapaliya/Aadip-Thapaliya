"""Render the animated SVG cards used by the profile README.

Theme: "Rhine Autumn" - navy jacket, cream shirt, autumn leaves and a river,
taken from the profile illustration.

Run locally:   python scripts/render_readme_cards.py
In CI:         .github/workflows/update-profile-art.yml runs it daily.

Uses only the Python standard library. Set GITHUB_TOKEN to raise the API limit.
"""

from __future__ import annotations

import base64
import datetime as dt
import html
import json
import os
import re
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "cards"
USER = "Aadip-Thapaliya"

# ----------------------------------------------------------------- content --

PROFILE = {
    "greeting": "// hallo, ich bin",
    "name": "Aadip Thapaliya",
    "tagline": [
        "Data Science student in Berlin. I forecast time series,",
        "measure causal impact, and automate the reports in between.",
    ],
    "meta": "B.Sc. Digital Business & Data Science @ UE Potsdam  ·  ML programme @ opencampus.sh",
    "location": "Berlin, DE",
    "skills": ["Python", "SQL", "R", "PyTorch", "TensorFlow", "scikit-learn",
               "PostgreSQL", "Power BI", "Causal Inference"],
}

TILES = [
    {"file": "forecast", "label": "FORECAST", "value": "10+",
     "line1": "forecasting models benchmarked", "line2": "on 20 equities, best: LightGBM",
     "foot": "ARIMA · GARCH · LSTM · N-BEATS", "viz": "spark"},
    {"file": "cause", "label": "CAUSE", "value": "5",
     "line1": "policy datasets stress-tested", "line2": "with IPW, AIPW, meta-learners",
     "foot": "Rosenbaum bounds · HTE", "viz": "dag"},
    {"file": "automate", "label": "AUTOMATE", "value": "-40%",
     "line1": "manual reporting effort", "line2": "via daily Python pipelines",
     "foot": "ingest · clean · report", "viz": "bars"},
]

REPOS = [
    {"name": "CLUE", "badge": "building now",
     "desc": "Open-source forecasting app: raw numbers in, clean forecasts and "
             "PDF reports out. No code needed, runs fully local, data stays private."},
    {"name": "OCG-SSM", "badge": None, "desc": None},
    {"name": "deepseek-harness-guide", "badge": None, "lang": "Markdown",
     "desc": "An independent beginner-to-advanced guide to DeepSeek Harness (dsh), "
             "the open-source, plugin-first agent harness."},
]

# ------------------------------------------------------------------- theme --

C = {
    "bg": "#0e1a2f", "bg2": "#15243e", "line": "#24365a",
    "cream": "#f3e9d2", "muted": "#9fb0c9", "dim": "#5f7392",
    "orange": "#f0803c", "amber": "#e3a24f", "teal": "#5fb3a6", "green": "#8fb36b",
}
LEVELS = ["#1a2945", "#2c5c63", "#4f9c93", "#e3a24f", "#f2733a"]
LANG_COLORS = {"Python": "#3572A5", "Markdown": "#e3e3e3", "Jupyter Notebook": "#DA5B0B",
               "R": "#198CE7", "TypeScript": "#3178c6", "JavaScript": "#f1e05a"}
SANS = "'Segoe UI', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, sans-serif"
MONO = "'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace"

BASE_CSS = f"""
.sans{{font-family:{SANS}}} .mono{{font-family:{MONO}}}
@keyframes fade{{from{{opacity:0}}to{{opacity:1}}}}
@keyframes rise{{from{{opacity:0;transform:translateY(10px)}}to{{opacity:1;transform:translateY(0)}}}}
@keyframes grow{{from{{transform:scaleY(0)}}to{{transform:scaleY(1)}}}}
@keyframes draw{{to{{stroke-dashoffset:0}}}}
@keyframes blink{{50%{{opacity:0}}}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.35}}}}
.fade{{animation:fade .8s ease-out both}}
.rise{{animation:rise .8s ease-out both}}
"""


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def text_w(s: str, size: float, bold: bool = False, mono: bool = False) -> float:
    """Rough rendered width, good enough for layout of short labels."""
    k = 0.61 if mono else (0.6 if bold else 0.54)
    return len(s) * size * k


def wrap(s: str, max_chars: int) -> list[str]:
    lines, cur = [], ""
    for word in s.split():
        if cur and len(cur) + 1 + len(word) > max_chars:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        lines.append(cur)
    return lines


def svg(w: int, h: int, body: str, css: str = "", title: str = "") -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{esc(title)}">'
            f"<title>{esc(title)}</title><style>{BASE_CSS}{css}</style>{body}</svg>\n")


def panel(w: int, h: int, pad: int = 6) -> str:
    """Card background with the 'margin' baked in, so cards tile with no gaps."""
    return (f'<defs><linearGradient id="pg" x1="0" y1="0" x2="1" y2="1">'
            f'<stop offset="0" stop-color="{C["bg2"]}"/><stop offset="1" stop-color="{C["bg"]}"/>'
            f'</linearGradient></defs>'
            f'<rect x="{pad}" y="{pad}" width="{w - 2 * pad}" height="{h - 2 * pad}" rx="16" '
            f'fill="url(#pg)" stroke="{C["line"]}"/>')


# -------------------------------------------------------------------- data --

def get(url: str, accept: str = "application/vnd.github+json") -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "profile-card-renderer", "Accept": accept})
    token = os.environ.get("GITHUB_TOKEN")
    if token and "api.github.com" in url:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def fetch_contributions() -> list[tuple[dt.date, int, int]]:
    page = get(f"https://github.com/users/{USER}/contributions", "text/html").decode("utf-8")
    cells = {}
    for td in re.finditer(r"<td[^>]*ContributionCalendar-day[^>]*>", page):
        tag = td.group(0)
        d = re.search(r'data-date="([\d-]+)"', tag)
        i = re.search(r'id="([^"]+)"', tag)
        lv = re.search(r'data-level="(\d)"', tag)
        if d and i and lv:
            cells[i.group(1)] = [dt.date.fromisoformat(d.group(1)), 0, int(lv.group(1))]
    for tip in re.finditer(r'<tool-tip[^>]*for="([^"]+)"[^>]*>([^<]*)</tool-tip>', page):
        if tip.group(1) in cells:
            m = re.match(r"\s*(\d+) contribution", tip.group(2))
            cells[tip.group(1)][1] = int(m.group(1)) if m else 0
    days = sorted((tuple(v) for v in cells.values()), key=lambda x: x[0])
    if not days:
        raise RuntimeError("no contribution cells found; GitHub markup may have changed")
    return days


def fetch_repo(spec: dict) -> dict:
    info = {"stars": 0, "forks": 0, "lang": spec.get("lang") or "Python", "desc": spec.get("desc") or ""}
    try:
        d = json.loads(get(f"https://api.github.com/repos/{USER}/{spec['name']}"))
        info["stars"] = d.get("stargazers_count", 0)
        info["forks"] = d.get("forks_count", 0)
        info["lang"] = spec.get("lang") or d.get("language") or info["lang"]
        info["desc"] = spec.get("desc") or d.get("description") or ""
    except Exception as e:  # keep rendering with fallbacks if the API is down
        print(f"warn: repo {spec['name']}: {e}")
    return info


# ------------------------------------------------------------------- cards --

LEAF = "M0,-7 C5,-4 5,4 0,8 C-5,4 -5,-4 0,-7 Z"


def leaves(w: int, h: int) -> str:
    out = []
    spec = [(140, 9, 0, C["orange"]), (520, 12, 3, C["amber"]), (760, 10, 6, C["orange"]),
            (980, 14, 1.5, C["amber"]), (1110, 11, 4.5, C["green"]), (330, 13, 7.5, C["amber"])]
    for x, dur, delay, col in spec:
        out.append(
            f'<g opacity="0"><animate attributeName="opacity" values="0;.55;.55;0" dur="{dur}s" '
            f'begin="{delay}s" repeatCount="indefinite"/>'
            f'<animateTransform attributeName="transform" type="translate" '
            f'values="{x},-20; {x + 40},{h * 0.45}; {x - 10},{h + 20}" dur="{dur}s" begin="{delay}s" '
            f'repeatCount="indefinite"/>'
            f'<path d="{LEAF}" fill="{col}"><animateTransform attributeName="transform" type="rotate" '
            f'from="0" to="360" dur="{dur / 2}s" repeatCount="indefinite"/></path></g>')
    return "".join(out)


def hero() -> str:
    W, H = 1200, 440
    img = base64.b64encode((ROOT / "assets" / "avatar.jpg").read_bytes()).decode()
    cx, cy, r = 214, 214, 150
    p = PROFILE
    tx = 418

    chips, x, y = [], tx, 340
    for i, s in enumerate(p["skills"]):
        cw = text_w(s, 13, mono=True) + 24
        if x + cw > W - 40:
            x, y = tx, y + 38
        chips.append(
            f'<g class="rise" style="animation-delay:{1.6 + i * .08:.2f}s">'
            f'<rect x="{x}" y="{y}" width="{cw:.0f}" height="28" rx="14" fill="{C["bg"]}" '
            f'stroke="{C["line"]}"/><text x="{x + cw / 2:.0f}" y="{y + 19}" text-anchor="middle" '
            f'class="mono" font-size="13" fill="{C["cream"]}">{esc(s)}</text></g>')
        x += cw + 10

    name_w = len(p["name"]) * 58 * 0.51 + 6  # measured for Segoe UI bold
    hills = (
        f'<path d="M6,{H - 70} C180,{H - 140} 320,{H - 90} 470,{H - 120} S800,{H - 160} 1000,{H - 105} '
        f'S1150,{H - 120} 1194,{H - 130} L1194,{H - 6} L6,{H - 6} Z" fill="{C["green"]}" opacity=".06"/>'
        f'<path d="M6,{H - 40} C220,{H - 90} 420,{H - 50} 640,{H - 75} S1000,{H - 95} 1194,{H - 60} '
        f'L1194,{H - 6} L6,{H - 6} Z" fill="{C["amber"]}" opacity=".05"/>'
        f'<path d="M6,{H - 26} Q300,{H - 40} 600,{H - 26} T1194,{H - 26}" fill="none" stroke="{C["teal"]}" '
        f'stroke-width="2" opacity=".35" stroke-dasharray="14 10">'
        f'<animate attributeName="stroke-dashoffset" from="0" to="-48" dur="2.5s" repeatCount="indefinite"/></path>')

    body = f"""{panel(W, H)}
<defs><clipPath id="ph"><circle cx="{cx}" cy="{cy}" r="{r}"/></clipPath>
<clipPath id="card"><rect x="6" y="6" width="{W - 12}" height="{H - 12}" rx="16"/></clipPath>
<clipPath id="nm"><rect x="{tx}" y="120" width="0" height="80">
<animate attributeName="width" from="0" to="{name_w:.0f}" dur="1.1s" begin=".3s" fill="freeze" calcMode="discrete"
 values="{';'.join(str(int(name_w * k / 16)) for k in range(17))}" keyTimes="{';'.join(f'{k/16:.4f}' for k in range(17))}"/>
</rect></clipPath></defs>
<g clip-path="url(#card)">{hills}{leaves(W, H)}</g>
<circle cx="{cx}" cy="{cy}" r="{r + 18}" fill="none" stroke="{C['orange']}" stroke-width="2" stroke-dasharray="4 10" opacity=".8">
<animateTransform attributeName="transform" type="rotate" from="0 {cx} {cy}" to="360 {cx} {cy}" dur="40s" repeatCount="indefinite"/></circle>
<circle cx="{cx}" cy="{cy}" r="{r + 6}" fill="none" stroke="{C['teal']}" stroke-width="1.5" opacity=".6"/>
<g class="fade"><image href="data:image/jpeg;base64,{img}" xlink:href="data:image/jpeg;base64,{img}" x="{cx - r}" y="{cy - r}" width="{2 * r}" height="{2 * r}" clip-path="url(#ph)"/></g>
<g class="fade" style="animation-delay:.6s"><circle cx="{cx + 106}" cy="{cy + 106}" r="13" fill="{C['bg']}"/>
<circle cx="{cx + 106}" cy="{cy + 106}" r="8" fill="{C['green']}" style="animation:pulse 2s infinite"/></g>
<text x="{cx}" y="{H - 32}" text-anchor="middle" class="mono fade" font-size="13" fill="{C['muted']}" letter-spacing="2" style="animation-delay:.8s">{esc(p['location'].upper())}</text>
<text x="{tx}" y="104" class="mono fade" font-size="16" fill="{C['orange']}">{esc(p['greeting'])}</text>
<g clip-path="url(#nm)"><text x="{tx}" y="176" class="sans" font-size="58" font-weight="700" fill="{C['cream']}">{esc(p['name'])}</text></g>
<rect x="{tx + name_w + 4:.0f}" y="132" width="4" height="50" fill="{C['orange']}" style="animation:blink 1s steps(1) infinite"/>
<text x="{tx}" y="226" class="sans rise" font-size="22" fill="{C['cream']}" opacity=".92" style="animation-delay:1.2s">{esc(p['tagline'][0])}</text>
<text x="{tx}" y="256" class="sans rise" font-size="22" fill="{C['cream']}" opacity=".92" style="animation-delay:1.3s">{esc(p['tagline'][1])}</text>
<text x="{tx}" y="302" class="mono rise" font-size="13.5" fill="{C['teal']}" style="animation-delay:1.45s">{esc(p['meta'])}</text>
{''.join(chips)}"""
    return svg(W, H, body, title=f"{p['name']}. {' '.join(p['tagline'])}")


def heatmap(days) -> str:
    W, H = 1200, 270
    weeks: dict[int, list] = defaultdict(list)
    start = days[0][0] - dt.timedelta(days=(days[0][0].weekday() + 1) % 7)  # Sunday-aligned
    for d, n, lv in days:
        weeks[(d - start).days // 7].append((d, n, lv))
    gx, gy, step, cell = 76, 66, 20.4, 16
    cells, months, last_m = [], [], None
    for wi in sorted(weeks):
        for d, n, lv in weeks[wi]:
            row = (d.weekday() + 1) % 7
            x, y = gx + wi * step, gy + row * step
            cells.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell}" height="{cell}" rx="4" '
                         f'fill="{LEVELS[lv]}" class="fade" style="animation-delay:{wi * .025:.3f}s">'
                         f'<title>{n} on {d.isoformat()}</title></rect>')
        first = weeks[wi][0][0]
        if first.month != last_m and first.day <= 7:
            months.append(f'<text x="{gx + wi * step:.1f}" y="{gy - 10}" class="mono" font-size="12" '
                          f'fill="{C["muted"]}">{first.strftime("%b")}</text>')
            last_m = first.month
    labels = "".join(f'<text x="{gx - 12}" y="{gy + r * step + 12.5:.1f}" text-anchor="end" class="mono" '
                     f'font-size="11" fill="{C["dim"]}">{t}</text>'
                     for r, t in ((1, "Mon"), (3, "Wed"), (5, "Fri")))
    total = sum(n for _, n, _ in days)
    lx = W - 40 - 5 * 20 - 76
    legend = (f'<text x="{lx}" y="{H - 26}" class="mono" font-size="11" fill="{C["dim"]}">less</text>'
              + "".join(f'<rect x="{lx + 36 + i * 20}" y="{H - 38}" width="14" height="14" rx="3" fill="{c}"/>'
                        for i, c in enumerate(LEVELS))
              + f'<text x="{lx + 36 + 5 * 20 + 4}" y="{H - 26}" class="mono" font-size="11" fill="{C["dim"]}">more</text>')
    body = f"""{panel(W, H)}
<text x="40" y="40" class="mono" font-size="13" fill="{C['orange']}">$ git log --since="1 year ago"</text>
<text x="{W - 40}" y="40" text-anchor="end" class="sans" font-size="15" fill="{C['cream']}"><tspan font-weight="700">{total:,}</tspan> contributions in the last year</text>
{''.join(months)}{labels}{''.join(cells)}
<text x="40" y="{H - 26}" class="mono" font-size="11" fill="{C['dim']}">refreshed {dt.date.today().isoformat()}</text>
{legend}"""
    return svg(W, H, body, title=f"{total} contributions in the last year")


def activity(days) -> str:
    W, H = 1200, 300
    today = dt.date.today()
    past = [x for x in days if x[0] <= today]
    by_month: dict[tuple, int] = defaultdict(int)
    for d, n, _ in past:
        by_month[(d.year, d.month)] += n
    months = []
    y, m = today.year, today.month
    for _ in range(12):
        months.append((y, m))
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    months.reverse()
    vals = [by_month[k] for k in months]
    vmax = max(vals) or 1

    # streaks
    longest = cur = 0
    for _, n, _ in past:
        cur = cur + 1 if n else 0
        longest = max(longest, cur)
    current = 0
    rev = list(reversed(past))
    if rev and rev[0][1] == 0:
        rev = rev[1:]  # today not done yet does not break the streak
    for _, n, _ in rev:
        if not n:
            break
        current += 1
    best = max(past, key=lambda x: x[1]) if past else (today, 0, 0)
    wd = defaultdict(int)
    for d, n, _ in past:
        wd[d.strftime("%A")] += n
    top_wd = max(wd, key=wd.get) if wd else "-"

    bx, by, bh, bw, gap = 50, 70, 160, 40, 18
    bars = []
    for i, ((yy, mm), v) in enumerate(zip(months, vals)):
        h = max(3, v / vmax * bh)
        x = bx + i * (bw + gap)
        col = C["orange"] if v == vmax and v else C["teal"]
        bars.append(
            f'<rect x="{x}" y="{by + bh - h:.1f}" width="{bw}" height="{h:.1f}" rx="6" fill="{col}" '
            f'style="transform-box:fill-box;transform-origin:bottom;animation:grow .9s cubic-bezier(.2,.8,.2,1) both;'
            f'animation-delay:{i * .07:.2f}s"/>'
            f'<text x="{x + bw / 2}" y="{by + bh - h - 8:.1f}" text-anchor="middle" class="mono fade" font-size="12" '
            f'fill="{C["cream"]}" style="animation-delay:{.6 + i * .07:.2f}s">{v}</text>'
            f'<text x="{x + bw / 2}" y="{by + bh + 22}" text-anchor="middle" class="mono" font-size="12" '
            f'fill="{C["muted"]}">{dt.date(yy, mm, 1).strftime("%b")}</text>')

    stats = [("current streak", f"{current} d"), ("longest streak", f"{longest} d"),
             ("busiest day", f"{best[1]}"), ("favourite weekday", top_wd)]
    subs = ["", "", best[0].strftime("%d %b %Y"), ""]
    tiles = []
    sx, sy, sw, sh = 770, 56, 190, 92
    for i, ((k, v), sub) in enumerate(zip(stats, subs)):
        x, y = sx + (i % 2) * (sw + 14), sy + (i // 2) * (sh + 14)
        tiles.append(
            f'<g class="rise" style="animation-delay:{.3 + i * .12:.2f}s">'
            f'<rect x="{x}" y="{y}" width="{sw}" height="{sh}" rx="12" fill="{C["bg"]}" stroke="{C["line"]}"/>'
            f'<text x="{x + 16}" y="{y + 28}" class="mono" font-size="11.5" fill="{C["muted"]}">{esc(k)}</text>'
            f'<text x="{x + 16}" y="{y + 64}" class="sans" font-size="{30 if len(v) < 7 else 24}" font-weight="700" '
            f'fill="{C["orange"] if i == 0 else C["cream"]}">{esc(v)}</text>'
            f'<text x="{x + sw - 14}" y="{y + 28}" text-anchor="end" class="mono" font-size="11" fill="{C["dim"]}">{esc(sub)}</text></g>')
    body = f"""{panel(W, H)}
<text x="40" y="40" class="mono" font-size="13" fill="{C['orange']}">$ contributions --by month</text>
<line x1="{bx - 8}" y1="{by + bh + 0.5}" x2="{bx + 12 * (bw + gap) - gap + 8}" y2="{by + bh + 0.5}" stroke="{C['line']}"/>
{''.join(bars)}{''.join(tiles)}"""
    return svg(W, H, body, title=f"Monthly contributions; current streak {current} days, longest {longest} days")


def tile_viz(kind: str, x: int, y: int) -> str:
    if kind == "spark":
        pts = [(0, 40), (16, 34), (32, 38), (48, 26), (64, 30), (80, 18), (96, 22)]
        fut = [(96, 22), (112, 14), (128, 10), (144, 6)]
        p = " ".join(f"{x + a},{y + b}" for a, b in pts)
        f = " ".join(f"{x + a},{y + b}" for a, b in fut)
        band = (f"M{x + 96},{y + 22} L{x + 144},{y - 8} L{x + 144},{y + 20} Z")
        return (f'<path d="{band}" fill="{C["orange"]}" opacity=".15" class="fade" style="animation-delay:1.4s"/>'
                f'<polyline points="{p}" fill="none" stroke="{C["teal"]}" stroke-width="2.5" stroke-linecap="round" '
                f'stroke-dasharray="200" stroke-dashoffset="200" style="animation:draw 1.2s ease-out .3s forwards"/>'
                f'<polyline points="{f}" fill="none" stroke="{C["orange"]}" stroke-width="2.5" stroke-dasharray="4 5" '
                f'class="fade" style="animation-delay:1.3s"/>'
                f'<circle cx="{x + 144}" cy="{y + 6}" r="4" fill="{C["orange"]}" style="animation:pulse 1.6s infinite"/>')
    if kind == "dag":
        n = {"Z": (x + 72, y - 4), "T": (x + 16, y + 40), "Y": (x + 128, y + 40)}
        edges = [("Z", "T"), ("Z", "Y"), ("T", "Y")]
        out = []
        for i, (a, b) in enumerate(edges):
            (x1, y1), (x2, y2) = n[a], n[b]
            col = C["orange"] if (a, b) == ("T", "Y") else C["dim"]
            out.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{col}" stroke-width="2" '
                       f'stroke-dasharray="140" stroke-dashoffset="140" '
                       f'style="animation:draw .8s ease-out {.3 + i * .35:.2f}s forwards"/>')
        for k, (cx, cy) in n.items():
            col = C["teal"] if k != "Z" else C["dim"]
            out.append(f'<circle cx="{cx}" cy="{cy}" r="11" fill="{C["bg"]}" stroke="{col}" stroke-width="2"/>'
                       f'<text x="{cx}" y="{cy + 4}" text-anchor="middle" class="mono" font-size="11" '
                       f'fill="{C["cream"]}">{k}</text>')
        return "".join(out)
    # bars: manual effort shrinking
    out = []
    for i, h in enumerate([44, 40, 34, 30, 27, 26]):
        col = C["orange"] if i == 5 else C["teal"]
        out.append(f'<rect x="{x + i * 24}" y="{y + 44 - h}" width="16" height="{h}" rx="3" fill="{col}" '
                   f'style="transform-box:fill-box;transform-origin:bottom;animation:grow .7s ease-out both;'
                   f'animation-delay:{.2 + i * .1:.1f}s"/>')
    return "".join(out)


def stat_tile(t: dict) -> str:
    W, H = 400, 250
    body = f"""{panel(W, H)}
<text x="30" y="44" class="mono" font-size="13" font-weight="700" fill="{C['orange']}" letter-spacing="2">{esc(t['label'])}</text>
<g transform="translate(0,0)">{tile_viz(t['viz'], 220, 36)}</g>
<text x="30" y="128" class="sans rise" font-size="60" font-weight="800" fill="{C['cream']}">{esc(t['value'])}</text>
<text x="30" y="160" class="sans" font-size="15" fill="{C['cream']}" opacity=".9">{esc(t['line1'])}</text>
<text x="30" y="182" class="sans" font-size="14" fill="{C['muted']}">{esc(t['line2'])}</text>
<line x1="30" y1="202" x2="{W - 30}" y2="202" stroke="{C['line']}"/>
<text x="30" y="224" class="mono" font-size="11.5" fill="{C['teal']}">{esc(t['foot'])}</text>"""
    return svg(W, H, body, title=f"{t['label']}: {t['value']} {t['line1']}")


def title_card(text: str, dark: bool) -> str:
    W, H = 1200, 96
    fg = C["cream"] if dark else C["bg"]
    sub = C["muted"] if dark else "#5a6b85"
    tw = text_w(text, 30, bold=True)
    body = f"""<text x="12" y="40" class="mono" font-size="14" fill="{C['orange']}">~/projects $ ls --active</text>
<text x="12" y="78" class="sans" font-size="30" font-weight="700" fill="{fg}">{esc(text)}</text>
<line x1="{tw + 32:.0f}" y1="68" x2="{W - 12}" y2="68" stroke="{sub}" stroke-opacity=".35" stroke-dasharray="1100" stroke-dashoffset="1100" style="animation:draw 1.4s ease-out .2s forwards"/>"""
    return svg(W, H, body, title=text)


def repo_card(spec: dict, info: dict) -> str:
    W, H = 400, 250
    lines = wrap(info["desc"], 48)[:4]
    lang = info["lang"]
    name = spec["name"]
    size = 22 if len(name) <= 22 else 19
    badge = ""
    if spec.get("badge"):
        bw = text_w(spec["badge"], 11, mono=True) + 30
        badge = (f'<rect x="{W - 30 - bw:.0f}" y="26" width="{bw:.0f}" height="24" rx="12" fill="{C["orange"]}" fill-opacity=".14" '
                 f'stroke="{C["orange"]}" stroke-opacity=".6"/>'
                 f'<circle cx="{W - 30 - bw + 13:.0f}" cy="38" r="4" fill="{C["orange"]}" style="animation:pulse 1.4s infinite"/>'
                 f'<text x="{W - 30 - bw + 23:.0f}" y="42" class="mono" font-size="11" fill="{C["orange"]}">{esc(spec["badge"])}</text>')
    desc = "".join(f'<text x="30" y="{100 + i * 22}" class="sans" font-size="14.5" fill="{C["muted"]}">{esc(l)}</text>'
                   for i, l in enumerate(lines))
    body = f"""{panel(W, H)}
<path d="M30,32 h10 l4,4 h12 v16 h-26 z" fill="none" stroke="{C['teal']}" stroke-width="1.6"/>
{badge}
<text x="30" y="80" class="sans" font-size="{size}" font-weight="700" fill="{C['cream']}">{esc(name)}</text>
<g class="fade" style="animation-delay:.2s">{desc}</g>
<line x1="30" y1="198" x2="{W - 30}" y2="198" stroke="{C['line']}"/>
<circle cx="36" cy="221" r="6" fill="{LANG_COLORS.get(lang, C['teal'])}"/>
<text x="50" y="226" class="mono" font-size="12.5" fill="{C['cream']}">{esc(lang)}</text>
<text x="{W - 30}" y="226" text-anchor="end" class="mono" font-size="12.5" fill="{C['muted']}">★ {info['stars']}  ·  forks {info['forks']}</text>"""
    return svg(W, H, body, title=f"{name}: {info['desc']}")


# -------------------------------------------------------------------- main --

def main() -> None:
    CARDS.mkdir(exist_ok=True)
    out = {"hero.svg": hero(),
           "title-building-dark.svg": title_card("What I'm building", True),
           "title-building-light.svg": title_card("What I'm building", False)}
    try:
        days = fetch_contributions()
        out["heatmap.svg"] = heatmap(days)
        out["activity.svg"] = activity(days)
    except Exception as e:
        print(f"warn: contributions not refreshed: {e}")
    for t in TILES:
        out[f"{t['file']}.svg"] = stat_tile(t)
    for spec in REPOS:
        out[f"repo-{spec['name'].lower()}.svg"] = repo_card(spec, fetch_repo(spec))
    for name, content in out.items():
        (CARDS / name).write_text(content, encoding="utf-8")
        print(f"wrote cards/{name} ({len(content) / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
