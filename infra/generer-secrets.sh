#!/usr/bin/env bash
# Crée infra/.env : les variables lues par infra/docker-compose.yml.
#
# Usage, depuis n'importe où : bash infra/generer-secrets.sh
# Entrée : aucune. Sortie : infra/.env (droits 600, hors git).
#
# - Refuse d'écraser un infra/.env existant (il porte le mot de passe de la
#   base : le changer après la création de la base casse auth et rest).
# - N'affiche jamais une valeur, seulement le nombre de variables écrites.
# - ANON_KEY et SERVICE_ROLE_KEY sont de vrais JWT HS256 signés avec JWT_SECRET.
# - Les réglages SMTP visent mailpit (local). En production, remplacer par
#   Brevo : SMTP_HOST=smtp-relay.brevo.com, SMTP_PORT=587, SMTP_USER, SMTP_PASS.
set -euo pipefail

cible="$(cd "$(dirname "$0")" && pwd)/.env"

if [ -e "$cible" ]; then
  echo "infra/.env existe déjà : rien n'est écrit. Supprimez-le d'abord pour le régénérer." >&2
  exit 1
fi

command -v python3 >/dev/null || { echo "python3 est nécessaire." >&2; exit 1; }

umask 077
CIBLE="$cible" python3 - <<'PY'
import base64, hashlib, hmac, json, os, secrets, time

def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def jwt(role: str, secret: str) -> str:
    now = int(time.time())
    header = b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = b64(json.dumps(
        {"role": role, "iss": "supabase", "iat": now, "exp": now + 5 * 365 * 24 * 3600},
        separators=(",", ":"),
    ).encode())
    signature = hmac.new(secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    return f"{header}.{payload}.{b64(signature)}"

jwt_secret = secrets.token_hex(32)
variables = {
    # Adresse publique
    "DOMAINE": "localhost",
    "SITE_URL": "https://localhost",
    "API_EXTERNAL_URL": "https://localhost",
    "ADDITIONAL_REDIRECT_URLS": "",
    # Secrets Supabase
    "POSTGRES_PASSWORD": secrets.token_hex(24),
    "JWT_SECRET": jwt_secret,
    "JWT_EXPIRY": "3600",
    "ANON_KEY": jwt("anon", jwt_secret),
    "SERVICE_ROLE_KEY": jwt("service_role", jwt_secret),
    "PG_META_CRYPTO_KEY": secrets.token_hex(16),
    # Empreinte HMAC des familles exclues des réglages (garde-fou 6)
    "CARTOFR_CLE_EMPREINTE": secrets.token_hex(32),
    # SMTP (mailpit en local, Brevo en production)
    "SMTP_HOST": "mailpit",
    "SMTP_PORT": "1025",
    "SMTP_USER": "",
    "SMTP_PASS": "",
    "SMTP_ADMIN_EMAIL": "admin@cartofr.local",
    "SMTP_SENDER_NAME": "cartoFR",
}

with open(os.environ["CIBLE"], "w", encoding="utf-8") as f:
    f.write("# Généré par infra/generer-secrets.sh. Ne jamais committer.\n")
    for nom, valeur in variables.items():
        f.write(f"{nom}={valeur}\n")
os.chmod(os.environ["CIBLE"], 0o600)
print(f"infra/.env créé, {len(variables)} variables")
PY
