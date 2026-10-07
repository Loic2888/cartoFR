-- 0002 — Groupes, réglages versionnés et cartos (T018 ; ARCHI, Données §2 ;
-- PRD FR-005, FR-007).
--
-- Règles tenues ici :
-- - RLS active sur les cinq tables (règle produit 7). Un membre ne lit que les
--   lignes de ses organisations (public.mes_organisations(), migration 0001) ;
--   anon ne lit rien.
-- - Chaque table porte organisation_id, et des clés étrangères composées
--   (id, organisation_id) empêchent une ligne de pointer vers le groupe, les
--   réglages ou la carto d'une autre organisation, même écrite en service_role.
-- - Aucune colonne de personne physique (principe 6, règle produit 4).
--   `groupes.nom` et `carto_societes.nom` sont des noms de société.
--   `cree_par` et `valide_par` sont des identifiants auth.users, jamais un nom
--   ni un e-mail ; ils passent à nul quand le compte est effacé.
-- - Le moteur ne tourne que sur une version de réglages validée (FR-005,
--   principe 2) : un déclencheur refuse une carto sur une version non validée,
--   et une version validée ne change plus.
-- - Les écritures passent par service_role (worker, Server Actions après
--   contrôle des droits côté serveur), qui contourne RLS. Aucune politique
--   d'écriture pour authenticated à ce stade ; T020 décidera si un membre
--   insère ses réglages directement (politique insert dédiée).

-- Un groupe cartographié par une organisation : sa tête et son nom.
create table public.groupes (
  id uuid primary key default gen_random_uuid(),
  organisation_id uuid not null references public.organisations (id) on delete cascade,
  tete_siren varchar(9) not null check (tete_siren ~ '^[0-9]{9}$'),
  -- Nom du groupe ou de sa société de tête, jamais celui d'une personne.
  nom text not null,
  cree_le timestamptz not null default now(),
  cree_par uuid references auth.users (id) on delete set null,
  -- Un groupe par tête dans une organisation (et clé du seed idempotent).
  unique (organisation_id, tete_siren),
  -- Cible des clés étrangères composées : garde l'organisation cohérente.
  unique (id, organisation_id)
);

