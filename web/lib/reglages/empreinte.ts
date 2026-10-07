// Empreinte d'un nom de famille exclu (T020, garde-fou 6, ARCHI « Familles
// exclues : masquées par empreinte »).
//
// Le consultant tape le nom une fois ; le serveur n'en garde que le
// HMAC-SHA256 avec la clé CARTOFR_CLE_EMPREINTE. Doit rendre exactement ce que
// rend worker/cartofr/empreinte.py, que le moteur (T021) compare au nom de
// chaque dirigeant : mêmes vecteurs dans empreinte.test.ts et
// worker/tests/test_reglages.py.
//
// node:crypto : ce module ne peut pas finir dans le bundle du navigateur. Il
// ne lit pas la clé lui-même (voir cle.ts, serveur seulement), pour rester
// testable par Vitest.
import { createHmac } from "node:crypto";

// Blancs retirés aux bords par str.strip() en Python (str.isspace). Pas
// String.prototype.trim : il ignore \x1c-\x1f et \x85, et retire ﻿, que
// Python garde.
const BLANCS_PYTHON =
  "\\t\\n\\x0b\\x0c\\r\\x1c-\\x1f \\x85\\xa0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000";
const BORDS = new RegExp(`^[${BLANCS_PYTHON}]+|[${BLANCS_PYTHON}]+$`, "gu");

/** Même normalisation que normaliser() en Python : blancs des bords retirés,
 * puis majuscules. */
export function normaliser(nom: string): string {
  return nom.replace(BORDS, "").toUpperCase();
}

/** 64 caractères hexadécimaux. Refuse une clé vide plutôt que de rendre une
 * empreinte devinable. */
export function empreinte(nom: string, cle: string): string {
  if (!cle) throw new Error("Clé d'empreinte vide.");
  return createHmac("sha256", cle).update(normaliser(nom), "utf8").digest("hex");
}
