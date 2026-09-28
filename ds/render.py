"""Rendu vidéo v2, pensé pour la rétention (Shorts / TikTok).

- Accroche géante lisible dès la 1re image, qui glisse ensuite en titre
- Graphique synchronisé avec la voix : il avance quand la voix cite une année ou un « moment »
- Caméra qui suit la tête des courbes, pays mis en avant quand la voix les cite
- Drapeaux, noms de pays en français, badge « écart » en direct
- Sous-titres karaoké (2 à 3 mots, mot prononcé en jaune)
- Effets sonores générés, fin qui reboucle sur la 1re image
"""
import logging
import re
import subprocess
import textwrap
import urllib.request
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.patheffects as pe  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager as fm  # noqa: E402
from matplotlib.offsetbox import AnnotationBbox, OffsetImage  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from . import sfx  # noqa: E402
from .countries import COULEURS, display_name, iso2, name_keys, norm  # noqa: E402
from .voice import chunk_words  # noqa: E402

HERE = Path(__file__).resolve().parent
FLAG_DIR = HERE / "cache" / "flags"

logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
for _f in (HERE / "fonts").glob("*.ttf"):
    fm.fontManager.addfont(str(_f))
_known = {f.name for f in fm.fontManager.ttflist}
FAMILY = next(([f] for f in ("Montserrat DS", "Segoe UI", "Arial") if f in _known), ["DejaVu Sans"])
plt.rcParams["font.family"] = FAMILY
plt.rcParams["font.weight"] = "semibold"

BG_TOP, BG_BOT = (22, 29, 48), (6, 8, 14)
FG, MUTED, GRID, ACCENT, INK = "#F7F7F8", "#8D97A9", "#232B3C", "#FFD23F", "#0B0E14"
PALETTE = ["#4CC9F0", "#F72585", "#FFD166", "#06D6A0", "#B388EB",
           "#FF9F1C", "#EF476F", "#3A86FF", "#8AC926", "#FF595E"]
STROKE = [pe.withStroke(linewidth=9, foreground="#04060A")]
STROKE_THIN = [pe.withStroke(linewidth=5, foreground="#04060A")]

HOOK_SIZE, TITLE_SIZE = 84, 52
HOOK_POS, TITLE_POS = (0.5, 0.58), (0.5, 0.875)
TRANSITION, LOOP = 0.4, 0.45
FOCUS_DUR, HIGHLIGHT_DUR = 1.7, 3.0


# ---------------------------------------------------------------- utilitaires
def clamp(v, a, b):
    return max(a, min(b, v))


def smooth(p):
    p = clamp(p, 0.0, 1.0)
    return p * p * (3 - 2 * p)


def lerp(a, b, p):
    return a + (b - a) * p


def fmt(v, unit=""):
    a = abs(v)
    if a >= 1e9:
        s = f"{v / 1e9:.1f}".replace(".", ",") + " Md"
    elif a >= 1e6:
        s = f"{v / 1e6:.1f}".replace(".", ",") + " M"
    elif a >= 1e4:
        s = f"{v:,.0f}".replace(",", " ")
    elif a >= 100:
        s = f"{v:.0f}"
    else:
        s = f"{v:.1f}".replace(".", ",")
    s = s.replace(",0 ", " ") if s.endswith((" M", " Md")) else s
    return f"{s} {unit}".strip() if unit and len(unit) <= 3 else s


def fmt_tick(v):
    s = fmt(v)
    return s[:-2] if s.endswith(",0") else s


def interp(pts, x):
    if x <= pts[0][0]:
        return pts[0][1]
    for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
        if xa <= x <= xb:
            return ya + (yb - ya) * (x - xa) / (xb - xa) if xb != xa else yb
    return pts[-1][1]


def tokens_of(text):
    text = re.sub(r"\s+([?!:;»%])", " \\1", text.strip())  # pas de « ? » orphelin en fin de ligne
    return text.split()


def nice_floor(lo, hi):
    if lo <= 0 or lo < 0.35 * hi:
        return min(0.0, lo * 1.1)
    step = 10 ** int(np.floor(np.log10(max(hi - lo, 1e-9))))
    return np.floor(lo * 0.9 / step) * step


