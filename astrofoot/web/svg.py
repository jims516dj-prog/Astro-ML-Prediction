"""Small server-side SVG renderers. Colours come from CSS classes so both themes work."""
from __future__ import annotations

import math

import numpy as np

GLYPH = {"Su": "☉", "Mo": "☽", "Me": "☿", "Ve": "♀", "Ma": "♂", "Ju": "♃", "Sa": "♄", "Ur": "♅",
         "Ne": "♆", "Pl": "♇", "Ra": "☊", "Ke": "☋"}
SIGN_GLYPH = "♈♉♊♋♌♍♎♏♐♑♒♓"


def chart_wheel(ch: dict, zodiac: str, size: int = 340) -> str:
    """Ascendant on the left, zodiac counter-clockwise (the astrologer's convention)."""
    c, R = size / 2, size / 2 - 6
    asc = _deg(ch["asc"])

    def pt(lon, r):
        a = math.radians(180 + (lon - asc))
        return c + r * math.cos(a), c - r * math.sin(a)

    out = [f'<svg viewBox="0 0 {size} {size}" class="wheel" role="img" aria-label="{zodiac} chart wheel">',
           f'<circle cx="{c}" cy="{c}" r="{R}" class="wl-ring"/>',
           f'<circle cx="{c}" cy="{c}" r="{R - 26}" class="wl-ring"/>',
           f'<circle cx="{c}" cy="{c}" r="{R * 0.42}" class="wl-ring"/>']
    for s in range(12):
        x1, y1 = pt(s * 30, R)
        x2, y2 = pt(s * 30, R - 26)
        out.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" class="wl-tick"/>')
        tx, ty = pt(s * 30 + 15, R - 13)
        out.append(f'<text x="{tx:.1f}" y="{ty:.1f}" class="wl-sign">{SIGN_GLYPH[s]}\ufe0e</text>')
    for i, cu in enumerate(ch["cusps"]):
        x1, y1 = pt(cu, R - 26)
        x2, y2 = pt(cu, R * 0.42)
        cls = "wl-angle" if i in (0, 3, 6, 9) else "wl-cusp"
        out.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" class="{cls}"/>')
        nx, ny = pt(cu + ((ch["cusps"][(i + 1) % 12] - cu) % 360) / 2, R * 0.47)
        out.append(f'<text x="{nx:.1f}" y="{ny:.1f}" class="wl-hnum">{i + 1}</text>')
    placed = []
    for p in sorted(ch["planets"], key=lambda q: q["lon"]):
        lon = p["lon"]
        r = R - 44
        for q in placed:
            if abs(((lon - q[0] + 180) % 360) - 180) < 7 and abs(r - q[1]) < 1:
                r -= 17
        placed.append((lon, r))
        x, y = pt(lon, r)
        tip = f'{p["name"]} {p["pos"]}{" ℞" if p["retro"] else ""} · house {p["house"]}'
        out.append(f'<text x="{x:.1f}" y="{y:.1f}" class="wl-planet"><title>{tip}</title>{GLYPH.get(p["p"], p["p"])}\ufe0e</text>')
    out.append("</svg>")
    return "".join(out)


def _deg(s) -> float:
    if isinstance(s, (int, float)):
        return float(s)
    from ..tables import SIGN_NAMES
    d, rest = s.split("°")
    m, sign = rest.split("′ ")
    return SIGN_NAMES.index(sign) * 30 + int(d) + int(m) / 60


def bars(items: list[tuple[str, float]], unit="pp", width=520, row=22, cls="bar") -> str:
    if not items:
        return ""
    mx = max(abs(v) for _, v in items) or 1
    h = row * len(items) + 8
    mid = width * 0.55
    out = [f'<svg viewBox="0 0 {width} {h}" class="bars" role="img">',
           f'<line x1="{mid}" y1="0" x2="{mid}" y2="{h}" class="axis"/>']
    for i, (lab, v) in enumerate(items):
        y = 4 + i * row
        w = abs(v) / mx * (width - mid - 60)
        x = mid if v >= 0 else mid - w
        out.append(f'<text x="{mid - 8 if v >= 0 else mid - w - 8}" y="{y + 14}" class="lbl" text-anchor="end">{lab}</text>')
        out.append(f'<rect x="{x:.1f}" y="{y + 3}" width="{max(w, 1):.1f}" height="{row - 8}" class="{cls} {"pos" if v >= 0 else "neg"}"/>')
        out.append(f'<text x="{(x + w + 6) if v >= 0 else (x - 6)}" y="{y + 14}" class="val" '
                   f'text-anchor="{"start" if v >= 0 else "end"}">{v:+.2f} {unit}</text>')
    out.append("</svg>")
    return "".join(out)


