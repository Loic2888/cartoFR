"""Tests du client de l'API diff de l'INPI, sans réseau (httpx.MockTransport).

Les données sont inventées : des SIREN factices, aucun nom de personne.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest

from cartofr.registre.inpi_diff import (
    Client,
    Curseur,
    ErreurInpi,
    IdentifiantsManquants,
    QuotaAtteint,
    charger_env,
    identifiants,
)

JOUR = date(2026, 1, 15)

# Trois pages factices : chaque page rend sa suite dans l'en-tête, la dernière est vide.
PAGES: dict[str | None, tuple[list[str], str | None]] = {
    None: (["000000001", "000000002"], "000000002"),
    "000000002": (["000000003", "000000004"], "000000004"),
    "000000004": (["000000005"], "000000005"),
    "000000005": ([], None),
}


@pytest.fixture(autouse=True)
def faux_identifiants(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INPI_USERNAME", "test@example.invalid")
    monkeypatch.setenv("INPI_PASSWORD", "mdp-FAKE")


class FauxInpi:
    """Serveur INPI factice : compte les appels, peut répondre 429 ou 401 à la demande."""

    def __init__(self, quota_apres: int | None = None, expire_au_appel: int | None = None) -> None:
        self.quota_apres = quota_apres
        self.expire_au_appel = expire_au_appel
        self.logins = 0
        self.diffs: list[str | None] = []

    def __call__(self, requete: httpx.Request) -> httpx.Response:
        if requete.url.path.endswith("/sso/login"):
            self.logins += 1
            return httpx.Response(200, json={"token": f"jeton-{self.logins}"})
        if requete.url.path.endswith("/companies/diff/count"):
            return httpx.Response(200, json={"isNbResultsOver10000": True})
        assert requete.url.params["from"] == "2026-01-14"
        assert requete.url.params["to"] == "2026-01-15"
        if self.expire_au_appel is not None and len(self.diffs) + 1 == self.expire_au_appel:
            if requete.headers["Authorization"] == "Bearer jeton-1":
                return httpx.Response(401)
        if self.quota_apres is not None and len(self.diffs) >= self.quota_apres:
            return httpx.Response(429)
        apres = requete.url.params.get("searchAfter")
        self.diffs.append(apres)
        sirens, suite = PAGES[apres]
        entetes = {"pagination-search-after": suite} if suite else {}
        return httpx.Response(200, json=[{"company": {"siren": s}} for s in sirens], headers=entetes)


def client(serveur: FauxInpi) -> Client:
    return Client(http=httpx.Client(transport=httpx.MockTransport(serveur)), delai=0, dormir=lambda _: None)


def sirens(pages: list[list[dict[str, dict[str, str]]]]) -> list[str]:
    return [f["company"]["siren"] for p in pages for f in p]


def test_pagination_suit_search_after(tmp_path: Path) -> None:
    serveur = FauxInpi()
    chemin = tmp_path / "curseur.json"
    pages = [p.formalites for p in client(serveur).lire(JOUR, JOUR, page_size=2, chemin=chemin)]
    assert sirens(pages) == ["000000001", "000000002", "000000003", "000000004", "000000005"]
    assert serveur.diffs == [None, "000000002", "000000004", "000000005"]
    curseur = Curseur.charger(chemin)
    assert curseur is not None
    assert (curseur.pages, curseur.formalites, curseur.fini) == (3, 5, True)


def test_quota_sauve_le_curseur_et_arrete(tmp_path: Path) -> None:
    chemin = tmp_path / "curseur.json"
    lues: list[str] = []
    with pytest.raises(QuotaAtteint) as erreur:
        for page in client(FauxInpi(quota_apres=2)).lire(JOUR, JOUR, page_size=2, chemin=chemin):
            lues += [f["company"]["siren"] for f in page.formalites]
    assert lues == ["000000001", "000000002", "000000003", "000000004"]
    sauve = Curseur.charger(chemin)
    assert sauve is not None
    assert erreur.value.curseur == sauve
    assert (sauve.search_after, sauve.pages, sauve.formalites, sauve.fini) == ("000000004", 2, 4, False)


def test_reprise_depuis_le_curseur_sauve(tmp_path: Path) -> None:
    chemin = tmp_path / "curseur.json"
    Curseur(JOUR, JOUR, search_after="000000004", pages=2, formalites=4).sauver(chemin)
    serveur = FauxInpi()
    curseur = Curseur.charger(chemin)
    pages = [p.formalites for p in client(serveur).lire(JOUR, JOUR, curseur, page_size=2, chemin=chemin)]
    assert sirens(pages) == ["000000005"]
    assert serveur.diffs == ["000000004", "000000005"]  # rien de relu avant le curseur
    fin = Curseur.charger(chemin)
    assert fin is not None
    assert (fin.pages, fin.formalites, fin.fini) == (3, 5, True)


def test_reprise_refuse_une_autre_periode(tmp_path: Path) -> None:
    autre = Curseur(date(2026, 1, 1), date(2026, 1, 1))
    with pytest.raises(ValueError):
        next(client(FauxInpi()).lire(JOUR, JOUR, autre, chemin=tmp_path / "c.json"))


def test_curseur_fini_ne_relit_rien(tmp_path: Path) -> None:
    serveur = FauxInpi()
    fini = Curseur(JOUR, JOUR, search_after="000000005", pages=3, formalites=5, fini=True)
    assert list(client(serveur).lire(JOUR, JOUR, fini, chemin=tmp_path / "c.json")) == []
    assert serveur.diffs == [] and serveur.logins == 0


def test_401_declenche_une_seule_reconnexion(tmp_path: Path) -> None:
    serveur = FauxInpi(expire_au_appel=2)
    pages = list(client(serveur).lire(JOUR, JOUR, page_size=2, chemin=tmp_path / "c.json"))
    assert len(pages) == 3
    assert serveur.logins == 2


def test_401_persistant_est_une_erreur(tmp_path: Path) -> None:
    def toujours_401(requete: httpx.Request) -> httpx.Response:
        if requete.url.path.endswith("/sso/login"):
            return httpx.Response(200, json={"token": "jeton"})
        return httpx.Response(401)

    c = Client(http=httpx.Client(transport=httpx.MockTransport(toujours_401)), delai=0, dormir=lambda _: None)
    with pytest.raises(ErreurInpi, match="code 401"):
        next(c.lire(JOUR, JOUR, chemin=tmp_path / "c.json"))


def test_5xx_reessaie_puis_abandonne(tmp_path: Path) -> None:
    appels = 0

    def toujours_503(requete: httpx.Request) -> httpx.Response:
        nonlocal appels
        if requete.url.path.endswith("/sso/login"):
            return httpx.Response(200, json={"token": "jeton"})
        appels += 1
        return httpx.Response(503)

    c = Client(
        http=httpx.Client(transport=httpx.MockTransport(toujours_503)),
        delai=0,
        essais=2,
        dormir=lambda _: None,
    )
    with pytest.raises(ErreurInpi, match="503"):
        next(c.lire(JOUR, JOUR, chemin=tmp_path / "c.json"))
    assert appels == 3


def test_compte_au_dela_de_10000(tmp_path: Path) -> None:
    compte = client(FauxInpi()).compter(JOUR, JOUR)
    assert compte.total is None and compte.plus_de_10000


def test_identifiants_manquants_message_clair(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("INPI_USERNAME")
    monkeypatch.delenv("INPI_PASSWORD")
    monkeypatch.setenv("CARTOFR_ENV_FILE", str(tmp_path / "absent.env"))
    charger_env()
    with pytest.raises(
        IdentifiantsManquants, match="Identifiants INPI absents : INPI_USERNAME, INPI_PASSWORD"
    ):
        identifiants()


def test_charger_env_lit_le_fichier_sans_ecraser(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("INPI_PASSWORD")
    fichier = tmp_path / "test.env"
    fichier.write_text('# commentaire\nINPI_USERNAME=autre@example.invalid\nINPI_PASSWORD="mdp-FICHIER"\n')
    monkeypatch.setenv("CARTOFR_ENV_FILE", str(fichier))
    charger_env()
    assert identifiants() == ("test@example.invalid", "mdp-FICHIER")
