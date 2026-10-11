"""Avvisi su CRS/EPSG/georiferimento con scelta guidata."""
from qgis.gui import QgsProjectionSelectionWidget
from qgis.PyQt.QtWidgets import (QButtonGroup, QDialog, QDialogButtonBox, QLabel, QRadioButton, QVBoxLayout,
                                 QWidget, QHBoxLayout)

from ..controller import Decision
from ..i18n import T
from .icons import icon

_COLORS = {'info': '#1971c2', 'warn': '#e67700', 'block': '#c92a2a'}
_TAGS = {'info': 'info', 'warn': 'attenzione', 'block': 'blocco'}


class CrsDialog(QDialog):
    def __init__(self, product, alerts, file_crs, project_crs, can_assign, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle(T('Controllo CRS - {p}', p=product.label))
        self.setWindowIcon(icon('crs'))
        self.setMinimumWidth(560)
        self.alerts = alerts
        self.file_crs, self.project_crs = file_crs, project_crs
        lay = QVBoxLayout(self)
        head = QLabel('<b>%s</b>' % product.label)
        lay.addWidget(head)
        for a in alerts:
            lab = QLabel('<span style="color:%s"><b>%s %s</b></span> %s' % (
                _COLORS[a.level], a.code, T(_TAGS[a.level]).upper(), a.text.replace('\n', '<br>')))
            lab.setWordWrap(True)
            lay.addWidget(lab)

        choices = []
        for a in alerts:
            for c in a.choices:
                if c not in choices:
                    choices.append(c)
        self.group = QButtonGroup(self)
        self.assign = None
        self._radios = {}
        if choices:
            box = QWidget()
            bl = QVBoxLayout(box)
            bl.addWidget(QLabel('<b>%s</b>' % T('Cosa vuoi fare?')))
            labels = {
                'reproject': T('Riproietta al volo nel CRS del progetto (consigliato)'),
                'set_project_crs': T('Imposta il CRS del progetto su quello del prodotto ({a})',
                                     a=file_crs.authid() if file_crs and file_crs.isValid() else '?'),
                'assign_crs': T('Il file non ha un CRS: assegna questo'),
                'cancel': T('Non caricare'),
            }
            first = None
            for c in choices:
                r = QRadioButton(labels.get(c, c))
                self.group.addButton(r)
                self._radios[c] = r
                bl.addWidget(r)
                first = first or r
                if c == 'assign_crs':
                    self.assign = QgsProjectionSelectionWidget()
                    self.assign.setOptionVisible(QgsProjectionSelectionWidget.CrsOption.CrsNotSet, False)
                    row = QWidget()
                    rl = QHBoxLayout(row)
                    rl.setContentsMargins(24, 0, 0, 0)
                    rl.addWidget(self.assign)
                    bl.addWidget(row)
                    self.assign.crsChanged.connect(self._sync)
                    r.toggled.connect(self._sync)
            if 'reproject' in self._radios:
                self._radios['reproject'].setChecked(True)
            elif 'assign_crs' in self._radios:
                self._radios['assign_crs'].setChecked(True)
            elif 'set_project_crs' in self._radios and len(choices) == 1:
                self._radios['set_project_crs'].setChecked(True)
            else:
                first.setChecked(True)
            lay.addWidget(box)
        self.buttons = QDialogButtonBox()
        self.ok_btn = self.buttons.addButton(T('Carica'), QDialogButtonBox.ButtonRole.AcceptRole)
        self.buttons.addButton(T('Annulla'), QDialogButtonBox.ButtonRole.RejectRole)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        lay.addWidget(self.buttons)
        self.group.buttonToggled.connect(self._sync)
        self._sync()

    def _sync(self, *_):
        need_crs = 'assign_crs' in self._radios and self._radios['assign_crs'].isChecked()
        if self.assign is not None:
            self.assign.setEnabled(need_crs)
        ok = not need_crs or (self.assign.crs().isValid())
        cancel = 'cancel' in self._radios and self._radios['cancel'].isChecked()
        self.ok_btn.setEnabled(ok and not cancel)

    def decision(self):
        if self.result() != QDialog.DialogCode.Accepted:
            return Decision(False)
        d = Decision(True)
        if 'set_project_crs' in self._radios and self._radios['set_project_crs'].isChecked():
            d.set_project_crs = True
        if 'assign_crs' in self._radios and self._radios['assign_crs'].isChecked():
            d.assign_crs = self.assign.crs()
            if self.project_crs is not None and not self.project_crs.isValid():
                d.set_project_crs = True
        return d
