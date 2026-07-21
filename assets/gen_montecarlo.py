#!/usr/bin/env python3
"""Generate a self-animating MONTE CARLO option-pricing SVG for the profile.

Pure standard library, no JS. Simulates geometric-Brownian-motion price paths
for a European call, draws them fanning out from today and "growing" left to
right via SMIL stroke-dashoffset animation (green if the path finishes in the
money, dim if not), overlays the strike, a terminal-price histogram, and a
live fair-value readout that counts up through more and more paths and
converges toward the closed-form Black–Scholes price.

Re-run daily by a GitHub Action so the simulation is never the same twice.
"""
from __future__ import annotations

import math
import os
import random

# ---- canvas -----------------------------------------------------------------
W, H = 940, 330
BG = "#0d1117"
GRID = "#1b2230"
GREEN = "#3fb950"
RED = "#f85149"
BLUE = "#58a6ff"
GOLD = "#f0c674"
TEXT = "#e6edf3"
DIM = "#8b949e"

# ---- model params -----------------------------------------------------------
S0, K = 100.0, 100.0
R, SIGMA, T = 0.02, 0.20, 1.0
STEPS = 52          # weekly steps over a year
N_DRAW = 32         # paths actually drawn
N_EST = 2000        # paths used for the converging estimate
CYCLE = 9.0         # seconds per animation loop

PLOT_L, PLOT_R, PLOT_T, PLOT_B = 150, 700, 66, 292
HIST_L, HIST_R = 712, 890


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def black_scholes_call(s, k, r, sig, t):
    d1 = (math.log(s / k) + (r + 0.5 * sig * sig) * t) / (sig * math.sqrt(t))
    d2 = d1 - sig * math.sqrt(t)
    return s * _norm_cdf(d1) - k * math.exp(-r * t) * _norm_cdf(d2)


def simulate(seed: int):
    rng = random.Random(seed)
    dt = T / STEPS
    drift = (R - 0.5 * SIGMA * SIGMA) * dt
    vol = SIGMA * math.sqrt(dt)
    draw_paths, terminals = [], []
    payoffs = []
    for j in range(N_EST):
        s = S0
        path = [s]
        for _ in range(STEPS):
            s *= math.exp(drift + vol * rng.gauss(0, 1))
            path.append(s)
        payoffs.append(max(s - K, 0.0))
        if j < N_DRAW:
            draw_paths.append(path)
            terminals.append(s)
    disc = math.exp(-R * T)
    # cumulative MC estimate after k paths
    running, cum = [], 0.0
    for i, p in enumerate(payoffs, 1):
        cum += p
        running.append(disc * cum / i)
    return draw_paths, terminals, payoffs, running


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _text_cycle(pairs, x, anchor_dur=CYCLE):
    """Cross-fade a sequence of strings at a fixed x (SMIL can't animate text)."""
    n = len(pairs)
    out = []
    for i, v in enumerate(pairs):
        a, b = i / n, (i + 1) / n
        kt = f"0;{max(a-0.0001,0):.4f};{a:.4f};{b:.4f};{min(b+0.0001,1):.4f};1"
        out.append(f'<tspan x="{x}">{_esc(v)}'
                   f'<animate attributeName="opacity" values="0;0;1;1;0;0" keyTimes="{kt}" '
                   f'dur="{anchor_dur}s" repeatCount="indefinite" calcMode="discrete"/></tspan>')
    return "".join(out)


