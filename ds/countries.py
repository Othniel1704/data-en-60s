"""Noms de pays en français, codes ISO2 (drapeaux) et couleurs, à partir des noms Banque mondiale."""
import re
import unicodedata

# Nom Banque mondiale -> (nom affiché en français, code ISO2 pour le drapeau)
PAYS = {
    # Afrique de l'Ouest
    "Cote d'Ivoire": ("Côte d'Ivoire", "ci"), "Senegal": ("Sénégal", "sn"), "Ghana": ("Ghana", "gh"),
    "Mali": ("Mali", "ml"), "Burkina Faso": ("Burkina Faso", "bf"), "Nigeria": ("Nigeria", "ng"),
    "Niger": ("Niger", "ne"), "Guinea": ("Guinée", "gn"), "Benin": ("Bénin", "bj"), "Togo": ("Togo", "tg"),
    "Liberia": ("Liberia", "lr"), "Sierra Leone": ("Sierra Leone", "sl"), "Gambia, The": ("Gambie", "gm"),
    "Guinea-Bissau": ("Guinée-Bissau", "gw"), "Cabo Verde": ("Cap-Vert", "cv"), "Mauritania": ("Mauritanie", "mr"),
    # Afrique centrale, de l'Est, australe
    "Cameroon": ("Cameroun", "cm"), "Congo, Dem. Rep.": ("RD Congo", "cd"), "Congo, Rep.": ("Congo", "cg"),
    "Gabon": ("Gabon", "ga"), "Chad": ("Tchad", "td"), "Central African Republic": ("Centrafrique", "cf"),
    "Equatorial Guinea": ("Guinée équatoriale", "gq"), "Kenya": ("Kenya", "ke"), "Ethiopia": ("Éthiopie", "et"),
    "Rwanda": ("Rwanda", "rw"), "Burundi": ("Burundi", "bi"), "Uganda": ("Ouganda", "ug"),
    "Tanzania": ("Tanzanie", "tz"), "Madagascar": ("Madagascar", "mg"), "Mauritius": ("Maurice", "mu"),
    "Comoros": ("Comores", "km"), "Djibouti": ("Djibouti", "dj"), "Somalia": ("Somalie", "so"),
    "Sudan": ("Soudan", "sd"), "South Africa": ("Afrique du Sud", "za"), "Angola": ("Angola", "ao"),
    "Mozambique": ("Mozambique", "mz"), "Zambia": ("Zambie", "zm"), "Zimbabwe": ("Zimbabwe", "zw"),
    "Botswana": ("Botswana", "bw"), "Namibia": ("Namibie", "na"), "Seychelles": ("Seychelles", "sc"),
    # Afrique du Nord et Moyen-Orient
    "Morocco": ("Maroc", "ma"), "Algeria": ("Algérie", "dz"), "Tunisia": ("Tunisie", "tn"),
    "Egypt, Arab Rep.": ("Égypte", "eg"), "Libya": ("Libye", "ly"), "Saudi Arabia": ("Arabie saoudite", "sa"),
    "United Arab Emirates": ("Émirats", "ae"), "Qatar": ("Qatar", "qa"), "Israel": ("Israël", "il"),
    "Iran, Islamic Rep.": ("Iran", "ir"), "Turkiye": ("Turquie", "tr"), "Turkey": ("Turquie", "tr"),
    "Lebanon": ("Liban", "lb"),
    # Europe
    "France": ("France", "fr"), "Germany": ("Allemagne", "de"), "United Kingdom": ("Royaume-Uni", "gb"),
    "Italy": ("Italie", "it"), "Spain": ("Espagne", "es"), "Portugal": ("Portugal", "pt"),
    "Belgium": ("Belgique", "be"), "Switzerland": ("Suisse", "ch"), "Netherlands": ("Pays-Bas", "nl"),
    "Luxembourg": ("Luxembourg", "lu"), "Poland": ("Pologne", "pl"), "Sweden": ("Suède", "se"),
    "Norway": ("Norvège", "no"), "Denmark": ("Danemark", "dk"), "Finland": ("Finlande", "fi"),
    "Ireland": ("Irlande", "ie"), "Austria": ("Autriche", "at"), "Greece": ("Grèce", "gr"),
    "Romania": ("Roumanie", "ro"), "Ukraine": ("Ukraine", "ua"), "Russian Federation": ("Russie", "ru"),
    # Amériques
    "United States": ("États-Unis", "us"), "Canada": ("Canada", "ca"), "Brazil": ("Brésil", "br"),
    "Mexico": ("Mexique", "mx"), "Argentina": ("Argentine", "ar"), "Colombia": ("Colombie", "co"),
    "Chile": ("Chili", "cl"), "Haiti": ("Haïti", "ht"), "Cuba": ("Cuba", "cu"),
    # Asie et Océanie
    "China": ("Chine", "cn"), "India": ("Inde", "in"), "Japan": ("Japon", "jp"), "Korea, Rep.": ("Corée du Sud", "kr"),
    "Indonesia": ("Indonésie", "id"), "Viet Nam": ("Vietnam", "vn"), "Philippines": ("Philippines", "ph"),
    "Pakistan": ("Pakistan", "pk"), "Bangladesh": ("Bangladesh", "bd"), "Thailand": ("Thaïlande", "th"),
    "Singapore": ("Singapour", "sg"), "Australia": ("Australie", "au"),
    # Agrégats
    "World": ("Monde", None), "Sub-Saharan Africa": ("Afrique subsaharienne", None),
    "European Union": ("Union européenne", "eu"), "Euro area": ("Zone euro", "eu"),
}

# Couleurs proches du drapeau, pour qu'on reconnaisse le pays d'un coup d'œil.
COULEURS = {
    "fr": "#4C8DFF", "sn": "#22C77A", "ci": "#FF9F1C", "gh": "#FF4D6D", "ml": "#F2D544", "bf": "#E5484D",
    "ng": "#2ECC71", "cm": "#35B37E", "ma": "#E5484D", "dz": "#1FAF6E", "tn": "#F0506E", "us": "#5B8CFF",
    "de": "#F2C744", "gb": "#6C8CFF", "cn": "#FF4D4D", "in": "#FF9933", "br": "#27AE60", "jp": "#FF6B81",
    "cd": "#3FA9F5", "be": "#F5D142", "ch": "#FF5A5F", "it": "#2ECC71", "es": "#F6C445",
}

_STOP = {"de", "du", "des", "la", "le", "les", "l", "d", "et", "rd", "rep", "the"}


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(l|d|qu|j|n|s)'", "", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def display_name(label, chart=None):
    noms = (chart or {}).get("noms") or {}
    if label in noms:
        return noms[label]
    return PAYS.get(label, (label, None))[0]


def iso2(label, chart=None):
    codes = (chart or {}).get("iso2") or {}
    if label in codes:
        return codes[label]
    return PAYS.get(label, (None, None))[1]


def name_keys(label, chart=None):
    """Mots qui, prononcés dans la narration, désignent cette série."""
    words = [w for w in norm(display_name(label, chart)).split() if w not in _STOP]
    words += [w for w in norm(label).split() if w not in _STOP]
    return {w for w in words if len(w) >= 4} or set(words)