# ---------------------------------------------------------------- drapeaux
_FLAGS = {}


def flag_image(code, px):
    """Drapeau rond (téléchargé une fois depuis flagcdn.com puis mis en cache)."""
    if not code:
        return None
    key = (code, px)
    if key in _FLAGS:
        return _FLAGS[key]
    FLAG_DIR.mkdir(parents=True, exist_ok=True)
    f = FLAG_DIR / f"{code}.png"
    if not f.exists():
        try:
            req = urllib.request.Request(f"https://flagcdn.com/w160/{code}.png", headers={"User-Agent": "data-en-60s"})
            f.write_bytes(urllib.request.urlopen(req, timeout=10).read())
        except Exception:
            _FLAGS[key] = None
            return None
    big = px * 4
    img = Image.open(f).convert("RGBA").resize((big, big), Image.LANCZOS)
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, big - 1, big - 1), fill=255)
    out = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    ImageDraw.Draw(out).ellipse((3, 3, big - 4, big - 4), outline=(255, 255, 255, 240), width=max(big // 14, 4))
    arr = np.asarray(out.resize((px, px), Image.LANCZOS)) / 255.0
    _FLAGS[key] = arr
    return arr


# ---------------------------------------------------------------- texte mot par mot
class Words:
    """Texte multicolore posé mot par mot (accroche, titre, sous-titres karaoké)."""

    def __init__(self, fig, n=40, zorder=20):
        self.fig = fig
        self.pool = [fig.text(0, 0, "", ha="left", va="baseline", zorder=zorder, visible=False) for _ in range(n)]
        self.cache = {}

    def _measure(self, tokens, size, weight):
        r = self.fig.canvas.get_renderer()
        fp = fm.FontProperties(family=FAMILY, weight=weight, size=size)
        W = self.fig.bbox.width
        w = [r.get_text_width_height_descent(t, fp, ismath=False)[0] / W for t in tokens]
        a = r.get_text_width_height_descent("a", fp, ismath=False)[0]
        space = (r.get_text_width_height_descent("a a", fp, ismath=False)[0] - 2 * a) / W
        return w, space

    @staticmethod
    def _greedy(widths, space, max_w):
        lines, cur = [[]], 0.0
        for i, wd in enumerate(widths):
            add = wd if not lines[-1] else space + wd
            if lines[-1] and cur + add > max_w:
                lines.append([i])
                cur = wd
            else:
                lines[-1].append(i)
                cur += add
        return lines

    def layout(self, tokens, size, weight, max_w):
        key = (tuple(tokens), size, weight, max_w)
        if key not in self.cache:
            widths, space = self._measure(tokens, size, weight)
            n = len(self._greedy(widths, space, max_w))
            lo, hi = max(widths), max_w  # lignes équilibrées : largeur minimale gardant le même nombre de lignes
            for _ in range(14):
                mid = (lo + hi) / 2
                if len(self._greedy(widths, space, mid)) <= n:
                    hi = mid
                else:
                    lo = mid
            lines = self._greedy(widths, space, hi)
            placed = []
            for li, line in enumerate(lines):
                total = sum(widths[i] for i in line) + space * (len(line) - 1)
                x = -total / 2
                for i in line:
                    placed.append((i, li, x))
                    x += widths[i] + space
            self.cache[key] = (placed, len(lines))
        return self.cache[key]

    def draw(self, tokens, cx, cy, size, weight, max_w, colors, alpha=1.0, scale=1.0, stroke=STROKE, line_h=1.1):
        placed, nl = self.layout(tokens, size, weight, max_w)
        H, dpi = self.fig.bbox.height, self.fig.dpi
        px = size * scale * dpi / 72 / H
        top = cy + (nl - 1) * px * line_h / 2 - 0.36 * px
        for k, (i, li, x) in enumerate(placed):
            t = self.pool[k]
            t.set_text(tokens[i])
            t.set_position((cx + x * scale, top - li * px * line_h))
            t.set_fontsize(size * scale)
            t.set_fontweight(weight)
            t.set_color(colors[i])
            t.set_alpha(alpha)
            t.set_path_effects(stroke)
            t.set_visible(alpha > 0.01)
        for t in self.pool[len(placed):]:
            t.set_visible(False)

    def hide(self):
        for t in self.pool:
            t.set_visible(False)


# ---------------------------------------------------------------- synchronisation voix / graphique
def find_word(wt, mot, after):
    target = norm(str(mot)).split()
    if not target:
        return None
    first = target[0]
    for i, (tok, t) in enumerate(wt):
        if t < after - 1e-6:
            continue
        hit = tok == first or (len(first) >= 5 and tok[: len(first) - 1] == first[:-1])
        if hit and all(i + k < len(wt) and wt[i + k][0] == target[k] for k in range(1, len(target))):
            return t
    return None


def build_plan(words, duration, x0, x1, moments, t_start, series_labels, chart):
    """Transforme la narration en images-clés (temps -> année), encadrés et mises en avant."""
    wt = [(norm(w["text"]), w["start"]) for w in words]
    events = []
    if moments:
        after = t_start
        for m in moments:
            t = find_word(wt, m.get("mot", ""), after) if m.get("mot") else None
            if t is None:
                continue
            after = t
            events.append((t, m.get("annee"), m))
    else:  # automatique : le graphique rejoint chaque année citée par la voix
        for tok, t in wt:
            if t >= t_start and re.fullmatch(r"(1[89]|20)\d\d", tok) and x0 <= int(tok) <= x1:
                events.append((t, int(tok), None))
    events.sort(key=lambda e: e[0])

    keys, cur, highlights = [(t_start, x0)], x0, []

    def serie_label(name):
        if not name:
            return None
        n = norm(name)
        for lab in series_labels:
            if n in (norm(lab), norm(display_name(lab, chart))) or n in name_keys(lab, chart):
                return lab
        return None

    for t, year, m in events:
        hl = None
        if m and (m.get("texte") or m.get("serie")):
            hl = {"t": t, "year": year, "year_end": m.get("annee_fin"), "serie": serie_label(m.get("serie")),
                  "texte": m.get("texte", "")}
        if year is None:
            if hl:
                highlights.append(hl)
            continue
        year = clamp(float(year), x0, x1)
        if year >= cur and t > keys[-1][0]:
            keys.append((t, year))
            cur = year
            if hl:
                highlights.append(hl)
                keys.append((t + 1.3, year))  # petite pause pour laisser lire l'encadré
        elif hl:
            highlights.append(hl)
    if cur < x1:
        t_end = max(keys[-1][0] + 3.0, duration * 0.8)
        keys.append((min(t_end, duration + 0.2), x1))

    focus = []
    for lab in series_labels:
        ks, last = name_keys(lab, chart), -9
        for tok, t in wt:
            if tok in ks and t - last > 1.5:
                focus.append((t, t + FOCUS_DUR, lab))
                last = t
    for h in highlights:
        if h["serie"]:
            focus.append((h["t"], h["t"] + HIGHLIGHT_DUR, h["serie"]))
    return keys, highlights, focus


def x_at(keys, t):
    if t <= keys[0][0]:
        return keys[0][1]
    for (ta, xa), (tb, xb) in zip(keys, keys[1:]):
        if ta <= t <= tb:
            p = (t - ta) / (tb - ta) if tb > ta else 1
            return lerp(xa, xb, 0.55 * p + 0.45 * smooth(p))
    return keys[-1][1]


# ---------------------------------------------------------------- rendu
class Renderer:
    def __init__(self, series, script, chart, words, duration, handle, dpi):
        self.series, self.chart, self.handle = series, chart, handle
        self.labels = list(series)
        self.kind = chart.get("graphique", "line")
        self.unit = chart.get("unite", "")
        self.dpi = dpi
        self.duration = duration
        self.total = duration + LOOP

        used, self.colors = set(), {}
        for lab in self.labels:
            c = COULEURS.get(iso2(lab, chart) or "")
            if not c or c in used:
                c = next(p for p in PALETTE if p not in used) if len(used) < len(PALETTE) else PALETTE[len(used) % 10]
            used.add(c)
            self.colors[lab] = c
        self.names = {lab: display_name(lab, chart) for lab in self.labels}
        self.flag_px = int(0.62 * dpi)
        self.flags = {lab: flag_image(iso2(lab, chart), self.flag_px) for lab in self.labels}

        xs = [p[0] for pts in series.values() for p in pts]
        ys = [p[1] for pts in series.values() for p in pts]
        self.x0, self.x1 = min(xs), max(xs)
        self.span = max(self.x1 - self.x0, 1e-9)
        self.ylo = nice_floor(min(ys), max(ys))
        self.yhi = max(ys) * 1.1

        # accroche : fin de la 1re phrase, bornée entre 1,4 et 2,4 s
        first_end = next((w["end"] for w in words if re.search(r"[.?!]$", w["text"])), 2.0)
        self.t_hook = clamp(first_end, 1.4, 2.4)
        self.t_start = self.t_hook + TRANSITION
        self.keys, self.highlights, self.focus = build_plan(
            words, duration, self.x0, self.x1, script.get("moments") or [], self.t_start, self.labels, chart)
        self.chunks = chunk_words(words, max_words=3, max_chars=18)

        self.head_tokens = tokens_of(script["texte_ecran"])
        self.head_colors = [ACCENT if re.search(r"\d", tk) else FG for tk in self.head_tokens]
        ecart = script.get("ecart") or chart.get("ecart")
        self.ecart = None
        if ecart and len(ecart) == 2:
            pair = []
            for name in ecart:
                n = norm(name)
                pair += [lab for lab in self.labels if n in (norm(lab), norm(self.names[lab])) or n in name_keys(lab, chart)][:1]
            self.ecart = pair if len(pair) == 2 else None
        self.ecart_times = [w["start"] for w in words if norm(w["text"]).startswith("ecart")]

        self.pos, self.xmax_bar = {}, None
        self._build_figure(script)

    # -- mise en page fixe
    def _build_figure(self, script):
        dpi = self.dpi
        self.fig = fig = plt.figure(figsize=(10.8, 19.2), dpi=dpi)
        W, H = int(10.8 * dpi), int(19.2 * dpi)
        g = np.linspace(0, 1, H)[:, None, None]
        top, bot = np.array(BG_TOP)[None, None, :], np.array(BG_BOT)[None, None, :]
        bg = (top * (1 - g) + bot * g)
        yy, xx = np.mgrid[0:H, 0:W]
        glow = np.exp(-(((xx - W * 0.45) / (W * 0.55)) ** 2 + ((yy - H * 0.5) / (H * 0.28)) ** 2))
        bg = bg + glow[:, :, None] * np.array([10, 16, 34])[None, None, :]
        fig.figimage(np.clip(bg, 0, 255).astype(np.uint8), xo=0, yo=0, origin="upper", zorder=-10)

        rect = [0.10, 0.345, 0.72, 0.355] if self.kind == "line" else [0.30, 0.345, 0.56, 0.355]
        self.ax = fig.add_axes(rect)
        self.head = Words(fig, n=24, zorder=30)
        self.caps = Words(fig, n=8, zorder=31)

        sous_titre = script.get("sous_titre") or self.chart.get("sous_titre") or self.chart.get("titre", "")
        self.t_sub = fig.text(0.5, 0.797, "\n".join(textwrap.wrap(sous_titre, 44)[:2]), ha="center", va="center",
                              fontsize=21, color=MUTED, fontweight="semibold", linespacing=1.2)
        self.t_year = fig.text(0.90, 0.738, "", ha="right", va="center", fontsize=72, fontweight="black",
                               color=FG, alpha=0.95)
        self.t_ec_lab = fig.text(0.10, 0.765, "", ha="left", va="center", fontsize=20, color=MUTED, fontweight="bold")
        self.t_ec_val = fig.text(0.10, 0.727, "", ha="left", va="center", fontsize=54, color=ACCENT,
                                 fontweight="black")
        self.t_src = fig.text(0.10, 0.31, f"Source : {self.chart.get('source', 'Banque mondiale')}", ha="left",
                              va="center", fontsize=18, color=MUTED)
        self.t_handle = fig.text(0.82, 0.31, self.handle, ha="right", va="center", fontsize=18, color=MUTED,
                                 fontweight="bold")
        self.static = [self.t_sub, self.t_year, self.t_ec_lab, self.t_ec_val, self.t_src, self.t_handle]

    # -- axes
    def _style(self, a):
        ax = self.ax
        ax.set_facecolor((0, 0, 0, 0))
        for s in ax.spines.values():
            s.set_visible(False)
        ax.tick_params(colors=MUTED, labelsize=24, length=0, pad=10)
        for lbl in ax.get_xticklabels() + ax.get_yticklabels():
            lbl.set_alpha(a)

    def focus_weights(self, t):
        w = {}
        for a, b, lab in self.focus:
            if a - 0.15 <= t <= b + 0.3:
                v = smooth((t - a + 0.15) / 0.15) * (1 - smooth((t - b) / 0.3))
                w[lab] = max(w.get(lab, 0), v)
        return w

    def draw_line(self, t, xc, chart_a, ghost_a):
        ax, x0, span = self.ax, self.x0, self.span
        ax.clear()
        right_head = max(xc, x0 + 0.22 * span)
        follow_r = right_head + 0.42 * (right_head - x0)
        full_r = self.x1 + 0.42 * span
        ax.set_xlim(x0 - 0.01 * span, lerp(full_r, follow_r, smooth(chart_a)))
        ax.set_ylim(self.ylo, self.yhi)
        ax.grid(axis="y", color=GRID, linewidth=1.6)
        ax.set_axisbelow(True)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: fmt_tick(v)))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{int(v)}" if v <= self.x1 + 1e-6 else ""))
        self._style(max(chart_a, ghost_a * 2))
        focus = self.focus_weights(t)
        dim = max(focus.values()) if focus else 0.0

        if ghost_a > 0.01:
            for lab, pts in self.series.items():
                ax.plot([p[0] for p in pts], [p[1] for p in pts], color=self.colors[lab], lw=5, alpha=ghost_a,
                        solid_capstyle="round")
        if chart_a <= 0.01:
            return

        heads = []
        for lab, pts in self.series.items():
            if pts[0][0] > xc:
                continue
            xe = min(xc, pts[-1][0])
            xs = [p[0] for p in pts if p[0] <= xe] + [xe]
            ys = [p[1] for p in pts if p[0] <= xe] + [interp(pts, xe)]
            w = focus.get(lab, 0.0)
            a = chart_a * (1 - 0.72 * dim * (1 - w))
            lw = 6 + 4 * w
            ax.plot(xs, ys, color=self.colors[lab], lw=lw + 12, alpha=0.10 * a, solid_capstyle="round")
            ax.plot(xs, ys, color=self.colors[lab], lw=lw, alpha=a, solid_capstyle="round", zorder=3)
            heads.append([xe, ys[-1], ys[-1], lab, a, w])

        # étiquettes à droite des têtes : réparties verticalement pour ne jamais se chevaucher
        heads.sort(key=lambda h: h[1])
        rng = self.yhi - self.ylo
        gap, lo, hi = rng * 0.145, self.ylo + rng * 0.06, self.yhi - rng * 0.05
        if heads and gap * (len(heads) - 1) > hi - lo:
            gap = (hi - lo) / max(len(heads) - 1, 1)
        for _ in range(60):
            moved = False
            for i in range(1, len(heads)):
                d = heads[i][2] - heads[i - 1][2]
                if d < gap - 1e-9:
                    push = (gap - d) / 2
                    heads[i][2] += push
                    heads[i - 1][2] -= push
                    moved = True
            for h in heads:
                h[2] = clamp(h[2], lo, hi)
            if not moved:
                break
        for xe, ye, yl, lab, a, w in heads:
            c = self.colors[lab]
            ax.scatter([xe], [ye], s=170 + 120 * w, color=c, zorder=6, edgecolor="white", linewidth=2.5, alpha=a)
            ax.annotate("", (xe, ye), xytext=(xe, yl), textcoords="data",
                        arrowprops=dict(arrowstyle="-", color=c, lw=2, alpha=0.5 * a,
                                        shrinkA=0, shrinkB=0, connectionstyle="arc3"), zorder=5)
            img = self.flags.get(lab)
            tx = 26
            if img is not None:
                ax.add_artist(AnnotationBbox(OffsetImage(img, zoom=(0.9 + 0.2 * w) * 72 / self.dpi, alpha=a),
                                             (xe, yl), xybox=(34, 0), boxcoords="offset points", frameon=False,
                                             zorder=7))
                tx = 58
            ax.annotate(self.names[lab], (xe, yl), xytext=(tx, 13), textcoords="offset points", va="center",
                        fontsize=22 + 3 * w, fontweight="heavy", color=c, alpha=a, zorder=7,
                        path_effects=STROKE_THIN)
            ax.annotate(fmt(interp(self.series[lab], xe), self.unit), (xe, yl), xytext=(tx, -16),
                        textcoords="offset points", va="center", fontsize=26 + 3 * w, fontweight="black", color=FG,
                        alpha=a, zorder=7, path_effects=STROKE_THIN)
        self._draw_highlights(t, xc, chart_a)

    def _draw_highlights(self, t, xc, chart_a):
        ax = self.ax
        active = [h for h in self.highlights if h["t"] <= t < h["t"] + HIGHLIGHT_DUR]
        for h in active[-1:]:
            p = smooth((t - h["t"]) / 0.2) * (1 - smooth((t - h["t"] - HIGHLIGHT_DUR + 0.3) / 0.3)) * chart_a
            year = h["year"]
            lab = h["serie"]
            if self.kind == "bar_race":
                if lab and lab in self.pos and h["texte"]:
                    v = interp(self.series[lab], xc)
                    dy = -125 if self.pos[lab] < 3 else 115
                    ax.annotate("\n".join(textwrap.wrap(h["texte"], 20)), (v, self.pos[lab]), xytext=(-60, dy),
                                textcoords="offset points", ha="right", va="center", fontsize=26,
                                fontweight="black", color=INK, alpha=p, zorder=9,
                                bbox=dict(boxstyle="round,pad=0.55", fc=ACCENT, ec="none", alpha=p),
                                arrowprops=dict(arrowstyle="-", color=ACCENT, lw=4, alpha=p))
                continue
            if year is None:
                continue
            if h.get("year_end"):
                ax.axvspan(year, h["year_end"], color=ACCENT, alpha=0.16 * p, lw=0, zorder=1)
            if h.get("year_end"):
                year = (year + h["year_end"]) / 2
            if lab:
                yv = interp(self.series[lab], year)
                pulse = 1 + 0.25 * np.sin((t - h["t"]) * 9)
                ax.scatter([year], [yv], s=900 * pulse, facecolors="none", edgecolors=ACCENT, linewidths=4,
                           alpha=p, zorder=8)
            else:
                yv = self.ylo + (self.yhi - self.ylo) * 0.5
                ax.axvline(year, color=ACCENT, lw=3, ls=(0, (4, 3)), alpha=0.7 * p, zorder=2)
            if h["texte"]:
                high = (yv - self.ylo) / (self.yhi - self.ylo) > 0.6
                xl = ax.get_xlim()
                rel = (year - xl[0]) / (xl[1] - xl[0])
                dx = -270 if rel > 0.6 else (60 if rel < 0.25 else -60)
                ax.annotate("\n".join(textwrap.wrap(h["texte"], 20)), (year, yv),
                            xytext=(dx, -150 if high else 120), textcoords="offset points", ha="left", va="center",
                            fontsize=26, fontweight="black", color=INK, alpha=p, zorder=9,
                            bbox=dict(boxstyle="round,pad=0.55", fc=ACCENT, ec="none", alpha=p),
                            arrowprops=dict(arrowstyle="-", color=ACCENT, lw=4, alpha=p))

    def draw_bars(self, t, xc, chart_a, ghost_a, top_n=8):
        ax = self.ax
        ax.clear()
        a_all = max(chart_a, ghost_a)
        vals = {lab: interp(p, xc) for lab, p in self.series.items() if p[0][0] <= xc}
        ranked = sorted(vals, key=lambda lab: -vals[lab])
        dt = clamp(t - getattr(self, "_t_prev", t), 0, 0.2)
        self._t_prev = t
        k = 1 - np.exp(-dt / 0.11) if dt > 0 else 1.0  # lissage indépendant du nombre d'images/s
        for r, lab in enumerate(ranked):
            self.pos[lab] = r if lab not in self.pos else self.pos[lab] + (r - self.pos[lab]) * k
        vmax = max(vals[lab] for lab in ranked[:top_n]) if ranked else 1
        target = vmax * 1.32
        self.xmax_bar = target if self.xmax_bar is None else self.xmax_bar + (target - self.xmax_bar) * min(k * 0.8, 1)
        ax.set_xlim(0, self.xmax_bar)
        ax.set_ylim(top_n - 0.4, -0.6)
        ax.grid(axis="x", color=GRID, linewidth=1.6)
        ax.set_axisbelow(True)
        ax.set_yticks([])
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: fmt_tick(v)))
        self._style(a_all)
        focus = {lab: w for lab, w in self.focus_weights(t).items() if self.pos.get(lab, 99) < top_n - 0.3}
        dim = max(focus.values()) if focus else 0.0
        for lab in vals:
            y = self.pos[lab]
            if y > top_n - 0.3:
                continue
            v, w = vals[lab], focus.get(lab, 0.0)
            a = a_all * (1 - 0.65 * dim * (1 - w))
            ax.barh(y, v, height=0.74, color=self.colors[lab], alpha=a, zorder=3)
            ax.text(-0.02 * self.xmax_bar, y, self.names[lab], ha="right", va="center", fontsize=25 + 2 * w,
                    fontweight="heavy", color=FG, alpha=a, clip_on=False)
            img = self.flags.get(lab)
            fx = v
            if img is not None:
                ax.add_artist(AnnotationBbox(OffsetImage(img, zoom=0.85 * 72 / self.dpi, alpha=a), (v, y),
                                             xybox=(-2, 0), boxcoords="offset points", box_alignment=(1, 0.5),
                                             frameon=False, zorder=5))
            ax.annotate(fmt(v, self.unit), (fx, y), xytext=(12, 0), textcoords="offset points", va="center",
                        fontsize=26, fontweight="black", color=FG, alpha=a, zorder=6)
        self._draw_highlights(t, xc, chart_a)

    def headline(self, t):
        """Position/échelle de l'accroche : géante au centre, puis titre, puis retour au centre (boucle)."""
        if t < self.t_hook:
            p = 0.0
        elif t < self.t_start:
            p = smooth((t - self.t_hook) / TRANSITION)
        elif t < self.total - LOOP:
            p = 1.0
        else:
            p = 1 - smooth((t - (self.total - LOOP)) / LOOP)
        pop = 0.94 + 0.06 * smooth(t / 0.15) if t < 0.2 else 1.0
        cx = lerp(HOOK_POS[0], TITLE_POS[0], p)
        cy = lerp(HOOK_POS[1], TITLE_POS[1], p)
        scale = lerp(1.0, TITLE_SIZE / HOOK_SIZE, p) * pop
        return p, cx, cy, scale

    def frame(self, t):
        p, cx, cy, scale = self.headline(t)
        chart_a, ghost_a = p, 0.16 * (1 - p)
        xc = x_at(self.keys, t) if t >= self.t_start else self.x0
        if t >= self.total - LOOP:
            xc = self.x1
        if self.kind == "bar_race":
            self.draw_bars(t, xc, chart_a, ghost_a * 1.3)
        else:
            self.draw_line(t, xc, chart_a, ghost_a)

        self.head.draw(self.head_tokens, cx, cy, HOOK_SIZE, "black", 0.86, self.head_colors, scale=scale)
        for s in self.static:
            s.set_alpha(chart_a)
        self.t_year.set_text(str(int(round(xc))))
        if self.ecart:
            a, b = self.ecart
            gap = abs(interp(self.series[a], xc) - interp(self.series[b], xc))
            self.t_ec_lab.set_text(f"ÉCART {self.names[a].upper()} / {self.names[b].upper()}")
            self.t_ec_val.set_text(fmt(gap, self.unit))
            bump = max([1 - abs(t - te - 0.15) / 0.35 for te in self.ecart_times] + [0])
            self.t_ec_val.set_fontsize(54 * (1 + 0.18 * bump))

        c = next((c for c in self.chunks if c["start"] - 0.05 <= t <= c["end"] + 0.1), None)
        if c and t < self.duration:
            toks = [w["text"] for w in c["words"]]
            cols = [ACCENT if w["start"] - 0.02 <= t < (c["words"][k + 1]["start"] if k + 1 < len(c["words"])
                                                         else c["end"] + 0.1) else FG
                    for k, w in enumerate(c["words"])]
            pop = 0.9 + 0.1 * smooth((t - c["start"]) / 0.08)
            self.caps.draw(toks, 0.47, 0.255, 60, "black", 0.76, cols, scale=pop)
        else:
            self.caps.hide()

    def rgba(self):
        self.fig.canvas.draw()
        return self.fig.canvas.buffer_rgba()

    def sfx_events(self):
        ev = [(self.t_hook, "whoosh", 0.35), (self.total - LOOP - 0.05, "whoosh_rev", 0.25)]
        ev += [(h["t"], "pop", 0.45) for h in self.highlights]
        ev += [(a, "tick", 0.12) for a, _, _ in self.focus]
        return ev

    def thumbnail(self, path):
        """Miniature : graphique complet + accroche en grand."""
        t = self.total - LOOP - 0.01
        self.frame(t)
        self.draw_line(t, self.x1, 0.3, 0) if self.kind == "line" else self.draw_bars(t, self.x1, 0.3, 0)
        for s_ in self.static:
            s_.set_alpha(0.3)
        self.caps.hide()
        self.head.draw(self.head_tokens, HOOK_POS[0], HOOK_POS[1] + 0.02, HOOK_SIZE, "black", 0.86,
                       self.head_colors)
        W, H = self.fig.canvas.get_width_height()
        Image.frombuffer("RGBA", (W, H), bytes(self.rgba())).convert("RGB").save(path, quality=92)


