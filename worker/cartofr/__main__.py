"""Point d'entrée du worker : `python -m cartofr` lance la file de travaux (T008).

But : configurer les journaux et faire tourner `cartofr.travaux.boucle`
jusqu'à SIGTERM (docker stop) ou SIGINT (Ctrl+C), puis sortir proprement
une fois le travail en cours fini.

Entrée : DATABASE_URL (jamais journalisée), CARTOFR_LOG (niveau, INFO par défaut).
Sortie : code 0 à l'arrêt demandé, 2 si DATABASE_URL manque.
"""

import logging
import os
import signal
import sys
import threading
from types import FrameType

from cartofr.db import ConfigurationManquante, url_base
from cartofr.travaux import boucle


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("CARTOFR_LOG", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s : %(message)s",
    )
    log = logging.getLogger("cartofr")
    try:
        url_base()
    except ConfigurationManquante as exc:
        log.error("%s", exc)
        return 2

    arret = threading.Event()

    def arreter(signum: int, _frame: FrameType | None) -> None:
        log.info("signal %s reçu : arrêt après le travail en cours", signal.Signals(signum).name)
        arret.set()

    signal.signal(signal.SIGTERM, arreter)
    signal.signal(signal.SIGINT, arreter)
    boucle(arret)
    return 0


if __name__ == "__main__":
    sys.exit(main())
