#!/usr/bin/env python3
"""Generate a self-contained, self-animating ORDER BOOK SVG for the profile.

Pure standard library, no JS — every bit of motion is SMIL <animate>. It
precomputes a short seeded sequence of limit-order-book states (a mid-price
random walk, depth on both sides, and a tape of executed trades) and animates
through them: the depth bars breathe as orders arrive and cancel, the tape
scrolls, the best bid/ask and last trade update, and a LIVE dot pulses.

Re-run daily by a GitHub Action so the book is never the same twice.
"""
from __future__ import annotations

import random

# ---- canvas -----------------------------------------------------------------
W, H = 940, 356
BG = "#0d1117"
PANEL = "#111823"
GRID = "#1b2230"
GREEN = "#3fb950"
RED = "#f85149"
BLUE = "#58a6ff"
TEXT = "#e6edf3"
DIM = "#8b949e"

LEVELS = 6          # price levels per side
FRAMES = 10         # distinct book states we cycle through
DUR = 12.0          # seconds for a full cycle
TICK = 0.05         # price increment between levels


def simulate(seed: int):
    """Return (frames, trades). Each frame: dict with mid, bid_sizes, ask_sizes.
    trades: list of (price, size, side) executed prints, newest last."""
    rng = random.Random(seed)
    mid = 100.00
    frames = []
    trades = []
    for _ in range(FRAMES):
        mid = round(mid + rng.choice([-1, 0, 0, 1]) * TICK, 2)
        bid_sizes = [rng.randint(3, 40) + (LEVELS - i) * rng.randint(1, 5)
                     for i in range(LEVELS)]
        ask_sizes = [rng.randint(3, 40) + (LEVELS - i) * rng.randint(1, 5)
                     for i in range(LEVELS)]
        frames.append({"mid": mid, "bids": bid_sizes, "asks": ask_sizes})
        # a couple of trades per frame
        for _ in range(rng.randint(1, 2)):
            side = rng.random() < 0.5
            px = mid + (TICK if not side else -TICK)
            trades.append((round(px, 2), rng.randint(1, 30), side))
    return frames, trades


def _anim(attr, values, dur=DUR, extra=""):
    vals = ";".join(str(v) for v in values)
    return (f'<animate attributeName="{attr}" values="{vals}" '
            f'dur="{dur}s" repeatCount="indefinite" calcMode="linear"{extra}/>')


