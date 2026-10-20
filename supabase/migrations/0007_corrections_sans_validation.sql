-- Corrections sans étape de validation (T051, US8, principe 2 amendé le 2026-10-16).
--
-- Une carto existe sans validation humaine ; une correction laisse une trace.
-- - Une version des réglages enregistrée sert au calcul suivant, sans
--   `valide_le`. Les colonnes `valide_le` et `valide_par` restent : elles
--   gardent l'historique des versions validées avant T051, et le seed de départ.
-- - Toute version est figée dès son enregistrement (avant : seulement une
--   version validée). Son auteur (`cree_par`) et sa date (`cree_le`) ne
--   changent plus : c'est la trace demandée par le principe 2.
-- - Une proposition de l'IA ne sert jamais de base à une carto (principe 1) :
--   seule la version que le consultant enregistre après revue le peut.
-- - L'effet d'une carto corrigée : le nombre de sociétés que ses corrections
--   ajoutent et retirent, par rapport à la carto sans correction (même tête,
--   même document), calculé par le worker. Nul pour une carto d'avant T051.
-- - Les versions enregistrées avant T051 sans jamais être validées deviennent
--   actives : la plus récente sert à la carto suivante. Aucune n'existe en
--   production à cette date (pas encore de serveur, T005).

drop trigger cartos_reglages_valides on public.cartos;
drop function public.cartos_reglages_valides();

create function public.cartos_reglages_pas_une_proposition()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if exists (
    select 1 from public.reglages r where r.id = new.reglages_id and r.origine = 'proposition'
  ) then
    raise exception 'Une proposition de l''IA ne sert pas de base à une carto : enregistrez-la d''abord.'
      using errcode = 'check_violation';
  end if;
  return new;
end
$$;

create trigger cartos_reglages_pas_une_proposition
  before insert or update of reglages_id on public.cartos
  for each row execute function public.cartos_reglages_pas_une_proposition();

-- Toute version est figée. Seuls cree_par, valide_par et proposition_id
-- (compte effacé, proposition supprimée) peuvent passer à nul.
create or replace function public.reglages_version_figee()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.contenu is distinct from old.contenu
    or new.version is distinct from old.version
    or new.groupe_id is distinct from old.groupe_id
    or new.organisation_id is distinct from old.organisation_id
    or new.origine is distinct from old.origine
    or new.cree_le is distinct from old.cree_le
    or (new.cree_par is distinct from old.cree_par and new.cree_par is not null)
    or new.valide_le is distinct from old.valide_le
    or (new.valide_par is distinct from old.valide_par and new.valide_par is not null)
    or new.proposition is distinct from old.proposition
    or new.corrections is distinct from old.corrections
    or (new.proposition_id is distinct from old.proposition_id and new.proposition_id is not null)
  then
    raise exception 'Version de réglages enregistrée : elle ne se modifie plus, créer une nouvelle version.'
      using errcode = 'check_violation';
  end if;
  return new;
end
$$;

revoke execute on function public.cartos_reglages_pas_une_proposition(), public.reglages_version_figee()
  from public, anon, authenticated;

alter table public.cartos
  add column societes_ajoutees integer check (societes_ajoutees >= 0),
  add column societes_retirees integer check (societes_retirees >= 0),
  -- Les deux, ou aucun.
  add constraint cartos_effet_complet check ((societes_ajoutees is null) = (societes_retirees is null));