def orb_svg(curve) -> str | None:
    if not curve:
        return None
    width, height, pad = 560, 220, 40
    vals = [c["edge_pp"] for c in curve]
    mx = max(1.0, max(abs(v) for v in vals))
    bw = (width - 2 * pad) / len(curve)
    zero = height / 2
    out = [f'<svg viewBox="0 0 {width} {height + 30}" class="chart" role="img" aria-label="learned orb">',
           f'<line x1="{pad}" y1="{zero}" x2="{width - pad}" y2="{zero}" class="axis"/>']
    for i, c in enumerate(curve):
        v = c["edge_pp"]
        h = abs(v) / mx * (height / 2 - 20)
        x = pad + i * bw + 6
        y = zero - h if v >= 0 else zero
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw - 12:.1f}" height="{max(h, 1):.1f}" class="bar {"pos" if v >= 0 else "neg"}">'
                   f'<title>{c["band"]}: {v:+.2f} pp (n={c["n"]})</title></rect>')
        out.append(f'<text x="{x + (bw - 12) / 2:.1f}" y="{height + 14}" class="lbl" text-anchor="middle">{c["band"]}</text>')
        out.append(f'<text x="{x + (bw - 12) / 2:.1f}" y="{(y - 4) if v >= 0 else (y + h + 12):.1f}" class="val" text-anchor="middle">{v:+.1f}</text>')
    out.append(f'<text x="{pad}" y="14" class="lbl">team1 edge beyond market, pp, by distance from exact</text></svg>')
    return "".join(out)


def placebo_svg(pl: dict) -> str:
    deltas = np.array(pl["deltas"]) * 1e4
    real = pl["real_delta"] * 1e4
    lo, hi = min(deltas.min(), real), max(deltas.max(), real)
    span = (hi - lo) or 1
    lo, hi = lo - 0.1 * span, hi + 0.1 * span
    bins = np.linspace(lo, hi, 16)
    counts, _ = np.histogram(deltas, bins)
    width, height, pad = 560, 200, 30
    bw = (width - 2 * pad) / len(counts)
    mx = counts.max() or 1
    X = lambda v: pad + (v - lo) / (hi - lo) * (width - 2 * pad)
    out = [f'<svg viewBox="0 0 {width} {height + 36}" class="chart" role="img" aria-label="placebo distribution">']
    for i, n in enumerate(counts):
        h = n / mx * (height - 30)
        out.append(f'<rect x="{pad + i * bw + 1:.1f}" y="{height - h:.1f}" width="{bw - 2:.1f}" height="{h:.1f}" class="bar muted"><title>{n} placebo skies</title></rect>')
    out.append(f'<line x1="{X(real):.1f}" y1="10" x2="{X(real):.1f}" y2="{height}" class="real"/>')
    out.append(f'<text x="{X(real) + 4:.1f}" y="20" class="val">real sky {real:+.2f}</text>')
    out.append(f'<line x1="{X(0):.1f}" y1="{height}" x2="{X(0):.1f}" y2="{height + 6}" class="axis"/>')
    out.append(f'<text x="{X(0):.1f}" y="{height + 18}" class="lbl" text-anchor="middle">0</text>')
    out.append(f'<text x="{pad}" y="{height + 32}" class="lbl">ΔRPS vs market model (×10⁻⁴) — left is better</text></svg>')
    return "".join(out)


def reliability_svg(P: np.ndarray, y: np.ndarray, size=240) -> str:
    conf = P.max(1)
    hit = (P.argmax(1) == y)
    edges = np.linspace(0.3, 0.9, 13)
    pad = 30
    S = lambda v: pad + (v - 0.3) / 0.6 * (size - 2 * pad)
    out = [f'<svg viewBox="0 0 {size} {size}" class="chart" role="img" aria-label="reliability diagram">',
           f'<line x1="{S(0.3)}" y1="{size - S(0.3)}" x2="{S(0.9)}" y2="{size - S(0.9)}" class="axis dashed"/>']
    pts = []
    for a, b in zip(edges[:-1], edges[1:]):
        msk = (conf > a) & (conf <= b)
        if msk.sum() >= 50:
            pts.append((conf[msk].mean(), hit[msk].mean(), msk.sum()))
    path = " ".join(f"{'M' if i == 0 else 'L'}{S(cx):.1f},{size - S(hy):.1f}" for i, (cx, hy, _) in enumerate(pts))
    out.append(f'<path d="{path}" class="line"/>')
    for cx, hy, n in pts:
        out.append(f'<circle cx="{S(cx):.1f}" cy="{size - S(hy):.1f}" r="3" class="dot"><title>predicted {cx:.2f} · observed {hy:.2f} · n={n}</title></circle>')
    out.append(f'<text x="{pad}" y="{size - 6}" class="lbl">predicted →</text>'
               f'<text x="4" y="{pad - 8}" class="lbl">observed</text></svg>')
    return "".join(out)
