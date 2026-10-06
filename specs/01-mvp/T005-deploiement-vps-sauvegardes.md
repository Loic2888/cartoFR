# T005 — Déployer sur le VPS Hetzner et poser les sauvegardes

**Story** : Socle · **Phase** : Setup · **Parallèle** : séquentiel
**Couvre** : R5 · ADR-003
**Estimé** : 2-3 h

## Contexte
Le serveur cible : Hetzner CX43 en Allemagne. **Préalable humain** : créer le compte Hetzner et le serveur, et pointer un nom de domaine.

## Périmètre
Serveur prêt, application déployée, sauvegardes actives, procédure écrite.

## Mise en œuvre

### Fichiers à créer ou modifier
- `infra/deploiement.md` — création du serveur, pare-feu, déploiement, restauration
- `infra/sauvegarde.sh` — `pg_dump` quotidien de la base de l'app
- `infra/cron/sauvegarde` — planification

### Fonctionnement attendu
- Pare-feu : ports 22, 80 et 443 seulement
- Sauvegardes Hetzner activées (7 jours)

### Technologies
- Hetzner Cloud, Docker Compose, cron

### Motifs d'architecture
Un seul serveur, aucune haute disponibilité (ADR-003).

## Critères de succès
- [ ] **C1** : `infra/deploiement.md` décrit le déploiement et la restauration pas à pas
- [ ] **C2** : `infra/sauvegarde.sh` produit un dump horodaté et garde 7 jours
- [ ] **C3** : La région du serveur, écrite dans `infra/deploiement.md`, est en UE
- [ ] **C4** : L'URL de l'app répond en HTTPS

## Tests et validation

### Vérification manuelle
1. Restaurer un dump sur une base vide et vérifier les tables

### Cas limites
- Aucun propre à cette tâche

## Dépendances

**À finir avant** : T004
**Bloque** : T015
**Fichiers partagés avec** : aucun

## Documentation
- **PRD** : —
- **ARCHI** : Infrastructure, Coûts
