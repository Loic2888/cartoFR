-- Secret JWT et durée de validité, lisibles par les fonctions SQL de Supabase.
-- Repris du jwt.sql officiel (supabase/supabase, docker/volumes/db).
-- Les valeurs viennent de l'environnement du conteneur db, jamais de ce fichier.
\set jwt_secret `echo "$JWT_SECRET"`
\set jwt_exp `echo "$JWT_EXP"`

ALTER DATABASE postgres SET "app.settings.jwt_secret" TO :'jwt_secret';
ALTER DATABASE postgres SET "app.settings.jwt_exp" TO :'jwt_exp';
