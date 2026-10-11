"""Controlli su tutto cio' che arriva dal server prima di toccare il disco. Puro Python."""
import os
import re
import zipfile

IMAGE_EXT = frozenset(['.jpg', '.jpeg', '.tif', '.tiff', '.png', '.dng'])

_BAD_CHARS = re.compile(r'[\x00-\x1f<>:"/\\|?*]')
_RESERVED = frozenset(['CON', 'PRN', 'AUX', 'NUL'] + ['COM%d' % i for i in range(1, 10)] +
                      ['LPT%d' % i for i in range(1, 10)])


def safe_filename(name, exts=None, maxlen=200):
    """Il nome se e' un semplice nome di file (niente percorsi, '..', caratteri vietati su Windows,
    nomi riservati), altrimenti None. `exts`: insieme di estensioni ammesse (minuscole, col punto)."""
    if not isinstance(name, str):
        return None
    name = name.strip()
    if not name or len(name) > maxlen or name.startswith('.') or name.endswith(('.', ' ')):
        return None
    if _BAD_CHARS.search(name):
        return None
    if name.split('.')[0].upper() in _RESERVED:
        return None
    if exts is not None and os.path.splitext(name)[1].lower() not in exts:
        return None
    return name


def safe_join(base, *parts):
    """base/parts se resta dentro base, altrimenti None."""
    base_real = os.path.realpath(base)
    path = os.path.realpath(os.path.join(base_real, *parts))
    try:
        if os.path.commonpath([base_real, path]) != base_real:
            return None
    except ValueError:                      # unita' diverse su Windows
        return None
    return path


def extract_zip_safe(zip_path, dest, max_total=40 * 1024 ** 3):
    """Decomprime senza permettere scritture fuori da `dest` (zip slip) ne' archivi spropositati.
    Restituisce la lista dei file scritti; solleva ValueError se l'archivio e' sospetto."""
    written = []
    with zipfile.ZipFile(zip_path) as z:
        infos = z.infolist()
        if sum(i.file_size for i in infos) > max_total:
            raise ValueError('archivio troppo grande')
        for info in infos:
            name = info.filename.replace('\\', '/')
            if name.startswith('/') or re.match(r'^[A-Za-z]:', name) or '..' in name.split('/'):
                raise ValueError('percorso non valido nell\'archivio: %s' % info.filename)
            target = safe_join(dest, *[p for p in name.split('/') if p])
            if target is None:
                raise ValueError('percorso non valido nell\'archivio: %s' % info.filename)
            if info.is_dir():
                os.makedirs(target, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with z.open(info) as src, open(target, 'wb') as out:
                while True:
                    chunk = src.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
            written.append(target)
    return written
