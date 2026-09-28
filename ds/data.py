"""Données : téléchargement Banque mondiale (gratuit, sans clé) et lecture CSV.

Format CSV commun (format « long ») :  label,x,value
    label = nom de la série (ex: pays), x = année, value = valeur
"""
import csv
from collections import defaultdict

import requests

WB_URL = "https://api.worldbank.org/v2/country/{countries}/indicator/{indicator}"


def fetch_worldbank(indicator, countries, start, end, out_csv):
    """Télécharge un indicateur Banque mondiale pour une liste de codes pays ISO3."""
    url = WB_URL.format(countries=";".join(countries), indicator=indicator)
    r = requests.get(url, params={"format": "json", "per_page": 20000, "date": f"{start}:{end}"}, timeout=60)
    r.raise_for_status()
    payload = r.json()
    if not isinstance(payload, list) or len(payload) < 2 or not payload[1]:
        raise RuntimeError(f"Aucune donnée pour {indicator} ({countries}). Vérifie le code indicateur.")
    rows, name, codes = [], payload[1][0]["indicator"]["value"], {}
    for item in payload[1]:
        codes[item["country"]["value"]] = str(item["country"]["id"]).lower()
        if item["value"] is None:
            continue
        rows.append((item["country"]["value"], int(item["date"]), float(item["value"])))
    if not rows:
        raise RuntimeError("Toutes les valeurs sont vides pour cette période.")
    rows.sort(key=lambda t: (t[0], t[1]))
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["label", "x", "value"])
        w.writerows(rows)
    return name, len(rows), codes


def load_series(csv_path):
    """Retourne {label: [(x, y), ...]} trié par x."""
    series = defaultdict(list)
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["value"] in ("", None):
                continue
            series[row["label"]].append((float(row["x"]), float(row["value"])))
    return {k: sorted(v) for k, v in series.items()}


def summarize(series, unit=""):
    """Résumé chiffré envoyé à Gemini pour qu'il n'invente aucun chiffre."""
    lines = []
    for label, pts in series.items():
        (x0, y0), (x1, y1) = pts[0], pts[-1]
        xmax, ymax = max(pts, key=lambda p: p[1])
        xmin, ymin = min(pts, key=lambda p: p[1])
        evol = f"{(y1 - y0) / y0 * 100:+.0f} %" if y0 else "n/a"
        ratio = f", x{y1 / y0:.1f}" if y0 > 0 else ""
        lines.append(
            f"- {label} : {int(x0)} = {y0:,.2f} ; {int(x1)} = {y1:,.2f} (évolution {evol}{ratio}) ; "
            f"max {ymax:,.2f} en {int(xmax)} ; min {ymin:,.2f} en {int(xmin)}"
        )
    # classement à la dernière année commune
    last_common = min(p[-1][0] for p in series.values())
    ranking = sorted(
        ((lab, dict(p).get(last_common)) for lab, p in series.items()),
        key=lambda t: -(t[1] or 0),
    )
    lines.append(f"Classement en {int(last_common)} : " + " > ".join(f"{l} ({v:,.2f})" for l, v in ranking if v is not None))
    if unit:
        lines.append(f"Unité : {unit}")
    return "\n".join(lines)
