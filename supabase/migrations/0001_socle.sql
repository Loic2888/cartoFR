-- 0001 — Socle de la base de l'app : organisations, membres, file de travaux,
-- état du registre, et cloisonnement RLS (T006 ; ARCHI, Données §2 ; ADR-004).
--
-- Règles tenues ici :
-- - RLS active sur chaque table (règle produit 7). Un membre ne lit que les
--   lignes de ses organisations ; anon ne lit rien.
-- - Aucune colonne de personne physique (principe 6, règle produit 4) : l'e-mail
--   d'un membre reste dans auth.users, géré par GoTrue. `organisations.nom` est
--   le nom d'une organisation cliente, pas d'une personne.
-- - Les écritures passent par service_role (worker, Server Actions), qui
--   contourne RLS. Aucune politique d'écriture pour authenticated à ce stade.

-- Organisations clientes (Youno d'abord).
create table public.organisations (
  id uuid primary key default gen_random_uuid(),
  nom text not null,
  cree_le timestamptz not null default now()
);

-- Qui appartient à quelle organisation. Effacer un compte auth efface ses
-- appartenances (règle produit 4, effacement possible).
create table public.membres (
  organisation_id uuid not null references public.organisations (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  role text not null default 'membre' check (role in ('membre', 'admin')),
  cree_le timestamptz not null default now(),
  primary key (organisation_id, user_id)
);

-- Lu par mes_organisations() à chaque requête d'un membre.
create index membres_user_id_idx on public.membres (user_id);

-- File de travaux, lue par le worker en `for update skip locked` (ADR-004).
-- organisation_id nul = travail global (synchro du registre).
create table public.travaux (
  id bigint generated always as identity primary key,
  type text not null,
  statut text not null default 'en_attente'
    check (statut in ('en_attente', 'en_cours', 'termine', 'echec')),
  organisation_id uuid references public.organisations (id) on delete cascade,
  parametres jsonb not null default '{}'::jsonb,
  cree_le timestamptz not null default now(),
  debut_le timestamptz,
  fin_le timestamptz,
  duree_ms integer,
  erreur text
);

-- Prochain travail à prendre : le plus ancien en attente.
create index travaux_en_attente_idx on public.travaux (cree_le) where statut = 'en_attente';
create index travaux_organisation_id_idx on public.travaux (organisation_id);

-- Copie du dernier passage de mises_a_jour (registre DuckDB), une ligne par
-- source (rne, sirene), pour l'écran admin. Donnée globale, sans organisation.
create table public.etat_registre (
  source text primary key,
  date_donnees date,
  dernier_passage timestamptz,
  statut text,
  volumes jsonb not null default '{}'::jsonb,
  erreur text,
  maj_le timestamptz not null default now()
);

-- Organisations de l'utilisateur connecté. security definer : lit membres
-- sans repasser par la politique de membres, sinon la politique de membres
-- s'appellerait elle-même (récursion infinie).
create function public.mes_organisations()
returns setof uuid
language sql
stable
security definer
set search_path = ''
as $$
  select m.organisation_id from public.membres m where m.user_id = auth.uid()
$$;

revoke execute on function public.mes_organisations() from public, anon;
grant execute on function public.mes_organisations() to authenticated;

-- RLS partout, y compris sur les tables globales.
alter table public.organisations enable row level security;
alter table public.membres enable row level security;
alter table public.travaux enable row level security;
alter table public.etat_registre enable row level security;

-- Les privilèges par défaut de Supabase donnent tout à anon et authenticated :
-- on les retire, puis on rend la lecture seule à authenticated. RLS filtre
-- ensuite les lignes.
revoke all on public.organisations, public.membres, public.travaux, public.etat_registre
  from anon, authenticated;
grant select on public.organisations, public.membres, public.travaux, public.etat_registre
  to authenticated;

create policy organisations_lecture_membres on public.organisations
  for select to authenticated
  using (id in (select public.mes_organisations()));

create policy membres_lecture_membres on public.membres
  for select to authenticated
  using (organisation_id in (select public.mes_organisations()));

-- Les travaux globaux (organisation_id nul) ne sont visibles d'aucun membre :
-- l'écran admin (T014) les lira par une politique dédiée.
create policy travaux_lecture_membres on public.travaux
  for select to authenticated
  using (organisation_id in (select public.mes_organisations()));

-- État du registre : public pour tout utilisateur connecté (aucune donnée client).
create policy etat_registre_lecture on public.etat_registre
  for select to authenticated
  using (true);
