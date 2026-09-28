"""Rendu vidéo : graphique animé 1080x1920 dessiné image par image (matplotlib),
sous-titres synchronisés, envoyé directement à FFmpeg avec la voix off."""
import math
import subprocess
import textwrap

import matplotlib

matplotlib.use("Agg")
import matplotlib.patheffects as pe  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402
from PIL import Image  # noqa: E402

PALETTE = ["#4CC9F0", "#F72585", "#FFD166", "#06D6A0", "#B388EB",
           "#FF9F1C", "#EF476F", "#3A86FF", "#8AC926", "#FF595E"]
BG, FG, MUTED, GRID, ACCENT = "#0E1117", "#F5F5F5", "#9AA4B2", "#262C38", "#FFD166"
STROKE = [pe.withStroke(linewidth=10, foreground="#000000")]


# ---------- formatage des nombres à la française ----------
def fmt(v, unit=""):
    a = abs(v)
    if a >= 1e9:
        s = f"{v / 1e9:.1f}".replace(".", ",") + " Md"
    elif a >= 1e6:
        s = f"{v / 1e6:.1f}".replace(".", ",") + " M"
    elif a >= 1e4:
        s = f"{v:,.0f}".replace(",", " ")
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
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0) if x1 != x0 else y1
    return pts[-1][1]


def ease(p):
    p = min(max(p, 0.0), 1.0)
    return p * p * (3 - 2 * p) * 0.25 + p * 0.75  # départ doux, vitesse quasi constante


# ---------- dessin des graphiques ----------
def style_axes(ax, unit):
    ax.set_facecolor(BG)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=26, length=0, pad=10)
    ax.grid(axis="y", color=GRID, linewidth=1.5)
    ax.set_axisbelow(True)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: fmt_tick(v)))


def draw_line(ax, series, colors, xc, x0, x1, ymin, ymax, unit):
    ax.clear()
    style_axes(ax, unit)
    ax.set_xlim(x0, x1 + (x1 - x0) * 0.32)
    ax.set_ylim(min(0, ymin), ymax * 1.12)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{int(v)}" if v <= x1 else ""))
    ends = []
    for label, pts in series.items():
        if pts[0][0] > xc:
            continue
        xs = [p[0] for p in pts if p[0] <= xc] + [min(xc, pts[-1][0])]
        ys = [p[1] for p in pts if p[0] <= xc] + [interp(pts, min(xc, pts[-1][0]))]
        ax.plot(xs, ys, color=colors[label], linewidth=7, solid_capstyle="round")
        ax.scatter([xs[-1]], [ys[-1]], s=260, color=colors[label], zorder=5, edgecolor=BG, linewidth=3)
        ends.append([xs[-1], ys[-1], label])
    # étiquettes en bout de courbe, écartées pour ne pas se chevaucher
    ends.sort(key=lambda e: e[1])
    span = (ymax * 1.12 - min(0, ymin))
    min_gap = span * 0.11
    for i in range(1, len(ends)):
        if ends[i][1] - ends[i - 1][1] < min_gap:
            ends[i][1] = ends[i - 1][1] + min_gap
    top = ymax * 1.12 - span * 0.04
    if ends and ends[-1][1] > top:  # si ça dépasse en haut, on redescend tout le groupe
        shift = ends[-1][1] - top
        for e in ends:
            e[1] -= shift
        for i in range(len(ends) - 2, -1, -1):
            if ends[i + 1][1] - ends[i][1] < min_gap:
                ends[i][1] = ends[i + 1][1] - min_gap
    for x, y, label in ends:
        short = label if len(label) <= 14 else label[:13] + "."
        ax.text(x + (x1 - x0) * 0.02, y, f"{short}\n{fmt(interp(series[label], min(xc, series[label][-1][0])), unit)}",
                color=colors[label], fontsize=24, fontweight="bold", va="center", linespacing=1.1)


def draw_bars(ax, series, colors, xc, unit, top_n=8):
    ax.clear()
    style_axes(ax, unit)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=1.5)
    vals = [(lab, interp(p, xc)) for lab, p in series.items() if p[0][0] <= xc]
    vals = sorted(vals, key=lambda t: t[1], reverse=True)[:top_n][::-1]
    if not vals:
        return
    labels = [v[0] for v in vals]
    ys = list(range(len(vals)))
    ax.barh(ys, [v[1] for v in vals], color=[colors[l] for l in labels], height=0.75)
    vmax = max(v[1] for v in vals)
    ax.set_xlim(0, vmax * 1.28)
    ax.set_ylim(-0.6, top_n - 0.4)
    ax.set_yticks(ys)
    ax.set_yticklabels([l if len(l) <= 13 else l[:12] + "." for l in labels], fontsize=27, color=FG, fontweight="bold")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: fmt_tick(v)))
    ax.tick_params(axis="x", labelsize=22)
    for y, (lab, v) in zip(ys, vals):
        ax.text(v + vmax * 0.02, y, fmt(v, unit), va="center", color=FG, fontsize=26, fontweight="bold")


