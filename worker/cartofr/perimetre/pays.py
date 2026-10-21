"""Les noms de pays et de zones qu'un document de périmètre écrit en titre de section (T054).

Plusieurs listes publiées ne donnent pas le pays sur la ligne de la société, mais en titre : « France »,
puis les sociétés françaises, puis « Allemagne »… (Société Générale, Crédit Agricole S.A., Carrefour).
Un titre se reconnaît à ce qu'il est, tout entier, un nom de cette liste : une ligne de nom coupée
(« CA VERSICHERUNGSSERVICE ») n'en est jamais un.

Usage :
    cle_pays("Afrique Du Sud") in PAYS  # True
    francais("FRANCE")                  # True
Entrée : une ligne ou une cellule. Sortie : sa clé (majuscules, sans accents, sans ponctuation).
"""

import unicodedata

# Outre-mer présent dans SIRENE. La Nouvelle-Calédonie et la Polynésie ont leurs propres registres.
OUTRE_MER = (
    "Guadeloupe", "Martinique", "Guyane", "La Réunion", "Réunion", "Mayotte",
    "Saint-Martin", "Saint-Barthélemy", "Saint-Pierre-et-Miquelon", "Antilles françaises",
)  # fmt: skip


def cle_pays(texte: str) -> str:
    """« Émirats arabes unis » -> « EMIRATS ARABES UNIS » : majuscules, sans accents ni ponctuation."""
    sans = unicodedata.normalize("NFKD", texte)
    sans = "".join(c for c in sans if not unicodedata.combining(c)).upper()
    sans = "".join(c if c.isalnum() else " " for c in sans)
    return " ".join(sans.split())


_FRANCE = {cle_pays(n) for n in ("France", "France métropolitaine", *OUTRE_MER)}

# Pays, en français, tels que les écrivent les documents (formes courtes et abrégées comprises).
_NOMS = """
Afghanistan|Afrique du Sud|Albanie|Algérie|Allemagne|Andorre|Angola|Anguilla|Arabie Saoudite|
Arab. Saoudite|Argentine|Arménie|Aruba|Australie|Autriche|Azerbaïdjan|Bahamas|Bahreïn|Bangladesh|
Barbade|Belgique|Belize|Bénin|Bermudes|Biélorussie|Bolivie|Bosnie-Herzégovine|Botswana|Brésil|
Brunei|Bulgarie|Burkina Faso|Burkina|Burundi|Cambodge|Cameroun|Canada|Cap-Vert|Chili|Chine|
Chypre|Colombie|Comores|Congo|République du Congo|République démocratique du Congo|RD Congo|
Corée|Corée du Sud|République de Corée|Costa Rica|Côte d'Ivoire|Croatie|Cuba|Curaçao|Danemark|
Djibouti|Dominique|Égypte|Émirats arabes unis|Emirats Arabes Unis|EAU|Équateur|Érythrée|Espagne|
Estonie|Eswatini|États-Unis|Etats-Unis d'Amérique|États-Unis d'Amérique|USA|Éthiopie|Fidji|
Finlande|Gabon|Gambie|Géorgie|Ghana|Gibraltar|Grèce|Grenade|Groenland|Guam|Guatemala|Guernesey|
Guinée|Guinée équatoriale|Guinée-Bissau|Guyana|Haïti|Honduras|Hong Kong|Hong-Kong|Hongrie|
Île Maurice|Maurice|Îles Caïmans|Iles Caïmans|Îles Cayman|Îles Vierges britanniques|
Iles Vierges Britanniques|Île de Man|Ile de Man|Îles Féroé|Inde|Indonésie|Irak|Iran|Irlande|
Islande|Israël|Italie|Jamaïque|Japon|Jersey|Jordanie|Kazakhstan|Kenya|Kirghizistan|Kosovo|Koweït|
Laos|Lesotho|Lettonie|Liban|Liberia|Libéria|Libye|Liechtenstein|Lituanie|Luxembourg|Macao|
Macédoine|Macédoine du Nord|Madagascar|Malaisie|Malawi|Maldives|Mali|Malte|Maroc|Mauritanie|
Mexique|Moldavie|Monaco|Mongolie|Monténégro|Mozambique|Myanmar|Namibie|Népal|Nicaragua|Niger|
Nigeria|Nigéria|Norvège|Nouvelle-Calédonie|Nouvelle-Zélande|Oman|Ouganda|Ouzbékistan|Pakistan|
Panama|Papouasie-Nouvelle-Guinée|Paraguay|Pays-Bas|Pérou|Philippines|Pologne|Polynésie française|
Porto Rico|Portugal|Qatar|République dominicaine|République tchèque|Tchéquie|Roumanie|
Royaume-Uni|Russie|Fédération de Russie|Rwanda|Saint-Marin|Salvador|El Salvador|Sénégal|Serbie|
Seychelles|Sierra Leone|Singapour|Slovaquie|Slovénie|Somalie|Soudan|Sri Lanka|Suède|Suisse|
Suriname|Syrie|Tadjikistan|Taïwan|Taiwan|Tanzanie|Tchad|Thaïlande|Togo|Trinité-et-Tobago|Tunisie|
Turkménistan|Turquie|Ukraine|Uruguay|Venezuela|Vietnam|Viêt Nam|Wallis-et-Futuna|Yémen|Zambie|
Zimbabwe
"""
# Zones qui ouvrent une section hors de France.
_ZONES = """
Étranger|International|Europe|Europe de l'Ouest|Europe de l'Est|Europe centrale|Reste de l'Europe|
Autres pays d'Europe|Amérique|Amériques|Amérique du Nord|Amérique latine|Amérique du Sud|
Amérique centrale|Asie|Asie-Pacifique|Asie Pacifique|Afrique|Afrique du Nord|Moyen-Orient|
Afrique Moyen-Orient|Océanie|Reste du monde|Autres pays|Hors de France
"""


def _cles(noms: str) -> set[str]:
    return {cle_pays(n) for n in noms.replace("\n", "").split("|") if n.strip()}


_ZONES_CLES = _cles(_ZONES)
_ETRANGERS = _cles(_NOMS) | _ZONES_CLES

PAYS = _FRANCE | _ETRANGERS


def francais(texte: str) -> bool:
    """La France métropolitaine ou un territoire d'outre-mer présent dans SIRENE."""
    return cle_pays(texte) in _FRANCE


def est_pays(texte: str) -> bool:
    """Un nom de pays ou de zone, tout entier : « Allemagne », « FRANCE », « Asie-Pacifique »."""
    return len(texte) <= 40 and cle_pays(texte) in PAYS


def est_zone(texte: str) -> bool:
    """Une zone (« Europe », « Étranger »), pas un pays : un tableau de chiffres par zone n'est pas
    une liste de sociétés."""
    return cle_pays(texte) in _ZONES_CLES
