# Moteur France

Copier ce dossier dans un dossier de travail, puis :

```bash
python -m venv .venv && .venv/bin/pip install duckdb pandas pyarrow ijson requests openpyxl
mkdir -p data out
# .env : INPI_USERNAME, INPI_PASSWORD (API), INPI_FTP_HOST, INPI_FTP_USERNAME, INPI_FTP_PASSWORD (stock). Jamais dans git.
# 1. SIRENE : télécharger StockUniteLegale et StockEtablissement (parquet, data.gouv.fr) dans data/unite_legale.parquet et data/etablissement.parquet
.venv/bin/python build_sieges.py
# 2. Registre INPI complet (environ 15 Go) puis tables de liens (environ 15 minutes)
.venv/bin/python ftp_download.py stock_RNE_formalites_NIVEAU1_<date>.zip
.venv/bin/python build_links.py data/rne_stock/stock_RNE_formalites_NIVEAU1_<date>.zip
# 3. Un groupe
.venv/bin/python brand_scan.py config/<groupe>.json
.venv/bin/python engine.py config/<groupe>.json
.venv/bin/python to_skill_tables.py config/<groupe>.json
```

Sans les tables `data/rne_links/`, `engine.py` passe en mode API (INPI, Annuaire, BODACC), limité par le quota INPI d'environ 10 000 fiches par jour.
Règles, réglages et pièges : `../../references/moteur-france.md`.