def build(seed: int = 23) -> str:
    draw_paths, terminals, payoffs, running = simulate(seed)
    bs = black_scholes_call(S0, K, R, SIGMA, T)

    all_vals = [v for p in draw_paths for v in p]
    ymin, ymax = min(all_vals), max(all_vals)
    ymin = min(ymin, K) * 0.99
    ymax = max(ymax, K) * 1.01
    span = ymax - ymin

    def X(i):
        return PLOT_L + (i / STEPS) * (PLOT_R - PLOT_L)

    def Y(v):
        return PLOT_B - (v - ymin) / span * (PLOT_B - PLOT_T)

    p = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" '
        f'role="img" aria-label="Monte Carlo option pricing">',
        f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="16" fill="{BG}" stroke="#232b3a"/>',
        # header
        f'<text x="20" y="34" font-family="\'Segoe UI\',Arial,sans-serif" font-size="16" '
        f'font-weight="700" fill="{TEXT}">MONTE CARLO</text>',
        f'<text x="150" y="34" font-family="\'SFMono-Regular\',Consolas,monospace" '
        f'font-size="12" fill="{DIM}">European call · {N_EST:,} simulated paths · GBM</text>',
        f'<text x="{W-20}" y="34" text-anchor="end" '
        f'font-family="\'SFMono-Regular\',Consolas,monospace" font-size="11" fill="{DIM}">'
        f'S₀={S0:.0f}  K={K:.0f}  σ={SIGMA:.0%}  T={T:.0f}y</text>',
    ]

    # gridlines + y labels
    for g in range(5):
        v = ymin + span * g / 4
        gy = Y(v)
        p.append(f'<line x1="{PLOT_L}" y1="{gy:.1f}" x2="{PLOT_R}" y2="{gy:.1f}" '
                 f'stroke="{GRID}" stroke-width="1"/>')
        p.append(f'<text x="{PLOT_L-8}" y="{gy+4:.1f}" text-anchor="end" '
                 f'font-family="\'SFMono-Regular\',Consolas,monospace" font-size="10" '
                 f'fill="{DIM}">{v:.0f}</text>')

    # strike line
    ky = Y(K)
    p.append(f'<line x1="{PLOT_L}" y1="{ky:.1f}" x2="{HIST_R}" y2="{ky:.1f}" '
             f'stroke="{GOLD}" stroke-width="1.4" stroke-dasharray="5 4" opacity="0.9"/>')
    p.append(f'<text x="{PLOT_L+4}" y="{ky-5:.1f}" '
             f'font-family="\'SFMono-Regular\',Consolas,monospace" font-size="10" '
             f'fill="{GOLD}">strike {K:.0f} — above = in the money</text>')

    # start dot
    p.append(f'<circle cx="{X(0):.1f}" cy="{Y(S0):.1f}" r="3.5" fill="{BLUE}"/>')

    # paths — each grows in via stroke-dashoffset, staggered
    for j, path in enumerate(draw_paths):
        pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(path))
        itm = path[-1] > K
        col = GREEN if itm else RED
        opac = 0.72 if itm else 0.38
        # rough polyline length for dash animation
        L = 0.0
        for i in range(1, len(path)):
            L += math.hypot(X(i) - X(i - 1), Y(path[i]) - Y(path[i - 1]))
        L = max(L, 1.0)
        start = (j / len(draw_paths)) * 0.55
        end = start + 0.34
        p.append(
            f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="1.3" '
            f'opacity="{opac}" stroke-dasharray="{L:.0f}" stroke-dashoffset="{L:.0f}">'
            f'<animate attributeName="stroke-dashoffset" values="{L:.0f};{L:.0f};0;0;{L:.0f}" '
            f'keyTimes="0;{start:.3f};{end:.3f};0.94;1" dur="{CYCLE}s" '
            f'repeatCount="indefinite" calcMode="linear"/>'
            f'</polyline>')

    # terminal-price histogram on the right (horizontal bars aligned to price axis)
    bins = 22
    counts = [0] * bins
    lo, hi = ymin, ymax
    # recompute a full terminal-price sample for a smooth histogram shape
    term_all = []
    rng = random.Random(seed + 1)
    dt = T / STEPS
    drift = (R - 0.5 * SIGMA * SIGMA) * dt
    vv = SIGMA * math.sqrt(dt)
    for _ in range(N_EST):
        s = S0
        for _ in range(STEPS):
            s *= math.exp(drift + vv * rng.gauss(0, 1))
        term_all.append(s)
    for s in term_all:
        if lo <= s <= hi:
            b = min(bins - 1, max(0, int((s - lo) / (hi - lo) * bins)))
            counts[b] += 1
    cmax = max(counts) or 1
    bin_h = (PLOT_B - PLOT_T) / bins
    p.append(f'<text x="{HIST_L}" y="{PLOT_T-6}" '
             f'font-family="\'SFMono-Regular\',Consolas,monospace" font-size="10" '
             f'fill="{DIM}">payoff dist.</text>')
    for b, c in enumerate(counts):
        if c == 0:
            continue
        yb = PLOT_B - (b + 1) * bin_h
        vmid = lo + (b + 0.5) / bins * (hi - lo)
        col = GREEN if vmid > K else RED
        bw = (HIST_R - HIST_L) * c / cmax
        p.append(f'<rect x="{HIST_L}" y="{yb+1:.1f}" width="{bw:.1f}" height="{bin_h-1.5:.1f}" '
                 f'rx="1.5" fill="{col}" fill-opacity="0.5"/>')

    # converging fair-value readout (counts up through more paths)
    checkpoints = [3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987, 1500, N_EST]
    price_strs = [f"${running[k-1]:.2f}" for k in checkpoints]
    n_strs = [f"n = {k:,} paths" for k in checkpoints]
    box_x, box_y = PLOT_L + 8, PLOT_T + 6
    p.append(f'<rect x="{box_x}" y="{box_y}" width="196" height="60" rx="9" '
             f'fill="#0d1117" fill-opacity="0.86" stroke="{GRID}"/>')
    p.append(f'<text x="{box_x+14}" y="{box_y+20}" '
             f'font-family="\'SFMono-Regular\',Consolas,monospace" font-size="11" fill="{DIM}">'
             f'estimated fair value</text>')
    p.append(f'<text x="{box_x+14}" y="{box_y+44}" '
             f'font-family="\'SFMono-Regular\',Consolas,monospace" font-size="22" '
             f'font-weight="700" fill="{GREEN}">'
             + _text_cycle(price_strs, box_x + 14) + '</text>')
    p.append(f'<text x="{box_x+182}" y="{box_y+44}" text-anchor="end" '
             f'font-family="\'SFMono-Regular\',Consolas,monospace" font-size="10" fill="{DIM}">'
             + _text_cycle(n_strs, box_x + 182) + '</text>')

    # Black–Scholes reference
    p.append(f'<text x="20" y="{H-12}" font-family="\'Segoe UI\',Arial,sans-serif" '
             f'font-size="11" fill="{DIM}">converges to Black–Scholes closed form '
             f'<tspan fill="{GOLD}" font-weight="700">${bs:.2f}</tspan> — '
             f'every path is SMIL-animated, zero JavaScript · regenerated daily</text>')

    p.append("</svg>")
    return "".join(p)


if __name__ == "__main__":
    svg = build()
    out = os.path.join(os.path.dirname(__file__), "montecarlo.svg")
    with open(out, "w") as f:
        f.write(svg)
    print(f"montecarlo.svg written ({len(svg)} bytes) · BS=${black_scholes_call(S0,K,R,SIGMA,T):.2f}")
