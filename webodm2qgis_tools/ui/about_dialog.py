"""Informazioni: crediti, avvertenze, lingua, apertura della guida."""
import os

from qgis.core import QgsSettings
from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QPushButton, QTextBrowser,
                                 QVBoxLayout)

from .. import i18n
from ..i18n import T
from .icons import icon
from .qt_helpers import localize_box

LANG_KEY = 'webodm2qgis_tools/language'
AUTHOR = 'Luca Mandolesi'
SITE = 'https://flyoveracademy.it'
REPO = 'https://github.com/pyarchinit/webodm2QGIS_tools'


def chosen_language():
    """'auto' oppure uno dei codici di i18n.LANGS."""
    v = QgsSettings().value(LANG_KEY, 'auto')
    return v if v in i18n.LANGS else 'auto'


def guide_path(lang=None):
    """File HTML della guida nella lingua corrente: italiano o inglese (le altre lingue usano l'inglese)."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    code = 'it' if (lang or i18n.language()) == 'it' else 'en'
    return os.path.join(here, 'docs', 'guide_%s.html' % code)


def open_guide(lang=None):
    p = guide_path(lang)
    if os.path.isfile(p):
        QDesktopServices.openUrl(QUrl.fromLocalFile(p))
        return True
    return False


def credits_html(version):
    return ('<h3>WebODM2QGIS-tools %s</h3>'
            '<p>%s <a href="%s">Flyoveracademy.it</a>.</p>'
            '<p>%s</p>'
            '<p style="color:#c92a2a"><b>%s</b></p>'
            '<ul><li>%s</li><li>%s</li><li>%s</li><li>%s</li></ul>'
            '<p>%s &mdash; <a href="%s">%s</a></p>') % (
        version,
        T('Realizzato da <b>{a}</b> di', a=AUTHOR), SITE,
        T("Scritto interamente con <b>Claude Code</b> (modelli Claude Sonnet e Opus di Anthropic). "
          "Software <b>sperimentale</b>, per <b>QGIS 4</b>."),
        T("ATTENZIONE: puo' fare danni. Software fornito senza alcuna garanzia, uso a tuo rischio."),
        T("Scrive file (TIFF, GeoPackage, VRT, ZIP estratti) nella cartella che scegli e puo' sovrascrivere file con "
          "lo stesso nome: scegli una cartella dedicata."),
        T("Puo' cambiare il CRS del progetto QGIS (te lo chiede) e aggiungere molti layer: lavora su una copia del "
          "progetto e fai un backup."),
        T("Salva la password del server nel gestore di autenticazione di QGIS; non usarlo su computer condivisi."),
        T("Non scrive nulla sul server WebODM (sola lettura), ma i file scaricati possono essere molto grandi: "
          "controlla lo spazio su disco."),
        T('Licenza: GNU GPL versione 2 o successiva (come QGIS).'), REPO, REPO)


class AboutDialog(QDialog):
    def __init__(self, version, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle(T('Informazioni'))
        self.setWindowIcon(icon('help'))
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        view = QTextBrowser()
        view.setOpenExternalLinks(True)
        view.setHtml(credits_html(version))
        view.setMinimumHeight(300)
        lay.addWidget(view)
        form = QFormLayout()
        self.lang = QComboBox()
        self.lang.addItem(T('Automatica (lingua di QGIS)'), 'auto')
        for c in i18n.LANGS:
            self.lang.addItem(i18n.LANG_NAMES[c], c)
        self.lang.setCurrentIndex(max(0, self.lang.findData(chosen_language())))
        form.addRow(T('Lingua'), self.lang)
        lay.addLayout(form)
        note = QLabel(T("La lingua scelta si applica al prossimo avvio di QGIS (o ricaricando il plugin)."))
        note.setWordWrap(True)
        lay.addWidget(note)
        guide = QPushButton(icon('open'), T('Apri la guida'))
        guide.clicked.connect(self._guide)
        lay.addWidget(guide)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        localize_box(buttons)
        lay.addWidget(buttons)

    def _guide(self):
        if not open_guide():
            self.sender().setText(T('Guida non trovata'))

    def accept(self):
        QgsSettings().setValue(LANG_KEY, self.lang.currentData())
        QDialog.accept(self)
