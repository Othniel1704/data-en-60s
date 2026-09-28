"""Data en 60s : pipeline semi-automatique de Shorts data.

Commandes (dans l'ordre d'un projet) :
  python main.py ideas                        Gemini propose des sujets
  python main.py new <slug> --idea N          crée le projet à partir de l'idée N (dernier fichier d'idées)
  python main.py new <slug> --csv data.csv --titre "..." --unite "..."   ou avec tes propres données
  python main.py script <slug>                Gemini écrit le script (à relire dans projects/<slug>/script.json)
  python main.py approve <slug>               tu valides le script (puis la vidéo)
  python main.py voice <slug>                 voix off
  python main.py render <slug> [--preview]    vidéo finale (ou aperçu rapide)
  python main.py upload <slug> [--publish-at 2026-10-02T17:00:00+02:00]
  python main.py status                       où en est chaque projet
  python main.py make <slug>                  voice + render d'un coup (après validation du script)
"""
import argparse
import datetime as dt
import json
import sys

from ds import core
from ds.core import IDEAS, PROJECTS, get_step, project_dir, read_json, require_step, set_step, write_json


def latest_ideas_file():
    files = sorted(IDEAS.glob("idees_*.json"))
    if not files:
        raise SystemExit("Aucun fichier d'idées : lance d'abord  python main.py ideas")
    return files[-1]


def cmd_ideas(args, cfg):
    from ds.gemini import IDEAS_PROMPT, ask_json

    done = [p.name for p in PROJECTS.iterdir() if p.is_dir()] if PROJECTS.exists() else []
    prompt = IDEAS_PROMPT.format(concept=cfg["channel"]["concept"], n=args.n, deja=", ".join(done) or "aucun",
                                 annee_max=dt.date.today().year - 2)
    ideas = ask_json(prompt, cfg["gemini"]["model"])
    IDEAS.mkdir(exist_ok=True)
    out = IDEAS / f"idees_{dt.datetime.now():%Y%m%d_%H%M}.json"
    write_json(out, ideas)
    for i, idea in enumerate(ideas, 1):
        print(f"{i:>2}. [{idea['graphique']:8}] {idea['titre']}\n     {idea['accroche']}  ({idea['indicateur']}, {', '.join(idea['pays'])})")
    print(f"\nEnregistré dans {out.name}. Choisis : python main.py new <slug> --idea N")


def cmd_new(args, cfg):
    from ds.data import fetch_worldbank, load_series

    d = project_dir(args.slug)
    if d.exists() and not args.force:
        raise SystemExit(f"Le projet {args.slug} existe déjà (ajoute --force pour l'écraser).")
    d.mkdir(parents=True, exist_ok=True)
    if args.csv:
        import shutil

        shutil.copy(args.csv, d / "data.csv")
        chart = {"titre": args.titre or args.slug, "angle": args.angle or "", "graphique": args.graphique,
                 "unite": args.unite or "", "indicateur_nom": args.titre or "", "source": args.source}
    else:
        idea = read_json(latest_ideas_file())[args.idea - 1]
        print(f"Téléchargement : {idea['indicateur']} pour {', '.join(idea['pays'])}...")
        name, n = fetch_worldbank(idea["indicateur"], idea["pays"], idea["debut"], idea["fin"], d / "data.csv")
        print(f"  {n} valeurs : {name}")
        chart = {**idea, "indicateur_nom": name, "source": "Banque mondiale"}
    write_json(d / "chart.json", chart)
    series = load_series(d / "data.csv")
    print(f"Séries : {', '.join(series)}")
    set_step(args.slug, "donnees")
    print(f"Projet prêt. Suite : python main.py script {args.slug}")


def cmd_script(args, cfg):
    from ds.data import load_series, summarize
    from ds.gemini import SCRIPT_PROMPT, ask_json

    require_step(args.slug, "donnees", "script_a_valider")
    d = project_dir(args.slug)
    chart = read_json(d / "chart.json")
    resume = summarize(load_series(d / "data.csv"), chart.get("unite", ""))
    prompt = SCRIPT_PROMPT.format(
        chaine=cfg["channel"]["name"], concept=cfg["channel"]["concept"], titre=chart["titre"],
        angle=chart.get("angle", ""), indicateur_nom=chart.get("indicateur_nom", ""), resume=resume,
        mots_min=cfg["video"]["mots_min"], mots_max=cfg["video"]["mots_max"])
    script = ask_json(prompt, cfg["gemini"]["model"])
    script["narration"] = script["narration"].replace("—", ",")
    write_json(d / "script.json", script)
    (d / "donnees_resume.txt").write_text(resume, encoding="utf-8")
    set_step(args.slug, "script_a_valider")
    nb = len(script["narration"].split())
    print(f"\n{script['texte_ecran']}\n\n{script['narration']}\n\n({nb} mots, environ {nb / 2.7:.0f} s)")
    print(f"\nÀ TOI : relis et modifie projects/{args.slug}/script.json (vérifie les chiffres avec donnees_resume.txt),")
    print(f"ajoute ta touche perso, puis : python main.py approve {args.slug}")


def cmd_approve(args, cfg):
    step = get_step(args.slug)
    nxt = {"script_a_valider": "script_valide", "video_a_valider": "pret_a_publier"}.get(step)
    if not nxt:
        raise SystemExit(f"Rien à valider pour {args.slug} (étape : {step}).")
    set_step(args.slug, nxt)
    print(f"{args.slug} : {step} -> {nxt}")


