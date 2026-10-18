"""Schéma de `pays.duckdb`, la carto du pays (T048, ARCHI ADR-006).

Le fichier est dérivé : il se reconstruit en entier depuis le registre et les documents
déposés, à chaque calcul. Il n'a pas d'historique et n'est jamais une source (principe 4).
Aucune colonne de personne : un entrepreneur individuel n'y est jamais écrit (garde-fou 6).

Une société absente de `pays_societes` n'a ni mère ni filiale dans la carto du pays : sa
carto est elle seule. La carto d'une société est cette société et tout ce qui descend d'elle
par `mere` (décision de Loïc, 2026-10-18) ; on ne remonte jamais à sa mère pour prendre ses
sœurs. Un groupe est la descente depuis sa tête. Seule exception : la tête d'un sous-groupe
(groupes emboîtés, T047) a sa mère dans le groupe parent, pour que la carto du parent
descende dans le sous-groupe.
"""

DDL = """
create table pays_groupes (
    tete varchar primary key,           -- SIREN de la tête, toujours une société active
    nom varchar,
    taille integer not null,            -- sociétés du groupe, tête comprise
    document varchar,                   -- fichier du document de périmètre utilisé, ou vide
    mutualiste boolean not null,        -- traitement à part (T049) ; faux pour l'instant
    parent varchar,                     -- tête du groupe parent (groupes emboîtés), ou vide
    date_donnees date
);
create table pays_societes (
    siren varchar primary key,
    groupe varchar not null,            -- tête du groupe où la société est rangée
    nom varchar,
    mere varchar,                       -- maison mère dans la carto du pays, vide pour une tête
    niveau integer not null,            -- 0 pour la tête de son groupe
    preuve varchar not null,
    confiance varchar not null check (confiance in ('A', 'B', 'C')),
    raison varchar not null,            -- raison d'entrée dans le groupe
    maniere varchar not null check (maniere in ('inscription', 'descente', 'arbre')),
    raison_departage varchar,           -- vide si un seul groupe la réclamait
    ciblable boolean not null,
    raison_ciblable varchar not null,
    opposition_prospection boolean not null,
    non_diffusible boolean not null
);
create table pays_bilan (
    calcule_le timestamptz not null,
    date_donnees date,
    groupes integer not null,
    societes integer not null,
    documents integer not null,
    documents_en_echec integer not null,
    duree_s double not null
);
"""
