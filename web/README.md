# web — interface de cartoFR

Next.js 16 (App Router), TypeScript strict, Tailwind et shadcn/ui. Voir `ARCHI.md` à la racine.

Commandes, depuis la racine du dépôt :

| Quoi | Commande |
|---|---|
| Installer | `npm --prefix web install` |
| Développer | `npm --prefix web run dev` |
| Lint | `npm --prefix web run lint` |
| Typecheck | `npm --prefix web run typecheck` |
| Tests | `npm --prefix web test` |
| Build | `npm --prefix web run build` |

Node.js 22.12 au moins (`.nvmrc`). La télémétrie de Next.js (envoi à Vercel, hors UE) se coupe avec `NEXT_TELEMETRY_DISABLED=1` : à poser dans la CI (T003) et l'image Docker (T004). Le build télécharge les polices Geist depuis Google : il a besoin du réseau.

L'interface ne contient aucune règle du moteur (principe 7) : elle affiche, valide la saisie et met en file.
