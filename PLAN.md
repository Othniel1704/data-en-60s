# Plan : chaîne « Data en 60s »

Objectif : une chaîne YouTube + TikTok monétisable, produite par un système semi-automatique où la machine fait 80 % du travail et toi 20 % (les 20 % qui évitent la démonétisation).

## 1. Les règles du jeu (vérifiées en septembre 2026)

| Plateforme | Seuil de monétisation | Point clé |
|---|---|---|
| YouTube (jusqu'au 31/01/2027) | 1 000 abonnés + 4 000 h de visionnage (12 mois) OU 10 M de vues Shorts (90 jours) | |
| YouTube (dès le 01/02/2027) | 1 000 abonnés + **8 000 h** OU **20 M de vues Shorts** | Une chaîne lancée aujourd'hui sera concernée |
| TikTok Creator Rewards (France éligible) | 10 000 abonnés + 100 000 vues sur 30 jours, compte personnel, 18 ans | Seules les vidéos de **plus d'1 minute** rapportent |

Deux règles YouTube qui dictent tout le système :

- **Contenu inauthentique** : les chaînes dont les vidéos sont interchangeables (même structure, voix IA sur images stock, peu de variation) sont retirées du programme. YouTube juge **toute la chaîne**, pas une vidéo.
- **Déclaration IA** : une voix de synthèse réaliste doit être déclarée à l'upload (le système le fait automatiquement). Déclarer ne pénalise pas, ne pas déclarer si.

## 2. Le concept choisi et pourquoi

**« Data en 60s »** : chaque vidéo raconte une vraie statistique surprenante à partir de données publiques (Banque mondiale, INSEE, Eurostat...), avec un graphique animé généré par le code, commenté en voix off. Angle fort : **France, Afrique de l'Ouest et monde comparés**.

Pourquoi ce concept et pas « histoires IA sur vidéos stock » :

1. **Chaque vidéo est unique par construction** : un jeu de données différent donne un graphique différent. C'est l'inverse du contenu « template ».
2. **Zéro coût** : le graphique est dessiné par le code, pas besoin de crédits de génération vidéo.
3. **Pas de droits d'auteur** : données publiques, graphiques maison, pas de marques.
4. **Ça sert aussi ta carrière** : une chaîne data qui marche est une ligne très forte sur un CV d'alternant Data/IA, et le pipeline lui-même est un projet GitHub montrable.
5. **Niche peu occupée en français** sur l'angle Afrique/France, avec un public diaspora large.

Thèmes d'exemple : population Côte d'Ivoire vs France depuis 1960, prix de l'électricité, espérance de vie, accès à Internet, PIB par habitant, urbanisation, âge médian, énergie solaire...

## 3. Le système (ce que fait la machine / ce que tu fais)

```
 [Machine] ideas   : Gemini propose 10 sujets avec la source de données
 [TOI]     choisir un sujet (30 s)
 [Machine] new     : télécharge les vraies données (Banque mondiale) ou ton CSV
 [Machine] script  : Gemini écrit le script À PARTIR des chiffres réels + titre, description, tags
 [TOI]     relire / réécrire une phrase, ajouter TON avis (5 min)  <- la touche humaine
 [Machine] voice   : voix off (Edge-TTS gratuit) OU tu enregistres ta voix (mieux)
 [Machine] render  : graphique animé 1080x1920 + sous-titres + miniature
 [TOI]     regarder la vidéo, valider (2 min)
 [Machine] upload  : YouTube en privé ou programmé, déclaration IA auto
 [TOI]     poster sur TikTok depuis ton téléphone (1 min)
```

Environ **10 à 15 minutes de ton temps par vidéo**. Les points [TOI] sont volontaires : ce sont eux qui prouvent qu'il y a un humain derrière.

## 4. Stratégie de publication

| Phase | Durée | Rythme | But |
|---|---|---|---|
| Lancement | Mois 1-2 | 4 à 5 Shorts / semaine | Trouver les sujets qui marchent (regarder la rétention, pas les vues) |
| Accélération | Mois 3-6 | 5 Shorts / semaine + 1 vidéo longue / mois | Doubler les formats qui marchent, accumuler des heures de visionnage |
| Monétisation | Dès les seuils | Idem | TikTok d'abord (seuil plus bas), YouTube ensuite |

- **Durée des Shorts : 65 à 75 secondes**, pour être éligible TikTok Creator Rewards.
- **Vidéo longue mensuelle** (8 à 12 min, « Les 10 chiffres les plus fous du mois ») : c'est elle qui fait monter les heures de visionnage, les Shorts seuls n'y suffisent presque jamais.
- **Ta voix** : dès que tu es à l'aise, enregistre toi-même la voix off. C'est le meilleur signal d'authenticité et ça fidélise.
- **Varier les formats** : courbes, courses de barres, duels « pays A vs pays B », quiz « à ton avis ? ». Ne jamais publier 10 vidéos identiques d'affilée.

## 5. Chiffres honnêtes

- La plupart des chaînes n'atteignent jamais les seuils. Compte **6 à 12 mois** de publication régulière avant les premiers revenus, si ça prend.
- Les revenus Shorts YouTube sont très faibles par vue. TikTok Creator Rewards paie environ **0,50 à 1,20 € pour 1 000 vues qualifiées** (vidéos de plus d'1 minute).
- Les vrais revenus d'une chaîne data viennent souvent d'ailleurs : sponsoring, affiliation (outils, formations), et opportunités pro.
- Coût du système : **0 €** (Gemini via ton Google AI Pro / free tier, Edge-TTS, Banque mondiale, FFmpeg).

## 6. Ce qui est déjà construit (v1) et la suite

**v1 (livrée)** : idées, données Banque mondiale ou CSV, script Gemini ancré sur les vrais chiffres, voix Edge-TTS ou manuelle, rendu vidéo animé (courbes et course de barres), sous-titres synchronisés, miniature, validation humaine, upload YouTube programmable avec déclaration IA.

**v2 (prochaines étapes possibles)** :
- nouveaux types de graphiques (carte, duel, camembert animé)
- musique de fond automatique (bibliothèque audio YouTube)
- intégration de plans Veo via tes 1 000 crédits Flow mensuels (intro visuelle)
- tableau de bord des performances (API YouTube Analytics) pour savoir quoi refaire
- publication programmée via GitHub Actions

## 7. Risques à surveiller

| Risque | Parade |
|---|---|
| Démonétisation « inauthentique » | Tes relectures, ta voix, variété des formats et sujets |
| Chiffre faux dans une vidéo | Le script est généré à partir des données réelles et tu relis avant de valider |
| Sujet sensible (santé, finance) | Rester factuel, pas de conseil ; YouTube cible les « personas IA experts » sur ces sujets |
| Abandon après 1 mois | Produire par lots : 1 soirée = 5 vidéos de la semaine |