def build(seed: int = 7) -> str:
    frames, trades = simulate(seed)
    maxsz = max(max(f["bids"] + f["asks"]) for f in frames)

    # layout: ladder occupies left ~62%, tape on the right
    lad_x0, lad_x1 = 20, 560
    center_x = (lad_x0 + lad_x1) / 2
    row_h = 20
    top_y = 64
    half = LEVELS * row_h
    max_bar = (lad_x1 - center_x) - 46  # leave room for size labels

    p = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" '
        f'role="img" aria-label="animated limit order book">',
        f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="16" fill="{BG}" stroke="#232b3a"/>',
        # header
        f'<text x="20" y="34" font-family="\'Segoe UI\',Arial,sans-serif" font-size="16" '
        f'font-weight="700" fill="{TEXT}">LIVE ORDER BOOK</text>',
        f'<text x="182" y="34" font-family="\'SFMono-Regular\',Consolas,monospace" '
        f'font-size="12" fill="{DIM}">price–time priority · matching engine</text>',
        # LIVE dot (pulsing)
        f'<circle cx="{W-92}" cy="29" r="5" fill="{GREEN}">'
        f'<animate attributeName="opacity" values="1;0.25;1" dur="1.4s" repeatCount="indefinite"/>'
        f'</circle>',
        f'<text x="{W-80}" y="34" font-family="\'SFMono-Regular\',Consolas,monospace" '
        f'font-size="12" font-weight="700" fill="{GREEN}">LIVE</text>',
        # column headers
        f'<text x="{lad_x0}" y="56" font-family="\'SFMono-Regular\',Consolas,monospace" '
        f'font-size="11" fill="{DIM}">price</text>',
        f'<text x="{lad_x1}" y="56" text-anchor="end" '
        f'font-family="\'SFMono-Regular\',Consolas,monospace" font-size="11" fill="{DIM}">size</text>',
    ]

    # --- ASK side (top, red), levels far-to-near so best ask sits by the spread
    for i in range(LEVELS):
        # level index from spread outward: nearest ask is level 0 visually bottom of ask block
        depth = LEVELS - 1 - i  # 0 = best ask (closest to mid)
        y = top_y + i * row_h
        price = frames[0]["mid"] + (depth + 1) * TICK
        widths = [max_bar * f["asks"][depth] / maxsz for f in frames]
        widths_seq = [f"{w:.1f}" for w in widths] + [f"{widths[0]:.1f}"]
        sizes_present = [f["asks"][depth] for f in frames]
        p.append(f'<rect x="{center_x}" y="{y+3}" height="{row_h-6}" rx="2" '
                 f'fill="{RED}" fill-opacity="0.55" width="{widths[0]:.1f}">'
                 f'{_anim("width", widths_seq)}</rect>')
        p.append(f'<text x="{lad_x0}" y="{y+14}" font-family="\'SFMono-Regular\',Consolas,monospace" '
                 f'font-size="12" fill="{RED}">{price:.2f}</text>')
        # size label cycles through the frame values (discrete)
        p.append(_size_label(lad_x1, y + 14, sizes_present, RED))

    # --- spread band
    spread_y = top_y + LEVELS * row_h
    p.append(f'<rect x="{lad_x0}" y="{spread_y-1}" width="{lad_x1-lad_x0}" height="20" '
             f'rx="3" fill="{PANEL}" stroke="{GRID}"/>')
    # animated mid price
    mids = [f"{f['mid']:.2f}" for f in frames]
    p.append(f'<text x="{center_x}" y="{spread_y+14}" text-anchor="middle" '
             f'font-family="\'SFMono-Regular\',Consolas,monospace" font-size="13" '
             f'font-weight="700" fill="{TEXT}">'
             + _text_cycle(mids, center_x) + '</text>')
    p.append(f'<text x="{lad_x0+6}" y="{spread_y+14}" '
             f'font-family="\'SFMono-Regular\',Consolas,monospace" font-size="11" fill="{DIM}">mid</text>')
    p.append(f'<text x="{lad_x1-6}" y="{spread_y+14}" text-anchor="end" '
             f'font-family="\'SFMono-Regular\',Consolas,monospace" font-size="11" fill="{DIM}">'
             f'spread {TICK*2:.2f}</text>')

    # --- BID side (bottom, green)
    bid_top = spread_y + 20
    for i in range(LEVELS):
        depth = i  # 0 = best bid (closest to mid)
        y = bid_top + i * row_h
        price = frames[0]["mid"] - (depth + 1) * TICK
        widths = [max_bar * f["bids"][depth] / maxsz for f in frames]
        widths_seq = [f"{w:.1f}" for w in widths] + [f"{widths[0]:.1f}"]
        sizes_present = [f["bids"][depth] for f in frames]
        p.append(f'<rect x="{center_x}" y="{y+3}" height="{row_h-6}" rx="2" '
                 f'fill="{GREEN}" fill-opacity="0.55" width="{widths[0]:.1f}">'
                 f'{_anim("width", widths_seq)}</rect>')
        p.append(f'<text x="{lad_x0}" y="{y+14}" font-family="\'SFMono-Regular\',Consolas,monospace" '
                 f'font-size="12" fill="{GREEN}">{price:.2f}</text>')
        p.append(_size_label(lad_x1, y + 14, sizes_present, GREEN))

    # center divider
    p.append(f'<line x1="{center_x}" y1="{top_y}" x2="{center_x}" y2="{bid_top + LEVELS*row_h}" '
             f'stroke="{GRID}" stroke-width="1"/>')

    # --- TAPE (right): scrolling executed trades ------------------------------
    tape_x = 600
    p.append(f'<line x1="{tape_x-16}" y1="{top_y-8}" x2="{tape_x-16}" y2="{bid_top+LEVELS*row_h}" '
             f'stroke="{GRID}" stroke-width="1"/>')
    p.append(f'<text x="{tape_x}" y="56" font-family="\'SFMono-Regular\',Consolas,monospace" '
             f'font-size="11" fill="{DIM}">time &amp; sales</text>')
    tape_top = top_y
    tape_h = (bid_top + LEVELS * row_h) - tape_top
    line_h = 22
    rows = trades[-12:]
    # duplicate rows so the upward scroll loops seamlessly
    seq = rows + rows
    scroll_dur = len(rows) * 1.6
    p.append(f'<clipPath id="tapeclip"><rect x="{tape_x-10}" y="{tape_top}" '
             f'width="{W-tape_x-8}" height="{tape_h}"/></clipPath>')
    p.append(f'<g clip-path="url(#tapeclip)">')
    p.append(f'<g transform="translate(0,0)">'
             f'<animateTransform attributeName="transform" type="translate" '
             f'values="0,0; 0,{-line_h*len(rows)}" dur="{scroll_dur}s" '
             f'repeatCount="indefinite" calcMode="linear"/>')
    for j, (px, sz, is_buy) in enumerate(seq):
        y = tape_top + 14 + j * line_h
        col = GREEN if is_buy else RED
        arrow = "▲" if is_buy else "▼"
        p.append(f'<text x="{tape_x}" y="{y}" font-family="\'SFMono-Regular\',Consolas,monospace" '
                 f'font-size="12" fill="{col}">{arrow} {px:.2f}</text>')
        p.append(f'<text x="{W-24}" y="{y}" text-anchor="end" '
                 f'font-family="\'SFMono-Regular\',Consolas,monospace" font-size="12" fill="{DIM}">'
                 f'{sz}</text>')
    p.append('</g></g>')

    # footer caption
    p.append(f'<text x="20" y="{H-12}" font-family="\'Segoe UI\',Arial,sans-serif" '
             f'font-size="11" fill="{DIM}">every bar, print &amp; tick is SMIL-animated — '
             f'zero JavaScript · regenerated daily</text>')
    p.append("</svg>")
    return "".join(p)


