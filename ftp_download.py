"""Télécharge un fichier du FTP RNE de l'INPI en reprenant là où il s'est arrêté.

Le serveur bloque souvent l'ouverture du canal de données : chaque essai abandonne au bout de
60 secondes sans données, puis se reconnecte et reprend à l'octet près.
Usage : python ftp_download.py stock_RNE_formalites_NIVEAU1_20260304_1400.zip
"""
import ftplib, os, pathlib, socket, sys, time
import inpi

name = sys.argv[1]
out = pathlib.Path(__file__).parent / "data" / "rne_stock" / name
e = inpi._env()
total = None
attempt = 0
while True:
    done = out.stat().st_size if out.exists() else 0
    if total and done >= total:
        break
    attempt += 1
    try:
        f = ftplib.FTP(e["INPI_FTP_HOST"], timeout=60)
        f.login(e["INPI_FTP_USERNAME"], e["INPI_FTP_PASSWORD"])
        f.voidcmd("TYPE I")
        total = total or f.size(name)
        with open(out, "ab") as fh:
            f.retrbinary(f"RETR {name}", fh.write, blocksize=1 << 20, rest=done or None)
        f.quit()
    except (socket.timeout, TimeoutError, OSError, EOFError, ftplib.Error) as x:
        now = out.stat().st_size if out.exists() else 0
        print(f"essai {attempt} : {type(x).__name__}, {now / 2**20:.0f} Mo sur {(total or 0) / 2**20:.0f} Mo", flush=True)
        time.sleep(10 if now > done else 30)
print(f"terminé : {out.stat().st_size} octets", flush=True)
(out.parent / f"{name}.ok").write_text("ok")
