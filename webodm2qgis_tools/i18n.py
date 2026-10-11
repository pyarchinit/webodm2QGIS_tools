"""Traduzioni: il testo italiano nel codice e' la chiave, T('Testo {n}', n=3).

Lingue: italiano (testo originale), inglese (i18n_en.py), francese, tedesco, spagnolo, portoghese
(translations.txt: una riga per testo, `italiano ||| fr ||| de ||| es ||| pt`).
Lingua = quella scelta dall'utente (Informazioni > Lingua) oppure, in automatico, la lingua di QGIS;
una lingua non supportata ripiega sull'inglese, un testo non tradotto ripiega sull'inglese e poi sull'italiano.
Puro Python: nessuna dipendenza da Qt, cosi' lo usano anche i moduli testabili senza QGIS.
"""
import os

from .i18n_en import EN

LANGS = ('it', 'en', 'fr', 'de', 'es', 'pt')
LANG_NAMES = {'it': 'Italiano', 'en': 'English', 'fr': 'Français', 'de': 'Deutsch', 'es': 'Español',
              'pt': 'Português'}
_ORDER = ('fr', 'de', 'es', 'pt')
_TABLES = None
_lang = 'it'


def tables():
    """{'fr': {italiano: testo}, ...}, letto una volta da translations.txt."""
    global _TABLES
    if _TABLES is None:
        _TABLES = {c: {} for c in _ORDER}
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'translations.txt')
        try:
            with open(path, encoding='utf-8') as f:
                for line in f:
                    line = line.rstrip('\n')
                    if not line.strip() or line.startswith('#'):
                        continue
                    parts = line.split(' ||| ')
                    if len(parts) != 1 + len(_ORDER):
                        continue
                    for code, text in zip(_ORDER, parts[1:]):
                        if text:
                            _TABLES[code][parts[0]] = text
        except OSError:
            pass
    return _TABLES


def normalize(code):
    """'it_IT', 'pt-BR', 'de_DE' -> uno di LANGS; lingue non supportate -> 'en'; vuoto -> 'it'."""
    code = (code or 'it').lower().replace('-', '_').split('_')[0]
    return code if code in LANGS else 'en'


def set_language(code):
    global _lang
    _lang = normalize(code)


def language():
    return _lang


def T(text, **kw):
    out = text
    if _lang == 'en':
        out = EN.get(text, text)
    elif _lang != 'it':
        out = tables().get(_lang, {}).get(text) or EN.get(text, text)
    if kw:
        try:
            out = out.format(**kw)
        except (KeyError, IndexError, ValueError):
            pass
    return out
