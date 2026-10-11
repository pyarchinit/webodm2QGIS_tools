"""Scelta corrente (server, progetto, task) e come si salva nel progetto QGIS. Puro Python."""
import json
from dataclasses import dataclass, asdict
from typing import Optional

ENTRY_SCOPE = 'webodm2qgis_tools'
ENTRY_KEY = 'selection'


@dataclass
class Selection:
    server_url: str = ''
    project_id: Optional[int] = None
    task_id: str = ''
    photos_dir: str = ''        # cartella locale delle foto originali (ripiego quando il server non le ha)
    session_name: str = ''      # sessione di import: nome e cartella scelti dall'utente
    session_folder: str = ''

    def complete(self):
        return bool(self.server_url and self.project_id is not None and self.task_id)

    def to_json(self):
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, text):
        """Tollerante: un progetto vecchio o rovinato non deve far fallire l'apertura."""
        try:
            d = json.loads(text or '{}')
            pid = d.get('project_id')
            return cls(server_url=str(d.get('server_url') or ''), project_id=int(pid) if pid is not None else None,
                       task_id=str(d.get('task_id') or ''), photos_dir=str(d.get('photos_dir') or ''),
                       session_name=str(d.get('session_name') or ''),
                       session_folder=str(d.get('session_folder') or ''))
        except (ValueError, TypeError, AttributeError):
            return cls()


def filter_tasks(tasks, text='', only_completed=False):
    t = (text or '').strip().lower()
    out = []
    for task in tasks:
        if only_completed and not task.completed:
            continue
        if t and t not in (task.name or '').lower() and t not in task.id.lower():
            continue
        out.append(task)
    out.sort(key=lambda x: x.created_at, reverse=True)
    return out


def filter_projects(projects, text=''):
    t = (text or '').strip().lower()
    return [p for p in projects if not t or t in p.name.lower() or t in p.description.lower()]
