"""Punto d'ingresso per le azioni salvate nei layer (codice Python delle azioni QGIS).

Un layer di foto ricorda `from webodm2qgis_tools.runtime import open_original`: cosi' l'azione funziona
anche dopo aver riaperto il progetto, finche' il plugin e' installato e attivo.
"""
from .i18n import T

controller = None            # impostato da plugin.py


def _ready():
    if controller is None:
        from qgis.utils import iface
        if iface is not None:
            iface.messageBar().pushWarning('WebODM2QGIS-tools', T('Il plugin non e\' attivo.'))
        return False
    return True


def open_original(layer_id, fid):
    if _ready():
        controller.open_original(layer_id, fid)


def show_photo(layer_id, fid):
    if _ready():
        controller.show_photo(layer_id, fid)
