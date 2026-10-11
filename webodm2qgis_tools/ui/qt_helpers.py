"""I pulsanti standard di Qt (OK, Annulla, Si', No, Sfoglia) li traduce QGIS secondo la SUA lingua, non quella scelta
per il plugin: qui si impostano a mano, cosi' un'interfaccia inglese non ha un "Annulla" accanto a testi inglesi."""
from qgis.PyQt.QtWidgets import QDialogButtonBox, QMessageBox, QToolButton

from ..i18n import T


def localize_box(box):
    """Testi del plugin sui pulsanti standard di un QDialogButtonBox."""
    names = (('Ok', 'OK'), ('Cancel', 'Annulla'), ('Close', 'Chiudi'))
    for attr, text in names:
        b = box.button(getattr(QDialogButtonBox.StandardButton, attr))
        if b is not None:
            b.setText(T(text) if text != 'OK' else 'OK')
    return box


def localize_file_widget(widget):
    """QgsFileWidget: il pulsante "Sfoglia..." ha il tooltip nella lingua di QGIS."""
    for b in widget.findChildren(QToolButton):
        b.setToolTip(T('Sfoglia...'))


def ask_yes_no(parent, title, text):
    """Domanda Si'/No con i pulsanti nella lingua del plugin. True se Si'."""
    box = QMessageBox(QMessageBox.Icon.Question, title, text, QMessageBox.StandardButton.NoButton, parent)
    yes = box.addButton(T('Sì'), QMessageBox.ButtonRole.YesRole)
    box.addButton(T('No'), QMessageBox.ButtonRole.NoRole)
    box.exec()
    return box.clickedButton() is yes
