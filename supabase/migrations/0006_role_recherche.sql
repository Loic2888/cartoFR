-- 0006 — Rôle en lecture seule du service recherche (T041 ; règle produit 7, ARCHI).
--
-- Avant : le service `recherche` lisait les cartos pour l'export du skill (T029)
-- avec le rôle `postgres`, qui contourne RLS. L'isolation entre organisations ne
-- tenait que par le filtre `organisation_id` écrit dans ses requêtes.
--
-- Maintenant : il se connecte avec `cartofr_recherche`, qui
-- - ne lit que les quatre tables de l'export (groupes, reglages, cartos,
--   carto_societes), et n'écrit nulle part ;
-- - ne contourne pas RLS : ses politiques ne lui montrent que les lignes de
--   l'organisation déclarée pour la transaction en cours,
--   `set_config('cartofr.organisation', '<uuid>', true)`. Sans organisation
--   déclarée, il ne voit rien. Une requête mal écrite ne peut donc pas lire une
--   autre organisation que celle déclarée.
--
-- Le mot de passe n'est pas ici (garde-fou 5) : infra/appliquer-migrations.sh le
-- pose depuis RECHERCHE_DB_PASSWORD (infra/.env) et ouvre alors la connexion.
-- Rôle créé sans connexion possible tant que ce mot de passe n'est pas posé.

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'cartofr_recherche') then
    create role cartofr_recherche nologin noinherit nosuperuser nocreatedb nocreaterole nobypassrls;
  end if;
end
$$;

-- postgres (l'opérateur, les tests) peut agir comme ce rôle (`set role cartofr_recherche`)
-- pour vérifier ce qu'il voit. Dans l'image Supabase, postgres n'est pas superutilisateur :
-- sans cette appartenance, il ne peut pas prendre le rôle.
grant cartofr_recherche to postgres;

-- Toute transaction ouverte par ce rôle est en lecture seule, même si le code oublie de le demander.
alter role cartofr_recherche set default_transaction_read_only = on;

-- L'organisation déclarée pour la transaction ; nulle si aucune (alors aucune ligne visible).
create function public.organisation_de_la_requete()
returns uuid
language sql
stable
set search_path = ''
as $$
  select nullif(current_setting('cartofr.organisation', true), '')::uuid
$$;

revoke execute on function public.organisation_de_la_requete() from public, anon, authenticated;
grant execute on function public.organisation_de_la_requete() to cartofr_recherche;

grant usage on schema public to cartofr_recherche;
grant select on public.groupes, public.reglages, public.cartos, public.carto_societes to cartofr_recherche;

create policy groupes_lecture_recherche on public.groupes
  for select to cartofr_recherche
  using (organisation_id = public.organisation_de_la_requete());

create policy reglages_lecture_recherche on public.reglages
  for select to cartofr_recherche
  using (organisation_id = public.organisation_de_la_requete());

create policy cartos_lecture_recherche on public.cartos
  for select to cartofr_recherche
  using (organisation_id = public.organisation_de_la_requete());

create policy carto_societes_lecture_recherche on public.carto_societes
  for select to cartofr_recherche
  using (organisation_id = public.organisation_de_la_requete());