-- Versions des réglages d'un groupe (marques, exclusions, organigramme), en
-- JSON validé par Zod puis pydantic. Une version validée est figée.
--
-- Validée = valide_le non nul. valide_par peut être nul sur une version
-- validée dans deux cas seulement, tracés par `origine` ou par l'effacement :
-- - les réglages de départ (origine 'depart'), repris de config/*.json, validés
--   par un humain du temps du prototype, hors de l'app ;
-- - le compte du validateur a été effacé (RGPD, règle produit 4).
-- On a écarté un faux utilisateur « système » dans auth.users : il ouvrirait
-- un compte GoTrue sans titulaire, et un compte effacé casserait de toute
-- façon une contrainte « valide_par obligatoire ».
create table public.reglages (
  id uuid primary key default gen_random_uuid(),
  groupe_id uuid not null,
  organisation_id uuid not null,
  version integer not null check (version >= 1),
  contenu jsonb not null check (jsonb_typeof(contenu) = 'object'),
  origine text not null default 'saisie' check (origine in ('saisie', 'depart')),
  cree_le timestamptz not null default now(),
  cree_par uuid references auth.users (id) on delete set null,
  valide_le timestamptz,
  valide_par uuid references auth.users (id) on delete set null,
  -- Pas de validateur sans date de validation.
  check (valide_par is null or valide_le is not null),
  unique (groupe_id, version),
  -- Cible de la clé étrangère composée de cartos.
  unique (id, groupe_id, organisation_id),
  foreign key (groupe_id, organisation_id)
    references public.groupes (id, organisation_id) on delete cascade
);

-- Cible de la clé étrangère composée de cartos (travail de la même organisation).
alter table public.travaux add constraint travaux_id_organisation_id_key unique (id, organisation_id);

-- Une carto : un calcul du moteur sur une version validée des réglages.
create table public.cartos (
  id uuid primary key default gen_random_uuid(),
  organisation_id uuid not null,
  groupe_id uuid not null,
  reglages_id uuid not null,
  -- Le travail de la file qui l'a calculée ; nul si le travail est purgé.
  travail_id bigint,
  statut text not null default 'en_attente'
    check (statut in ('en_attente', 'en_cours', 'terminee', 'echec')),
  -- Date des données du registre au moment du calcul (FR-007, SC-003).
  date_donnees date,
  cree_le timestamptz not null default now(),
  fin_le timestamptz,
  duree_ms integer check (duree_ms >= 0),
  -- Message affiché à l'utilisateur (données trop anciennes, échec…).
  avertissement text,
  unique (id, organisation_id),
  foreign key (groupe_id, organisation_id)
    references public.groupes (id, organisation_id) on delete cascade,
  -- Les réglages sont ceux du même groupe, dans la même organisation.
  foreign key (reglages_id, groupe_id, organisation_id)
    references public.reglages (id, groupe_id, organisation_id) on delete cascade,
  -- Le travail est celui de la même organisation. Seul travail_id passe à nul.
  foreign key (travail_id, organisation_id)
    references public.travaux (id, organisation_id) on delete set null (travail_id)
);

-- Les sociétés retenues dans une carto. Le nom est la dénomination de la
-- société (registre), jamais celui d'un dirigeant.
create table public.carto_societes (
  carto_id uuid not null,
  organisation_id uuid not null,
  siren varchar(9) not null check (siren ~ '^[0-9]{9}$'),
  nom text,
  -- 0 pour la tête, 1 pour ses filiales directes, etc.
  niveau integer not null check (niveau >= 0),
  maison_mere_siren varchar(9) check (maison_mere_siren ~ '^[0-9]{9}$'),
  -- Nulle pour la tête, qui n'entre pas par un lien.
  confiance char(1) check (confiance in ('A', 'B', 'C')),
  -- Pourquoi la société est dans le groupe. Texte écrit par le worker, qui
  -- garantit qu'il ne contient aucun nom de personne (garde-fou 6).
  preuve text,
  ciblable boolean not null,
  raison_ciblable text,
  -- diffusionCommerciale = false au RNE : marquée, jamais cachée (garde-fou 6).
  opposition_prospection boolean not null,
  -- Non-diffusion INSEE (statut de diffusion partielle).
  non_diffusible boolean not null,
  primary key (carto_id, siren),
  foreign key (carto_id, organisation_id)
    references public.cartos (id, organisation_id) on delete cascade
);

-- Les liens retenus : société dirigeante → société dirigée.
create table public.carto_liens (
  id bigint generated always as identity primary key,
  carto_id uuid not null,
  organisation_id uuid not null,
  parent_siren varchar(9) not null check (parent_siren ~ '^[0-9]{9}$'),
  enfant_siren varchar(9) not null check (enfant_siren ~ '^[0-9]{9}$'),
  -- Rôle au registre (président, gérant, associé…).
  role text,
  -- La preuve du lien. Texte écrit par le worker, qui garantit qu'il ne
  -- contient aucun nom de personne (garde-fou 6) : un dirigeant commun
  -- s'écrit « dirigeant commun », jamais par son nom.
  preuve text not null,
  confiance char(1) not null check (confiance in ('A', 'B', 'C')),
  foreign key (carto_id, organisation_id)
    references public.cartos (id, organisation_id) on delete cascade
);

-- Index des clés étrangères et des lectures courantes.
create index groupes_cree_par_idx on public.groupes (cree_par);
-- (groupe_id, version) sert déjà la cascade depuis groupes.
create index reglages_organisation_groupe_idx on public.reglages (organisation_id, groupe_id);
create index reglages_cree_par_idx on public.reglages (cree_par);
create index reglages_valide_par_idx on public.reglages (valide_par);
-- Liste des cartos d'un groupe, la plus récente d'abord.
create index cartos_groupe_cree_le_idx on public.cartos (groupe_id, cree_le desc);
create index cartos_organisation_id_idx on public.cartos (organisation_id);
create index cartos_reglages_idx on public.cartos (reglages_id, groupe_id, organisation_id);
create index cartos_travail_idx on public.cartos (travail_id, organisation_id);
-- carto_societes : sa clé primaire (carto_id, siren) sert déjà la cascade.
create index carto_liens_carto_idx on public.carto_liens (carto_id, organisation_id);

-- Une carto ne part que sur une version validée des réglages (FR-005).
create function public.cartos_reglages_valides()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if not exists (
    select 1 from public.reglages r where r.id = new.reglages_id and r.valide_le is not null
  ) then
    raise exception 'Réglages non validés : une carto ne peut partir que sur une version validée.'
      using errcode = 'check_violation';
  end if;
  return new;
end
$$;

create trigger cartos_reglages_valides
  before insert or update of reglages_id on public.cartos
  for each row execute function public.cartos_reglages_valides();

-- Une version validée est figée : ni son contenu, ni son numéro, ni son
-- groupe, ni sa validation ne changent. Seuls cree_par et valide_par peuvent
-- passer à nul (compte effacé). Pour changer les réglages, on crée une version.
create function public.reglages_version_figee()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if old.valide_le is not null and (
    new.contenu is distinct from old.contenu
    or new.version is distinct from old.version
    or new.groupe_id is distinct from old.groupe_id
    or new.organisation_id is distinct from old.organisation_id
    or new.origine is distinct from old.origine
    or new.valide_le is distinct from old.valide_le
    or (new.valide_par is distinct from old.valide_par and new.valide_par is not null)
  ) then
    raise exception 'Version de réglages validée : elle ne se modifie plus, créer une nouvelle version.'
      using errcode = 'check_violation';
  end if;
  return new;
end
$$;

create trigger reglages_version_figee
  before update on public.reglages
  for each row execute function public.reglages_version_figee();

revoke execute on function public.cartos_reglages_valides(), public.reglages_version_figee()
  from public, anon, authenticated;

-- RLS sur les cinq tables.
alter table public.groupes enable row level security;
alter table public.reglages enable row level security;
alter table public.cartos enable row level security;
alter table public.carto_societes enable row level security;
alter table public.carto_liens enable row level security;

-- Les privilèges par défaut de Supabase donnent tout à anon et authenticated :
-- on les retire, puis on rend la lecture seule à authenticated. RLS filtre
-- ensuite les lignes.
revoke all on public.groupes, public.reglages, public.cartos, public.carto_societes, public.carto_liens
  from anon, authenticated;
revoke all on sequence public.carto_liens_id_seq from anon, authenticated;
grant select on public.groupes, public.reglages, public.cartos, public.carto_societes, public.carto_liens
  to authenticated;

create policy groupes_lecture_membres on public.groupes
  for select to authenticated
  using (organisation_id in (select public.mes_organisations()));

create policy reglages_lecture_membres on public.reglages
  for select to authenticated
  using (organisation_id in (select public.mes_organisations()));

create policy cartos_lecture_membres on public.cartos
  for select to authenticated
  using (organisation_id in (select public.mes_organisations()));

create policy carto_societes_lecture_membres on public.carto_societes
  for select to authenticated
  using (organisation_id in (select public.mes_organisations()));

create policy carto_liens_lecture_membres on public.carto_liens
  for select to authenticated
  using (organisation_id in (select public.mes_organisations()));
