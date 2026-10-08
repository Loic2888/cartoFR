-- 0003 — Cas douteux d'une carto et décisions du consultant (T027 ; PRD FR-009,
-- US4).
--
-- Règles tenues ici :
-- - RLS active sur les deux tables (règle produit 7), cloisonnées par
--   organisation comme 0002 : un membre ne lit que les lignes de ses
--   organisations (public.mes_organisations()) ; anon ne lit rien.
-- - Clés étrangères composées (…, organisation_id) : un cas ou une décision ne
--   peut pas pointer vers la carto ou le groupe d'une autre organisation, même
--   écrit en service_role.
-- - Aucune colonne de personne physique (principe 6, règle produit 4).
--   `carto_cas.nom` est la dénomination de la société (SIRENE). Les indices
--   sont des textes du worker, qui garantit qu'ils ne citent aucun dirigeant
--   personne : un dirigeant commun s'y écrit comme un nombre.
--   `decide_par` est un identifiant auth.users, jamais un nom ni un e-mail ; il
--   passe à nul quand le compte est effacé.
-- - Le moteur range les cas, le consultant décide (principe 1). Une décision
--   n'est jamais modifiée ni effacée : une nouvelle décision la remplace, la
--   plus récente est en vigueur (cartofr.moteur.decisions_en_vigueur). Elle
--   vaut pour le groupe, donc pour les cartos suivantes.
-- - Écritures : `carto_cas` par le worker, `decisions` par une Server Action
--   (T028) en service_role, après lecture du cas avec la session du membre
--   (RLS). Aucune politique d'écriture pour authenticated.

-- Les cas douteux d'une carto, rangés par le moteur avec leur règle et leurs
-- indices. Un cas par société.
create table public.carto_cas (
  carto_id uuid not null,
  organisation_id uuid not null,
  siren varchar(9) not null check (siren ~ '^[0-9]{9}$'),
  -- Dénomination de la société au registre, jamais celle d'un dirigeant.
  nom text,
  -- Pourquoi le cas est douteux (cartofr.moteur.modele.TypeCas), au moins un.
  types text[] not null check (
    cardinality(types) >= 1
    and types <@ array['confiance_c', 'co_entreprise', 'participation', 'etrangere', 'decision']
  ),
  -- La règle qui a placé la société là : entrée dans le groupe, ou pas.
  regle text not null,
  -- Dans la carto rendue (carto_societes) ou non.
  retenue boolean not null,
  indices_pour text[] not null default '{}',
  indices_contre text[] not null default '{}',
  -- La décision du consultant appliquée à ce calcul, nulle s'il n'y en a pas.
  decision text check (decision in ('retenir', 'ecarter')),
  primary key (carto_id, siren),
  foreign key (carto_id, organisation_id)
    references public.cartos (id, organisation_id) on delete cascade
);

-- Les décisions du consultant, par groupe : reprises par chaque carto suivante.
create table public.decisions (
  id bigint generated always as identity primary key,
  organisation_id uuid not null,
  groupe_id uuid not null,
  siren varchar(9) not null check (siren ~ '^[0-9]{9}$'),
  decision text not null check (decision in ('retenir', 'ecarter')),
  -- La carto sur laquelle elle a été prise ; nulle si cette carto est effacée.
  carto_id uuid,
  decide_le timestamptz not null default now(),
  -- Le membre qui a décidé (auth.users) ; nul si son compte est effacé (RGPD).
  decide_par uuid references auth.users (id) on delete set null,
  foreign key (groupe_id, organisation_id)
    references public.groupes (id, organisation_id) on delete cascade,
  foreign key (carto_id, organisation_id)
    references public.cartos (id, organisation_id) on delete set null (carto_id)
);

-- Lecture par le worker : toutes les décisions d'un groupe.
create index decisions_groupe_idx on public.decisions (groupe_id, organisation_id, siren);
create index decisions_organisation_id_idx on public.decisions (organisation_id);
create index decisions_carto_idx on public.decisions (carto_id, organisation_id);
create index decisions_decide_par_idx on public.decisions (decide_par);
-- carto_cas : sa clé primaire (carto_id, siren) sert déjà la cascade.

alter table public.carto_cas enable row level security;
alter table public.decisions enable row level security;

-- Comme 0002 : les privilèges par défaut de Supabase sont retirés, puis la
-- lecture seule est rendue à authenticated. RLS filtre ensuite les lignes.
revoke all on public.carto_cas, public.decisions from anon, authenticated;
revoke all on sequence public.decisions_id_seq from anon, authenticated;
grant select on public.carto_cas, public.decisions to authenticated;

create policy carto_cas_lecture_membres on public.carto_cas
  for select to authenticated
  using (organisation_id in (select public.mes_organisations()));

create policy decisions_lecture_membres on public.decisions
  for select to authenticated
  using (organisation_id in (select public.mes_organisations()));
