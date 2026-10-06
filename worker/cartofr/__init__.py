"""cartofr : le worker de cartoFR.

Contient toute la logique métier (principe 7 de CLAUDE.md) : registre des
sociétés et des liens, synchro INPI et INSEE, moteur de cartographie, file de
travaux. L'interface web ne fait qu'afficher et mettre en file.
"""

from importlib.metadata import version

__version__ = version("cartofr")
