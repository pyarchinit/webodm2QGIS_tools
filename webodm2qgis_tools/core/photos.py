"""Punti di scatto delle foto: da shots.geojson di ODM a PhotoShot. Puro Python.

Il file e' in gradi WGS84 (anche nei task non georiferiti, dove la posizione e' fittizia); `translation` e'
la posizione della camera nel riferimento metrico locale della ricostruzione; `rotation` e' il vettore
asse-angolo (Rodrigues) di OpenSfM, rotazione mondo -> camera.
"""
import math
import os
import time
from dataclasses import dataclass, field, replace
from typing import List, Optional

from .safety import IMAGE_EXT, safe_filename

ORIG_YES, ORIG_NO, ORIG_UNKNOWN = 'si', 'no', '?'


@dataclass
class PhotoShot:
    filename: str
    lon: float
    lat: float
    alt: float
    camera: str = ''
    focal: Optional[float] = None
    width: int = 0
    height: int = 0
    capture_time: Optional[float] = None
    position: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])    # locale, metri
    rotation: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    azimuth: Optional[float] = None         # gradi da nord in senso orario; direzione in cui guarda
    tilt: Optional[float] = None            # gradi dal nadir (0 = guarda in basso, 90 = orizzontale)


def view_direction(rvec):
    """Direzione dell'asse ottico della camera nel riferimento del mondo (x est, y nord, z su)."""
    rx, ry, rz = rvec
    theta = math.sqrt(rx * rx + ry * ry + rz * rz)
    if theta < 1e-12:
        r = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    else:
        k = (rx / theta, ry / theta, rz / theta)
        c, s = math.cos(theta), math.sin(theta)
        kx = ((0, -k[2], k[1]), (k[2], 0, -k[0]), (-k[1], k[0], 0))
        r = [[(c if i == j else 0) + (1 - c) * k[i] * k[j] + s * kx[i][j] for j in range(3)] for i in range(3)]
    # asse ottico = terza colonna di R^T = terza riga di R
    d = (r[2][0], r[2][1], r[2][2])
    return d


def orientation(rvec):
    return orientation_from_dir(view_direction(rvec))


def orientation_from_dir(d):
    horiz = math.hypot(d[0], d[1])
    tilt = math.degrees(math.acos(max(-1.0, min(1.0, -d[2]))))
    azimuth = math.degrees(math.atan2(d[0], d[1])) % 360.0 if horiz > 1e-6 else None
    return azimuth, tilt


def _floats(v, n):
    if isinstance(v, (list, tuple)) and len(v) >= n:
        try:
            return [float(x) for x in v[:n]]
        except (TypeError, ValueError):
            return None
    return None


def parse_shots(geojson):
    """-> (lista di PhotoShot, numero di feature scartate). Scarta nomi file ostili o coordinate assenti."""
    shots, skipped = [], 0
    if not isinstance(geojson, dict) or not isinstance(geojson.get('features'), list):
        return shots, 0
    for feat in geojson['features']:
        try:
            props = feat.get('properties') or {}
            name = safe_filename(props.get('filename'), IMAGE_EXT)
            coords = _floats((feat.get('geometry') or {}).get('coordinates'), 2)
            if name is None or coords is None or not (-180 <= coords[0] <= 180 and -90 <= coords[1] <= 90):
                skipped += 1
                continue
            full = (feat['geometry']['coordinates'] + [0.0, 0.0, 0.0])
            alt = float(full[2])
            rot = _floats(props.get('rotation'), 3) or [0.0, 0.0, 0.0]
            azimuth, tilt = orientation(rot) if props.get('rotation') else (None, None)
            ct = props.get('capture_time')
            shots.append(PhotoShot(
                filename=name, lon=coords[0], lat=coords[1], alt=alt, camera=str(props.get('camera') or ''),
                focal=float(props['focal']) if props.get('focal') is not None else None,
                width=int(props.get('width') or 0), height=int(props.get('height') or 0),
                capture_time=float(ct) if ct is not None else None,
                position=_floats(props.get('translation'), 3) or [0.0, 0.0, alt], rotation=rot,
                azimuth=azimuth, tilt=tilt))
        except (TypeError, ValueError, KeyError, AttributeError):
            skipped += 1
    return shots, skipped


def find_local(folder, filename, _cache={}):
    """Cerca `filename` nella cartella locale delle foto (anche in sottocartelle, senza badare alle
    maiuscole). L'indice e' costruito una volta per cartella: non si scandisce il disco a ogni clic."""
    name = safe_filename(filename, IMAGE_EXT)
    if not folder or name is None or not os.path.isdir(folder):
        return None
    direct = os.path.join(folder, name)
    if os.path.isfile(direct):
        return direct
    key = os.path.realpath(folder)
    stamp, index = _cache.get(key, (0.0, None))
    # indice ricostruito se manca, o se il nome non c'e' e l'indice ha piu' di 30 s (foto aggiunte nel frattempo)
    if index is None or (name.lower() not in index and time.time() - stamp > 30):
        index = build_index(folder)
        _cache[key] = (time.time(), index)
    return index.get(name.lower())


def build_index(folder, max_files=200000):
    index, n = {}, 0
    for root, _dirs, files in os.walk(folder):
        for f in files:
            if os.path.splitext(f)[1].lower() in IMAGE_EXT:
                index.setdefault(f.lower(), os.path.join(root, f))
                n += 1
                if n >= max_files:
                    return index
    return index


def valid_matrix(m):
    """True se `m` e' una matrice 4x4 di numeri finiti (come la dà il plugin WebODM: p' = M . [x y z 1])."""
    try:
        return (len(m) == 4 and all(len(r) == 4 for r in m)
                and all(math.isfinite(float(v)) for r in m for v in r))
    except (TypeError, ValueError):
        return False


def apply_matrix(shots, m):
    """Posizioni e direzioni delle foto dopo la trasformazione del plugin WebODM (scala, rotazione, ed
    eventualmente georiferimento). La parte 3x3 ruota (e scala) anche l'asse ottico: azimut e inclinazione
    si ricalcolano. Restituisce nuovi PhotoShot, gli originali restano com'erano."""
    if not valid_matrix(m):
        raise ValueError('matrice non valida')
    m = [[float(v) for v in r] for r in m]
    out = []
    for s in shots:
        p = [sum(m[r][c] * s.position[c] for c in range(3)) + m[r][3] for r in range(3)]
        az, tilt = s.azimuth, s.tilt
        if az is not None or tilt is not None:
            d = view_direction(s.rotation)
            dd = [sum(m[r][c] * d[c] for c in range(3)) for r in range(3)]
            n = math.sqrt(sum(v * v for v in dd))
            if n > 1e-12:
                az, tilt = orientation_from_dir([v / n for v in dd])
        out.append(replace(s, position=p, alt=p[2], azimuth=az, tilt=tilt))
    return out
