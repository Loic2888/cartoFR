-- 0004 — Réglages proposés par l'IA et corrections humaines (T025, T026 ;
-- ARCHI « IA (P2, US3) » ; PRD FR-008, SC-007).
--
-- Pas de nouvelle table : une proposition est une version de `reglages`
-- (origine 'proposition'), écrite par le worker (travail `proposition`), donc
-- déjà sous RLS (migration 0002 : un membre ne lit que les réglages de ses
-- organisations, anon rien).
--
-- Règles tenues ici :
-- - L'IA ne décide jamais (principe 1) : une version 'proposition' n'est
--   jamais validée telle quelle. Le consultant accepte, corrige ou rejette
--   chaque élément ; c'est la version qui en sort (origine 'saisie') qui est
--   validée, avec le nombre de corrections (SC-007).
-- - Chaque élément proposé porte sa source (URL) dans `proposition`, à côté
--   du contenu : `contenu` garde le schéma des réglages (Zod, pydantic), que
--   le moteur lit sans rien savoir de l'IA.
-- - Aucune colonne de personne physique (principe 6) : `proposition` porte
--   des noms de marques et de sociétés, des URL et des nombres.

alter table public.reglages drop constraint reglages_origine_check;
alter table public.reglages add constraint reglages_origine_check
  check (origine in ('saisie', 'depart', 'proposition'));

alter table public.reglages
  -- Détail d'une proposition de l'IA : modèle, éléments proposés (liste,
  -- valeur, source, homonymes au registre). Nul hors origine 'proposition'.
  add column proposition jsonb check (proposition is null or jsonb_typeof(proposition) = 'object'),
  -- Version validée tirée d'une proposition : la proposition revue, et le
  -- nombre d'éléments rejetés, corrigés ou ajoutés par le consultant.
  add column proposition_id uuid,
  add column corrections integer check (corrections >= 0),
  add constraint reglages_proposition_avec_origine
    check ((origine = 'proposition') = (proposition is not null)),
  add constraint reglages_proposition_jamais_validee
    check (origine <> 'proposition' or valide_le is null),
  add constraint reglages_corrections_avec_proposition
    check (proposition_id is null or corrections is not null),
  -- La proposition revue est du même groupe, dans la même organisation.
  add constraint reglages_proposition_id_fkey foreign key (proposition_id, groupe_id, organisation_id)
    references public.reglages (id, groupe_id, organisation_id) on delete set null (proposition_id);

create index reglages_proposition_idx on public.reglages (proposition_id, groupe_id, organisation_id);

-- Une version validée reste figée : on y ajoute ses corrections et sa
-- proposition d'origine. Seuls cree_par, valide_par et proposition_id
-- (proposition supprimée) peuvent passer à nul.
create or replace function public.reglages_version_figee()
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
    or new.corrections is distinct from old.corrections
    or (new.proposition_id is distinct from old.proposition_id and new.proposition_id is not null)
  ) then
    raise exception 'Version de réglages validée : elle ne se modifie plus, créer une nouvelle version.'
      using errcode = 'check_violation';
  end if;
  return new;
end
$$;

revoke execute on function public.reglages_version_figee() from public, anon, authenticated;
