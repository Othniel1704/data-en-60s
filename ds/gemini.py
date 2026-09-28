"""Appels Gemini : idées de sujets et scripts. Clé : GEMINI_API_KEY dans le fichier .env"""
import json
import logging
import os
import re
import time

logging.getLogger("google_genai").setLevel(logging.ERROR)

# Si le modèle principal est saturé, on bascule sur le suivant.
MODELES_SECOURS = ["gemini-flash-latest", "gemini-2.5-flash", "gemini-flash-lite-latest", "gemini-2.0-flash"]
TRANSITOIRE = ("503", "429", "500", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "overloaded", "high demand")

IDEAS_PROMPT = """Tu es le rédacteur en chef d'une chaîne de vidéos courtes.
Concept de la chaîne :
{concept}

Sujets déjà traités (ne pas refaire) : {deja}

Propose {n} idées de vidéos. Chaque idée doit reposer sur UN indicateur RÉEL de la Banque mondiale
(code indicateur exact, ex : SP.POP.TOTL, SP.DYN.LE00.IN, IT.NET.USER.ZS, EG.ELC.ACCS.ZS, NY.GDP.PCAP.CD, SP.URB.TOTL.IN.ZS).
Varie les thèmes (démographie, énergie, numérique, économie, santé factuelle, éducation, environnement)
et varie les formats : "line" (courbes, 2 à 5 pays) ou "bar_race" (course de barres, 6 à 10 pays).

Réponds UNIQUEMENT en JSON : une liste d'objets avec les clés
"slug" (kebab-case court), "titre", "accroche" (question ou fait choc, 10 mots max), "angle" (pourquoi c'est surprenant),
"indicateur", "pays" (liste de codes ISO3), "debut" (année), "fin" (année, max {annee_max}), "graphique" ("line" ou "bar_race"),
"unite" (courte, ex : "habitants", "ans", "% de la population", "$ par habitant")."""

SCRIPT_PROMPT = """Tu écris la voix off d'un Short vertical pour la chaîne "{chaine}".
Concept : {concept}

Sujet : {titre}
Angle : {angle}
Source : Banque mondiale, indicateur "{indicateur_nom}"

DONNÉES RÉELLES (les seuls chiffres autorisés) :
{resume}

Règles :
- Français oral, phrases courtes, tutoiement, ton curieux et direct. Pas de tiret cadratin.
- Entre {mots_min} et {mots_max} mots (la vidéo doit dépasser 1 minute).
- Les 2 premières secondes = accroche forte (question ou chiffre choc).
- Utilise UNIQUEMENT les chiffres des données ci-dessus, arrondis de façon naturelle ("presque 30 millions").
  N'invente aucun chiffre, aucune date, aucune cause non évidente. Si tu expliques une cause, reste prudent ("en partie grâce à...").
- Structure : accroche, ce que montre le graphique, le moment le plus surprenant, une explication, une question finale au public.
- Cite la source à la fin en une phrase courte.

Réponds UNIQUEMENT en JSON avec les clés :
"texte_ecran" (titre affiché en haut de la vidéo, 8 mots max),
"narration" (le texte lu),
"titre_youtube" (moins de 70 caractères, sans clickbait mensonger, avec 1 emoji max),
"description" (3 à 5 lignes + 5 hashtags à la fin),
"tags" (liste de 8 à 12 mots-clés),
"commentaire_epingle" (question pour lancer les commentaires)."""


def _client():
    from google import genai

    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise SystemExit("GEMINI_API_KEY manquante : crée le fichier .env (voir .env.exemple).")
    return genai.Client(api_key=key)


def ask_json(prompt, model, essais=3):
    """Appelle Gemini en JSON. Réessaie quand le modèle est saturé, puis change de modèle."""
    client = _client()
    modeles = [model] + [m for m in MODELES_SECOURS if m != model]
    derniere = None
    for rang, m in enumerate(modeles):
        attente = 5
        for essai in range(1, essais + 1):
            try:
                resp = client.models.generate_content(
                    model=m,
                    contents=prompt,
                    config={"response_mime_type": "application/json", "temperature": 0.9},
                )
                text = re.sub(r"^```(?:json)?|```$", "", (resp.text or "").strip()).strip()
                if not text:
                    raise ValueError("réponse vide")
                data = json.loads(text)
                if rang > 0:
                    print(f"  (généré avec le modèle de secours {m})")
                return data
            except Exception as e:
                derniere = e
                msg = str(e)
                if isinstance(e, (json.JSONDecodeError, ValueError)):
                    print(f"  Réponse illisible, nouvelle tentative ({essai}/{essais})...")
                elif any(c in msg for c in TRANSITOIRE):
                    print(f"  {m} est saturé, nouvelle tentative dans {attente} s ({essai}/{essais})...")
                elif "API key" in msg or "API_KEY" in msg or "PERMISSION_DENIED" in msg:
                    raise SystemExit(
                        "Clé Gemini refusée. Vérifie GEMINI_API_KEY dans .env "
                        "(nouvelle clé : https://aistudio.google.com/apikey)."
                    )
                elif "NOT_FOUND" in msg or "404" in msg:
                    break  # ce modèle n'existe pas, on passe au suivant
                else:
                    raise
                if essai < essais:
                    time.sleep(attente)
                    attente = min(attente * 2, 30)
        if rang < len(modeles) - 1:
            print(f"  Abandon de {m}, essai avec {modeles[rang + 1]}...")
    raise SystemExit(
        f"Gemini est indisponible pour le moment ({derniere}).\n"
        "Ce n'est pas une erreur de ton installation : réessaie dans quelques minutes."
    )
