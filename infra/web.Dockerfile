# syntax=docker/dockerfile:1
# Image de l'interface Next.js (contexte : web/). Node 22 comme web/.nvmrc.
# Démarre par `node server.js` du dossier standalone : `next start` ne marche
# pas avec output: "standalone".
# Le .dockerignore de cette image est web.Dockerfile.dockerignore (à côté).

FROM node:22-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-slim AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Les polices Geist sont téléchargées au build (next/font) : réseau nécessaire.
RUN npm run build && mkdir -p public

FROM node:22-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
USER node
EXPOSE 3000
CMD ["node", "server.js"]