def cmd_voice(args, cfg):
    from ds.voice import audio_duration, even_words, generate_edge

    require_step(args.slug, "script_valide", "voix_ok", "video_a_valider")
    d = project_dir(args.slug)
    script = read_json(d / "script.json")
    vcfg = cfg["voix"]
    if vcfg["moteur"] == "manuel":
        if not (d / "voice.mp3").exists():
            raise SystemExit(f"Mode manuel : enregistre ta voix dans projects/{args.slug}/voice.mp3 (lis la narration).")
        words = even_words(script["narration"], audio_duration(d / "voice.mp3"))
        write_json(d / "words.json", words)
    else:
        generate_edge(script["narration"], vcfg["voix_edge"], vcfg["vitesse"], d / "voice.mp3", d / "words.json")
    dur = audio_duration(d / "voice.mp3")
    set_step(args.slug, "voix_ok")
    print(f"Voix OK : {dur:.1f} s" + ("  (attention : moins d'1 minute, pas éligible TikTok Rewards)" if dur < 61 else ""))


def cmd_render(args, cfg):
    from ds.data import load_series
    from ds.render import render
    from ds.voice import audio_duration, chunk_words

    require_step(args.slug, "voix_ok", "video_a_valider", "pret_a_publier")
    d = project_dir(args.slug)
    script, chart = read_json(d / "script.json"), read_json(d / "chart.json")
    words = read_json(d / "words.json")
    out = d / ("apercu.mp4" if args.preview else "final.mp4")
    dur = audio_duration(d / "voice.mp3")
    print(f"Rendu {'aperçu' if args.preview else 'final'} ({dur + 2:.0f} s de vidéo)...")
    render(load_series(d / "data.csv"), script, chart, chunk_words(words), d / "voice.mp3", dur, out,
           None if args.preview else d / "miniature.jpg", cfg["channel"]["handle"], fps=cfg["video"]["fps"],
           preview=args.preview, music=cfg["video"].get("musique") or None,
           music_volume=cfg["video"].get("volume_musique", 0.08))
    if not args.preview:
        set_step(args.slug, "video_a_valider")
        print(f"Vidéo : {out}\nÀ TOI : regarde-la en entier, puis : python main.py approve {args.slug}")
    else:
        print(f"Aperçu : {out}")


def cmd_make(args, cfg):
    cmd_voice(args, cfg)
    args.preview = False
    cmd_render(args, cfg)


def cmd_upload(args, cfg):
    from ds.youtube import upload

    require_step(args.slug, "pret_a_publier")
    d = project_dir(args.slug)
    s, chart = read_json(d / "script.json"), read_json(d / "chart.json")
    synthetic = cfg["voix"]["moteur"] == "edge"
    desc = s["description"].rstrip() + f"\n\nSource des données : {chart.get('source', 'Banque mondiale')}"
    if chart.get("indicateur_nom"):
        desc += f" ({chart['indicateur_nom']})"
    if synthetic:
        desc += "\nVoix off générée par synthèse vocale. Graphique réalisé à partir des données officielles."
    vid = upload(d / "final.mp4", d / "miniature.jpg", s["titre_youtube"], desc, s.get("tags", []),
                 cfg["youtube"]["categorie"], cfg["youtube"]["visibilite"], synthetic, args.publish_at,
                 cfg["channel"]["langue"])
    write_json(d / "youtube.json", {"id": vid, "url": f"https://youtube.com/shorts/{vid}",
                                    "publish_at": args.publish_at, "uploaded": dt.datetime.now().isoformat()})
    set_step(args.slug, "publie")
    print(f"En ligne (privé ou programmé) : https://youtube.com/shorts/{vid}")
    print(f"Commentaire à épingler : {s.get('commentaire_epingle', '')}")
    print("TikTok : poste final.mp4 depuis ton téléphone avec le même titre.")


def cmd_status(args, cfg):
    if not PROJECTS.exists() or not any(PROJECTS.iterdir()):
        print("Aucun projet.")
        return
    todo = {"script_a_valider": "relire le script", "video_a_valider": "regarder la vidéo",
            "donnees": "lancer script", "script_valide": "lancer make", "voix_ok": "lancer render",
            "pret_a_publier": "lancer upload", "publie": ""}
    for p in sorted(PROJECTS.iterdir()):
        if p.is_dir():
            st = get_step(p.name)
            print(f"  {p.name:32} {st or '?':18} {todo.get(st, '')}")


def main():
    core.load_env()
    cfg = core.load_config()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("ideas"); s.add_argument("-n", type=int, default=10)
    s = sub.add_parser("new"); s.add_argument("slug"); s.add_argument("--idea", type=int)
    s.add_argument("--csv"); s.add_argument("--titre"); s.add_argument("--angle"); s.add_argument("--unite")
    s.add_argument("--graphique", choices=["line", "bar_race"], default="line")
    s.add_argument("--source", default="Banque mondiale"); s.add_argument("--force", action="store_true")
    for name in ("script", "approve", "voice", "make"):
        sub.add_parser(name).add_argument("slug")
    s = sub.add_parser("render"); s.add_argument("slug"); s.add_argument("--preview", action="store_true")
    s = sub.add_parser("upload"); s.add_argument("slug"); s.add_argument("--publish-at")
    sub.add_parser("status")
    args = ap.parse_args()
    if args.cmd == "new" and not args.csv and not args.idea:
        ap.error("new : indique --idea N ou --csv fichier.csv")
    globals()[f"cmd_{args.cmd}"](args, cfg)


if __name__ == "__main__":
    sys.exit(main())
