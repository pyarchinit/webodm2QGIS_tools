"""URL del server e percorsi API di WebODM. Puro Python."""
import re
from urllib.parse import urlsplit, urlunsplit

UUID_RE = re.compile(r'^[0-9a-fA-F-]{8,40}$')


def normalize_base_url(text):
    """'localhost:29800/' -> 'http://localhost:29800'. ValueError se non e' un indirizzo http(s)."""
    t = (text or '').strip()
    if not t:
        raise ValueError('indirizzo vuoto')
    if '://' not in t:
        t = 'http://' + t
    p = urlsplit(t)
    if p.scheme not in ('http', 'https') or not p.netloc:
        raise ValueError('indirizzo non valido')
    path = p.path.rstrip('/')
    if path.endswith('/api'):
        path = path[:-4]
    return urlunsplit((p.scheme, p.netloc, path, '', ''))


def host_of(url):
    return (urlsplit(url).hostname or '').lower()


def is_local_host(url):
    h = host_of(url)
    return h in ('localhost', '127.0.0.1', '::1') or h.endswith('.localhost')


def plain_http_remote(url):
    """True se la password viaggerebbe in chiaro verso un host non locale."""
    return urlsplit(url).scheme == 'http' and not is_local_host(url)


def server_key(url):
    """Nome sicuro per usarlo come cartella."""
    p = urlsplit(url)
    return re.sub(r'[^A-Za-z0-9._-]+', '_', (p.netloc + p.path).strip('/')) or 'server'


def check_ids(project_id, task_id=None):
    int(project_id)
    if task_id is not None and not UUID_RE.match(str(task_id)):
        raise ValueError('id del task non valido')


def task_api(project_id, task_id, tail=''):
    check_ids(project_id, task_id)
    return '/api/projects/%d/tasks/%s/%s' % (int(project_id), task_id, tail)


def plugin_api(task_id, name):
    check_ids(0, task_id)
    return '/api/plugins/webodm-model-tools/task/%s/%s' % (task_id, name)


def web_url(base, kind, project_id, task_id):
    """Pagine web di WebODM: 'dashboard', '3d', 'map'."""
    check_ids(project_id, task_id)
    if kind == 'dashboard':
        return base + '/dashboard/'
    if kind in ('3d', 'map'):
        return '%s/%s/project/%d/task/%s/' % (base, kind, int(project_id), task_id)
    raise ValueError(kind)
