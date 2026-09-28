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

IDEAS_PROMPT = """Tu es le rédacteur en chef d'une chaîne TikTok / YouTube Shorts francophone qui veut devenir virale.
Concept de la chaîne :
{concept}

Sujets déjà traités (ne pas refaire) : {deja}

Propose {n} idées de vidéos. Critères, par ordre d'importance :
1. ENJEU PERSONNEL pour le public : argent, salaires, prix, avenir des jeunes, pays d'origine, fierté, injustice,
   comparaison avec la France. Une statistique « jolie » sans enjeu ne fait pas de vues.
2. SURPRISE VÉRIFIABLE : un classement qui se renverse, un pays qui rattrape un autre, un chiffre qui contredit une idée reçue.
3. DÉBAT EN COMMENTAIRES : le public doit avoir envie d'écrire « et mon pays ? » ou « impossible ».

Varie les formats :
- "duel" : 2 ou 3 pays face à face (graphique "line")
- "remontada" : un pays qui rattrape ou dépasse un autre (graphique "line")
- "classement" : course de barres de 6 à 10 pays, le 1er n'est révélé qu'à la fin (graphique "bar_race")
- "devine" : la vidéo pose une question, le public doit deviner avant la révélation ("bar_race" ou "line")

Utilise UNIQUEMENT des indicateurs réels de la Banque mondiale, par exemple (code exact) :
NY.GDP.PCAP.CD (PIB par habitant, $), BX.TRF.PWKR.DT.GD.ZS (argent envoyé par la diaspora, % du PIB),
BX.TRF.PWKR.CD.DT (argent envoyé par la diaspora, $), IT.NET.USER.ZS (internet, % population),
IT.CEL.SETS.P2 (abonnements mobiles pour 100 habitants), EG.ELC.ACCS.ZS (accès à l'électricité, %),
SP.DYN.LE00.IN (espérance de vie, ans), SP.DYN.TFRT.IN (enfants par femme), SP.POP.TOTL (population),
SP.URB.TOTL.IN.ZS (population urbaine, %), SE.TER.ENRR (études supérieures, %), FP.CPI.TOTL.ZG (inflation, %),
SL.UEM.1524.ZS (chômage des 15-24 ans, %).

Réponds UNIQUEMENT en JSON : une liste d'objets avec les clés
"slug" (kebab-case court), "titre", "accroche" (5 à 8 mots, affichée en géant dans la 1re image, avec un chiffre si possible),
"format" ("duel", "remontada", "classement" ou "devine"), "angle" (pourquoi ça va surprendre et faire réagir),
"indicateur", "pays" (codes ISO3), "debut" (année), "fin" (année, max {annee_max}), "graphique" ("line" ou "bar_race"),
"unite" (3 caractères max, ex : "ans", "%", "$", ou "" s'il n'y a pas d'unité courte)."""

SCRIPT_PROMPT = """Tu écris la voix off d'un Short vertical pour la chaîne "{chaine}".
Concept : {concept}

Sujet : {titre}
Format : {format}
Angle : {angle}
Accroche proposée : {accroche}
Source : Banque mondiale, indicateur "{indicateur_nom}"

DONNÉES RÉELLES (les seuls chiffres autorisés) :
{resume}

OBJECTIF : que le spectateur ne swipe pas dans les 2 premières secondes, regarde jusqu'au bout et revoie la vidéo.

STRUCTURE OBLIGATOIRE :
1. ACCROCHE (1re phrase, 12 mots maximum) : un chiffre choc ou une question qui crée un manque.
   Jamais « Bonjour », jamais « Aujourd'hui on va parler de ».
2. POINT DE DÉPART (1 phrase courte) : la situation au début du graphique.
3. MOUVEMENT : dès la 3e phrase, dis « regarde » (ou équivalent) : c'est là que le graphique démarre.
   Cite ensuite les années dans l'ordre chronologique : le graphique avance quand tu prononces une année.
4. RÉVÉLATION : le moment le plus surprenant, en une phrase courte et forte.
5. EXPLICATION prudente en une phrase (« en partie grâce à... »).
6. FIN EN BOUCLE : la dernière phrase fait écho à l'accroche, pour que la vidéo s'enchaîne naturellement
   sur son début quand elle recommence. Pas de « abonne-toi », pas de source (elle est affichée à l'écran).

STYLE : français oral, tutoiement, phrases de 4 à 12 mots, rythme rapide, un chiffre fort toutes les 2 ou 3 phrases,
arrondis naturels (« presque 70 ans »). Écris les années en chiffres. Pas de tiret cadratin.
Entre {mots_min} et {mots_max} mots. N'invente aucun chiffre, aucune date, aucune cause certaine.

Réponds UNIQUEMENT en JSON avec les clés :
"texte_ecran" : l'accroche affichée en géant dans la 1re image puis en titre (5 à 8 mots, avec un chiffre si possible),
"sous_titre" : ce que mesure le graphique, en français, court (ex : « Espérance de vie à la naissance, 1960-2022 »),
"narration" : le texte lu,
"moments" : 2 à 4 repères qui synchronisent le graphique avec la voix. Chaque repère est un objet
   {{"mot": un mot EXACT de la narration (sans ponctuation) prononcé à l'instant voulu,
     "annee": l'année que le graphique doit atteindre à ce mot (ou l'année à mettre en valeur si elle est déjà passée),
     "serie": le pays concerné (facultatif),
     "texte": un encadré de 6 mots maximum affiché à ce moment (facultatif),
     "annee_fin": fin d'une période à surligner (facultatif)}}.
   Le 1er repère est le mot qui lance le mouvement (souvent « regarde ») avec l'année de départ.
   Mets un "texte" sur le repère de la révélation.
"ecart" : si la vidéo compare 2 pays, la liste de leurs deux noms, sinon null,
"titre_youtube" : moins de 70 caractères, fidèle aux données, 1 emoji maximum,
"description" : 3 à 5 lignes + 5 hashtags à la fin,
"tags" : liste de 8 à 12 mots-clés,
"commentaire_epingle" : une question qui donne envie de répondre (ex : « Et ton pays, il serait où ? »)."""


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
