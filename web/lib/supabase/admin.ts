// Client Supabase avec la clé service_role (T009) : contourne RLS et parle à
// l'API d'administration de GoTrue (invitations).
//
// Serveur seulement : `server-only` fait échouer le build si un composant
// client l'importe, la clé ne peut donc pas finir dans le bundle du navigateur.
// À n'appeler qu'après avoir vérifié les droits de l'appelant avec sa propre
// session (lib/session.ts).
import "server-only";

import { createClient } from "@supabase/supabase-js";

import { lireEnv } from "./env";

export function creerClientAdmin() {
  return createClient(lireEnv("SUPABASE_URL"), lireEnv("SUPABASE_SERVICE_ROLE_KEY"), {
    auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false },
  });
}
