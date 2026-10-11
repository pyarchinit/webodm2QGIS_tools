"""Strutture dati. Puro Python."""
from dataclasses import dataclass, field
from typing import List, Optional

from ..i18n import T

QUEUED, RUNNING, FAILED, COMPLETED, CANCELED = 10, 20, 30, 40, 50


def status_label(code):
    return {QUEUED: T('In coda'), RUNNING: T('In elaborazione'), FAILED: T('Fallito'),
            COMPLETED: T('Completato'), CANCELED: T('Annullato')}.get(code, T('Sconosciuto'))


@dataclass
class Server:
    name: str
    url: str
    user: str = ''
    authcfg: str = ''           # id della configurazione nel gestore di autenticazione di QGIS


@dataclass
class Project:
    id: int
    name: str
    description: str = ''
    task_ids: List[str] = field(default_factory=list)

    @classmethod
    def from_json(cls, d):
        return cls(id=int(d['id']), name=str(d.get('name') or ('#%s' % d['id'])),
                   description=str(d.get('description') or ''),
                   task_ids=[str(t) for t in (d.get('tasks') or [])])


@dataclass
class Task:
    id: str
    project_id: int
    name: str
    status: Optional[int] = None
    created_at: str = ''
    images_count: int = 0
    epsg: Optional[int] = None
    wkt: str = ''
    srs: Optional[dict] = None
    available_assets: List[str] = field(default_factory=list)

    @property
    def georeferenced(self):
        return bool(self.epsg or self.wkt)

    @property
    def completed(self):
        return self.status == COMPLETED

    @property
    def label(self):
        return self.name or self.id[:8]

    @classmethod
    def from_json(cls, d, project_id=None):
        epsg = d.get('epsg')
        return cls(id=str(d['id']), project_id=int(project_id if project_id is not None else d.get('project')),
                   name=str(d.get('name') or ''), status=d.get('status'),
                   created_at=str(d.get('created_at') or ''),
                   images_count=int(d.get('images_count') or 0),
                   epsg=int(epsg) if epsg else None, wkt=str(d.get('wkt') or ''),
                   srs=d.get('srs') if isinstance(d.get('srs'), dict) else None,
                   available_assets=[str(a) for a in (d.get('available_assets') or [])])


@dataclass
class Product:
    key: str                    # identificatore unico nel task
    label: str
    group: str                  # gruppo mostrato nel pannello
    kind: str                   # raster | pointcloud | vector | photos | model | shot | xyz | image | document | archive | file
    path: str = ''              # percorso API (relativo al server); vuoto per i prodotti virtuali (xyz)
    filename: str = ''
    source: str = 'odm'         # odm | plugin
    meta: dict = field(default_factory=dict)
    size: Optional[int] = None
    extra_files: List[dict] = field(default_factory=list)    # per gli scatti: gli altri formati


@dataclass
class CrsInfo:
    """Cio' che serve sapere di un CRS senza dipendere da QGIS."""
    authid: str = ''
    valid: bool = False
    geographic: bool = False
    description: str = ''
    problem: str = ''           # es. griglia PROJ mancante


@dataclass
class Alert:
    code: str
    level: str                  # info | warn | block
    text: str
    choices: tuple = ()         # codici di scelte offerte all'utente (vedi crs_dialog)
