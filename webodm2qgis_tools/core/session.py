"""Sessione di import: un nome e una cartella scelti dall'utente. Puro Python.

Tutto cio' che si scarica in una sessione sta in `<cartella>/<nome sessione>/<task>/...`; il gruppo nel
pannello Livelli di QGIS ha il nome della sessione; un file `sessione.json` ne descrive il contenuto.
"""
import json
import os
import re
import time
from dataclasses import dataclass

from .safety import safe_join

MANIFEST = 'sessione.json'
_BAD = re.compile(r'[\x00-\x1f<>:"/\\|?*]')


def dirname_of(text, fallback='sessione'):
    """Il nome scelto dall'utente -> nome di cartella valido su Windows e Linux."""
    t = _BAD.sub('_', (text or '').strip())
    t = re.sub(r'\s+', ' ', t).strip(' .')
    if not t or t.upper() in ('CON', 'PRN', 'AUX', 'NUL') or re.match(r'^(COM|LPT)\d$', t.upper()):
        t = fallback
    return t[:80]


def default_name(task_label, when=None):
    return '%s %s' % (task_label or 'Import', time.strftime('%Y-%m-%d', when or time.localtime()))


@dataclass
class Session:
    name: str = ''
    folder: str = ''            # cartella scelta dall'utente, che contiene la cartella della sessione

    def valid(self):
        return bool(self.name.strip() and self.folder)

    @property
    def root(self):
        """<cartella>/<nome>; None se non valida."""
        if not self.valid():
            return None
        return safe_join(self.folder, dirname_of(self.name))

    def task_dir(self, task_label, task_id):
        """Cartella di un task dentro la sessione (nome leggibile + inizio dell'id: unica anche con nomi uguali)."""
        if not self.valid():
            return None
        return safe_join(self.root, '%s_%s' % (dirname_of(task_label, 'task'), str(task_id)[:8]))

    def file_path(self, task_label, task_id, *parts):
        """Percorso di un file della sessione; None se uscirebbe dalla cartella del task."""
        base = self.task_dir(task_label, task_id)
        return safe_join(base, *parts) if base else None

    def to_dict(self):
        return {'name': self.name, 'folder': self.folder}

    @classmethod
    def from_dict(cls, d):
        d = d if isinstance(d, dict) else {}
        return cls(name=str(d.get('name') or ''), folder=str(d.get('folder') or ''))


def write_manifest(session, server_url, entries):
    """Scrive `sessione.json` nella cartella della sessione; `entries` = lista di dict (task, prodotti...).
    Restituisce il percorso, None se non riesce (non e' mai un errore bloccante)."""
    root = session.root
    if root is None:
        return None
    try:
        os.makedirs(root, exist_ok=True)
        path = os.path.join(root, MANIFEST)
        old = {}
        if os.path.isfile(path):
            with open(path, encoding='utf-8') as f:
                old = json.load(f)
        data = {'name': session.name, 'server': server_url, 'created': old.get('created') or int(time.time()),
                'updated': int(time.time()), 'items': (old.get('items') or []) + list(entries)}
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        return path
    except (OSError, ValueError):
        return None
