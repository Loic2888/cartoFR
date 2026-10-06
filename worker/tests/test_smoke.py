"""Vérifie que le paquet s'installe et s'importe."""

from importlib.metadata import version

import cartofr


def test_paquet_importable() -> None:
    assert cartofr.__version__ == version("cartofr")
