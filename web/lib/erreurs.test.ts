import { describe, expect, it } from "vitest";

import { ERREUR_INCONNUE, codeErreurPourUrl, messageErreurAuth } from "./erreurs";

describe("messageErreurAuth", () => {
  it.each([
    ["otp_expired", /expiré/],
    ["flow_state_expired", /expiré/],
    ["over_email_send_rate_limit", /Trop de demandes/],
    ["over_request_rate_limit", /Trop de demandes/],
    ["signup_disabled", /Aucun compte/],
    ["otp_disabled", /Aucun compte/],
    ["user_not_found", /Aucun compte/],
    ["invalid_credentials", /Identifiants invalides/],
    ["email_exists", /déjà un compte/],
    ["session_not_found", /session a expiré/],
    ["email_address_invalid", /pas valide/],
  ])("traduit le code %s", (code, attendu) => {
    expect(messageErreurAuth({ code, message: "English text" })).toMatch(attendu);
  });

  it("accepte un code seul, venu de l'URL", () => {
    expect(messageErreurAuth("otp_expired")).toMatch(/Demandez-en un nouveau/);
  });

  it("reconnaît une erreur réseau sans code", () => {
    expect(messageErreurAuth({ name: "AuthRetryableFetchError", status: 0 })).toMatch(
      /ne répond pas/,
    );
    expect(messageErreurAuth({ message: "TypeError: fetch failed" })).toMatch(/ne répond pas/);
    expect(messageErreurAuth(new TypeError("Failed to fetch"))).toMatch(/ne répond pas/);
  });

  it("traduit un statut 429 sans code", () => {
    expect(messageErreurAuth({ status: 429 })).toMatch(/Trop de demandes/);
  });

  it.each([
    [undefined],
    [null],
    [{}],
    [{ code: "code_jamais_vu", message: "Something went wrong" }],
    [{ code: "toString" }],
    [{ code: "__proto__" }],
    [42],
  ])("rend un message générique en français pour %j", (erreur) => {
    expect(messageErreurAuth(erreur)).toBe(ERREUR_INCONNUE);
  });

  it("ne renvoie jamais le texte anglais de GoTrue", () => {
    const message = messageErreurAuth({ message: "Email link is invalid or has expired" });
    expect(message).not.toMatch(/invalid|expired/i);
  });
});

describe("codeErreurPourUrl", () => {
  it("garde un code simple", () => {
    expect(codeErreurPourUrl("otp_expired")).toBe("otp_expired");
  });

  it.each([[null], [undefined], [""], ["<script>"], ["a".repeat(41)], ["OTP"], ["x/../y"]])(
    "remplace %j par lien_invalide",
    (code) => {
      expect(codeErreurPourUrl(code)).toBe("lien_invalide");
    },
  );
});
