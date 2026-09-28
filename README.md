# Data en 60s : usine à Shorts data (semi-automatique)

Transforme des données publiques réelles en Shorts verticaux (YouTube + TikTok) avec graphique animé, voix off et sous-titres. La machine fait le travail répétitif, tu gardes la main sur les 3 moments qui comptent : choix du sujet, relecture du script, validation de la vidéo.

La stratégie complète (monétisation, rythme, risques) est dans **PLAN.md**.

## Installation (une seule fois)

1. **Python 3.11+** et **FFmpeg** installés
   - Windows : `winget install Python.Python.3.12` puis `winget install Gyan.FFmpeg`
   - Vérifie : `python --version` et `ffmpeg -version`
2. Dans le dossier du projet :
   ```bash
   python -m venv .venv
   .venv\Scripts\activate          # Windows  (Mac/Linux : source .venv/bin/activate)
   pip install -r requirements.txt
   ```
3. **Clé Gemini (gratuite)** : va sur https://aistudio.google.com/apikey, crée une clé, copie `.env.exemple` en `.env` et colle-la.
4. Personnalise **config.toml** (nom de chaîne, @handle, voix).

## Routine d'une vidéo (10 à 15 min de ton temps)

```bash
python main.py ideas                       # 10 idées de sujets (Gemini)
python main.py new pop-ci-france --idea 3  # télécharge les vraies données de l'idée n°3
python main.py script pop-ci-france        # Gemini écrit le script à partir des chiffres réels
#   -> TOI : ouvre projects/pop-ci-france/script.json, corrige, ajoute ta touche
python main.py approve pop-ci-france
python main.py make pop-ci-france          # voix + vidéo (2 à 3 min de calcul)
#   -> TOI : regarde projects/pop-ci-france/final.mp4
python main.py approve pop-ci-france
python main.py upload pop-ci-france --publish-at 2026-10-02T18:00:00+02:00
python main.py status                      # où en sont tous tes projets
```

Astuce : `python main.py render <slug> --preview` fait un aperçu rapide en basse qualité.

**Produire par lots** : une soirée par semaine, prépare 5 projets jusqu'à `approve`, lance les `make`, puis programme les uploads sur la semaine avec `--publish-at`.

## Le format v2 (pensé pour la rétention)

Ce que fait chaque vidéo, d'après ce qui marche sur Shorts et TikTok en 2026 :

| Règle | Ce que fait le système |
|---|---|
| La 1re seconde décide du swipe | L'accroche (`texte_ecran`) s'affiche en géant dès la 1re image, chiffres en jaune, puis glisse en titre |
| Un changement visuel toutes les 1,5 à 2 s | Caméra qui suit les courbes, pays mis en avant quand la voix les cite, encadrés, badge d'écart qui pulse |
| 60 à 80 % des vues démarrent sans le son | Sous-titres karaoké de 2 à 3 mots, le mot prononcé en jaune |
| Ce qu'on voit = ce qu'on entend | Le graphique avance quand la voix cite une année ou un « moment » |
| La relecture compte comme une vue partielle | Pas d'écran de fin : la dernière image redevient la première (boucle) |
| 30 à 45 s retiennent le mieux | Scripts de 95 à 120 mots (réglable dans `config.toml`) |

### Les champs du script qui pilotent la vidéo

```json
"texte_ecran": "30 ans de vie en moins. Et aujourd'hui ?",
"sous_titre": "Espérance de vie à la naissance, 1960-2022",
"moments": [
  {"mot": "regarde", "annee": 1960},
  {"mot": "bloque", "annee": 1980, "annee_fin": 2000, "serie": "Côte d'Ivoire", "texte": "20 ans bloquée à 51 ans"},
  {"mot": "2022", "annee": 2022}
],
"ecart": ["France", "Sénégal"]
```

- `moments` : au mot `mot` (écrit exactement comme dans la narration), le graphique atteint `annee`. Si l'année est déjà passée, le point est mis en valeur. `texte` ajoute un encadré jaune, `annee_fin` surligne une période.
- Sans `moments`, le graphique suit automatiquement les années prononcées par la voix.
- `ecart` : badge qui affiche en direct l'écart entre deux pays.

Si tu modifies la narration, garde les mots utilisés dans `moments` (sinon `approve` retire le repère et te prévient).

Drapeaux : téléchargés automatiquement une fois (flagcdn.com) puis gardés dans `ds/cache/flags`. Police : Montserrat (licence libre OFL, dans `ds/fonts`). Effets sonores : générés par le code, sans droits.

## Tes propres données (encore plus original)

Tout CSV au format `label,x,value` fonctionne (INSEE, Eurostat, data.gouv.fr, Kaggle, tes propres relevés) :

```bash
python main.py new prix-kebab --csv mes_donnees.csv --titre "Prix du kebab à Paris" --unite "€" --graphique line --source "Mon relevé"
```

Graphiques disponibles : `line` (courbes, 2 à 5 séries) et `bar_race` (course de barres, 6 à 10 séries).

## Ta propre voix (recommandé dès que possible)

Dans `config.toml`, mets `moteur = "manuel"`. Après `approve`, enregistre la narration de `script.json` avec ton téléphone, dépose le fichier en `projects/<slug>/voice.mp3`, puis `python main.py make <slug>`. Les sous-titres sont calés automatiquement (moins précis qu'avec Edge-TTS). Ta voix = meilleure protection contre la démonétisation et la mention « voix de synthèse » n'est plus ajoutée.

## Upload YouTube (configuration une seule fois)

1. https://console.cloud.google.com : crée un projet, active **YouTube Data API v3**.
2. « Écran de consentement OAuth » : type Externe, ajoute ton adresse Gmail comme utilisateur test.
3. « Identifiants » : crée un ID client OAuth de type **Application de bureau**, télécharge le JSON, renomme-le `client_secret.json` à la racine du projet.
4. Au premier `upload`, ton navigateur s'ouvre pour autoriser ta chaîne. Ensuite c'est automatique.

Les vidéos partent **en privé** (ou programmées) : tu gardes un dernier contrôle dans YouTube Studio. La déclaration « contenu synthétique » est cochée automatiquement si la voix est Edge-TTS.

Quota gratuit de l'API : largement suffisant pour quelques vidéos par jour.

## TikTok

Poste `final.mp4` à la main depuis ton téléphone (1 minute). La publication automatique via l'API TikTok demande un audit de l'application par TikTok : à envisager plus tard, quand la chaîne tourne.

## Structure

```
main.py            commandes
config.toml        réglages de la chaîne
ds/data.py         Banque mondiale + CSV + résumé chiffré
ds/gemini.py       prompts idées et scripts
ds/voice.py        Edge-TTS, voix manuelle, sous-titres
ds/render.py       graphiques animés, accroche, sous-titres karaoké, synchronisation + FFmpeg
ds/countries.py    noms de pays en français, drapeaux, couleurs
ds/sfx.py          effets sonores générés
ds/fonts/          police Montserrat (OFL)
ds/youtube.py      upload
projects/<slug>/   un dossier par vidéo (données, script, voix, final.mp4, miniature.jpg)
```

## Règles d'or

- Relis toujours les chiffres du script avec `donnees_resume.txt` : ta crédibilité en dépend.
- Pas de conseil santé ou finance, pas de logos de marques, pas de musique protégée.
- Varie sujets et formats : YouTube juge la chaîne entière, pas une vidéo.