# ---------- rendu complet ----------
def render(series, script, chart, words_chunks, audio_path, duration, out_mp4, thumb_path,
           handle, fps=30, preview=False, music=None, music_volume=0.08):
    dpi = 50 if preview else 100
    fps = 15 if preview else fps
    w, h = int(10.8 * dpi), int(19.2 * dpi)
    pad_end = 2.0
    total = duration + pad_end

    labels = list(series.keys())
    colors = {lab: PALETTE[i % len(PALETTE)] for i, lab in enumerate(labels)}
    xs_all = [p[0] for pts in series.values() for p in pts]
    ys_all = [p[1] for pts in series.values() for p in pts]
    x0, x1 = min(xs_all), max(xs_all)
    ymin, ymax = min(ys_all), max(ys_all)
    unit = chart.get("unite", "")
    kind = chart.get("graphique", "line")

    plt.rcParams["font.family"] = "DejaVu Sans"
    fig = plt.figure(figsize=(10.8, 19.2), dpi=dpi, facecolor=BG)
    ax = fig.add_axes([0.13, 0.33, 0.83, 0.43] if kind == "line" else [0.25, 0.33, 0.70, 0.43])

    title = "\n".join(textwrap.wrap(script["texte_ecran"], 20))
    fig.text(0.5, 0.905, title, ha="center", va="center", fontsize=58, fontweight="bold", color=FG, linespacing=1.15)
    fig.text(0.07, 0.8, "\n".join(textwrap.wrap((chart.get("indicateur_nom") or unit), 38)[:2]), ha="left", va="center",
             fontsize=22, color=MUTED)
    year_txt = fig.text(0.95, 0.785, "", ha="right", fontsize=64, fontweight="bold", color=ACCENT, alpha=0.9)
    sub_txt = fig.text(0.5, 0.2, "", ha="center", va="center", fontsize=60, fontweight="bold", color=FG,
                       path_effects=STROKE, linespacing=1.1)
    fig.text(0.5, 0.045, f"Source : {chart.get('source', 'Banque mondiale')}   ·   {handle}",
             ha="center", fontsize=22, color=MUTED)
    end_txt = fig.text(0.5, 0.2, "", ha="center", va="center", fontsize=54, fontweight="bold", color=ACCENT,
                       path_effects=STROKE)
    prog = fig.add_axes([0, 0.995, 1, 0.005])
    prog.set_axis_off()
    prog_bar = prog.barh([0], [0], color=ACCENT, height=1)[0]
    prog.set_xlim(0, 1)
    prog.set_ylim(-0.5, 0.5)

    a_start, a_end = 1.0, max(duration * 0.85, 2.0)

    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
           "-i", str(audio_path)]
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(music),
                "-filter_complex", f"[1:a]apad[v];[2:a]volume={music_volume}[m];[v][m]amix=inputs=2:duration=first[a]"]
    else:
        cmd += ["-filter_complex", "[1:a]apad[a]"]
    cmd += ["-map", "0:v", "-map", "[a]", "-t", f"{total:.2f}",
            "-c:v", "libx264", "-preset", "veryfast" if preview else "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out_mp4)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    n_frames = math.ceil(total * fps)
    thumb_frame = int(a_end * fps) + 1
    ci = 0
    for i in range(n_frames):
        t = i / fps
        p = ease((t - a_start) / (a_end - a_start))
        xc = x0 + p * (x1 - x0)
        if kind == "bar_race":
            draw_bars(ax, series, colors, xc, unit)
        else:
            draw_line(ax, series, colors, xc, x0, x1, ymin, ymax, unit)
        year_txt.set_text(str(int(round(xc))))

        while ci < len(words_chunks) - 1 and t >= words_chunks[ci + 1]["start"]:
            ci += 1
        c = words_chunks[ci] if words_chunks else None
        visible = c and c["start"] - 0.05 <= t <= c["end"] + 0.1 and t < duration
        sub_txt.set_text("\n".join(textwrap.wrap(c["text"], 18)) if visible else "")
        end_txt.set_text(f"Abonne-toi\n{handle}" if t >= duration + 0.2 else "")
        prog_bar.set_width(min(t / total, 1))

        fig.canvas.draw()
        buf = fig.canvas.buffer_rgba()
        proc.stdin.write(bytes(buf))
        if i == thumb_frame and thumb_path:  # miniature propre, sans sous-titre
            sub_txt.set_text("")
            fig.canvas.draw()
            Image.frombuffer("RGBA", (w, h), bytes(fig.canvas.buffer_rgba())).convert("RGB").save(thumb_path, quality=92)
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("FFmpeg a échoué pendant le rendu.")
    plt.close(fig)
