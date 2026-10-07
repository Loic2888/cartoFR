"""Schéma du registre `registre.duckdb` : les tables et leur sens.

Usage : `creer_tables(con)` sur une connexion DuckDB vide.
Entrées : aucune. Sorties : les tables `societes`, `liens`, `dirigeants_personnes`,
`sieges`, `unites_legales` et `mises_a_jour`, vides.

Règles portées par le schéma :
- un lien ou une société n'est jamais effacé, il est fermé : `debut` et `fin`
  (principe 4). `fin` vide = encore en vigueur ;
- aucune colonne de personne physique hors de `dirigeants_personnes`, qui sert
  au calcul seulement et ne sort jamais du worker (garde-fou 6, principe 6).
"""

import duckdb

DDL = """
-- Une ligne par personne morale du registre (RNE), enrichie de SIRENE.
create table societes (
    siren varchar primary key,
    denomination varchar,               -- nom de la personne morale (RNE)
    diffusion_commerciale boolean,      -- RNE : false = la société refuse la prospection
    opposition_prospection boolean,     -- = not diffusion_commerciale ; marquée, jamais cachée
    non_diffusible boolean,             -- SIRENE : statutDiffusionUniteLegale <> 'O' ; vide si absente
    salaries bigint,                    -- effectif déclaré au RNE
    etat_administratif varchar,         -- SIRENE : 'A' active, 'C' cessée ; vide si absente
    date_creation date,                 -- SIRENE : date de création de l'unité légale
    debut date not null,                -- entrée dans le registre (date du stock au chargement initial)
    fin date,                           -- sortie du registre ; vide = présente
    check (fin is null or fin >= debut)
);

-- Une ligne par mandat "société parent dirige société enfant".
-- Pas de clé : le RNE contient des doublons (même parent, enfant, rôle), gardés tels quels.
-- Pas de nom du parent : quand le parent est une entreprise individuelle, son nom est
-- celui d'une personne. Le nom se lit dans `societes` ou `sieges`.
create table liens (
    parent varchar not null,            -- SIREN de la société dirigeante
    enfant varchar not null,            -- SIREN de la société dirigée
    role varchar,                       -- code de rôle RNE (roleEntreprise)
    source varchar not null default 'rne_stock',
    debut date not null,                -- date à laquelle le lien est connu en vigueur
    fin date,                           -- date de fermeture ; vide = en vigueur
    fin_inconnue boolean not null default false,  -- déjà fermé à la date du stock, vraie date de fin inconnue
    check (fin is null or fin >= debut)
);

-- Dirigeants personnes physiques, sous forme de clé nom|prénom|naissance.
-- Usage interne au calcul seulement : jamais exportée, affichée ni journalisée.
create table dirigeants_personnes (
    siren varchar not null,             -- société dirigée
    personne varchar not null,          -- clé de la personne, donnée personnelle
    role varchar,
    debut date not null,
    fin date,
    fin_inconnue boolean not null default false,
    check (fin is null or fin >= debut)
);

-- Siège actif de chaque personne morale active (SIRENE, hors entreprises individuelles).
create table sieges (
    siren varchar,
    siret_siege varchar,
    num varchar,
    type_voie varchar,
    voie varchar,
    cp varchar,
    commune varchar,
    adresse_cle varchar,                -- adresse normalisée, pour trouver les voisines de siège
    nom varchar,                        -- denominationUniteLegale : nom de la personne morale
    cj bigint,                          -- catégorie juridique
    naf varchar,
    tranche varchar                     -- tranche d'effectif SIRENE
);

-- Unités légales SIRENE des personnes morales : les noms que le moteur cherche
-- (dénomination, sigle, enseigne) pour trouver les sociétés d'une marque (T016).
-- Hors entreprises individuelles (catégorie 1000) : leur nom est celui d'une personne.
-- Aucune colonne de personne : ni prénom, ni nom, ni sexe, ni pseudonyme, ni nom d'usage.
create table unites_legales (
    siren varchar primary key,
    denomination varchar,              -- denominationUniteLegale
    sigle varchar,                     -- sigleUniteLegale
    denomination_usuelle_1 varchar,    -- denominationUsuelle1UniteLegale (enseigne)
    denomination_usuelle_2 varchar,
    denomination_usuelle_3 varchar,
    categorie_juridique bigint,        -- jamais 1000
    naf varchar,                       -- activitePrincipaleUniteLegale
    tranche_effectifs varchar,         -- trancheEffectifsUniteLegale
    etat_administratif varchar,        -- 'A' active, 'C' cessée
    debut date not null,
    fin date,
    check (fin is null or fin >= debut),
    check (categorie_juridique <> 1000)
);

-- Journal : une ligne par construction ou synchro du registre (FR-003).
create sequence mises_a_jour_id;
create table mises_a_jour (
    id bigint primary key default nextval('mises_a_jour_id'),
    source varchar not null,            -- 'construction_initiale', 'inpi_diff', ...
    debut_le timestamptz not null default current_timestamp,
    fin_le timestamptz,
    statut varchar not null default 'en_cours' check (statut in ('en_cours', 'succes', 'echec')),
    ajoutes bigint,                     -- lignes ajoutées (sociétés et liens)
    fermes bigint,                      -- lignes fermées (date de fin posée)
    erreur varchar                      -- message court, sans donnée personnelle
);

comment on table societes is 'Personnes morales du registre, avec debut et fin. Jamais supprimées, fermées.';
comment on table liens is 'Liens société dirige société, avec debut et fin. Jamais supprimés, fermés.';
comment on table dirigeants_personnes is
    'Usage interne au calcul seulement. Données personnelles : ne quitte jamais le worker.';
comment on table sieges is 'Siège actif des personnes morales actives (SIRENE).';
comment on table unites_legales is
    'Unités légales SIRENE des personnes morales (hors catégorie 1000), colonnes de société seulement.';
comment on table mises_a_jour is 'Journal des constructions et synchros du registre.';
"""


def creer_tables(con: duckdb.DuckDBPyConnection) -> None:
    """Crée toutes les tables du registre, vides."""
    con.execute(DDL)
