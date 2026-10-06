-- Mots de passe des rôles utilisés par auth (GoTrue) et rest (PostgREST).
-- Repris du roles.sql officiel (supabase/supabase, docker/volumes/db), réduit
-- aux services lancés. Joué une seule fois, à la création de la base.
-- La valeur vient de l'environnement du conteneur db, jamais de ce fichier.
\set pgpass `echo "$POSTGRES_PASSWORD"`

ALTER USER authenticator WITH PASSWORD :'pgpass';
ALTER USER supabase_auth_admin WITH PASSWORD :'pgpass';
