"""Credenziali nel gestore di autenticazione di QGIS (protetto dalla password principale).

Non finiscono mai in QgsSettings, nel progetto .qgz, nei log o in un URL.
"""
from qgis.core import QgsApplication, QgsAuthMethodConfig

METHOD = 'Basic'


def available():
    am = QgsApplication.authManager()
    return am is not None and not am.isDisabled()


def store(name, user, password, authcfg=''):
    """Salva (o aggiorna) utente/password; restituisce l'id della configurazione, '' se non riesce
    (gestore disabilitato o password principale rifiutata)."""
    if not available():
        return ''
    am = QgsApplication.authManager()
    if not am.setMasterPassword(True):
        return ''
    cfg = QgsAuthMethodConfig(METHOD)
    if authcfg:
        am.loadAuthenticationConfig(authcfg, cfg, True)
    cfg.setName('WebODM: %s' % name)
    cfg.setMethod(METHOD)
    cfg.setConfig('username', user)
    cfg.setConfig('password', password)
    cfg.setConfig('realm', '')
    if authcfg and cfg.id() == authcfg:
        ok = am.updateAuthenticationConfig(cfg)
    else:
        ok, cfg = am.storeAuthenticationConfig(cfg)
    return cfg.id() if ok else ''


def load(authcfg):
    """(utente, password) oppure None."""
    if not authcfg or not available():
        return None
    am = QgsApplication.authManager()
    if not am.setMasterPassword(True):
        return None
    cfg = QgsAuthMethodConfig()
    if not am.loadAuthenticationConfig(authcfg, cfg, True):
        return None
    return cfg.config('username'), cfg.config('password')


def remove(authcfg):
    if authcfg and available():
        QgsApplication.authManager().removeAuthenticationConfig(authcfg)
