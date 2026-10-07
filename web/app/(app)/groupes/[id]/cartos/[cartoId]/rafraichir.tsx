"use client";

// Tant que la carto est en attente ou en cours, la page se relit toutes les
// 3 s (T022), comme la fiche du groupe (T021). Rien n'est affiché ici.
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { RAFRAICHISSEMENT_MS } from "../lancer-carto";

export function Rafraichir() {
  const router = useRouter();
  useEffect(() => {
    const minuterie = setInterval(() => router.refresh(), RAFRAICHISSEMENT_MS);
    return () => clearInterval(minuterie);
  }, [router]);
  return null;
}
