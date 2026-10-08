-- 0005 — Suppression d'un compte : une organisation garde un administrateur
-- (T031 ; règle produit 4, effacement possible ; docs/registre-traitements.md).
--
-- Ce qui se passe déjà quand un compte est effacé de auth.users (0001, 0002) :
-- - ses appartenances (membres) disparaissent, en cascade ;
-- - groupes.cree_par, reglages.cree_par et reglages.valide_par passent à nul :
--   les groupes, réglages et cartos restent à l'organisation, sans aucune
--   référence au compte. cartos, carto_societes, carto_liens et travaux n'ont
--   aucune colonne d'utilisateur. L'e-mail n'a jamais quitté auth.users.
--
-- Ce que cette migration ajoute : la règle du dernier administrateur.
-- Quand l'appartenance d'un administrateur disparaît (compte effacé, ou ligne
-- supprimée en service_role) et qu'il ne reste aucun administrateur dans une
-- organisation qui a encore des membres, le membre le plus ancien (cree_le,
-- puis user_id pour départager) devient administrateur. Sans membre restant,
-- l'organisation reste telle quelle, avec ses groupes et ses cartos : seul
-- l'opérateur (Youno) peut la supprimer ou y inviter quelqu'un.
--
-- Pourquoi promouvoir plutôt que refuser : un refus bloquerait l'effacement
-- (droit RGPD) tant qu'un autre admin n'est pas nommé, et l'app n'a pas encore
-- d'écran pour changer un rôle. Le membre promu a déjà été invité par un admin
-- de cette organisation ; il gagne seulement le droit d'inviter et de voir
-- l'écran du registre.
--
-- La règle vit en base, pas dans Next.js : elle tient quel que soit le chemin
-- de l'effacement (Server Action, console GoTrue, SQL de l'opérateur).
-- RLS inchangée : aucune politique ni aucun privilège n'est modifié.

-- security definer : GoTrue efface auth.users avec son propre rôle
-- (supabase_auth_admin), qui n'a aucun droit d'écriture sur public.membres.
-- La promotion se fait donc avec les droits du propriétaire de la fonction.
create function public.membres_garder_un_admin()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  org uuid;
begin
  -- Une seule passe par organisation touchée par l'instruction.
  for org in
    select distinct a.organisation_id from anciens a where a.role = 'admin'
  loop
    -- Organisation supprimée (cascade depuis organisations) : rien à garder.
    continue when not exists (select 1 from public.organisations o where o.id = org);
    -- Un administrateur reste : rien à faire.
    continue when exists (
      select 1 from public.membres m where m.organisation_id = org and m.role = 'admin'
    );
    update public.membres m
       set role = 'admin'
     where m.organisation_id = org
       and m.user_id = (
         select m2.user_id from public.membres m2
          where m2.organisation_id = org
          order by m2.cree_le, m2.user_id
          limit 1
       );
  end loop;
  return null;
end
$$;

revoke execute on function public.membres_garder_un_admin() from public, anon, authenticated;

-- Déclencheur d'instruction, après la suppression : il voit l'état final
-- (toutes les lignes de l'instruction déjà supprimées, cascades comprises).
create trigger membres_garder_un_admin
  after delete on public.membres
  referencing old table as anciens
  for each statement execute function public.membres_garder_un_admin();
