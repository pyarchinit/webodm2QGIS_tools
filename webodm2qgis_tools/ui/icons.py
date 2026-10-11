"""Icone disegnate in SVG dal codice (nessun file da distribuire, si adattano a qualunque dimensione)."""
from qgis.PyQt.QtCore import QByteArray, Qt
from qgis.PyQt.QtGui import QColor, QIcon, QPainter, QPixmap
from qgis.PyQt.QtSvg import QSvgRenderer

_STROKE = '#2b6cb0'
_PATHS = {
    'connect': '<path d="M5 12a7 7 0 0 1 14 0M8 12a4 4 0 0 1 8 0"/><circle cx="12" cy="16" r="1.5" fill="%s"/><path d="M12 17.5V21"/>',
    'task': '<rect x="3.5" y="4" width="17" height="16" rx="2"/><path d="M7 9h10M7 13h10M7 17h6"/>',
    'session': '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M12 10v5M9.5 12.5H14.5"/>',
    'refresh': '<path d="M20 11a8 8 0 1 0-2.3 5.7M20 5v6h-6"/>',
    'panel': '<rect x="3.5" y="4" width="17" height="16" rx="2"/><path d="M9 4v16"/>',
    'ortho': '<path d="M3 7l9-4 9 4-9 4zM3 12l9 4 9-4M3 17l9 4 9-4"/>',
    'cloud': '<circle cx="7" cy="8" r="1"/><circle cx="12" cy="6" r="1"/><circle cx="17" cy="9" r="1"/><circle cx="9" cy="13" r="1"/><circle cx="15" cy="14" r="1"/><circle cx="6" cy="17" r="1"/><circle cx="12" cy="19" r="1"/><circle cx="18" cy="18" r="1"/>',
    'photos': '<rect x="3.5" y="6" width="17" height="13" rx="2"/><circle cx="12" cy="12.5" r="3.2"/><path d="M8 6l1.2-2h5.6L16 6"/>',
    'photo_tool': '<path d="M12 21s-6-5.5-6-10a6 6 0 0 1 12 0c0 4.5-6 10-6 10z"/><circle cx="12" cy="11" r="2"/>',
    'shots': '<rect x="4" y="3.5" width="16" height="17" rx="1.5"/><path d="M4 16l4.5-4.5 3.5 3.5 3-3 5 5"/><circle cx="9" cy="8" r="1.3"/>',
    'viewer': '<rect x="3" y="4.5" width="18" height="12" rx="2"/><path d="M8 20h8M12 16.5V20"/><path d="M3 8.5h18"/>',
    'crs': '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c3 3 3 14 0 17M12 3.5c-3 3-3 14 0 17"/>',
    'help': '<circle cx="12" cy="12" r="8.5"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 1-1 1.7M12 17h.01"/>',
    'check': '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    'folder': '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    'open': '<path d="M14 4h6v6M20 4l-9 9M18 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4"/>',
    'download': '<path d="M12 4v11M7.5 11l4.5 4.5 4.5-4.5M5 20h14"/>',
}
_cache = {}


def _render(svg, size, color):
    r = QSvgRenderer(QByteArray(svg.encode('utf-8')))
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    r.render(p)
    p.end()
    return pm


def icon(name, color=_STROKE):
    key = (name, color)
    if key not in _cache:
        body = _PATHS[name].replace('%s', color)
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="%s" '
               'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">%s</svg>' % (color, body))
        ic = QIcon()
        for s in (16, 24, 32, 48):
            ic.addPixmap(_render(svg, s, color))
        _cache[key] = ic
    return _cache[key]


def light(color_name, size=14):
    """Pallino colorato del semaforo CRS: green | yellow | red | grey."""
    key = ('light', color_name)
    if key not in _cache:
        col = {'green': '#2f9e44', 'yellow': '#f08c00', 'red': '#e03131', 'grey': '#adb5bd'}[color_name]
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(col))
        p.setPen(QColor('#ffffff'))
        p.drawEllipse(1, 1, size - 2, size - 2)
        p.end()
        _cache[key] = QIcon(pm)
    return _cache[key]


def names():
    return list(_PATHS)
