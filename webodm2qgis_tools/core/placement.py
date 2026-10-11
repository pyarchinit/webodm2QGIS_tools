"""Posizionare uno scatto (prospetto/pianta in CRS locale) sul canvas: l'angolo in alto a sinistra va su un
punto scelto, nel CRS del progetto. Puro Python."""
import math

from ..i18n import T
from .models import Alert


def placed_bounds(width, height, ulx, uly):
    """(ulx, uly, lrx, lry) dell'immagine di `width` x `height` metri con l'angolo in alto a sinistra in (ulx, uly)."""
    vals = (width, height, ulx, uly)
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in vals):
        raise ValueError('valori non numerici')
    if width <= 0 or height <= 0:
        raise ValueError('dimensioni non valide')
    return (ulx, uly, ulx + width, uly - height)


def crs_problems(valid, geographic, metres):
    """Avvisi bloccanti sul CRS del progetto: lo scatto ha le dimensioni in metri, quindi serve un CRS
    proiettato in metri."""
    if not valid:
        return [Alert('P07', 'block', T("Il progetto non ha un CRS: impostalo prima di posizionare lo scatto."))]
    if geographic:
        return [Alert('P08', 'block', T(
            "Il CRS del progetto e' in gradi: lo scatto ha dimensioni in metri. Imposta un CRS proiettato "
            "in metri (per esempio UTM) e riprova."))]
    if not metres:
        return [Alert('P09', 'block', T("Il CRS del progetto non e' in metri: le dimensioni dello scatto sarebbero errate."))]
    return []


def placed_name(stem, existing):
    """Nome file libero: <stem>_posizionato.vrt, poi _2, _3... (un file caricato in QGIS non si puo' sovrascrivere)."""
    n = 1
    while True:
        name = '%s_posizionato%s.vrt' % (stem, '' if n == 1 else '_%d' % n)
        if name not in existing:
            return name
        n += 1