def _size_label(x, y, sizes, color):
    """A right-aligned size number that cycles through per-frame values."""
    return (f'<text x="{x}" y="{y}" text-anchor="end" '
            f'font-family="\'SFMono-Regular\',Consolas,monospace" font-size="12" fill="{color}">'
            + _text_cycle([str(s) for s in sizes], x) + '</text>')


def _text_cycle(values, x):
    """Stack of <tspan>s at the same x, each visible only during its slot — SMIL
    can't animate text content, so we cross-fade precomputed strings. Each tspan
    repeats the parent x so they overlap instead of flowing left-to-right."""
    n = len(values)
    out = []
    for i, v in enumerate(values):
        a, b = i / n, (i + 1) / n
        kt = f"0;{max(a-0.0001,0):.4f};{a:.4f};{b:.4f};{min(b+0.0001,1):.4f};1"
        vals = "0;0;1;1;0;0"
        out.append(f'<tspan x="{x}">{_esc(v)}'
                   f'<animate attributeName="opacity" values="{vals}" keyTimes="{kt}" '
                   f'dur="{DUR}s" repeatCount="indefinite" calcMode="discrete"/></tspan>')
    return "".join(out)


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


if __name__ == "__main__":
    import os
    svg = build()
    out = os.path.join(os.path.dirname(__file__), "orderbook.svg")
    with open(out, "w") as f:
        f.write(svg)
    print(f"orderbook.svg written ({len(svg)} bytes)")