def render(series, script, chart, words, audio_path, duration, out_mp4, thumb_path,
           handle, fps=30, preview=False, music=None, music_volume=0.08):
    dpi = 50 if preview else 100
    fps = 15 if preview else fps
    R = Renderer(series, script, chart, words, duration, handle, dpi)
    W, H = R.fig.canvas.get_width_height()
    total = R.total

    sfx_path = Path(out_mp4).with_name("sfx.wav")
    sfx.compose(total, R.sfx_events(), sfx_path)

    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
           "-i", str(audio_path), "-i", str(sfx_path)]
    mix = "[1:a]apad[v];[2:a]volume=0.6[s]"
    inputs = "[v][s]"
    n = 2
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(music)]
        mix += f";[3:a]volume={music_volume}[m]"
        inputs += "[m]"
        n = 3
    mix += f";{inputs}amix=inputs={n}:duration=first:dropout_transition=0:normalize=0[a]"
    cmd += ["-filter_complex", mix, "-map", "0:v", "-map", "[a]", "-t", f"{total:.2f}",
            "-c:v", "libx264", "-preset", "veryfast" if preview else "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out_mp4)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n_frames = int(round(total * fps))
    try:
        for i in range(n_frames):
            R.frame(i / fps)
            proc.stdin.write(bytes(R.rgba()))
    finally:
        proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("FFmpeg a échoué pendant le rendu.")
    if thumb_path:
        R.thumbnail(thumb_path)
    plt.close(R.fig)
    return {"keys": R.keys, "highlights": R.highlights, "focus": len(R.focus), "hook": R.t_hook}
